import json, sys

path = r"F:\Projects\MetroExodusVR\work\strings_ascii.json"
strings = json.load(open(path, encoding="utf-8"))

lo = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x496000
hi = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x4A6000

sel = [e for e in strings if lo <= e["off"] < hi]
print(f"strings in [{lo:#x},{hi:#x}): {len(sel)}")
for e in sel:
    print(f"0x{e['off']:08X}\t{e['s']}")
