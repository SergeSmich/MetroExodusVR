p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

if 'recognizer (c): name == "override_font_name"' in t:
    print("already")
    exit(0)

anchor = "    not_b = len(code)\n"
if anchor not in t:
    print("missing not_b")
    exit(1)

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
open(p, "w", encoding="utf-8", newline="").write(t)
print("rec_c inserted")
