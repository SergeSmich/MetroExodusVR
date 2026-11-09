import sys

p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

anchor = '    code += b"\\xff\\x40\\x00"  # inc dword ptr [rax]      (calls seen)\n'
if anchor not in t:
    print("ANCHOR MISSING")
    sys.exit(1)

snippet = r"""    code += b"\xff\x40\x00"  # inc dword ptr [rax]      (calls seen)

    # --- recognizers (A-0025 §3): name=="on_draw_item" / name startswith "item"
    code += b"\x48\x83\x7d\x08\x0c"  # cmp qword [rbp+8], 12
    ra1 = len(code)
    code += b"\x75\0"  # jne rec_b
    code += b"\x48\x8b\x45\x00"  # mov rax, [rbp]
    code += b"\x81\x38" + b"on_d"
    ra2 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x04" + b"raw_"
    ra3 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x08" + b"item"
    ra4 = len(code)
    code += b"\x75\0"
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\x48\x89\x99\x28\x19\0\0"  # mov [rcx+0x1928], rbx (list control)
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rdi+8] (value len)
    code += b"\x89\x91\x30\x19\0\0"  # mov [rcx+0x1930], edx
    code += b"\xff\x81\x44\x19\0\0"  # inc dword [rcx+0x1944] (count a)
    code += b"\x4c\x8b\x0f"  # mov r9, [rdi]
    code += b"\x41\xba\x10\0\0\0"  # mov r10d, 16
    code += b"\x4c\x39\xd2"  # cmp rdx, r10
    code += b"\x76\x03"  # jbe keep
    code += b"\x44\x89\xd2"  # mov edx, r10d
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    ra_loop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    ra6 = len(code)
    code += b"\x74\0"  # je rec_b
    code += b"\x47\x0f\xb6\x04\x19"  # movzx r8d, byte [r9+r11]
    code += b"\x46\x88\x84\x19\x48\x19\0\0"  # mov [rcx+r11+0x1948], r8b
    code += b"\x49\xff\xc3"  # inc r11
    ra7 = len(code)
    code += b"\xeb\0"  # jmp ra_loop

    rec_b = len(code)
    code += b"\x48\x83\x7d\x08\x04"  # cmp qword [rbp+8], 4
    rb1 = len(code)
    code += b"\x72\0"  # jb not_b
    code += b"\x48\x8b\x45\x00"  # mov rax, [rbp]
    code += b"\x81\x38" + b"item"
    rb2 = len(code)
    code += b"\x75\0"  # jne not_b
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\x48\x89\x99\x38\x19\0\0"  # mov [rcx+0x1938], rbx
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rbp+8] (name len)
    code += b"\x89\x91\x40\x19\0\0"  # mov [rcx+0x1940], edx
    code += b"\xff\x81\x34\x19\0\0"  # inc dword [rcx+0x1934] (count b)
    code += b"\x4c\x8b\x0f"  # mov r9, [rbp]
    code += b"\x41\xba\x10\0\0\0"  # mov r10d, 16
    code += b"\x4c\x39\xd2"  # cmp rdx, r10
    code += b"\x76\x03"  # jbe keep
    code += b"\x44\x89\xd2"  # mov edx, r10d
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    rb_loop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    rb4 = len(code)
    code += b"\x74\0"  # je not_b
    code += b"\x47\x0f\xb6\x04\x19"  # movzx r8d, byte [r9+r11]
    code += b"\x46\x88\x84\x19\x58\x19\0\0"  # mov [rcx+r11+0x1958], r8b
    code += b"\x49\xff\xc3"
    rb5 = len(code)
    code += b"\xeb\0"  # jmp rb_loop
    not_b = len(code)
"""

t = t.replace(anchor, snippet, 1)

# extend the short-branch patch list
old_tail = "        (agg3, agg_done),\n    ):"
new_tail = (
    "        (agg3, agg_done),\n"
    "        (ra1, rec_b),\n"
    "        (ra2, rec_b),\n"
    "        (ra3, rec_b),\n"
    "        (ra4, rec_b),\n"
    "        (ra6, rec_b),\n"
    "        (ra7, ra_loop),\n"
    "        (rb1, not_b),\n"
    "        (rb2, not_b),\n"
    "        (rb4, not_b),\n"
    "        (rb5, rb_loop),\n"
    "    ):"
)
if old_tail not in t:
    print("PATCH LIST MISSING")
    sys.exit(1)
t = t.replace(old_tail, new_tail, 1)

open(p, "w", encoding="utf-8", newline="").write(t)
print("snippet + patches inserted")
