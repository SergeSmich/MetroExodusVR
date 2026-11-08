"""Find RIP-relative code references to an RVA range in MetroExodus.exe.

Usage: python tools/find_xrefs.py <start-rva-hex> <end-rva-hex>
"""

import sys
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

EXE = r"F:\SteamLibrary\steamapps\common\Metro Exodus\MetroExodus.exe"
pe = pefile.PE(EXE, fast_load=True)
data = open(EXE, "rb").read()
secs = [
    (
        s.Name.rstrip(b"\x00").decode(),
        s.VirtualAddress,
        s.Misc_VirtualSize,
        s.PointerToRawData,
        s.SizeOfRawData,
        bool(s.Characteristics & 0x20000000),
    )
    for s in pe.sections
]


def rva_to_off(rva):
    for n, va, vs, raw, rs, ex in secs:
        if va <= rva < va + max(vs, rs):
            d = rva - va
            if d < rs:
                return raw + d
    return None


def read_cstr(rva, limit=160):
    off = rva_to_off(rva)
    if off is None:
        return None
    end = data.find(b"\x00", off, off + limit)
    if end < 0:
        return None
    raw = data[off:end]
    if len(raw) < 2:
        return None
    printable = sum(1 for c in raw if 32 <= c < 127)
    if printable < len(raw) * 0.9:
        return None
    return raw.decode("latin-1")


def main():
    lo = int(sys.argv[1], 16)
    hi = int(sys.argv[2], 16)
    t = [s for s in secs if s[0] == ".text"][0]
    base, _, raw, size, _ = t[1], t[2], t[3], t[4], t[5]
    code = data[raw : raw + size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    hits = []
    for ins in md.disasm(code, base):
        if ins.id == 0 or not ins.operands:
            continue
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                tgt = ins.address + ins.size + op.mem.disp
                if lo <= tgt < hi:
                    hits.append((ins.address, tgt, read_cstr(tgt)))
    for a, tg, s in hits:
        print("0x%X -> 0x%X  %r" % (a, tg, s))
    print("total:", len(hits))


if __name__ == "__main__":
    main()
