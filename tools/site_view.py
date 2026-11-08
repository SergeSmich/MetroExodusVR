#!/usr/bin/env python3
"""Dump instructions around given RVAs of the mod DLL with RIP-target annotation."""

import sys, json
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

DLL = r"F:\Projects\MetroExodusVR\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
PE = json.load(
    open(r"F:\Projects\MetroExodusVR\work\pe_analysis.json", encoding="utf-8")
)
data = open(DLL, "rb").read()
sections = PE["sections"] if isinstance(PE, dict) and "sections" in PE else PE


def rva_to_off(rva):
    for s in sections:
        va, raw, rs = s["va"], s["raw"], s["rawsize"]
        if va <= rva < va + max(s["vsize"], rs):
            if rva - va >= rs:
                return None
            return raw + (rva - va)
    return None


def off_to_rva(off):
    for s in sections:
        if s["raw"] <= off < s["raw"] + s["rawsize"]:
            return s["va"] + (off - s["raw"])
    return None


def read_cstr(rva, maxlen=200):
    o = rva_to_off(rva)
    if o is None:
        return None
    e = data.find(b"\0", o, o + maxlen)
    if e < 0:
        return None
    try:
        return data[o:e].decode("utf-8", "replace")
    except Exception:
        return None


md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

addrs = [int(a, 16) for a in sys.argv[1:]]
for start in addrs:
    off = rva_to_off(start)
    print(f"\n=== site {start:#x} ===")
    n = 0
    for ins in md.disasm(data[off : off + 120], start):
        extra = ""
        if ins.id != 0:
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    tgt = ins.address + ins.size + op.mem.disp
                    if 0 <= op.mem.disp < 0x80000000:
                        s = read_cstr(tgt)
                        extra = f"  -> {tgt:#x}"
                        if s is not None:
                            extra += f" '{s}'"
                    else:
                        extra = f"  -> {tgt:#x}"
        print(
            f"  {ins.address:#08x}  {ins.bytes.hex():<20} {ins.mnemonic} {ins.op_str}{extra}"
        )
        n += 1
        if n >= 14:
            break
