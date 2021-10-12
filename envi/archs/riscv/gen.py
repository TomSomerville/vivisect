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

_binfields = _regfields + _immfields

# The RVC instructions have more specific imm information than the form
_immvalues = _immfields + _binfields + [
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

_binvalues = [
    r'[01]+',
]

# Some RVC instructions use decimal constants instead of binary
_decvalues = [
    r'[0-9]+',
]

# the required bin field may also have a value of 'rm'
_reqbinvalues = _reqbinfields + _binvalues + [
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
    C_OPCODE = enum.auto()
    C_REG = enum.auto()


RiscVForm = namedtuple('RiscVForm', [
    'name',
    'fields',
])

RiscVField = namedtuple('RiscVField', [
    'value',  # "name" or integer constant
    'type',
    'columns',
    'bits',
    'mask',
    'shift',
])

RiscVOp = namedtuple('RiscVOp', [
    'name',
    'cat',
    'form',
    'mask',
    'value',
    'operands',
    'flags',
    'notes',
])


def get_instr_mask(fields):
    mask = '0b'
    value = '0b'
    for field in fields:
        if isinstance(field.value, int):
            mask += '1' * field.bits
            value += bin(field.value)[2:]
        else:
            mask += '0' * field.bits
            value += '0' * field.bits

    return (int(mask, 2), int(value, 2))


def get_instr_flags(name, fields):
    # TODO: determine the instruction flags
    # envi.IF_NOFALL
    # envi.IF_PRIV
    # envi.IF_CALL
    # envi.IF_BRANCH
    # envi.IF_RET
    # envi.IF_COND
    # envi.IF_REPEAT
    # envi.IF_BRANCH_COND

    # For now just return an empty flags
    return 0

def get_operand_type(operand):
    # TODO: determine operand type based on value and type

    # Just return the type enum name for now
    return operand.type.name


def get_field_type(field):
    if _immvaluepat.match(field):
        return OpcodeType.IMM
    elif _decvaluepat.match(field):
        return OpcodeType.CONST
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
        else:
            return OpcodeType.CONST
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
        try:
            if isinstance(columns[col], tuple):
                end = columns[col][0]
            else:
                end = columns[col]
        except IndexError:
            if isinstance(columns[-1], tuple):
                end = columns[-1][1]
            else:
                end = 0

        field_bits = start - end
        field_shift = end

        # Determine the type of this field by pattern
        field_type = get_field_type(value)

        # Generate the mask and shift that could be used to extract this field
        # from an instruction
        #field_mask = int('0b' + '1' * field_bits, 2)
        field_mask = (2 ** field_bits) - 1
        fields.append(RiscVField(value, field_type, int(size), field_bits, field_mask, field_shift))

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
                    if _binvaluepat.match(value[0][1]) and _binfieldpat.match(field.value) and \
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


def scrape_instr_table(text, default_cat=None, forms=None):
    # Find the instruction definitions
    parts = [
        r'\n +&\n((?:\\.*instbit.* [&\\]+ *\n)+)\\[a-z]+line{\d-\d+}\n',
        r'\\multicolumn[^\\]+\\bf (.*RV.*)} & \\\\ *\n',
        r'\n&\n((?:\\multicolumn.* & *\n)+\\multicolumn.* & [A-Z0-9a-z.-]+) (?:{\\em \\tiny (.*)})? *\\\\ *\n\\[a-z]+line{\d-\d+}\n',
    ]
    pat = _makepat(parts, re.MULTILINE)

    field_size_parts = [
        r'\\instbit{(\d+)}',
        'instbitrange{(\d+)}{(\d+)}',
    ]
    field_size_pat = _makepat(field_size_parts, re.MULTILINE)

    cat_extension_pat = re.compile(r'{(Z[^}]+)}')
    cat_pat = re.compile(r'(RV[0-9]+[^ ]*)')

    info_parts = [
        r'\\multicolumn{(\d+)}{[|c]+}{(.*)} &',
        r' ([A-Z0-9a-z.-]+)',
    ]
    info_pat = _makepat(info_parts, re.MULTILINE)

    columns = []
    if forms is None:
        forms = {}
    instructions = {}
    if default_cat is not None:
        instructions[default_cat] = {}

    cur_cat = default_cat

    for match in pat.findall(text):
        #print(match)
        fieldbits, catname, instrmatch, notesmatch = match
        if fieldbits:
            columns = [int(m[0]) if m[0] else (int(m[1]), int(m[2])) \
                    for m in field_size_pat.findall(fieldbits)]
        elif instrmatch:
            instr_fields = [(int(m[0]), m[1]) if m[1] else m[2] for m in info_pat.findall(instrmatch)]
            #print(instr_fields)
            # If the last field of instrmatch ends in '-type' this is a form
            # name (the relevant forms are repeated each section
            instr_name = instr_fields[-1]
            if cur_cat is None or instr_name.endswith('-type'):
                form_name = instr_fields[-1].upper().replace('-', '_')
                fields = get_field_info(instr_fields[:-1], columns)
                print('Adding form %s (%s)' % (form_name, fields))
                forms[form_name] = RiscVForm(form_name, fields)
            else:
                assert instr_name not in instructions[cur_cat]

                descr = instr_fields[:-1]
                # We don't need the parsed form info right now
                print(instr_name, descr)
                form_name, _ = find_form(descr, forms)

                # Now find the bit width of the fields
                op_fields = get_field_info(descr, columns)

                # the opcode is the last field, ensure it is a constant
                assert op_fields[-1].type == OpcodeType.CONST

                # Get the combined mask and post-mask value for this
                # instruction
                op_mask, op_value = get_instr_mask(op_fields)

                # And generate the flags for this instruction
                op_flags = get_instr_flags(instr_name, op_fields)

                op = RiscVOp(instr_name, cur_cat, form_name, op_mask,
                        op_value, op_fields, op_flags, notesmatch)
                instructions[cur_cat][instr_name] = op
                print('Adding op [%s] %s (%s): %s' % (cur_cat, instr_name, form_name, op_fields))
        else:
            extmatch = cat_extension_pat.search(catname)
            if extmatch:
                cur_cat = extmatch.group(1)
            else:
                catmatch = cat_pat.search(catname)
                cur_cat = catmatch.group(1)
                if cur_cat[-1].isdigit():
                    # Add the default 'I' to the category
                    cur_cat += 'I'

            assert cur_cat not in instructions
            instructions[cur_cat] = {}
            #print(cur_cat)

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
        forms[form_name] = RiscVForm(form_name, fields)

    return forms


def scrape_instrs(git_repo):
    forms = {}
    instrs = {}

    with open(git_repo + '/src/instr-table.tex', 'r') as f:
        instr_table = f.read()
    unpriv_forms, unpriv_instrs = scrape_instr_table(instr_table)
    forms.update(unpriv_forms)
    for cat, data in unpriv_instrs.items():
        if cat not in instrs:
            instrs[cat] = data
        else:
            instrs[cat].update(data)

    with open(git_repo + '/src/priv-instr-table.tex', 'r') as f:
        instr_table = f.read()
    # the privileged instructions should default to the base RV32I category
    priv_forms, priv_instrs = scrape_instr_table(instr_table, 'RV32I')
    forms.update(priv_forms)
    for cat, data in priv_instrs.items():
        if cat not in instrs:
            instrs[cat] = data
        else:
            instrs[cat].update(data)

    with open(git_repo + '/src/c.tex', 'r') as f:
        instr_table = f.read()
    # the compact instructions should default to the base RV32C category
    rvc_forms = scrape_rvc_forms(instr_table)
    forms.update(rvc_forms)

    with open(git_repo + '/src/rvc-instr-table.tex', 'r') as f:
        instr_table = f.read()
    _, rvc_instrs = scrape_instr_table(instr_table, 'RV32C', rvc_forms)
    for cat, data in rvc_instrs.items():
        if cat not in instrs:
            instrs[cat] = data
        else:
            instrs[cat].update(data)

    return forms, instrs


def export_instrs(forms, instrs, git_info):
    # Export all the forms
    form_list = list(forms.keys())

    # Make a list of the categories (the categories are the primary keys of the
    # instructions)
    cat_list = list(instrs.keys())

    # To turn the instruction names into python constants we first need to
    # remove any embedded '.'s.  Also while looping through the instruction
    # categories build up a list of all the categories that each instruction is
    # present in.
    riscv_name_lookup = {}
    for cat, cat_data in instrs.items():
        for instr_name in cat_data.keys():
            new_name = instr_name.replace('.', '_')
            if instr_name not in riscv_name_lookup:
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

        # Now save the scraped FORM, CAT, and OP (instruction) values
        out.write('def RISCV_FORM(enum.IntEnum):\n')
        for form in form_list:
            out.write('    %s = enum.auto()\n' % form.upper())
        out.write('\n\n')

        out.write('def RISCV_CAT(enum.IntEnum):\n')
        for cat in cat_list:
            out.write('    %s = enum.auto()\n' % cat.upper())
        out.write('\n\n')

        out.write('def RISCV_OP(enum.IntEnum):\n')
        for instr in riscv_name_lookup.keys():
            out.write('    %s = enum.auto()\n' % instr.upper())

    with open(os.path.join(cur_dir, 'instr_table.py'), 'w') as out:
        # First log the git information
        out.write('# Generated from:\n')
        for info in git_info:
            out.write('#   %s\n' % info)
        out.write('\n')

        # Dump the types used to encode the instructions
        out.write('''from collections import namedtuple

RiscVField = namedtuple('RiscVField', ['type', 'mask', 'shift', 'flags'])
RiscVOp = namedtuple('RiscVOp', ['name', 'cat', 'form', 'mask', 'value', 'operands', 'flags'])

''')

        # Dump the form and instructions
        # TODO: Some things need to be done before this list of instructions is
        #       good:
        #       1. Generate a list of operand types based on the 'value' and
        #          'type' for each register or immediate operand field
        #          (get_operand_type)
        #       2. Generate the correct flags for each instruction
        #          (get_instr_flags)
        out.write('instructions = {\n')
        for name, (old_name, cats) in riscv_name_lookup.items():
            instr = instrs[cats[0]][old_name]

            # Only register and immediate fields should be printed
            operand_list = []
            for op in instr.operands:
                if op.type in (OpcodeType.IMM, OpcodeType.C_REG, OpcodeType.REG):
                    op_type = get_operand_type(op)
                    # TODO: for now the operand flags field is a placeholder
                    operand_list.append("RiscVField('%s', 0x%x, %d, %s)" % \
                            (op_type, op.mask, op.shift, 0))
            operand_str = ', '.join(operand_list)

            instr_str = "RiscVOp('%s', %r, '%s', 0x%x, 0x%x, [%s], %s)" % \
                    (instr.name, cats, instr.form, instr.mask, instr.value, operand_str, instr.flags)
            out.write("    '%s': %s,\n" % (name, instr_str))
        out.write('}\n')


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
