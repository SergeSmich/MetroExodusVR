"""Scan MetroExodus.exe .text for instructions using a given immediate operand."""

import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402

EXE = str(re_paths.EXE)


def main():
    wants = set()
    for a in sys.argv[1:]:
        v = int(a, 0) & 0xFFFFFFFF
        wants.add(v)
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
    text = next(s for s in secs if s[0] == ".text")
    name, va, vs, raw, rs = text
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    for ins in md.disasm(d[raw : raw + rs], base + va):
        if ins.id == 0:
            continue
        for op in ins.operands:
            if op.type == X86_OP_IMM and (op.imm & 0xFFFFFFFF) in wants:
                print(
                    f"{ins.address - base:#010x}  {ins.bytes.hex():<24} {ins.mnemonic:<8}{ins.op_str}"
                )
                break


if __name__ == "__main__":
    main()
