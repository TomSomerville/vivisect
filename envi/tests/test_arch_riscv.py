import os
import unittest
import vivisect
import envi.archs.riscv.emu as eape
import envi.archs.riscv.const as eapc
import envi.const as e_const
import envi.common as e_common
import envi.tests.riscv_test_instructions as inst
# from envi.archs.riscv.regs import *
# from envi.archs.riscv.const import *

import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
_log_level = os.environ.get('LOG_LEVEL', 'INFO')
if hasattr(logging, _log_level):
    e_common.initLogging(logger, level=getattr(logging, _log_level))
else:
    e_common.initLogging(logger, level=int(_log_level))


def getVivEnv(arch='riscv', endian=e_const.ENDIAN_LSB):
    vw = vivisect.VivWorkspace()
    vw.setMeta("Architecture", arch)
    vw.setMeta('bigend', endian)
    # vw.addMemoryMap(0, 7, 'firmware', b'\xff' * 16384)
    # vw.addMemoryMap(0xbfbff000, 7, 'firmware', b'\xfe' * 0x1000)
    # vw.addMemoryMap(0x10000000, 7, 'ram', b'\xfd' * 0x1000)
    # vw.addMemoryMap(0x10010000, 7, 'ram', b'\xfc' * 0x1000)

    emu = vw.getEmulator()
    emu.logread = emu.logwrite = True

    return vw, emu


class RiscVUnitTests(unittest.TestCase):
    
    def test_envi_riscv_disasm(self):
        bademu = 0
        goodemu = 0
        test_pass = 0

        vw, emu = getVivEnv()

        for test_bytes, result_instr in inst.instructions.items():
            try:
                # test decoding of the instructions
                op = vw.arch.archParseOpcode(bytes.fromhex(test_bytes), 0, va=0x40004560)
                op_str = repr(op).strip()
                if op_str == result_instr:
                    test_pass += 1
                if result_instr != op_str:
                    logging.error('{}: ours: {} != {}'.format(test_bytes, repr(op_str), repr(result_instr)))

            except Exception as  e:
                logging.exception('ERROR: {}: {}'.format(test_bytes, result_instr))

        logger.info("%d of %d successes", test_pass, len(inst.instructions))
        self.assertEqual(test_pass, len(inst.instructions))
