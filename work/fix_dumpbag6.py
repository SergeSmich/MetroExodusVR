import sys

p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
t = t.replace(
    "    cap_len = int.from_bytes(d[0x38:0x3c], 'little')",
    "    cap_len = int.from_bytes(d[0x28:0x2c], 'little')",
)
t = t.replace(
    "    matched = int.from_bytes(d[0x2c:0x30], 'little')",
    "    matched = int.from_bytes(d[0x2c:0x30], 'little')",
)
t = t.replace("    has_kind2 = d[0x3c]", "    has_kind2 = d[0x23]")
t = t.replace(
    '    caller = int.from_bytes(d[0x28:0x30], "little")',
    '    caller = int.from_bytes(d[0x38:0x40], "little")',
)
t = t.replace(
    "    +0x2c last caption len, +0x30..0x40 last caption sample (16 bytes)\n"
    "    +0x40 qword [control+0x60], +0x25 gate [control+0xac]&1\n"
    "    +0x48 raw records (stride 0x98, up to 40)",
    "    +0x28 dword caption len, +0x2c dword matched, +0x30..0x38 sample (8)\n"
    "    +0x38 Q caller, +0x40 Q [control+0x60], +0x25 gate\n"
    "    +0x23 has_kind2, +0x26 body kind, +0x27 found\n"
    "    +0x48 raw records (stride 0x98, up to 40)",
)
open(p, "w", encoding="utf-8", newline="").write(t)
print("ok", "d[0x28:0x2c]" in t and "d[0x38:0x40]" in t and "d[0x23]" in t)
