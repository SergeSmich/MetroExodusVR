"""Print the strings referenced by ``lea rip`` in an EXE range.

Usage: python tools/exe_lea_strings.py 0xdc41d0 0xdc4280
"""

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402
re_paths.require(str(re_paths.EXE))


EXE = str(re_paths.EXE)


def main():
    lo = int(sys.argv[1], 0)
    hi = int(sys.argv[2], 0)
    d = Path(EXE).read_bytes()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    n = struct.unpack_from("<H", d, pe + 6)[0]
    opt = struct.unpack_from("<H", d, pe + 20)[0]
    base = struct.unpack_from("<Q", d, pe + 24 + 24)[0]
    so = pe + 24 + opt
    secs = []
    for i in range(n):
        o = so + 40 * i
        vs, va, rs, raw = struct.unpack_from("<IIII", d, o + 8)
        secs.append((va, vs, raw, rs))

    def off(rva):
        for va, vs, raw, rs in secs:
            if va <= rva < va + max(vs, rs):
                return raw + (rva - va)
        return None

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    code = d[off(lo) : off(lo) + (hi - lo)]
    for ins in md.disasm(code, base + lo):
        if not ins.operands:
            continue
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                tgt = ins.address + ins.size + op.mem.disp
                rva = tgt - base
                o = off(rva)
                s = ""
                if o is not None:
                    e = d.find(b"\0", o)
                    raw = d[o:e]
                    if all(32 <= c < 127 for c in raw) and raw:
                        s = raw.decode("latin-1")
                if s:
                    print(
                        f"{ins.address - base:#010x}  {ins.mnemonic} {ins.op_str:<40} -> {rva:#x} {s!r}"
                    )
                break


if __name__ == "__main__":
    main()
