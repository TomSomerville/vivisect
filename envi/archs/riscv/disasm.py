import sys
import struct
import traceback

import envi
import envi.bits as e_bits

from envi.archs.riscv.const import *
from envi.archs.riscv.regs import *
from envi.archs.riscv.instr_table import *
from envi.archs.riscv.operands import *

class RiscVDisasm:
    def __init__(self, endian=envi.ENDIAN_LSB, psize=4):
        self.psize = psize
        self.setEndian(endian)

    def setEndian(self, endian):
        self.endian = endian
        self.fmt = ('<I', '>I')[endian]

    def disasm(self, bytez, offset, va):
        # Stuff we'll be putting in the opcode object
        optype = None # This gets set if we successfully decode below
        mnem = None
        operands = []
        prefixes = 0

        if offset & 0x3:
            raise envi.InvalidAddress(offset)

        ival, = struct.unpack_from(self.fmt, bytez, offset)
        print('hex ival = ', hex(ival))

        for i in instructions:
            if i.mask & ival == i.value:
                found = i
                break
    
        opers = []

        for field in found.fields:
            val = (ival >> field.shift) & field.mask
            oper = OPERCLASSES[field.type](val, va)
            opers.append(oper)

        return RiscVOpcode(va, found.opcode, found.name, 4, opers, found.flags)

OPERCLASSES = {
    RISCV_FIELD.REG: RiscVRegOper,
    RISCV_FIELD.IMM: RiscVImmOper,
    RISCV_FIELD.RM: RiscVImmOper,
    RISCV_FIELD.C_REG: RiscVRegOper,
    }