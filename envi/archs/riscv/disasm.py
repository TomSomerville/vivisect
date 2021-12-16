import sys
import struct
import traceback

import envi
import envi.bits as e_bits

from envi.archs.riscv.const import *
from envi.archs.riscv.regs import *
from envi.archs.riscv.instr_table import instructions

class ricsvDisasm:
	def __init__(self, endian=ENDIAN=MSB, options=CAT_RISCV_DEFAULT, psize=4):
		self.psize = psize

		self._instr_dict = None
		self._dis_regctx = Riscv32RegisterContext()
		self.setCategories(options)

	def setEndian(self, endian):
        self.endian = endian
        self.fmt = ('<I', '>I')[endian]

	def disasm(self, bytes, offset, va):
		# Stuff we'll be putting in the opcode object
		optype = None # This gets set if we successfully decode below
		mnem = None
		operands = []
		prefixes = 0

		if offset & 0x3:
			raise envi.InvalidAddress(offset)

		ival, = struct.unpack_from(self.fmt, bytez, offset)
		print('hex ival = ', hex(ival))

		key = ival

		cat = self.instructions.get(key)
		if not cat:
            raise envi.InvalidInstruction(bytez[offset:offset+4], 'No Instruction Group Found: %x' % key, va)

        for mask in cat:
            masked_ival = ival & mask
            try:
                data = cat[mask][masked_ival]
                break
            except KeyError:
                pass
        else:
            raise envi.InvalidInstruction(bytez[offset:offset+4], 'No Instruction Matched in Group: %x' % key, va)

        name, opcode, form, cat, operands, iflags = data

        decoder = decoders.get(form, form_DFLT)

        nopcode, opers, iflags = decoder(self, va, ival, opcode, operands, iflags)
        if nopcode != None:
            opcode = nopcode

        mnem, opcode, opers, iflags = self.simplifiedMnems(ival, mnem, opcode, opers, iflags)
        iflags |= self.__ARCH__

        return RiscVIns(va, opcode, name, size=4, operands=opers)

		

