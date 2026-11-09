import sys

p = r"tools\apply_ru.py"
t = open(p, encoding="utf-8").read()
old = 'code += b"\\x0f\\xb6\\x43\\xac"  # movzx eax, byte [rbx+0xac]'
new = 'code += b"\\x0f\\xb6\\x83\\xac\\0\\0\\0"  # movzx eax, byte [rbx+0xac] (disp32!)'
if old not in t:
    print("PATTERN MISSING")
else:
    t = t.replace(old, new)
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("gate disp32 patched")
