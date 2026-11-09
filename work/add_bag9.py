import sys

p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

anchor_b = "    not_b = len(code)\n"
if anchor_b not in t:
    print("ANCHOR not_b MISSING")
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
t = t.replace(anchor_b, rec_c, 1)

anchor_sample = """    code += b"\\xeb\\0"  # jmp nsloop
    nsdone = len(code)
"""
if anchor_sample not in t:
    print("ANCHOR nsdone MISSING")
    sys.exit(1)

fn_read = r"""    code += b"\xeb\0"  # jmp nsloop
    nsdone = len(code)

    # --- read the EXISTING font_name value before any write (A-0026 §3) ------
    code += b"\x4c\x8d\x15\0\0\0\0"  # lea r10, [rip+caption_lit]
    fixups.append((len(code) - 4, b"caption_lit"))
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
    code += b"\x43\x8a\x34\x18"  # mov sil, [r8+r11]
    code += b"\x43\x3a\x34\x1a"  # cmp sil, [r10+r11]
    fn6 = len(code)
    code += b"\x75\0"  # jne fn_next
    code += b"\x49\xff\xc3"
    fn7 = len(code)
    code += b"\xeb\0"  # jmp fn_cloop
    fn_match = len(code)
    code += b"\x4c\x8b\x42\x70"  # mov r8, [rdx+0x70] (value len)
    code += b"\x44\x89\x80\x88\x19\0\0"  # mov [rax+0x1988], r8d
    code += b"\x48\x83\x7a\x78\x0f"  # cmp qword [rdx+0x78], 0xf
    fn10 = len(code)
    code += b"\x76\0"  # jbe fn_vsso
    code += b"\x48\x8b\x4a\x60"  # mov rcx, [rdx+0x60]
    fn11 = len(code)
    code += b"\xeb\0"  # jmp fn_vcopy
    fn_vsso = len(code)
    code += b"\x48\x8d\x4a\x60"  # lea rcx, [rdx+0x60]
    fn_vcopy = len(code)
    code += b"\x41\xba\x08\0\0\0"  # mov r10d, 8
    code += b"\x4c\x39\xd2"  # cmp rdx, r10 -- BUG guard: use r8
    code += b"\x76\x03"
    code += b"\x45\x89\xd0"  # mov r8d, r10d
    code += b"\x48\x89\xc2"  # mov rdx, rax -- placeholder
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    fn_vloop = len(code)
    code += b"\x4c\x39\xc3"  # cmp r11, r8
    fn12 = len(code)
    code += b"\x73\0"  # jae fn_done
    code += b"\x44\x0f\xb6\x14\x19"  # movzx r10d, byte [rcx+r11]
    code += b"\x42\x88\x94\x18\x8c\x19\0\0"  # mov [rax+r11+0x198c], r10b
    code += b"\x49\xff\xc3"
    fn13 = len(code)
    code += b"\xeb\0"
    fn_next = len(code)
    code += b"\x48\x81\xc2\x98\0\0\0"  # add rdx, 0x98
    fn14 = len(code)
    code += b"\xeb\0"  # jmp fn_loop
    fn_done = len(code)
"""
t = t.replace(anchor_sample, fn_read, 1)

old_first = '    code += b"\\x48\\x89\\x99\\x08\\x19\\0\\0"  # mov [rcx+0x1908], rbx (first control)'
new_first = (
    '    code += b"\\x48\\x89\\x99\\x08\\x19\\0\\0"  # mov [rcx+0x1908], rbx (first control)\n'
    '    code += b"\\x48\\x8b\\x03"  # mov rax, [rbx]\n'
    '    code += b"\\x48\\x89\\x81\\x98\\x19\\0\\0"  # mov [rcx+0x1998], rax'
)
if old_first not in t:
    print("ANCHOR first control MISSING")
    sys.exit(1)
t = t.replace(old_first, new_first, 1)

old_tail = "        (rb5, rb_loop),\n    ):"
new_tail = (
    "        (rb5, rb_loop),\n"
    "        (rc1, not_c),\n"
    "        (rc2, not_c),\n"
    "        (rc3, not_c),\n"
    "        (rc4, not_c),\n"
    "        (rc5, not_c),\n"
    "        (rc6, not_c),\n"
    "        (rc7, not_c),\n"
    "        (rc8, rc_loop),\n"
    "        (fn1, fn_done),\n"
    "        (fn2, fn_next),\n"
    "        (fn3, fn_inline),\n"
    "        (fn4, fn_cmp),\n"
    "        (fn5, fn_match),\n"
    "        (fn6, fn_next),\n"
    "        (fn7, fn_cloop),\n"
    "        (fn10, fn_vsso),\n"
    "        (fn11, fn_vcopy),\n"
    "        (fn12, fn_done),\n"
    "        (fn13, fn_vloop),\n"
    "        (fn14, fn_loop),\n"
    "    ):"
)
if old_tail not in t:
    print("PATCH TAIL MISSING")
    sys.exit(1)
t = t.replace(old_tail, new_tail, 1)

old_data = '        (b"prop_name", prop + b"\\0"),'
new_data = (
    '        (b"prop_name", prop + b"\\0"),\n        (b"caption_lit", b"font_name\\0"),'
)
if old_data not in t:
    print("DATA ANCHOR MISSING")
    sys.exit(1)
t = t.replace(old_data, new_data, 1)

open(p, "w", encoding="utf-8", newline="").write(t)
print("bag9 injections done")
