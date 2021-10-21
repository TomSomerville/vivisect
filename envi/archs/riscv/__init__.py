"""
riscv module
"""

import envi

from envi.archs.riscv.regs import *
from envi.archs.riscv.disasm import *
from envi.archs.riscv.const import *

class RiscvModule(envi.ArchitectureModule):
    def __init__(self):
        envi.ArchitectureModule.__init__(self, "RiscV")
        self._arch_dis = RiscVDisasm()

    def archGetRegCtx(self):
        return RiscVRegisterContext()

    def archGetNopInstr(self):
        return b'\x00\x00\x00\x13' # NOP is emulated with addi x0, x0, 0

    def archGetRegisterGroups(self):
        groups = envi.ArchitectureModule.archGetRegisterGroups(self)
        general= ('general', registers, )
        groups.append(general)
        return groups

    def getPointerSize(self):
            return 4

#no idea on this one, other 32 bit like i386 use "0x%.8x" % va. I cannot seem to locate what calls this. grepping only seems to have this in the various __init__ files

    def pointerString(self, va):
        return '0x%.8x' % va

#no idea on this one
    def archParseOpcode(self, bytez, offset=0, va=0):
        return self._arch_dis.disasm(bytez, offset, va)

    def getEmulator(self):
        return RiscVEmulator()


# NOTE: This one must be after the definition of RiscvModule
from envi.archs.riscv.emu import *                    
