import envi.registers as e_reg

from envi.archs.riscv.const import *



#x0 is hard wired with all bits equal to 0

#Manual states that the following registers are conventionally used for:
#x1 holds return address
#x2 is stack pointer
#x5 alternate link register

registers = [
    'x0', 'x1', 'x2', 'x3', 'x4', 'x5', 'x6', 'x7', 'x8', 'x9', 'x10', 
    'x11', 'x12', 'x13', 'x14', 'x15', 'x16', 'x17', 'x18', 'x19', 'x20', 
    'x21', 'x22', 'x23', 'x24', 'x25', 'x26', 'x27', 'x28', 'x29', 'x30', 
    'x31', 'pc'
]

registers_info = [ (reg, 32) for reg in registers ]

l = locals()
e_reg.addLocalEnums(l, registers_info)

registers_mets = []

status_meta = []

class RISCVRegisterContext(e_reg.RegisterContext):
    def __init__(self):
        e_reg.RegisterContext.__init__(self)
        self.loadRegDef(registers_info)
        self.loadRegMetas([], statmetas=status_meta)
        self.setRegisterIndexes(REG_PC, REG_X2)
