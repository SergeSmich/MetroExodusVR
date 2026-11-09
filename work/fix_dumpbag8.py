import sys

p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
t = t.replace(
    "    first_q60 = int.from_bytes(d[0x1910:0x1918], 'little')",
    "    first_q60 = int.from_bytes(d[0x1910:0x1918], 'little')\n"
    "    vtable = int.from_bytes(d[0x1918:0x1920], 'little')\n"
    "    bag_bytes = int.from_bytes(d[0x1920:0x1924], 'little')",
)
t = t.replace(
    '          f"first_control={first_control:#x} first_q60={first_q60:#018x}")',
    '          f"first_control={first_control:#x} first_q60={first_q60:#018x}")\n'
    '    print(f"vtable={vtable:#x} bag_bytes={bag_bytes:#x}")',
)
open(p, "w", encoding="utf-8", newline="").write(t)
print("ok", "vtable" in t)
