import argparse

import vivisect
import envi

import envi.common as e_common
import logging
import struct
logger = logging.getLogger()

def parseBytes(value, size=4):
    if size ==4:
        data = struct.pack('<I', value)
    else:
        data = struct.pack('<H', value)
    
    return emu.archParseOpcode(data)


def start(_archname=None, _verbose=0):
    global emu, vw
    vw = vivisect.VivWorkspace()
    # Copied from vivisect/parsers/blob.py
    vw.setMeta('Architecture', _archname)
    vw.setMeta('Platform', 'unknown')
    vw.setMeta('Format', 'blob')
    vw.setMeta('bigend', envi.const.ENDIAN_MSB)
    #vw.setMeta('DefaultCall', vivisect.const.archcalls.get(_archname, 'unknown'))

    # setup logging
    vw.verbose = min(_verbose, len(e_common.LOG_LEVELS)-1)
    level = e_common.LOG_LEVELS[vw.verbose]
    e_common.initLogging(logger, level=level)

    print('workspace arch set to %s' % _archname)
    emu = vw.getEmulator()

    from IPython import embed
    embed(colors="neutral")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    ppc_arch_list = [n for n in envi.arch_names.values()]
    parser.add_argument('-a', '--arch', default='riscv', choices=ppc_arch_list)
    parser.add_argument('-v', '--verbose', dest='verbose', default=False, action='count',
                        help='Enable verbose mode (multiples matter: -vvvv)')

    args = parser.parse_args()

    start(args.arch, args.verbose)