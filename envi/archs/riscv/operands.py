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

    def repr(self, op):
        return riscv_regs.registers[self.reg]

    def render(self, mcanv, op, idx):
        rname = self.repr(op)
        mcanv.addNameText(rname, typename='registers')


class RiscVImmOper():
    def __init__(self):
        pass

    def setOperValue(self):
        pass

    def getOperValue(self):
        pass

    def getOperAddr(self):
        pass


#essentially just a reg
#make reg parent
#self.reg + 8
#see uper screenie
class RiscVCRegOper():
    def __init__(self):
        pass

    def setOperValue(self):
        pass

    def getOperValue(self):
        pass

    def getOperAddr(self):
        pass


#essentially just a number
class RiscVRMOper():
    def __init__(self):
        pass

    def setOperValue(self):
        pass

    def getOperValue(self):
        pass

    def getOperAddr(self):
        pass

