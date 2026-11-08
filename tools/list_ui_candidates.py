"""List likely user-facing UI strings from the mod DLL and their xref counts."""

import json
import re

import pefile

DLL = r"F:\Projects\MetroExodusVR\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
XREFS = r"F:\Projects\MetroExodusVR\work\xrefs.json"
OUT = r"F:\Projects\MetroExodusVR\work\ui_candidates.txt"

pe = pefile.PE(DLL, fast_load=True)
secs = {
    s.Name.rstrip(b"\x00").decode(): (
        s.VirtualAddress,
        s.VirtualAddress + s.Misc_VirtualSize,
    )
    for s in pe.sections
}
print(secs)

A = json.load(open(XREFS, encoding="utf-8"))
S = {int(k): v for k, v in A["strings"].items()}
L = {int(k): v for k, v in A["lea"].items()}
P = {int(k): v for k, v in A.get("ptr", {}).items()}
M = {int(k): v for k, v in A.get("mid", {}).items()}
I = {int(k): v for k, v in A.get("imm", {}).items()}

lo, hi = secs[".rdata"]
allowed = re.compile(r"^[A-Z0-9][A-Z0-9 .,:;!?()\[\]/+%&'\"-]*$")


def interesting(tl: str) -> bool:
    if not (2 <= len(tl) <= 64):
        return False
    if not allowed.match(tl):
        return False
    letters = [c for c in tl if c.isalpha()]
    if len(letters) < 2:
        return False
    up = sum(1 for c in letters if c.isupper()) / len(letters)
    if up < 0.9:
        return False
    if " " not in tl and len(tl) < 4:
        return False
    return True


rows = []
for va, t in sorted(S.items()):
    if not (lo <= va < hi):
        continue
    tl = t.strip()
    if not interesting(tl):
        continue
    rows.append(
        (
            va,
            tl,
            len(L.get(va, [])),
            len(P.get(va, [])),
            len(M.get(va, [])),
            len(I.get(va, [])),
        )
    )

print("candidates:", len(rows))
with open(OUT, "w", encoding="utf-8") as f:
    for va, tl, l, p, m, i in rows:
        f.write("0x%06X l=%d p=%d m=%d i=%d %s\n" % (va, l, p, m, i, tl))
for va, tl, l, p, m, i in rows:
    print("0x%06X l=%d p=%d m=%d i=%d %s" % (va, l, p, m, i, tl))
