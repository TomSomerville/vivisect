import envi.registers as e_reg

from envi.archs.riscv.const import *



#x0 is hard wired with all bits equal to 0

#Manual states that the following registers are conventionally used for:
#x1 holds return address
#x2 is stack pointer
#x5 alternate link register

registers = [
    'zero', 'ra', 'sp', 'gp', 'tp', 't0', 't1', 't2', 's0', 's1', 'a0', 
    'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 's2', 's3', 's4', 
    's5', 's6', 's7', 's8', 's9', 's10', 's11', 't3', 't4', 't5', 
    't6', 'pc', 'ft0', 'ft1,', 'ft2', 'ft3', 'ft4', 'ft5', 'ft6', 'ft7',
    'fs0', 'fs1', 'fa0', 'fa1', 'fa2', 'fa3', 'fa4', 'fa5', 'fa6', 'fa7',
    'fs2', 'fs3', 'fs4', 'fs5', 'fs6', 'fs7', 'fs8', 'fs9', 'fs10', 'fs11',
    'ft8', 'ft9', 'ft10', 'ft11' 
]

registers_info = [ (reg, 32) for reg in registers ]

l = locals()
e_reg.addLocalEnums(l, registers_info)

REG_X0  = REG_ZERO
REG_X1  = REG_RA
REG_X2  = REG_SP
REG_X3  = REG_GP
REG_X4  = REG_TP
REG_X5  = REG_T0
REG_X6  = REG_T1
REG_X7  = REG_T2
REG_X8  = REG_S0
REG_X9  = REG_S1
REG_X10 = REG_A0
REG_X11 = REG_A1
REG_X12 = REG_A2
REG_X13 = REG_A3
REG_X14 = REG_A4
REG_X15 = REG_A5
REG_X16 = REG_A6
REG_X17 = REG_A7
REG_X18 = REG_S2
REG_X19 = REG_S3
REG_X20 = REG_S4
REG_X21 = REG_S5
REG_X22 = REG_S6
REG_X23 = REG_S7
REG_X24 = REG_S8
REG_X25 = REG_S9
REG_X26 = REG_S10
REG_X27 = REG_S11
REG_X28 = REG_T3
REG_X29 = REG_T4
REG_X30 = REG_T5
REG_X31 = REG_T6

REG_F0  = REG_FT0
REG_F1  = REG_FT1
REG_F2  = REG_FT2
REG_F3  = REG_FT3
REG_F4  = REG_FT4
REG_F5  = REG_FT5
REG_F6  = REG_FT6
REG_F7  = REG_FT7
REG_F8  = REG_FS0
REG_F9  = REG_FS1
REG_F10 = REG_FA0
REG_F11 = REG_FA1
REG_F12 = REG_FA2
REG_F13 = REG_FA3
REG_F14 = REG_FA4
REG_F15 = REG_FA5
REG_F16 = REG_FA6
REG_F17 = REG_FA7
REG_F18 = REG_FS2
REG_F19 = REG_FS3
REG_F20 = REG_FS4
REG_F21 = REG_FS5
REG_F22 = REG_FS6
REG_F23 = REG_FS7
REG_F24 = REG_FS8
REG_F25 = REG_FS9
REG_F26 = REG_FS10
REG_F27 = REG_FS11
REG_F28 = REG_FT8
REG_F29 = REG_FT9
REG_F30 = REG_FT10
REG_F31 = REG_FT11

registers_mets = []

status_meta = []

class RiscVRegisterContext(e_reg.RegisterContext):
    def __init__(self):
        e_reg.RegisterContext.__init__(self)
        self.loadRegDef(registers_info)
        self.loadRegMetas([], statmetas=status_meta)
        self.setRegisterIndexes(REG_PC, REG_X2)
