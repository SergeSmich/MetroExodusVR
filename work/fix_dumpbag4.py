import sys

p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
t = t.replace(
    "    cap_len = int.from_bytes(d[0x2c:0x30], 'little')\n    cap_sample = d[0x30:0x40]",
    "    cap_len = int.from_bytes(d[0x38:0x3c], 'little')\n"
    "    cap_sample = d[0x30:0x38]\n"
    "    kind_found = d[0x26]\n"
    "    found = d[0x27]",
)
t = t.replace(
    '    print(f"last caption len={cap_len} sample={cap_sample!r}")',
    '    print(f"last caption len={cap_len} sample={cap_sample!r} found={found} kind={kind_found}")',
)
open(p, "w", encoding="utf-8", newline="").write(t)
print("ok", "d[0x38:0x3c]" in t)
