import sys

p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
t = t.replace(
    "    kind_found = d[0x26]\n    found = d[0x27]",
    "    kind_found = d[0x26]\n"
    "    found = d[0x27]\n"
    "    matched = int.from_bytes(d[0x2c:0x30], 'little')\n"
    "    has_kind2 = d[0x3c]",
)
t = t.replace(
    '    print(f"last caption len={cap_len} sample={cap_sample!r} found={found} kind={kind_found}")',
    '    print(f"matched={matched} last caption len={cap_len} sample={cap_sample!r}")\n'
    '    print(f"found={found} kind={kind_found} has_kind2={has_kind2}")',
)
open(p, "w", encoding="utf-8", newline="").write(t)
print("ok", "matched = int.from_bytes" in t)
