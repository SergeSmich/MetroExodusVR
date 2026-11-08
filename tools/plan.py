#!/usr/bin/env python3
"""Build a translation/layout plan: strings, sites, inline chunk structure."""

import re, json, io, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

ROOT = r"F:\Projects\MetroExodusVR"
DLL = ROOT + r"\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
PE = json.load(open(ROOT + r"\work\pe_analysis.json", encoding="utf-8"))
data = open(DLL, "rb").read()
sections = PE["sections"]
IMAGE_BASE = PE["image_base"]

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

FUNCS = json.load(open(ROOT + r"\work\funcs.json", encoding="utf-8"))["funcs"]


def func_start(rva):
    best = 0x1000
    for a, b, _ in FUNCS:
        if a <= rva < b:
            return a
        if a <= rva:
            best = a
    return best


def rva_to_off(rva):
    for s in sections:
        end = s["va"] + max(s["vsize"], s["rawsize"])
        if s["va"] <= rva < end:
            d = rva - s["va"]
            return None if d >= s["rawsize"] else s["raw"] + d
    return None


def read_cstr(rva, maxlen=200):
    o = rva_to_off(rva)
    if o is None:
        return None
    e = data.find(b"\0", o, o + maxlen)
    if e < 0:
        return None
    return data[o:e].decode("latin-1")


ID = re.compile(r"^(mevr_|btn_|m3_|wpn_)")
LOW = re.compile(r"^[a-z0-9_]+$")
FMT = re.compile(r"^[^A-Za-z\u0410-\u044f]*$|^\{[^}]*\}[%PX0-9.:]*$")


def is_display(s):
    return not (ID.match(s) or LOW.match(s) or FMT.match(s))


def parse_caption_sites():
    out = []
    for ln in open(ROOT + r"\work\caption_sites.txt", encoding="utf-8"):
        m = re.match(r"^0x([0-9A-Fa-f]+)\s+(\S+)\s+(.*?)\s+\|\s+(.*)$", ln.rstrip("\n"))
        if not m:
            continue
        addr = int(m.group(1), 16)
        s = m.group(3)
        if s.startswith("'") and s.endswith("'"):
            s = s[1:-1]
        sites = []
        for part in m.group(4).split():
            if ":" not in part:
                continue
            a, k = part.split(":", 1)
            sites.append((int(a, 16), k))
        out.append({"addr": addr, "text": s, "sites": sites})
    return out


def disasm_window(lo, size):
    off = rva_to_off(lo)
    return list(md.disasm(data[off : off + size], lo))


def analyze_inline(entry):
    """Return chunk list [(insn_addr, width, str_offset, dst_desc)] and len-const addr."""
    addr = entry["addr"]
    orig_len = len(entry["text"])
    hi = addr + orig_len
    inline_sites = [s for s, k in entry["sites"] if k != "lea"]
    res = []
    for site in inline_sites:
        lo = func_start(site)
        off = rva_to_off(lo)
        ins = list(md.disasm(data[off : off + (site - lo) + 0x90], lo))
        # index of first instruction at/after site
        idx = None
        for i, x in enumerate(ins):
            if x.address == site:
                idx = i
                break
        if idx is None:
            res.append({"site": site, "error": "site not at instruction boundary"})
            continue
        chunks = []
        for i, x in enumerate(ins):
            if x.id == 0:
                continue
            for op in x.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    tgt = x.address + x.size + op.mem.disp
                    if addr <= tgt < hi or tgt == addr:
                        width = {1: 1, 2: 2, 4: 4, 8: 8}.get(op.size, 0)
                        chunks.append(
                            {
                                "insn": x.address,
                                "target": tgt,
                                "str_off": tgt - addr,
                                "width": width,
                                "disp_off": x.address + x.size - 4,
                                "desc": f"{x.mnemonic} {x.op_str}",
                                "delta_to_site": site - x.address,
                            }
                        )
        # find length setter: nearest preceding 'mov qword ptr [..], imm' with imm == orig_len
        len_const = None
        cap_const = None
        for x in reversed(ins[: idx + 1]):
            if x.mnemonic != "mov" or len(x.operands) != 2:
                continue
            if x.operands[1].type != 2:  # X86_OP_IMM
                continue
            imm = x.operands[1].imm
            if len_const is None and imm == orig_len and x.operands[0].size == 8:
                len_const = {
                    "insn": x.address,
                    "imm": imm,
                    "desc": f"{x.mnemonic} {x.op_str}",
                    "imm_off": x.address + x.size - 4,
                }
            elif cap_const is None and imm == 0xF and x.operands[0].size == 8:
                cap_const = {
                    "insn": x.address,
                    "imm": imm,
                    "desc": f"{x.mnemonic} {x.op_str}",
                }
        res.append(
            {
                "site": site,
                "chunks": chunks,
                "len_const": len_const,
                "cap_const": cap_const,
            }
        )
    return res


def main():
    caps = [c for c in parse_caption_sites() if is_display(c["text"])]
    plan = []
    for c in caps:
        e = {
            "addr": c["addr"],
            "text": c["text"],
            "orig_len": len(c["text"]),
            "sites": c["sites"],
        }
        if any(k != "lea" for _, k in c["sites"]):
            e["inline"] = analyze_inline(c)
        plan.append(e)
    json.dump(
        plan,
        open(ROOT + r"\work\plan.json", "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )

    buf = io.StringIO()
    for e in plan:
        if "inline" not in e:
            continue
        buf.write(f"\n=== {e['addr']:#x} {e['text']!r} len={e['orig_len']}\n")
        for blk in e["inline"]:
            buf.write(f"  site {blk['site']:#x}\n")
            if "error" in blk:
                buf.write(f"    ERROR {blk['error']}\n")
                continue
            tot = 0
            for ch in blk["chunks"]:
                buf.write(
                    f"    +{ch['str_off']:#04x} w={ch['width']} @{ch['insn']:#x} d={ch['delta_to_site']:#x} {ch['desc']}\n"
                )
                tot = max(tot, ch["str_off"] + ch["width"])
            buf.write(
                f"    total={tot} lenconst={blk['len_const']} cap={blk['cap_const']}\n"
            )
    open(ROOT + r"\work\inline_summary.txt", "w", encoding="utf-8").write(
        buf.getvalue()
    )
    print(buf.getvalue())
    print(
        "entries:", len(plan), "inline strings:", sum(1 for e in plan if "inline" in e)
    )


if __name__ == "__main__":
    main()
