#!/usr/bin/env python3
"""Detailed per-site dump of inline string construction (writes UTF-8)."""

import re, json, io
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

ROOT = r"F:\Projects\MetroExodusVR"
DLL = ROOT + r"\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
PE = json.load(open(ROOT + r"\work\pe_analysis.json", encoding="utf-8"))
data = open(DLL, "rb").read()
sections = PE["sections"]


def rva_to_off(rva):
    for s in sections:
        if s["va"] <= rva < s["va"] + max(s["vsize"], s["rawsize"]):
            d = rva - s["va"]
            return None if d >= s["rawsize"] else s["raw"] + d
    return None


def read_cstr(rva, maxlen=120):
    o = rva_to_off(rva)
    if o is None:
        return None
    e = data.find(b"\0", o, o + maxlen)
    if e < 0:
        return None
    return data[o:e].decode("latin-1")


ID = re.compile(r"^(mevr_|btn_|m3_|wpn_)")
LOW = re.compile(r"^[a-z0-9_]+$")
FMT = re.compile(r"^[^A-Za-zА-Яа-я]*$|^\{[^}]*\}[%PX0-9.:]*$")


def parse_sites():
    out = []
    for ln in open(ROOT + r"\work\caption_sites.txt", encoding="utf-8"):
        m = re.match(r"^0x([0-9A-Fa-f]+)\s+(\S+)\s+(.*?)\s+\|\s+(.*)$", ln.rstrip("\n"))
        if not m:
            continue
        a = int(m.group(1), 16)
        s = m.group(3)
        if s.startswith("'"):
            s = s[1:-1]
        if ID.match(s) or LOW.match(s) or FMT.match(s):
            continue
        for part in m.group(4).split():
            if ":" not in part:
                continue
            ad, k = part.split(":", 1)
            ad = int(ad, 16)
            if k != "lea" and 0xB0000 <= ad < 0xC0000:
                out.append((ad, k, a, s))
    return out


md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

buf = io.StringIO()
for site, kind, saddr, s in parse_sites():
    buf.write(
        f"\n########## {site:#x} {kind} -> {saddr:#x} {s!r} (len {len(s)}) ##########\n"
    )
    # find function start: search .pdata? just start 0x90 before, skip mid-instruction by using
    # known function starts from disasm: dump from site-0x60 but mark
    start = site - 0x60
    off = rva_to_off(start)
    n = 0
    for ins in md.disasm(data[off : off + 0x160], start):
        extra = ""
        if ins.id != 0:
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    tgt = ins.address + ins.size + op.mem.disp
                    extra += f"  -> {tgt:#x}"
                    cs = read_cstr(tgt)
                    if cs is not None:
                        extra += f" {cs!r}"
        mark = "  <<<< SITE" if ins.address == site else ""
        if ins.address < site - 0x50:
            pass
        buf.write(
            f"  {ins.address:#08x}  {ins.bytes.hex():<26} {ins.mnemonic} {ins.op_str}{extra}{mark}\n"
        )
        n += 1
        if n >= 46:
            break

open(ROOT + r"\work\inline_plan.txt", "w", encoding="utf-8").write(buf.getvalue())
print("wrote", len(buf.getvalue()), "bytes")
