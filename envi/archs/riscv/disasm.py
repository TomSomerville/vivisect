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
        self.setCategories()

    def setCategories(self):
        # True = 32 bit
        # False = 16 bit
        self.instrs = {True: {}, False: {}}
        xlen = self.psize * 8
        for entry in instructions:
            instr_size = entry.cat[0].cat != RISCV_CAT.C
            if entry.mask not in self.instrs[instr_size]:
                self.instrs[instr_size][entry.mask] = {}
            if any(cat.xlen == xlen for cat in entry.cat):
                if entry.value in self.instrs[instr_size][entry.mask]:
                    assert False

                self.instrs[instr_size][entry.mask][entry.value] = entry



    def setEndian(self, endian):
        self.endian = endian
        self.fmt = {
            # True is 32 bit
            # False is 16 bit
            True: ('<I', '>I')[endian],
            False: ('<H', '>H')[endian]
        }

    def disasm(self, bytez, offset, va):
        # Stuff we'll be putting in the opcode object
        optype = None # This gets set if we successfully decode below
        mnem = None
        operands = []
        prefixes = 0

        # TODO; If RiscV ever supports Big Endian this may change
        opcode_size = bytez[offset] & 0x3 == 0x3

        opcode_bytes = (2, 4)[opcode_size]

        ival, = struct.unpack_from(self.fmt[opcode_size], bytez, offset)
        print(hex(ival))

        for mask in self.instrs[opcode_size]:
            masked_value  = ival & mask
            found = self.instrs[opcode_size][mask].get(masked_value)
            if found is not None:
                break
        else:
            raise envi.InvalidInstruction(bytez[offset:offset+opcode_bytes], 'No Instruction Matched: %x' % ival, va)

        opers = tuple(OPERCLASSES[f.type](ival=ival, args=f.args va=va, oflags=f.flags) for f in found.fields)
        return RiscVOpcode(va, found.opcode, found.name, opcode_bytes, opers, found.flags)


OPERCLASSES = {
    RISCV_FIELD.REG: RiscVRegOper,
    RISCV_FIELD.C_REG: RiscVCRegOper,
    RISCV_FIELD.CSR_REG = RiscVCSRRegOper,
    RISCV_FIELD.MEM: RiscVMemOper,
    RISCV_FIELD.MEM_SP: RiscVMemSPOper,
    RISCV_FIELD.IMM: RiscVImmOper,
    RISCV_FIELD.RM: RiscVRMOper,
}
