import sys

p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
t = t.replace(
    "    calls, caption, res = d[0], d[1], d[2]",
    "    calls = int.from_bytes(d[0:4], 'little')\n"
    "    caption = int.from_bytes(d[4:8], 'little')\n"
    "    res = d[0x24]\n"
    "    cap_len = int.from_bytes(d[0x2c:0x30], 'little')\n"
    "    cap_sample = d[0x30:0x40]",
)
t = t.replace(
    '    print(f"calls={calls} caption={caption} set_ok={res}")',
    '    print(f"calls={calls} caption={caption} set_ok={res}")\n'
    '    print(f"last caption len={cap_len} sample={cap_sample!r}")',
)
t = t.replace(
    "    +0x00 calls seen, +0x01 caption matches, +0x02 result of the nested set",
    "    +0x00 calls dword, +0x04 caption matches dword, +0x24 result of the set\n"
    "    +0x2c last caption len, +0x30..0x40 last caption sample (16 bytes)",
)
open(p, "w", encoding="utf-8", newline="").write(t)
print("dump_bag ok")

for p in (r"work\probe_control_fields.py", r"work\probe_glyph.py"):
    t = open(p, encoding="utf-8").read()
    t = t.replace(
        'print(f"calls={m[0]} caption={m[1]} set_ok={m[2]} control={control:#x}")',
        "print(f\"calls={int.from_bytes(m[0:4], 'little')} "
        "caption={int.from_bytes(m[4:8], 'little')} set_ok={m[0x24]} "
        'control={control:#x}")',
    )
    t = t.replace(
        "calls, cap, set_ok = m[0], m[1], m[2]",
        "calls = int.from_bytes(m[0:4], 'little')\n"
        "cap = int.from_bytes(m[4:8], 'little')\n"
        "set_ok = m[0x24]",
    )
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("ok", p)
