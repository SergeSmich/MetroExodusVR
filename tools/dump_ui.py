import json, io, sys

strings = json.load(
    open(r"F:\Projects\MetroExodusVR\work\strings_ascii.json", encoding="utf-8")
)
lo = 0x496000
hi = 0x4A6000
sel = [e for e in strings if lo <= e["off"] < hi]
with io.open(
    r"F:\Projects\MetroExodusVR\work\ui_range.txt", "w", encoding="utf-8", newline="\n"
) as f:
    for e in sel:
        f.write("0x%08X\t%s\n" % (e["off"], e["s"]))
print("lines", len(sel))
