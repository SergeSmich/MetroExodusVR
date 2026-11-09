import sys

p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
t = t.replace(
    "    has_kind2 = d[0x23]",
    "    has_kind2 = d[0x23]\n"
    "    found_any = int.from_bytes(d[0x1900:0x1904], 'little')\n"
    "    set_ok_any = int.from_bytes(d[0x1904:0x1908], 'little')\n"
    "    first_control = int.from_bytes(d[0x1908:0x1910], 'little')\n"
    "    first_q60 = int.from_bytes(d[0x1910:0x1918], 'little')",
)
t = t.replace(
    '    print(f"found={found} kind={kind_found} has_kind2={has_kind2}")',
    '    print(f"found={found} kind={kind_found} has_kind2={has_kind2}")\n'
    '    print(f"found_any={found_any} set_ok_any={set_ok_any} "\n'
    '          f"first_control={first_control:#x} first_q60={first_q60:#018x}")',
)
open(p, "w", encoding="utf-8", newline="").write(t)
print("ok", "found_any" in t)
