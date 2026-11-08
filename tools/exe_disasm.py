"""Disassemble a range of MetroExodus.exe .text.

Usage: python tools/exe_disasm.py 0xdc4000 0xdc4e10
"""

import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"F:\SteamLibrary\steamapps\common\Metro Exodus\MetroExodus.exe"


def load():
    d = open(EXE, "rb").read()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    n = struct.unpack_from("<H", d, pe + 6)[0]
    opt = struct.unpack_from("<H", d, pe + 20)[0]
    base = struct.unpack_from("<Q", d, pe + 24 + 24)[0]
    so = pe + 24 + opt
    secs = []
    for i in range(n):
        o = so + 40 * i
        name = d[o : o + 8].rstrip(b"\0").decode()
        vs, va, rs, raw = struct.unpack_from("<IIII", d, o + 8)
        secs.append((name, va, vs, raw, rs))
    return d, base, secs


def rva2off(secs, rva):
    for name, va, vs, raw, rs in secs:
        if va <= rva < va + max(vs, rs):
            return raw + (rva - va)
    return None


def main():
    d, base, secs = load()
    lo = int(sys.argv[1], 0)
    hi = int(sys.argv[2], 0)
    off = rva2off(secs, lo)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    for ins in md.disasm(d[off : off + (hi - lo)], base + lo):
        if ins.id == 0:
            print(f"{ins.address - base:#09x}  {'?':<24} db")
            continue
        print(
            f"{ins.address - base:#09x}  {ins.bytes.hex():<24} {ins.mnemonic:<8}{ins.op_str}"
        )


if __name__ == "__main__":
    main()
