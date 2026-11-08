"""Find rip-relative xrefs to one or more RVAs in MetroExodus.exe .text.

Usage: python tools/xrefs.py 0x14c9f64 [0x...]
Also accepts a substring: --str tcmap
"""

import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

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


def off2rva(secs, off):
    for name, va, vs, raw, rs in secs:
        if raw <= off < raw + rs:
            return va + (off - raw), name
    return None, None


def main():
    d, base, secs = load()
    args = sys.argv[1:]
    targets = {}
    if args and args[0] == "--str":
        needle = args[1].encode()
        off = 0
        while True:
            i = d.find(needle, off)
            if i < 0:
                break
            rva, sname = off2rva(secs, i)
            if rva is not None:
                targets[rva] = (args[1], rva)
            off = i + 1
    else:
        for a in args:
            rva = int(a, 0)
            targets[rva] = (a, rva)

    text = next(s for s in secs if s[0] == ".text")
    name, va, vs, raw, rs = text
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    hits = {rva: [] for rva in targets}
    code = d[raw : raw + rs]
    for ins in md.disasm(code, base + va):
        if ins.id == 0:
            continue
        if not ins.operands:
            continue
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                t = ins.address + ins.size + op.mem.disp - base
                if t in hits:
                    hits[t].append((ins.address - base, ins))
                break
    for rva, (label, _) in targets.items():
        print(f"== {label} rva {rva:#x}: {len(hits[rva])} xrefs")
        for addr, ins in hits[rva]:
            print(f"  {addr:#010x}  {ins.mnemonic} {ins.op_str}")


if __name__ == "__main__":
    main()
