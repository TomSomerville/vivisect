import envi
import envi.archs.riscv.regs as riscv_regs


class RiscVOpcode():
    def __init__(self):
        pass

class RiscVRegOper(envi.RegisterOper):
    #reg == 5 bit number from disasm.py
    #va == memory address
    #oflags == not used at the moment. 
    def __init__(self, reg, va=0, oflags=0):
        self.va = va
        self.reg = reg
        self.oflags = oflags
    
    def __eq__(self, oper):
        if not isinstance(oper, self.__class__):
            return False
        if self.reg != oper.reg:
            return False
        if self.oflags != oper.oflags:
            return False
        return True

    def involvesPC(self):
        return self.reg == REG_PC

    def getWidth(self, emu):
        return emu.getRegisterWidth(self.reg) // 8
        
    def getOperValue(self, op, emu=None):
        if self.reg == REG_PC:
            return self.va

        if emu is None:
            return None
        return emu.getRegister(self.reg)

    def setOperValue(self, op, emu=None, val=None):
        if emu is None:
            return
        emu.setRegister(self.reg, val)

    def getOperAddr(self, op, emu=None):
        return None

    #returns content intended to be printed to screen
    def repr(self, op):
        return riscv_regs.registers[self.reg]

    #displays the values on the vivisect canvas gui
    def render(self, mcanv, op, idx):
        rname = self.repr(op)
        mcanv.addNameText(rname, typename='registers')

#line 345 of envi/__init__.py - aaron please verify correct class here...
class RiscVImmOper(envi.ImmedOper):
    def __init__(self, imm, va=0, size):
        self.imm = imm
        self.va = va
        self.size = size

    def __eq__(self, oper):
        if not isinstance(oper, self.__class__):
            return False
        if self.imm != oper.imm:
            return False
        if self.oflags != oper.oflags:
            return False
        return True

    def getOperValue(self, op, emu=none):
        return self.imm

    def getWidth(self, emu):
        return self.size

    #returns content intended to be printed to screen
    def repr(self, op):
        return '#0x%.3x' % (self.imm)

    #displays the values on the vivisect canvas gui
    def render(self, mcanv, op, idx):
        val = self.imm
        mcanv.addText('#')
        #size of value should be trimmed or set to max for arch? 22bits is longest immediate (UType)
        mcanv.addNameText('0x%.3x' % (val))

    #no def involvesPC needed correct?
    def involvesPC(self):
        return False

    #no setOperValue needed, as the value does not need to be stored anywhere and exists only in this instruction?
    def setOperValue(self):
        pass

    #no setOperValue needed, as the value does not need to be stored anywhere and exists only in this instruction?
    def getOperAddr(self):
        pass


#essentially just a reg
#make reg parent
#self.reg + 8
#see uper screenie
class RiscVCRegOper(RiscVRegOper):
    def __init__(self, c_reg, va=0, oflags=0):
        reg = c_reg + 8
        super().__init__(reg, va, oflags)
        #I think the super call above will work, however adding aarons code commented out for the time being just in case. 
        #I like the one aboce because its less mess and simpler to understand to me at least. Will remove comments after proven.
        #super(RiscVCRegOper, self).__init__(reg, va, oflags)

    def setOperValue(self):
        pass

    def getOperValue(self):
        pass

    def getOperAddr(self):
        pass


#essentially just a number
class RiscVRMOper(RiscVImmOper):
    def __init__(self, rm, va=0, oflags=0):
        super().__init__(rm, va, oflags)

    def setOperValue(self):
        pass

    def getOperValue(self):
        pass

    def getOperAddr(self):
        pass

