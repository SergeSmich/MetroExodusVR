import sys

p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

# 1. Remove len/sample writes from the pre-filter block (they describe any call).
old_pre = """    code += b"\\xff\\x40\\x04"  # inc dword ptr [rax+4]    (caption matches)
    code += b"\\x48\\x8b\\x57\\x08"  # mov rdx, [rdi+8]     (caption len)
    code += b"\\x89\\x50\\x28"  # mov [rax+0x28], edx  (caption len)
    code += b"\\x4c\\x8b\\x0f"  # mov r9, [rdi]        (caption bytes)
    code += b"\\x41\\xba\\x08\\0\\0\\0"  # mov r10d, 8
    code += b"\\x4c\\x39\\xd2"  # cmp rdx, r10
    ncclamp = len(code)
    code += b"\\x76\\x03"  # jbe keep (count stays rdx)
    code += b"\\x44\\x89\\xd2"  # mov edx, r10d (count = 8)
    code += b"\\x45\\x33\\xdb"  # xor r11d, r11d
    nsloop = len(code)
    code += b"\\x4c\\x39\\xda"  # cmp rdx, r11
    nb1 = len(code)
    code += b"\\x74\\0"  # je sample done
    code += b"\\x47\\x0f\\xb6\\x04\\x19"  # movzx r8d, byte [r9+r11]
    code += b"\\x46\\x88\\x44\\x18\\x30"  # mov [rax+r11+0x30], r8b (sample)
    code += b"\\x49\\xff\\xc3"  # inc r11
    nb2 = len(code)
    code += b"\\xeb\\0"  # jmp nsloop
    nsdone = len(code)
"""
new_pre = """    code += b"\\xff\\x40\\x04"  # inc dword ptr [rax+4]    (caption matches)
"""
if old_pre not in t:
    print("PRE BLOCK MISSING")
else:
    t = t.replace(old_pre, new_pre)

# 2. Add the same block inside the hit branch, after the matched counter.
old_hit = """    code += b"\\xff\\x40\\x2c"  # inc dword ptr [rax+0x2c] (matched counter)
"""
new_hit = """    code += b"\\xff\\x40\\x2c"  # inc dword ptr [rax+0x2c] (matched counter)
    # len + sample describe THIS matched call (A-0024 §1)
    code += b"\\x48\\x8b\\x57\\x08"  # mov rdx, [rdi+8]     (caption len)
    code += b"\\x89\\x50\\x28"  # mov [rax+0x28], edx  (caption len)
    code += b"\\x4c\\x8b\\x0f"  # mov r9, [rdi]        (caption bytes)
    code += b"\\x41\\xba\\x08\\0\\0\\0"  # mov r10d, 8
    code += b"\\x4c\\x39\\xd2"  # cmp rdx, r10
    ncclamp = len(code)
    code += b"\\x76\\x03"  # jbe keep (count stays rdx)
    code += b"\\x44\\x89\\xd2"  # mov edx, r10d (count = 8)
    code += b"\\x45\\x33\\xdb"  # xor r11d, r11d
    nsloop = len(code)
    code += b"\\x4c\\x39\\xda"  # cmp rdx, r11
    nb1 = len(code)
    code += b"\\x74\\0"  # je sample done
    code += b"\\x47\\x0f\\xb6\\x04\\x19"  # movzx r8d, byte [r9+r11]
    code += b"\\x46\\x88\\x44\\x18\\x30"  # mov [rax+r11+0x30], r8b (sample)
    code += b"\\x49\\xff\\xc3"  # inc r11
    nb2 = len(code)
    code += b"\\xeb\\0"  # jmp nsloop
    nsdone = len(code)
"""
if old_hit not in t:
    print("HIT BLOCK MISSING")
else:
    t = t.replace(old_hit, new_hit)

# 3. class identity: vtable qword + bag byte size, after the caller store.
old_ctrl = """    code += b"\\x48\\x8b\\x84\\x24\\x88\\0\\0\\0"  # mov rax, [rsp+0x88]
    code += b"\\x48\\x89\\x41\\x38"  # mov [rcx+0x38], rax (caller)
"""
new_ctrl = """    code += b"\\x48\\x8b\\x84\\x24\\x88\\0\\0\\0"  # mov rax, [rsp+0x88]
    code += b"\\x48\\x89\\x41\\x38"  # mov [rcx+0x38], rax (caller)
    # class identity (A-0024 §5): vtable qword + bag byte size
    code += b"\\x48\\x8b\\x03"  # mov rax, [rbx] (vtable ptr)
    code += b"\\x48\\x89\\x81\\x18\\x19\\0\\0"  # mov [rcx+0x1918], rax
    code += b"\\x48\\x8b\\x41\\x18"  # mov rax, [rcx+0x18] (bag end)
    code += b"\\x48\\x2b\\x41\\x10"  # sub rax, [rcx+0x10] (begin)
    code += b"\\x89\\x81\\x20\\x19\\0\\0"  # mov [rcx+0x1920], eax (bag bytes)
"""
if old_ctrl not in t:
    print("CTRL BLOCK MISSING")
else:
    t = t.replace(old_ctrl, new_ctrl)

open(p, "w", encoding="utf-8", newline="").write(t)
print("done")
