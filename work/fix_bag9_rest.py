p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

# font_name_lit data
if 'b"font_name_lit"' not in t:
    oldd = '(b"prop_name", prop + b"\\0"),'
    if oldd not in t:
        print("missing data anchor")
    else:
        t = t.replace(oldd, oldd + '\n        (b"font_name_lit", b"font_name\\0"),', 1)
        print("font_name_lit added")
else:
    print("font_name_lit ok")

# 1998
if "first found-control vtable" not in t:
    old = r'    code += b"\x48\x89\x99\x08\x19\0\0"  # mov [rcx+0x1908], rbx (first control)'
    if old not in t:
        print("missing 1998 anchor")
        for i, l in enumerate(t.splitlines(), 1):
            if "1908" in l and "first control" in l:
                print("line", i, repr(l))
    else:
        new = (
            old
            + '\n    code += b"\\x48\\x8b\\x03"  # mov rax, [rbx] (A-0026 \xa75)\n    code += b"\\x48\\x89\\x81\\x98\\x19\\0\\0"  # mov [rcx+0x1998], rax'
        )
        t = t.replace(old, new, 1)
        print("1998 added")
else:
    print("1998 ok")

# rc patches
if "(rc1, not_c)" not in t:
    if "(rb5, rb_loop),\n    ):" in t:
        t = t.replace(
            "(rb5, rb_loop),\n    ):",
            "(rb5, rb_loop),\n"
            "        (rc1, not_c),\n"
            "        (rc2, not_c),\n"
            "        (rc3, not_c),\n"
            "        (rc4, not_c),\n"
            "        (rc5, not_c),\n"
            "        (rc6, not_c),\n"
            "        (rc7, not_c),\n"
            "        (rc8, rc_loop),\n"
            "    ):",
            1,
        )
        print("rc patches added")
    else:
        print("rc patch anchor missing")
        # try to find tail
        for i, l in enumerate(t.splitlines(), 1):
            if "rb5" in l and "rb_loop" in l:
                print("rb5 line", i, repr(l))
else:
    print("rc patches ok")

# fn patches
if "(fn1, fn_done)" not in t:
    anchor = "(sc10, scan_loop),"
    if anchor not in t:
        print("fn patch anchor missing")
    else:
        t = t.replace(
            anchor,
            anchor + "\n"
            "        (fn1, fn_done),\n"
            "        (fn2, fn_next),\n"
            "        (fn3, fn_inline),\n"
            "        (fn4, fn_cmp),\n"
            "        (fn5, fn_match),\n"
            "        (fn6, fn_next),\n"
            "        (fn7, fn_cloop),\n"
            "        (fn8, fn_vsso),\n"
            "        (fn9, fn_vcopy),\n"
            "        (fn10, fn_vcnt),\n"
            "        (fn11, fn_vgo),\n"
            "        (fn12, fn_done),\n"
            "        (fn13, fn_vloop),\n"
            "        (fn14, fn_loop),",
            1,
        )
        print("fn patches added")
else:
    print("fn patches ok")

open(p, "w", encoding="utf-8", newline="").write(t)
print("saved")
