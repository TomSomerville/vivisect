from envi import *
from .regs import *
from .const import *
from .disasm import *
# from .bits import *
from envi.archs.riscv import *

class RiscVCall(envi.CallingConvention):
    '''
    RiscV Calling Convention.
    '''
    arg_def = [(CC_REG, REG_X10 + x) for x in range(8)]
    arg_def.append((CC_STACK_INF, 8))
    retaddr_def = (CC_REG, REG_X1)
    retval_def = (CC_REG, REG_X10)
    flags = CC_CALLEE_CLEANUP
    align = 4
    pad = 0

RiscVcall = RiscVCall()

class RiscVAbstractEmulator(envi.Emulator):

    def __init__(self, archmod=None, endian=ENDIAN_MSB, psize=4):
        self.psize = psize
        super(RiscVAbstractEmulator, self).__init__(archmod=archmod)
        self.setEndian(endian)

        self.addCallingConvention("riscvcall", RiscVCall)

class RiscVEmulator(RiscVRegisterContext, RiscVModule, RiscVAbstractEmulator):
    def __init__(self, archmod=None, endian=ENDIAN_LSB, psize=4):
        RiscVAbstractEmulator.__init__(self, archmod=RiscVModule(), endian=endian, psize=psize)
        RiscVRegisterContext.__init__(self)
        RiscVModule.__init__(self)