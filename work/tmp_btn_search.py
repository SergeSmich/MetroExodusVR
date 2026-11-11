import re

d = open("work/0.9.1/MetroExodusVR.dll.orig", "rb").read()
for label, pat in [
    ("btn_ ascii", b"btn_"),
    ("mevr_vr ascii", b"mevr_vr"),
    ("mevr ascii", b"mevr"),
    ("btn_ u16", "btn_".encode("utf-16-le")),
    ("mevr u16", "mevr".encode("utf-16-le")),
    ("vr_hints", b"vr_hints"),
]:
    hits = [m.start() for m in re.finditer(re.escape(pat), d)]
    print(label, len(hits), [hex(h) for h in hits[:8]])
    for h in hits[:6]:
        ctx = d[max(0, h - 24) : h + 40].split(b"\x00")
        print("   ", [c for c in ctx if c][:4])
