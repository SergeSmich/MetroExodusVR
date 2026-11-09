import sys

p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

old = '    code += b"\\x48\\x8b\\x84\\x24\\x88\\0\\0\\0"  # mov rax, [rsp+0x88]\n    code += b"\\x48\\x89\\x41\\x38"  # mov [rcx+0x38], rax (caller)'
new = (
    '    code += b"\\x48\\x8b\\x84\\x24\\x88\\0\\0\\0"  # mov rax, [rsp+0x88]\n'
    '    code += b"\\x48\\x89\\x41\\x38"  # mov [rcx+0x38], rax (caller)\n'
    "\n"
    "    # --- aggregate counters across matched controls (tail of the marker) --\n"
    '    code += b"\\x80\\x79\\x27\\x00"  # cmp byte [rcx+0x27], 0 (found?)\n'
    "    agg1 = len(code)\n"
    '    code += b"\\x74\\0"  # je agg_done\n'
    '    code += b"\\xff\\x81\\x00\\x19\\0\\0"  # inc dword [rcx+0x1900] (found_any)\n'
    '    code += b"\\x80\\x79\\x24\\x00"  # cmp byte [rcx+0x24], 0 (set ok?)\n'
    "    agg2 = len(code)\n"
    '    code += b"\\x74\\0"  # je agg_done\n'
    '    code += b"\\xff\\x81\\x04\\x19\\0\\0"  # inc dword [rcx+0x1904] (set_ok_any)\n'
    '    code += b"\\x48\\x83\\xb9\\x08\\x19\\0\\0\\x00"  # cmp qword [rcx+0x1908], 0\n'
    "    agg3 = len(code)\n"
    '    code += b"\\x75\\0"  # jne agg_done (keep first)\n'
    '    code += b"\\x48\\x89\\x99\\x08\\x19\\0\\0"  # mov [rcx+0x1908], rbx (first control)\n'
    '    code += b"\\x48\\x8b\\x43\\x60"  # mov rax, [rbx+0x60]\n'
    '    code += b"\\x48\\x89\\x81\\x10\\x19\\0\\0"  # mov [rcx+0x1910], rax (its q60)\n'
    "    agg_done = len(code)"
)

if old not in t:
    print("PATTERN MISSING")
else:
    t = t.replace(old, new)
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("aggregate counters added; agg1/agg2/agg3 branches need patching")
