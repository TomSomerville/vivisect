import envi
import envi.archs.riscv.regs as riscv_regs


class RiscVOpcode(envi.Opcode):
    def __init__(self, va, opcode, mnem, size, opers, iflags=0):
        super()__init__(va, opcode, mnem, 0, size, operands, iflags)

    def getBranches(self, emu=None):
        ret = []
        
        flags = 0
        addb = False

        if self.iflags & (IF_COND):
            flags |= envi.BR_COND
            addb = True

        if not self.iflags & (envi.IF_NOFALL | envi.IF_RET | envi.IF_BRANCH) or self.iflags & envi.IF_COND:
            ret.append((self.va + self.size, flags|envi.BR_FALL))

       if len(self.opers) == 0:
           if self.iflags & envi.IF_CALL:
               ret.append(None, flags | envi.BR_PROC))
            return ret

        if self.iflags & IF_CALL:
            flags |= envi.BR_PROC
            addb = True

        elif (self.iflags & IF_CALLCC) == IF_CALLCC:
            flags |= (envi.BR_PROC | envi.BR_COND)
            addb = True

        elif self.iflags & IF_BRANCH:
            addb = True

        if addb:
            oper = self.opers[-1]
            if oper.isDeref():
                flags |= envi.BR_DEREF
                tova = oper.getOperAddr(self, emu=emu)
            else:
                tova = oper.getOperValue(self, emu=emu)

            ret.append((tova, flags))

        return ret

    def render(self):
        if self.prefixes:
            pfx = self._getPrefixName(self.prefixes)
            if pfx:
                mcanv.addNameText("%s: " % pfx, pfx)

        mnem = self.mnem
        mcanv.addNameText(mnem, self.mnem, typename="mnemonic")
        mcanv.addText(" ")

        # Allow each of our operands to render
        imax = len(self.opers)
        lasti = imax - 1
        for i in range(imax):
            oper = self.opers[i]
            oper.render(mcanv, self, i)
            if i != lasti:
                mcanv.addText(",")

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
    def __init__(self, val, va=0):
        self.val = val
        self.va = va

    def __eq__(self, oper):
        if not isinstance(oper, self.__class__):
            return False
        if self.val != oper.val:
            return False
        if self.oflags != oper.oflags:
            return False
        return True

    def getOperValue(self, op, emu=none):
        return self.val

    #Rework to calculate #of BYTES, not bits
    def getWidth(self, emu):
        return emu.getPointerSize()

    #returns content intended to be printed to screen
    def repr(self, op):
        return hex(self.val)

    #displays the values on the canvas
    def render(self, mcanv, op, idx):
        value = self.val
        hint = mcanv.syms.getSymHint(op.va, idx)
        if hint != None:
            if mcanv.mem.isValidPointer(value):
                mcanv.addVaText(hint, value)
            else:
                mcanv.addNameText(hint)
        elif mcanv.mem.isValidPointer(value):
            name = addrToName(mcanv, value)
            mcanv.addVaText(name, value)
        else:

            if abs(self.val) >= 4096:
                mcanv.addNameText(hex(value))
            else:
                mcanv.addNameText(str(value))

    #no def involvesPC needed correct?
    def involvesPC(self):
        return False

    def getOperAddr(self):
        return None

    #shouldnt be needed for Immediates
    def setOperValue(self):
        pass

class RiscVCRegOper(RiscVRegOper):
    def __init__(self, c_reg, va=0, oflags=0):
        reg = c_reg + 8
        super().__init__(reg, va, oflags)
