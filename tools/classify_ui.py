"""Bulk-classify xref instructions for UI strings.

Usage:  python tools/classify_ui.py [lo] [hi]
Prints per-string instruction kind and a summary, and writes work/classify.txt.
"""

import json
import sys
import collections

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

DLL = r"F:\Projects\MetroExodusVR\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
XREFS = r"F:\Projects\MetroExodusVR\work\xrefs.json"
OUT = r"F:\Projects\MetroExodusVR\work\classify.txt"

pe = pefile.PE(DLL, fast_load=True)
data = open(DLL, "rb").read()
secs = [
    (
        s.Name.rstrip(b"\x00").decode(),
        s.VirtualAddress,
        s.Misc_VirtualSize,
        s.PointerToRawData,
        s.SizeOfRawData,
    )
    for s in pe.sections
]


def off(r):
    for n, va, vs, raw, rs in secs:
        if va <= r < va + max(vs, rs):
            d = r - va
            if d < rs:
                return raw + d
    return None


A = json.load(open(XREFS, encoding="utf-8"))
S = {int(k): v for k, v in A["strings"].items()}
LEA = {int(k): v for k, v in A["lea"].items()}
PTR = {int(k): v for k, v in A.get("ptr", {}).items()}

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
md.skipdata = True


def kind(site):
    o = off(site)
    if o is None:
        return "nooff"
    for ins in md.disasm(data[o : o + 16], site):
        m = ins.mnemonic
        if m == "lea":
            return "lea"
        if m == "mov":
            ops = ins.op_str
            if "] ," in ops or ops.endswith("]") or "ptr [" in ops:
                return "movload"
            return "mov"
        return m
    return "undec"


def main():
    lo = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x49F650
    hi = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x4A0C38 + 0x40
    rows = []
    counter = collections.Counter()
    for va in sorted(S):
        if not (lo <= va < hi):
            continue
        kinds = []
        for e in LEA.get(va, []):
            kinds.append((e[0], kind(e[0]), "lea-bucket"))
        for e in PTR.get(va, []):
            kinds.append((e, "ptrslot", "ptr"))
        if not kinds:
            counter["none"] += 1
            rows.append((va, S[va], "none", []))
            continue
        desc = ",".join(sorted({k for _, k, _ in kinds}))
        counter[desc] += 1
        rows.append((va, S[va], desc, kinds))

    print("range 0x%X..0x%X  strings=%d" % (lo, hi, len(rows)))
    for k, c in counter.most_common():
        print("   %-20s %d" % (k, c))
    with open(OUT, "w", encoding="utf-8") as f:
        for va, t, desc, kinds in rows:
            f.write("0x%06X %-12s %r\n" % (va, desc, t))
            for site, k, src in kinds:
                f.write("        site 0x%X %s (%s)\n" % (site, k, src))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
