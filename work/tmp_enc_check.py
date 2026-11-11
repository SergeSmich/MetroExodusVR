import sys
from pathlib import Path

ROOT = Path(r"F:\Projects\MetroExodusVR")
charpath = ROOT / "ru" / "charmap.txt"

cps = []
for line in charpath.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    cps.append(int(line[2:], 16) if line.upper().startswith("U+") else int(line, 0))

rev = {}
for i, cp in enumerate(cps):
    if cp and cp not in rev:
        rev[cp] = i


def enc(s):
    out = bytearray()
    for ch in s:
        idx = rev[ord(ch)]
        if idx < 0xE0:
            out.append(idx)
        else:
            ci = (idx + 0xDE41) // 255
            b = idx + 0xDE41 - ci * 255
            out += bytes([ci, b])
    return bytes(out)


rows = []
for line in (
    (ROOT / "kit091" / "ru" / "strings-0.9.1.tsv")
    .read_text(encoding="utf-8")
    .splitlines()
):
    if not line or line.startswith("#"):
        continue
    p = line.split("\t")
    if len(p) >= 3:
        rows.append(p)

for want in ("TURN MODE", "SNAP TURN ANGLE", "VR HINTS", "BODY TURNING"):
    for p in rows:
        if p[1] == want:
            b = enc(p[2])
            print(f"{want!r} -> ru {p[2]!r}")
            print("  bytes ", b.hex(" "))
            print("  cp1251", b.decode("cp1251", "replace"))
            print("  latin1", b.decode("latin1"))
            print("  u16le ", b.decode("utf-16-le", "replace"))
