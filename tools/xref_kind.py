"""Classify xref instructions per string: real lea vs inline mov loads."""

import json
import sys

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402
re_paths.require(str(re_paths.DLL), re_paths.XREFS, re_paths.FUNCS)


DLL = str(re_paths.DLL)
XREFS = str(re_paths.XREFS)
FUNCS = str(re_paths.FUNCS)

pe = pefile.PE(DLL, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
data = open(DLL, "rb").read()

secs = []
for s in pe.sections:
    secs.append(
        (
            s.Name.rstrip(b"\x00").decode(),
            s.VirtualAddress,
            s.Misc_VirtualSize,
            s.PointerToRawData,
            s.SizeOfRawData,
        )
    )


def rva_to_off(rva):
    for name, va, vs, raw, rs in secs:
        if va <= rva < va + max(vs, rs):
            d = rva - va
            if d < rs:
                return raw + d
    return None


def sec_of(rva):
    for name, va, vs, raw, rs in secs:
        if va <= rva < va + max(vs, rs):
            return name
    return None


A = json.load(open(XREFS, encoding="utf-8"))
S = {int(k): v for k, v in A["strings"].items()}
LEA = {int(k): v for k, v in A["lea"].items()}
PTR = {int(k): v for k, v in A["ptr"].items()}

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
md.skipdata = True


def insn_at(rva):
    o = rva_to_off(rva)
    if o is None:
        return None
    # decode a small window before to be safe, but we know exact instruction start
    for ins in md.disasm(data[o : o + 16], rva):
        return ins
    return None


def classify(string_rva):
    """Return list of (site_rva, kind, mnemonic, op_str)."""
    res = []
    sites = []
    for e in LEA.get(string_rva, []):
        sites.append(e[0])
    for e in PTR.get(string_rva, []):
        sites.append(e[0])
    for site in sorted(set(sites)):
        ins = insn_at(site)
        if ins is None:
            res.append((site, "unknown", "?", "?"))
            continue
        if ins.mnemonic == "lea":
            kind = "lea"
        elif ins.mnemonic == "mov":
            kind = "mov-load"
        else:
            kind = ins.mnemonic
        res.append((site, kind, ins.mnemonic, ins.op_str))
    return res


if __name__ == "__main__":
    F = json.load(open(FUNCS, encoding="utf-8"))
    calls = {int(k): v for k, v in F["calls"].items()}
    for target in [0x312CD0, 0x311490, 0x297640]:
        print("callers of 0x%X: %s" % (target, [hex(c) for c in calls.get(target, [])]))
    print()
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            va = int(arg, 16)
            print("=== 0x%X %r ===" % (va, S.get(va)))
            for site, kind, mn, ops in classify(va):
                print("   site 0x%X  %-8s %s %s" % (site, kind, mn, ops))
