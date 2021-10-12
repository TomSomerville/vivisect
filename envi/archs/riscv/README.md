# Regenerating instruction table and constants
To regenerate the `envi/archs/riscv/const_gen.py` and
`envi/archs/riscv/instr_table.py` files from the latest RISC-V follow these
steps:
1. Clone the RISC-V ISA manual git repo
```
$ git clone https://github.com/riscv/riscv-isa-manual
```
2. In the base vivisect directory run the `envi.archs.riscv.gen` script:
```
$ cd vivisect
$ python -m envi.archs.riscv.gen ../riscv-isa-manual
```
