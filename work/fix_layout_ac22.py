import sys

p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()

pairs = [
    (
        'code += b"\\x89\\x50\\x38"  # mov [rax+0x38], edx  (len at +0x38)',
        'code += b"\\x89\\x50\\x28"  # mov [rax+0x28], edx  (caption len)',
    ),
    (
        'code += b"\\xc6\\x40\\x3c\\x00"  # mov byte [rax+0x3c], 0 (has kind-2 = 0)',
        'code += b"\\xc6\\x40\\x23\\x00"  # mov byte [rax+0x23], 0 (has kind-2 = 0)',
    ),
    (
        'code += b"\\xc6\\x40\\x3c\\x01"  # mov byte [rax+0x3c], 1 (kind-2 header seen)',
        'code += b"\\xc6\\x40\\x23\\x01"  # mov byte [rax+0x23], 1 (kind-2 header seen)',
    ),
    (
        'code += b"\\x48\\x89\\x41\\x28"  # mov [rcx+0x28], rax',
        'code += b"\\x48\\x89\\x41\\x38"  # mov [rcx+0x38], rax (caller)',
    ),
]

for old, new in pairs:
    if old not in t:
        print("MISSING:", old)
    t = t.replace(old, new)

open(p, "w", encoding="utf-8", newline="").write(t)
print("len@28:", "[rax+0x28], edx" in t)
print("has@23:", "[rax+0x23]" in t)
print("caller@38:", "[rcx+0x38], rax" in t)
