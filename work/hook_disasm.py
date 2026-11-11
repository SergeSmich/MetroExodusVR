"""Disassemble the caption-font hook cave inside a built DLL to sanity-check it.

python work/hook_disasm.py build\\MetroExodusVR.bag6.dll 0xc27d90
"""

import sys
from pathlib import Path

sys.path.insert(0, r"F:\Projects\MetroExodusVR\tools")
from apply_ru import PE  # noqa: E402
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

P, RVA = sys.argv[1], int(sys.argv[2], 16)
data = Path(P).read_bytes()
pe = PE(data)
off = pe.rva_to_off(RVA)
print(f"{P} hook RVA {RVA:#x} -> file off {off:#x}")

md = Cs(CS_ARCH_X86, CS_MODE_64)
code = data[off : off + 0x400]
n = 0
for ins in md.disasm(code, RVA):
    print(f"{ins.address:#x}  {ins.mnemonic} {ins.op_str}")
    n += 1
    if ins.mnemonic == "ret" or n > 200:
        break
