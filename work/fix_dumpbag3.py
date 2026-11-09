import sys

p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
t = t.replace("RAW_OFF = 0x40", "RAW_OFF = 0x48")
t = t.replace(
    "    res = d[0x24]\n",
    "    res = d[0x24]\n"
    "    gate = d[0x25]\n"
    "    q60 = int.from_bytes(d[0x40:0x48], 'little')\n",
)
t = t.replace(
    '    print(f"last caption len={cap_len} sample={cap_sample!r}")',
    '    print(f"last caption len={cap_len} sample={cap_sample!r}")\n'
    '    print(f"gate [c+0xac]&1={gate} qword [c+0x60]={q60:#018x} (hi32={q60 >> 32:#x})")',
)
t = t.replace(
    "    +0x2c last caption len, +0x30..0x40 last caption sample (16 bytes)",
    "    +0x2c last caption len, +0x30..0x40 last caption sample (16 bytes)\n"
    "    +0x40 qword [control+0x60], +0x25 gate [control+0xac]&1\n"
    "    +0x48 raw records (stride 0x98, up to 40)",
)
open(p, "w", encoding="utf-8", newline="").write(t)
print("dump_bag updated for +0x48 records")
