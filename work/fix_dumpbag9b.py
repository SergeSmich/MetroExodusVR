p = r"work\dump_bag.py"
t = open(p, encoding="utf-8").read()
if "of_count" not in t:
    t = t.replace(
        "    ib_name = d[0x1958:0x1968]",
        """    ib_name = d[0x1958:0x1968]
    of_count = int.from_bytes(d[0x1968:0x196c], 'little')
    of_vlen = int.from_bytes(d[0x196c:0x1970], 'little')
    of_control = int.from_bytes(d[0x1970:0x1978], 'little')
    of_val = d[0x1978:0x1988]
    curfn_len = int.from_bytes(d[0x1988:0x198c], 'little')
    curfn_val = d[0x198c:0x1994]
    first_vt = int.from_bytes(d[0x1998:0x19a0], 'little')""",
    )
    t = t.replace(
        '          f"nlen={ib_nlen} name={ib_name!r}")',
        """          f"nlen={ib_nlen} name={ib_name!r}")
    print(f"override_font_name(game, c): count={of_count} control={of_control:#x} "
          f"vlen={of_vlen} value={of_val!r}")
    print(f"current font_name: len={curfn_len} bytes={curfn_val!r}")
    print(f"first found-control vtable (+0x1998)={first_vt:#x}")""",
    )
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("dump_bag updated")
else:
    print("already")
