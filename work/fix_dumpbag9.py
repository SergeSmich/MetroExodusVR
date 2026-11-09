import sys

p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
t = t.replace(
    "    bag_bytes = int.from_bytes(d[0x1920:0x1924], 'little')",
    "    bag_bytes = int.from_bytes(d[0x1920:0x1924], 'little')\n"
    "    od_control = int.from_bytes(d[0x1928:0x1930], 'little')\n"
    "    od_vlen = int.from_bytes(d[0x1930:0x1934], 'little')\n"
    "    od_count = int.from_bytes(d[0x1944:0x1948], 'little')\n"
    "    od_val = d[0x1948:0x1958]\n"
    "    ib_count = int.from_bytes(d[0x1934:0x1938], 'little')\n"
    "    ib_control = int.from_bytes(d[0x1938:0x1940], 'little')\n"
    "    ib_nlen = int.from_bytes(d[0x1940:0x1944], 'little')\n"
    "    ib_name = d[0x1958:0x1968]",
)
t = t.replace(
    '    print(f"vtable={vtable:#x} bag_bytes={bag_bytes:#x}")',
    '    print(f"vtable={vtable:#x} bag_bytes={bag_bytes:#x}")\n'
    '    print(f"on_draw_item: count={od_count} control={od_control:#x} "\n'
    '          f"vlen={od_vlen} value={od_val!r}")\n'
    '    print(f"item*: count={ib_count} control={ib_control:#x} "\n'
    '          f"nlen={ib_nlen} name={ib_name!r}")',
)
open(p, "w", encoding="utf-8", newline="").write(t)
print("ok", "od_count" in t)
