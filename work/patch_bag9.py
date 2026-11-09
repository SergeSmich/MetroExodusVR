import sys, struct

p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

# ---- 1) recognizer (c) after not_b ----
if 'recognizer (c): name == "override_font_name"' in t:
    print("rec_c already present")
else:
    anchor = "    not_b = len(code)\n"
    if anchor not in t:
        print("missing not_b anchor")
        sys.exit(1)
    rec_c = r"""    not_b = len(code)

    # --- recognizer (c): name == "override_font_name" (A-0026 §4) ------------
    code += b"\x48\x83\x7d\x08\x12"  # cmp qword [rbp+8], 18
    rc1 = len(code)
    code += b"\x75\0"  # jne not_c
    code += b"\x48\x8b\x45\x00"  # mov rax, [rbp]
    code += b"\x81\x38" + b"over"
    rc2 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x04" + b"ride"
    rc3 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x08" + b"_fon"
    rc4 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x0c" + b"t_na"
    rc5 = len(code)
    code += b"\x75\0"
    code += b"\x66\x81\x78\x10" + b"me"  # cmp word [rax+0x10], 'me'
    rc6 = len(code)
    code += b"\x75\0"
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\xff\x81\x68\x19\0\0"  # inc dword [rcx+0x1968] (count c)
    code += b"\x48\x89\x99\x70\x19\0\0"  # mov [rcx+0x1970], rbx
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rdi+8]
    code += b"\x89\x91\x6c\x19\0\0"  # mov [rcx+0x196c], edx
    code += b"\x4c\x8b\x0f"  # mov r9, [rdi]
    code += b"\x41\xba\x10\0\0\0"  # mov r10d, 16
    code += b"\x4c\x39\xd2"  # cmp rdx, r10
    code += b"\x76\x03"  # jbe keep
    code += b"\x44\x89\xd2"  # mov edx, r10d
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    rc_loop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    rc7 = len(code)
    code += b"\x74\0"  # je not_c
    code += b"\x47\x0f\xb6\x04\x19"  # movzx r8d, byte [r9+r11]
    code += b"\x46\x88\x84\x19\x78\x19\0\0"  # mov [rcx+r11+0x1978], r8b
    code += b"\x49\xff\xc3"
    rc8 = len(code)
    code += b"\xeb\0"  # jmp rc_loop
    not_c = len(code)
"""
    t = t.replace(anchor, rec_c, 1)
    t = t.replace(
        "        (rb5, rb_loop),\n    ):",
        "        (rb5, rb_loop),\n"
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
    print("rec_c added")

# ---- 2) font_name reader after scan_done, before setter setup ----
if "read the EXISTING font_name value" in t:
    print("fn_reader already present")
else:
    anchor2 = "    scan_done = len(code)\n\n    # --- set the font property on the same control ---------------------------\n"
    if anchor2 not in t:
        print("missing scan_done anchor")
        sys.exit(1)
    fn_reader = r"""    scan_done = len(code)

    # --- read the EXISTING font_name value before any write (A-0026 §3) ------
    # Scan the same bag for name "font_name" (9 bytes), capture value len+8B.
    # Preserves rbx/rbp/rdi; clobbers rax,rcx,rdx,r8-r11,rsi.
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fn_mfx = len(code) - 4
    fixups.append((fn_mfx, b"marker"))
    code += b"\x4c\x8d\x15\0\0\0\0"  # lea r10, [rip+font_name_lit]
    fixups.append((len(code) - 4, b"font_name_lit"))
    code += b"\x48\x8b\x53\x38"  # mov rdx, [rbx+0x38]
    code += b"\x4c\x8b\x4b\x40"  # mov r9, [rbx+0x40]
    fn_loop = len(code)
    code += b"\x4c\x39\xca"  # cmp rdx, r9
    fn1 = len(code)
    code += b"\x73\0"  # jae fn_done
    code += b"\x48\x83\x7a\x18\x09"  # cmp qword [rdx+0x18], 9
    fn2 = len(code)
    code += b"\x75\0"  # jne fn_next
    code += b"\x48\x83\x7a\x20\x0f"  # cmp qword [rdx+0x20], 0xf
    fn3 = len(code)
    code += b"\x76\0"  # jbe fn_inline
    code += b"\x4c\x8b\x42\x08"  # mov r8, [rdx+8]
    fn4 = len(code)
    code += b"\xeb\0"  # jmp fn_cmp
    fn_inline = len(code)
    code += b"\x4c\x8d\x42\x08"  # lea r8, [rdx+8]
    fn_cmp = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    fn_cloop = len(code)
    code += b"\x49\x83\xfb\x09"  # cmp r11, 9
    fn5 = len(code)
    code += b"\x73\0"  # jae fn_match
    code += b"\x43\x8a\x04\x18"  # mov al, [r8+r11]
    code += b"\x43\x3a\x04\x1a"  # cmp al, [r10+r11]
    fn6 = len(code)
    code += b"\x75\0"  # jne fn_next
    code += b"\x49\xff\xc3"
    fn7 = len(code)
    code += b"\xeb\0"  # jmp fn_cloop
    fn_match = len(code)
    # rdx = matching record, rcx = marker
    code += b"\x4c\x8b\x42\x70"  # mov r8, [rdx+0x70] (value len)
    code += b"\x44\x89\x81\x88\x19\0\0"  # mov [rcx+0x1988], r8d
    code += b"\x48\x83\x7a\x78\x0f"  # cmp qword [rdx+0x78], 0xf (val cap)
    fn8 = len(code)
    code += b"\x76\0"  # jbe fn_vsso
    code += b"\x48\x8b\x42\x60"  # mov rax, [rdx+0x60] (heap ptr)
    fn9 = len(code)
    code += b"\xeb\0"  # jmp fn_vcopy
    fn_vsso = len(code)
    code += b"\x48\x8d\x42\x60"  # lea rax, [rdx+0x60] (inline)
    fn_vcopy = len(code)
    # rax = value bytes ptr, r8 = value len, rcx = marker
    code += b"\x41\xba\x08\0\0\0"  # mov r10d, 8
    code += b"\x4d\x39\xc2"  # cmp r10, r8  (cap count at 8)
    fn10 = len(code)
    code += b"\x76\0"  # jbe fn_vcnt (8 <= len => copy 8)
    code += b"\x44\x89\xc2"  # mov edx, r8d (count = len)
    fn11 = len(code)
    code += b"\xeb\0"  # jmp fn_vgo
    fn_vcnt = len(code)
    code += b"\x41\xba\x08\0\0\0"  # mov r10d, 8
    code += b"\x44\x89\xd2"  # mov edx, r10d (count = 8)
    fn_vgo = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    fn_vloop = len(code)
    code += b"\x41\x39\xd3"  # cmp r11d, edx
    fn12 = len(code)
    code += b"\x73\0"  # jae fn_done
    code += b"\x46\x0f\xb6\x04\x18"  # movzx r8d, byte [rax+r11]
    code += b"\x46\x88\x84\x19\x8c\x19\0\0"  # mov [rcx+r11+0x198c], r8b
    code += b"\x49\xff\xc3"
    fn13 = len(code)
    code += b"\xeb\0"  # jmp fn_vloop
    fn_next = len(code)
    code += b"\x48\x81\xc2\x98\0\0\0"  # add rdx, 0x98
    fn14 = len(code)
    code += b"\xeb\0"  # jmp fn_loop
    fn_done = len(code)

    # --- set the font property on the same control ---------------------------
"""
    t = t.replace(anchor2, fn_reader, 1)
    t = t.replace(
        "        (sc10, scan_loop),\n    ):",
        "        (sc10, scan_loop),\n"
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
        "        (fn14, fn_loop),\n"
        "    ):",
        1,
    )
    print("fn_reader added")

# ---- 3) +0x1998 when first found control is recorded ----
if "0x1998" in t and "first found-control vtable" in t:
    print("1998 already present")
else:
    old = '    code += b"\x48\x89\x99\x08\x19\0\0"  # mov [rcx+0x1908], rbx (first control)'
    if old not in t:
        print("missing first-control anchor")
        sys.exit(1)
    new = (
        old + "\n"
        '    code += b"\x48\x8b\x03"  # mov rax, [rbx] (A-0026 §5)\n'
        '    code += b"\x48\x89\x81\x98\x19\0\0"  # mov [rcx+0x1998], rax'
    )
    t = t.replace(old, new, 1)
    print("1998 added")

# ---- 4) font_name_lit in data ----
if 'b"font_name_lit"' in t:
    print("font_name_lit data already")
else:
    oldd = '(b"prop_name", prop + b"\\0"),'
    if oldd not in t:
        print("missing data anchor")
        sys.exit(1)
    t = t.replace(oldd, oldd + '\n        (b"font_name_lit", b"font_name\\0"),', 1)
    print("font_name_lit data added")

open(p, "w", encoding="utf-8", newline="").write(t)
print("done")
