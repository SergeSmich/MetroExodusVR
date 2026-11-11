from pathlib import Path

ROOT = Path(r"F:\Projects\MetroExodusVR")

needle = bytes.fromhex("48 49 63 44 47 01 3c 3f 37 3f 48 3f 3a 35")
for name in ("work/tmp-probe1.dll", "work/0.9.1/MetroExodusVR.dll.orig"):
    d = (ROOT / name).read_bytes()
    hits = []
    p = 0
    while True:
        p = d.find(needle, p)
        if p < 0:
            break
        hits.append(p)
        p += 1
    print(name, "hits", [hex(h) for h in hits][:10])


# US charmap as index -> codepoint
def load(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(int(line[2:], 16) if line.upper().startswith("U+") else int(line, 0))
    return out


us = load(ROOT / "ru" / "charmap_us.txt")
ru = load(ROOT / "ru" / "charmap.txt")
print("us", len(us), "ru", len(ru))
b = needle
print("ru-decode:", "".join(chr(ru[i]) if i < len(ru) else "?" for i in b))
print("us-decode:", "".join(chr(us[i]) if i < len(us) else "?" for i in b))
