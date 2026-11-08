"""Disassemble a function/range with string and call annotations."""

import json, sys, bisect
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

DLL = r"F:\Projects\MetroExodusVR\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
pe = pefile.PE(DLL, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
data = open(DLL, "rb").read()
sections = [
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
    for name, va, vs, raw, rs, ex in sections:
        if va <= rva < va + max(vs, rs):
            d = rva - va
            if d < rs:
                return raw + d
    return None


A = json.load(open(r"F:\Projects\MetroExodusVR\work\xrefs.json", encoding="utf-8"))
strings = {int(k): v for k, v in A["strings"].items()}
sorted_s = sorted(strings)


def string_at(t):
    if t in strings:
        return strings[t]
    i = bisect.bisect_right(sorted_s, t) - 1
    if i >= 0:
        b = sorted_s[i]
        if b <= t < b + len(strings[b]):
            return "%s[+%d]" % (strings[b], t - b)
    return None


F = json.load(open(r"F:\Projects\MetroExodusVR\work\funcs.json", encoding="utf-8"))
funcs = [tuple(x) for x in F["funcs"]]
starts = [f[0] for f in funcs]
calls = {int(k): v for k, v in F["calls"].items()}
callers = {}
for tgt, sites in calls.items():
    for s in sites:
        callers.setdefault(s, []).append(tgt)


def containing(a):
    i = bisect.bisect_right(starts, a) - 1
    if i < 0:
        return None
    b, e, u = funcs[i]
    return (b, e) if b <= a < e else None


def disasm(start, end=None, annotate=True):
    if end is None:
        c = containing(start)
        end = c[1] if c else start + 0x400
    off = rva_to_off(start)
    code = data[off : off + (end - start)]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    for ins in md.disasm(code, start):
        note = ""
        if annotate and ins.id:
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    t = (ins.address + ins.size + op.mem.disp) & 0xFFFFFFFFFFFFFFFF
                    st = string_at(t)
                    if st:
                        note += "  ; %r" % st[:90]
                elif op.type == X86_OP_IMM:
                    v = op.imm & 0xFFFFFFFFFFFFFFFF
                    if v >= base + sections[0][1] and v < base + 0x20000000:
                        note += "  ; sub_%X" % (v - base)
                    elif v < 0x20000000 and v >= sections[0][1]:
                        note += "  ; sub_%X" % v
        if ins.id == 0:
            print(
                "  0x%X  .byte 0x%02x" % (ins.address, ins.bytes[0] if ins.bytes else 0)
            )
        else:
            print(
                "  0x%X  %-38s%s" % (ins.address, ins.mnemonic + " " + ins.op_str, note)
            )


if __name__ == "__main__":
    a = int(sys.argv[1], 16)
    b = int(sys.argv[2], 16) if len(sys.argv) > 2 else None
    print("func:", containing(a))
    disasm(a, b)
