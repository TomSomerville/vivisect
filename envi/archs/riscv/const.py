import enum

from envi.archs.riscv.const_gen import *


class RISCV_CAT(enum.IntFlag):
    """
    RISC-V Instruction categories

    This enumeration helps map the architecture name to the instruction
    categories.  The specific values don't really matter here but in general
    each nibble denotes a "type" of instruction category because I felt like
    organizing them in that way.

    Architecture Types:
      I           integer (base)
      M           multiply & divide instructions
      A           atomic memory & inter-processor sync instructions
      E           reduced number of gprs

      F           single-precision floating-point
      D           double-precision floating-point
      Q           quad-precision floating-point

      Zicsr       control and status register instructions
      Zifencei    instruction-fetch fence
      Zihintpause PAUSE encoding of FENCE and specific meanings

      G           IMAFD,Zicsr,Zifencei

      C           compressed (VLE/16-bit instructions)
      E           embedded, only 16 "x" register

    Placeholder categories
      L           decimal floating-point
      B           bit manipulation
      J           dynamically translated languages
      T           transactional memory
      P           packed-SIMD
      V           vector

      Zam         misaligned atomics
      Zfh         half-precision floating point
      Zfhmin      half-precision floating point
      Zfinx       floating point in integer registers
      Zdinx       floating point in integer registers
      Zhinx       floating point in integer registers
      Zhinxmin    floating point in integer registers
      Ztso        total store ordering

    All instruction categories that are just placeholders and do not represent
    valid instructions that can be disassembled and emulated by this envi
    module are defined with a leading '_'.
    """
    # Base Functionality
    I           = 1 << 0
    M           = 1 << 1
    A           = 1 << 2

    # Floating point
    F           = 1 << 8
    D           = 1 << 9
    Q           = 1 << 10
    L           = 1 << 11  # draft

    # "other" (mostly placeholders)
    C           = 1 << 16
    E           = 1 << 17  # draft
    B           = 1 << 18  # draft
    J           = 1 << 19  # draft
    T           = 1 << 20  # draft
    P           = 1 << 21  # draft
    V           = 1 << 22  # draft

    # "Z" categories
    Zicsr       = 1 << 32
    Zifencei    = 1 << 33
    Zihintpause = 1 << 34
    Zam         = 1 << 34  # draft
    Zfh         = 1 << 36  # draft
    Zfhmin      = 1 << 37  # frozen
    Zfinx       = 1 << 38  # frozen
    Zdinx       = 1 << 39  # frozen
    Zhinx       = 1 << 40  # frozen
    Zhinxmin    = 1 << 41  # frozen
    Ztso        = 1 << 42  # frozen

    # Convenience Names
    G        = I | M | A | F | D | Zicsr | Zifencei

    def __contains__(self, item):
        return self.value & int(item) == self.value