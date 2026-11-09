p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

if "read the EXISTING font_name value" in t:
    print("already present")
    exit(0)

anchor2 = "    scan_done = len(code)\n\n    # --- set the font property on the same control ---------------------------\n"
if anchor2 not in t:
    print("missing scan_done anchor")
    i = t.find("scan_done = len(code)")
    print("scan_done at", i)
    if i >= 0:
        print(repr(t[i : i + 120]))
    exit(1)

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

# add fn patches after sc10
if "(fn1, fn_done)" not in t:
    anchor = "(sc10, scan_loop),"
    if anchor not in t:
        print("fn patch anchor missing")
        exit(1)
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

open(p, "w", encoding="utf-8", newline="").write(t)
print("fn_reader inserted")
