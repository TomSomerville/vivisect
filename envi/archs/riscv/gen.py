import re
import enum
import os.path
import argparse
import itertools
import subprocess
from collections import namedtuple


_immfields = [
    r'imm\[[^]]+\]',
    r'imm',
    r'offset',
    r'jump target',
]

# The RVC instructions add lots of variation to the possible register fields
_regfields = [
    r'rs[0-9]?',
    r'rd',
    r'rd/rs[0-9]?',
    r'\\rs(?:one|two)prime',
    r'\\rdprime',
    r'\\rs(?:one|two)prime/\\rdprime',
    r'\\rdprime/\\rs(?:one|two)prime',
]

# All fields are allowed to have binary constants in them, but the funct and
# opcode fields must have constants in them.
_reqbinfields = [
    r'funct[0-9]',
    r'opcode',
    r'op',
]

_binvalues = [
    r'[01]+',
]

# Some RVC instructions use decimal constants instead of binary
_decvalues = [
    r'[0-9]+',
]

_binfields = _regfields + _immfields

# The RVC instructions have more specific imm information than the form
_immvalues = _immfields + [
    r'shamt\[[^]]+\]',
    r'shamt',
    # Special IMM names used by the FENCE instruction
    r'fm',
    r'pred',
    r'succ',
    # Atomic operation IMM fields
    r'aq',
    r'rl',
    r'csr',
    r'uimm',
    r'uimm\[[^]]+\]',
    r'nzimm\[[^]]+\]',
    r'nzuimm\[[^]]+\]',
]
_regvalues = _regfields + [
    r'rs[0-9]?/rd\$\\n?eq\$0',
    r'rs[0-9]?\$\\n?eq\$0',
    r'rs[0-9]?\$\\n?eq\$\$\\{[0-9,]+\\}\$',
    r'rd\$\\n?eq\$0',
    r'rd\$\\n?eq\$\$\\{[0-9,]+\\}\$',
    r'rs[0-9]?/rd\$\\n?eq\$0',
    r'rs[0-9]?/rd\$\\n?eq\$\$\\{[0-9,]+\\}\$',
]

# the required bin field may also have a value of 'rm' (rounding mode)
_reqbinvalues = _reqbinfields + _binvalues + _decvalues + [
    r'rm',
]


def _makepat(parts, options=0):
    if options & re.MULTILINE:
        return re.compile(r'(?:' + r')|(?:'.join(parts) + r')', options)
    else:
        return re.compile(r'(?:^' + r'$)|(?:^'.join(parts) + r'$)', options)


_immfieldpat = _makepat(_immfields)
_regfieldpat = _makepat(_regfields)
_reqbinfieldpat = _makepat(_reqbinfields)
_binfieldpat = _makepat(_binfields)
_immvaluepat = _makepat(_immvalues)
_regvaluepat = _makepat(_regvalues)

# Some instructions encode an IMM value (uimm) in register fields, so when
# checking for a form match we need a special pattern that is the register
# patterns + 'uimm'
_regvalueformmatchpat = _makepat(_regvalues + [r'uimm'])

_binvaluepat = _makepat(_binvalues)
_decvaluepat = _makepat(_decvalues)
_reqbinvaluepat = _makepat(_reqbinvalues)


class OpcodeType(enum.Enum):
    OPCODE = enum.auto()
    REG = enum.auto()
    CONST = enum.auto()
    IMM = enum.auto()
    RM = enum.auto()
    C_OPCODE = enum.auto()
    C_REG = enum.auto()


Form = namedtuple('Form', [
    'name',
    'fields',
])

Field = namedtuple('Field', [
    'value',  # "name" or integer constant
    'type',
    'columns',
    'bits',
    'mask',
    'shift',
])

Op = namedtuple('Op', [
    'name',
    'cat',
    'form',
    'mask',
    'value',
    'fields',
    'flags',
    'notes',
])


def get_instr_mask(fields):
    mask = '0b'
    value = '0b'
    for field in fields:
        if field.type in (OpcodeType.CONST, OpcodeType.OPCODE, OpcodeType.C_OPCODE):
            mask += '1' * field.bits
            if isinstance(field.value, int):
                value += bin(field.value)[2:]
            elif isinstance(field.value, str) and _binvaluepat.match(field.value):
                value += field.value
            elif isinstance(field.value, str) and _decvaluepat.match(field.value):
                # Convert the decimal value string to an integer first
                value += bin(int(field.value))[2:]
            else:
                raise Exception('Cannot create mask with non-integer field: %r' % field)

        else:
            mask += '0' * field.bits
            value += '0' * field.bits

    return (int(mask, 2), int(value, 2))


def get_instr_flags(name, fields, priv=False):
    # Return the correct set of flags for the instruction
    #   envi.IF_NOFALL
    #   envi.IF_PRIV
    #   envi.IF_CALL
    #   envi.IF_BRANCH
    #   envi.IF_RET
    #   envi.IF_COND
    #   envi.IF_REPEAT
    #   envi.IF_BRANCH_COND

    flags = ''
    if name in ('J', 'JR', 'C.JR', 'C.J'):
        flags = 'envi.IF_CALL | envi.IF_NOFALL'
    elif name in ('JAL', 'JALR', 'C.JAL', 'C.JALR'):
        flags = 'envi.IF_CALL'
    elif name in ('BEQ', 'BNE', 'BLT', 'BGE', 'BLTU', 'BGEU', 'C.BNEZ', 'C.BEQZ'):
        flags = 'envi.IF_COND | envi.IF_BRANCH'

    if flags and priv:
        return flags + ' | envi.IF_PRIV'
    elif flags:
        return flags
    elif priv:
        return 'envi.IF_PRIV'
    else:
        return 0


def get_field_type(field):
    if _immvaluepat.match(field):
        return OpcodeType.IMM
    elif _regvaluepat.match(field):
        if 'prime' in field:
            return OpcodeType.C_REG
        else:
            return OpcodeType.REG
    elif _reqbinvaluepat.match(field):
        if 'opcode' == field:
            return OpcodeType.OPCODE
        elif 'op' == field:
            return OpcodeType.C_OPCODE
        elif 'rm' == field:
            return OpcodeType.RM
        else:
            return OpcodeType.CONST
    #elif _decvaluepat.match(field):
    #    return OpcodeType.CONST
    else:
        raise Exception('Unknown field type: %r' % field)


def get_field_info(instr_fields, columns):
    # Determine the field bit widths and field types
    col = 0
    fields = []
    for size, value in instr_fields:
        if isinstance(columns[col], tuple):
            start = columns[col][0]
        else:
            start = columns[col]

        col += int(size)

        # Now get the start of the next field
        if col < len(columns):
            if isinstance(columns[col], tuple):
                end = columns[col][0]
            else:
                end = columns[col]
        else:
            # If the previous column was the last field then end is -1 to keep
            # up the pattern of the end being exclusive (the start of the next
            # column)
            end = -1

        # Start is inclusive but end is not
        field_bits = start - end

        # Because end is the start of the next column beyond the current field
        # add 1 to end to get the correct shift value for this field
        field_shift = end + 1

        # Determine the type of this field by pattern
        field_type = get_field_type(value)

        # Generate the mask and shift that could be used to extract this field
        # from an instruction
        #field_mask = int('0b' + '1' * field_bits, 2)
        field_mask = (2 ** field_bits) - 1
        fields.append(Field(value, field_type, int(size), field_bits, field_mask, field_shift))

    return fields


def find_form(fields, forms):
    # Special cases, some instructions split single imm fields up into multiple
    # smaller fields.
    #
    # The FENCE instruction with 'fm', 'pred', succ' are actually 3 subfields.
    # There are other instruction names that represent specific FENCE
    # instructions and those also need the same treatment.  Specifically
    # FENCE.TSO ('1000', '0011', '0011') and PAUSE ('0000', '0001', '0000')
    #
    # Some CB form RVC instructions split the rdprime/rsoneprime field into two
    # fields, one that is imm[5] or nzuimm[5] (1 bit) and a 2-bit constant.
    # Combine them into 1 "field" to make it easier to match.
    field_names = [f[1] for f in fields]
    if field_names[:3] == ['fm', 'pred', 'succ'] or \
            field_names[:3] == ['1000', '0011', '0011'] or \
            field_names[:3] == ['0000', '0001', '0000']:
        fields = [fields[:3]] + fields[3:]
    elif field_names[1:3] == ['aq', 'rl']:
        fields = [fields[:3]] + fields[3:]
    elif field_names[1] == 'shamt':
        fields = [fields[:2]] + fields[2:]
    elif field_names[1] in ('imm[5]', 'nzuimm[5]') and \
            len(field_names[2]) == 2 and \
            _binvaluepat.match(field_names[2]):
        fields = fields[:1] + [fields[1:3]] + fields[3:]

    for form_name, form in forms.items():
        #print('trying %s (%d =? %d)' % (form_name, len(fields), len(form.fields)))

        if len(fields) == len(form.fields):
            parsed = []
            for value, field in zip(fields, form.fields):
                if not isinstance(value, list):
                    # If the column width doesn't match, this doesn't work. Just
                    # checking column widths at the moment
                    if value[0] != field.columns:
                        #print('%s WIDTH MISMATCH %s' % (value, field))
                        match = False
                        break

                    # if required bin fields aren't binary constants, this form
                    # doesn't match.
                    if _reqbinfieldpat.match(field.value):
                        if _reqbinvaluepat.match(value[1]):
                            #print('%s matched %s' % (value, field))
                            if _binvaluepat.match(value[1]):
                                parsed.append((value[0], int(value[1], 2)))
                            else:
                                parsed.append((value[0], value[1]))
                        else:
                            #print('%s REQ FIELD MISMATCH %s' % (value, field))
                            match = False
                            break
                    else:
                        # The imm field matches get a little weird because the
                        # RVC instructions and forms aren't super consistent.
                        # If the field doesn't start with 'imm' then the two
                        # don't have to match.
                        #
                        # The RVC register fields get a little complicated, also
                        # ensure that both the value and field strings have
                        # 'prime' in them or they both don't.
                        if _binvaluepat.match(value[1]) and _binfieldpat.match(field.value):
                            #print('bin %s matched %s' % (value, field))
                            parsed.append((value[0], int(value[1], 2)))
                        elif _decvaluepat.match(value[1]) and _binfieldpat.match(field.value):
                            #print('dec %s matched %s' % (value, field))
                            parsed.append((value[0], int(value[1], 10)))
                        elif _immvaluepat.match(value[1]) and _immfieldpat.match(field.value) and \
                                ((_immfieldpat.match(value[1]) and value[1] == field.value) or \
                                not _immfieldpat.match(value[1]) or \
                                not field.value.startswith('imm') or \
                                (value[1].startswith('imm') and field.value == 'imm')):
                            #print('imm %s matched %s' % (value, field))
                            parsed.append(value)
                        elif _regvalueformmatchpat.match(value[1]) and _regfieldpat.match(field.value) and \
                                ((_regfieldpat.match(value[1]) and value[1] in field.value) or \
                                    not _regfieldpat.match(value[1]) or \
                                    ('prime' in value[1] and 'prime' in field.value)) and \
                                (('prime' in value[1] and 'prime' in field.value) or \
                                    ('prime' not in value[1] and 'prime' not in field.value)):
                            #print('reg %s matched %s' % (value, field))
                            parsed.append(value)

                        else:
                            #print('%s NO MATCH %s' % (value, field))
                            match = False
                            break
                else:
                    # Get the total columns that make up this aggregate field
                    col_width = sum([v[0] for v in value])

                    # Lists only match bin fields
                    if _binvaluepat.match(value[0][1]) and _reqbinfieldpat.match(field.value) and \
                            col_width == field.columns:
                        #print('%s matched %s' % (value, field))
                        parsed.extend([(value[0][0], int(value[0][1], 2))] + value[1:])
                    elif isinstance(value[0][1], str) and _binfieldpat.match(field.value) and \
                            col_width == field.columns:
                        #print('%s matched %s' % (value, field))
                        parsed.extend(value)
                    else:
                        #print('%s NO MATCH %s' % (value, field))
                        match = False
                        break
            else:
                # Find the bit width of the fields
                return form_name, parsed

    # If no form was found, and there are multiple fields in a row that are
    # binary, try collapsing them together.  The RVC instruction table gets
    # weird with how instructions are laid out sometimes.
    #
    # Try first without collapsing the first field
    idx_start = None
    idx_stop = None
    for i in range(1, len(fields)):
        if _binvaluepat.match(fields[i][1]):
            if idx_start is None:
                idx_start = i
        elif idx_start is not None:
            idx_stop = i
            break

    if idx_start is not None and idx_stop is not None and idx_stop - idx_start > 1:
        # Construct the new instruction field
        new_field = (sum(int(f[0]) for f in fields[idx_start:idx_stop]), \
                ''.join(f[1] for f in fields[idx_start:idx_stop]))
        collapsed_fields = fields[:idx_start] + [new_field] + fields[idx_stop:]
        return find_form(collapsed_fields, forms)

    # Try again but start from field 0 this time
    idx_start = None
    idx_stop = None
    for i in range(0, len(fields)):
        if _binvaluepat.match(fields[i][1]):
            if idx_start is None:
                idx_start = i
        elif idx_start is not None:
            idx_stop = i
            break

    if idx_start is not None and idx_stop is not None and idx_stop - idx_start > 1:
        # Construct the new instruction field
        new_field = (sum(int(f[0]) for f in fields[idx_start:idx_stop]), \
                ''.join(f[1] for f in fields[idx_start:idx_stop]))
        collapsed_fields = fields[:idx_start] + [new_field] + fields[idx_stop:]
        return find_form(collapsed_fields, forms)
    else:
        # This special case doesn't apply, signal a failure
        raise Exception('no form match found for %r' % fields)


def add_instr(instrs, name, cat_list, form, fields, notes, priv=False):
    # the opcode is the last field, ensure it is a constant
    assert fields[-1].type == OpcodeType.CONST

    # If there is a note that is just 'HINT' that indicates this is a weird
    # instruction like C.SLLI64 that is only a hint but not defined as a real
    # instruction?  If so, just skip it.
    if 'HINT' in notes:
        print('Skipping HINT-ONLY instruction %s' % name)
        return

    # Get the combined mask and post-mask value for this instruction
    op_mask, op_value = get_instr_mask(fields)

    # And generate the flags for this instruction
    op_flags = get_instr_flags(name, fields, priv)

    if not cat_list:
        raise Exception('ERROR: no categories defined for: %s, %s, %s, %s, priv=%s' % (name, form, fields, notes, priv))

    for cat in cat_list:
        if cat not in instrs:
            instrs[cat] = {}
        assert name not in instrs[cat]

        op = Op(name, cat, form, op_mask, op_value, fields, op_flags, notes)
        instrs[cat][name] = op
        extra_info_str = '%s-type' % op.form
        if notes:
            extra_info_str += '; ' + '; '.join(n for n in notes)
        print('Adding op [%s] %s (%s):' % (op.cat, op.name, extra_info_str))
        for field in op.fields:
            ftype = '(%s)' % field.type.name
            print('  %-7s %-20s: bits=%d, mask=0x%02x, shift=%d' % (ftype, field.value, field.bits, field.mask, field.shift))

# Find the instruction definitions
_parts = [
    r'\n +&\n((?:\\.*instbit.* [&\\]+ *\n)+)\\[a-z]+line{\d-\d+}\n',
    r'\\multicolumn[^\\]+\\bf (.*RV.*)} & \\\\ *\n',
    r'\n&\n((?:\\multicolumn.* & *\n)+\\multicolumn.* & [A-Z0-9a-z.-]+) (?:{\\em \\tiny (.*)})? *\\\\ *\n\\[a-z]+line{\d-\d+}\n',
]
_pat = _makepat(_parts, re.MULTILINE)

_field_size_parts = [
    r'\\instbit{(\d+)}',
    'instbitrange{(\d+)}{(\d+)}',
]
_field_size_pat = _makepat(_field_size_parts, re.MULTILINE)

_cat_extension_pat = re.compile(r'{(Z[^}]+)}')
_cat_pat = re.compile(r'(RV[0-9]+[^ ]*)')

_info_parts = [
    r'\\multicolumn{(\d+)}{[|c]+}{(.*)} &',
    r' ([A-Z0-9a-z.-]+)',
]
_info_pat = _makepat(_info_parts, re.MULTILINE)


def cats_from_str(catname):
    #print(catname)
    if catname[:2] != 'RV':
        return []

    # Check how many RV?? archs are listed in the first word
    arch, extra = catname.split(' ', maxsplit=1)
    cat_list = []
    for part in arch.split('/'):
        if part[:2] != 'RV':
            cat_list.append('RV' + part)
        else:
            cat_list.append(part)

    # See if this is an extension
    match = _cat_extension_pat.search(extra)
    if match:
        for i in range(len(cat_list)):
            cat_list[i] += match.group(1)

    return cat_list


def scrape_instr_table(text, default_cat=None, forms=None, priv=False):
    columns = []
    if forms is None:
        forms = {}
    instructions = {}
    #if default_cat is not None:
    #    instructions[default_cat] = {}
    #cur_cat = default_cat
    cur_cats = []

    for match in _pat.findall(text):
        #print(match)
        fieldbits, catname, instrmatch, notesmatch = match
        if fieldbits:
            columns = [int(m[0]) if m[0] else (int(m[1]), int(m[2])) \
                    for m in _field_size_pat.findall(fieldbits)]
        elif instrmatch:
            instr_fields = [(int(m[0]), m[1]) if m[1] else m[2] for m in _info_pat.findall(instrmatch)]
            #print(instr_fields)
            # If the last field of instrmatch ends in '-type' this is a form
            # name (the relevant forms are repeated each section
            instr_name = instr_fields[-1]
            if instr_name.endswith('-type'):
                form_name = instr_fields[-1].upper().replace('-', '_')
                fields = get_field_info(instr_fields[:-1], columns)
                print('Adding form %s (%s)' % (form_name, fields))
                forms[form_name] = Form(form_name, fields)
            else:
                cat_list = []

                # Remove any surrounding ()
                if len(notesmatch) >= 2 and notesmatch[0] == '(' and notesmatch[-1] == ')':
                    notesmatch = notesmatch[1:-1]

                # Split the notes on any semicolons
                notes = []
                for notepart in notesmatch.split(';'):
                    note = notepart.strip()
                    if note[:2] == 'RV' and note[:11] != 'RV32 Custom':
                        # If there is a space in this then the stuff after the
                        # space should be a separate note
                        extra = None
                        if ' ' in note:
                            cat_note, extra = note.split(' ', maxsplit=1)
                            note = cat_note

                        # Turn this into one or more categories
                        for catpart in note.split('/'):
                            if catpart[:2] != 'RV':
                                catpart = 'RV' + catpart

                            if default_cat is not None:
                                # Append the last character of the supplied
                                # default category to the new category
                                catpart += default_cat[-1]
                            cat_list.append(catpart)

                        # If there was an extra note add it to the notes list
                        if extra is not None:
                            notes.append(extra)
                    elif note:
                        notes.append(note)

                # If the category list is still empty, use the default category
                if not cat_list:
                    if cur_cats:
                        cat_list.extend(cur_cats)
                    elif default_cat is not None:
                        cat_list.append(default_cat)

                descr = instr_fields[:-1]
                # We don't need the parsed form info right now
                form_name, _ = find_form(descr, forms)

                # Now find the bit width of the fields
                op_fields = get_field_info(descr, columns)
                add_instr(instructions, instr_name, cat_list, form_name, op_fields, tuple(notes), priv=priv)
        else:
            # If there are any category names found, add them to the instruction
            # table
            cur_cats = cats_from_str(catname)
            for cat in cur_cats:
                assert cat not in instructions
                instructions[cat] = {}
            #print(cur_cats)

    return forms, instructions


def scrape_rvc_forms(text):
    form_lines = [
        r'\\[a-z]+line{3-18}\n\n',
        r'([^&]+) & [^&]+ &\n',
        r'((?:\\multicolumn{[0-9]+}{[|c]+}{[^}]+} [&\\]+ *\n)+)',
    ]
    form_pat = re.compile(r''.join(form_lines), re.MULTILINE)
    field_pat = re.compile(r'^\\multicolumn{([0-9]+)}{[|c]+}{([^}]+)}', re.MULTILINE)

    # Because the RVC table doesn't use columns the same way, use a fixed
    # 16-element list where each column is 1 bit wide in the get_field_info()
    # function call, this list should be the bit position in reverse order
    rvc_columns = [i for i in reversed(range(16))]

    forms = {}
    for formmatch in form_pat.findall(text):
        form_name = formmatch[0]
        form_fields = [(int(m[0]), m[1]) for m in field_pat.findall(formmatch[1])]

        bit_total = sum([int(f[0]) for f in form_fields])
        if bit_total != 16:
            raise Exception('missing bits! %d != 16' % bit_total)

        fields = get_field_info(form_fields, rvc_columns)
        print('Adding form %s: %s' % (form_name, fields))
        forms[form_name] = Form(form_name, fields)

    return forms


def scrape_instrs(git_repo):
    forms = {}
    instrs = {}

    with open(git_repo + '/src/instr-table.tex', 'r') as f:
        instr_table = f.read()
    unpriv_forms, unpriv_instrs = scrape_instr_table(instr_table)
    forms.update(unpriv_forms)

    # SPECIAL CASES:
    #   Unconditional Jumps are JAL with rd set to 0, so find JAL and make a
    #   duplicate entry for "J"
    jmps = ('JAL', 'JALR')
    uncond_jmps = [j.replace('AL', '') for j in jmps]

    print('Creating special case instructions not in the RISCV tables: %s' % uncond_jmps)
    for cat in unpriv_instrs.keys():
        # turn JAL into J and JALR into JR
        for old, new in zip(jmps, uncond_jmps):
            if old in unpriv_instrs[cat]:
                old_instr = unpriv_instrs[cat][old]

                new_fields = []
                for field in old_instr.fields:
                    if field.value == 'rd':
                        new_field = Field(0, OpcodeType.CONST, field.columns,
                                field.bits, field.mask, field.shift)
                        new_fields.append(new_field)
                    else:
                        # copy from JAL field
                        new_fields.append(field)

                add_instr(unpriv_instrs, new, [cat], old_instr.form, new_fields, old_instr.notes, priv=False)

    for cat, data in unpriv_instrs.items():
        if cat not in instrs:
            instrs[cat] = data
        else:
            instrs[cat].update(data)

    with open(git_repo + '/src/priv-instr-table.tex', 'r') as f:
        instr_table = f.read()
    # the privileged instructions should default to the base RV32I category
    priv_forms, priv_instrs = scrape_instr_table(instr_table, 'RV32I', priv=True)
    forms.update(priv_forms)
    for cat, data in priv_instrs.items():
        if cat not in instrs:
            instrs[cat] = data
        else:
            instrs[cat].update(data)

    with open(git_repo + '/src/c.tex', 'r') as f:
        instr_table = f.read()

    # the compact instruction tables specific architecture size with each
    # instruction
    rvc_forms = scrape_rvc_forms(instr_table)
    forms.update(rvc_forms)

    with open(git_repo + '/src/rvc-instr-table.tex', 'r') as f:
        instr_table = f.read()
    _, rvc_instrs = scrape_instr_table(instr_table, default_cat='RV32C', forms=rvc_forms)
    for cat, data in rvc_instrs.items():
        if cat not in instrs:
            instrs[cat] = data
        else:
            instrs[cat].update(data)

    return forms, instrs


def format_field_name(field):
    # Make the field names look a little nicer
    if '\\vert' in field.value:
        # Squash any latex $\vert$ sequences into a ',' character
        return field.value.replace('$\\vert$', ',')
    elif '\\neq' in field.value:
        return field.value.replace('$\\neq$', '!=').replace('$\{', '{').replace('\}$', '}')
    elif field.value == '\\rdprime':
        return "rd`"
    elif field.value == '\\rsoneprime':
        return "rs1`"
    elif field.value == '\\rstwoprime':
        return "rs2`"
    elif field.value == '\\rsoneprime/\\rdprime':
        return "rs1`/rd`"
    else:
        return field.value


def export_instrs(forms, instrs, git_info):
    # Export all the forms
    form_list = list(forms.keys())

    # Make a list of the categories (the categories are the primary keys of the
    # instructions)
    #cat_list = list(instrs.keys())

    # To turn the instruction names into python constants we first need to
    # remove any embedded '.'s.  Also while looping through the instruction
    # categories build up a list of all the categories that each instruction is
    # present in.
    riscv_name_lookup = {}
    for cat, cat_data in instrs.items():
        for instr_name in cat_data.keys():
            new_name = instr_name.replace('.', '_')
            if new_name not in riscv_name_lookup:
                riscv_name_lookup[new_name] = [instr_name, [cat]]
            else:
                riscv_name_lookup[new_name][1].append(cat)

    # Create these files in the envi/archs/riscv/ directory, not the directory
    # that the python command is run in (which is what os.getcwd() will return).
    cur_dir = os.path.dirname(__file__)
    with open(os.path.join(cur_dir, 'const_gen.py'), 'w') as out:
        # First log the git information
        out.write('# Generated from:\n')
        for info in git_info:
            out.write('#   %s\n' % info)
        out.write('\n')

        # These constants will be IntEnums
        out.write('import enum\n\n\n')

        # Write the custom IF_??? and OF_??? flags used by RISC-V instructions
        # (if any)
        #out.write('IF_NONE = 0\n\n')
        #out.write('OF_NONE = 0\n\n\n')

        # Now save the scraped FORM, CAT, and OP (instruction) values
        out.write('class RISCV_FORM(enum.IntEnum):\n')
        for form in form_list:
            out.write('    %s = enum.auto()\n' % form.upper())
        out.write('\n\n')

        # TODO: The category name strings don't yet match between the
        # instruction encodings and the table entries
        #out.write('class RISCV_CAT(enum.IntEnum):\n')
        #for cat in cat_list:
        #    out.write('    %s = enum.auto()\n' % cat.upper())
        #out.write('\n\n')

        # Write out the field types
        out.write('class RISCV_FIELD(enum.IntEnum):\n')
        for field_type in ('REG', 'C_REG', 'IMM', 'RM'):
            out.write('    %s = enum.auto()\n' % field_type)
        out.write('\n\n')

        out.write('class RISCV_INS(enum.IntEnum):\n')
        for instr in riscv_name_lookup.keys():
            out.write('    %s = enum.auto()\n' % instr.upper())

    with open(os.path.join(cur_dir, 'instr_table.py'), 'w') as out:
        # First log the git information
        out.write('# Generated from:\n')
        for info in git_info:
            out.write('#   %s\n' % info)

        # Dump the types used to encode the instructions
        out.write('''
from collections import namedtuple

import envi
from envi.archs.riscv.const import RISCV_FORM, RISCV_INS, RISCV_FIELD, RISCV_CAT

RiscVInsCat = namedtuple('RiscVInsCat', ['xlen', 'cat'])
RiscVField = namedtuple('RiscVField', ['name', 'type', 'shift', 'mask', 'flags'])
RiscVIns = namedtuple('RiscVIns', ['name', 'opcode', 'form', 'cat', 'mask', 'value', 'fields', 'flags'])

__all__ = ['instructions']

''')

        # Dump the form and instructions
        # TODO:
        #
        # - figure out how to actually handle the weird imm[*****] fields
        #
        # - do we want unsigned flags for some IMM fields for unsigned
        #   functions? (LWU vs LW) or should that be a different field type?
        #   Or maybe based on the field name like imm vs uimm (or nzuimm)
        #
        # - Is the 'funct' field something that would be useful to turn into
        #   flags or some other info?
        out.write('instructions = (\n')
        for name, (old_name, cats) in riscv_name_lookup.items():
            instr = instrs[cats[0]][old_name]

            # Only register and immediate fields should be printed
            operand_list = []
            # In general the operands should be displayed in reverse order than
            # they are encoded in the instruction so reverse the operand fields
            # now.
            for op in reversed(instr.fields):
                if op.type in (OpcodeType.IMM, OpcodeType.RM, OpcodeType.C_REG, OpcodeType.REG):
                    # TODO: for now the operand flags field is a placeholder
                    operand_list.append("RiscVField('%s', RISCV_FIELD.%s, %d, 0x%x, %s)" % \
                            (format_field_name(op), op.type.name, op.shift, op.mask, 0))
            if len(operand_list) == 1:
                operand_str = operand_list[0]
            else:
                operand_str = ', '.join(operand_list)

            # Turn the categories from strings into RiscVInsCat values
            cat_list = []
            cat_parts_pat = re.compile(r'^RV([0-9]+)([^ ]*)$')
            for cat in cats:
                match = cat_parts_pat.search(cat)
                assert match
                cat_list.append('RiscVInsCat(%s, RISCV_CAT.%s)' % (match.group(1), match.group(2)))

            if len(cat_list) == 1:
                #cats_str = 'RISCV_CAT.' + cat[0] + ','
                cats_str = '%s,' % cat_list[0]
            else:
                #cats_str = ', '.join('RISCV_CAT.' + c for c in cats)
                cats_str = ', '.join(cat_list)

            instr_str = "RiscVIns('%s', RISCV_INS.%s, RISCV_FORM.%s, (%s), 0x%x, 0x%x, (%s), %s)" % \
                    (old_name, name, instr.form, cats_str, instr.mask, instr.value, operand_str, instr.flags)
            out.write("    %s,\n" % instr_str)
        out.write(')\n')


def main(git_repo):
    # First get a hash/version so we can capture that in the output
    cmd = ['git', '-C', git_repo, 'remote', 'get-url', 'origin']
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        git_url = p.stdout.read().strip()

    cmd = ['git', '-C', git_repo, 'describe', '--all']
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        git_tag = p.stdout.read().strip()

    cmd = ['git', '-C', git_repo, 'rev-parse', 'HEAD']
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        git_hash = p.stdout.read().strip()

    forms, instrs = scrape_instrs(git_repo)
    export_instrs(forms, instrs, (git_url, git_tag, git_hash))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='path to RISC-V manual git repo')
    args = parser.parse_args()
    main(args.path)