"""Find packed-ref consumers of a field at a given displacement: a dword read
from [reg+disp] followed by `shr r64, 0x18` within a few instructions.

python work/tmp_xelem_disp.py 0x60 [0x6b0]
"""

import sys
from pathlib import Path

sys.path.insert(0, r"F:\Projects\MetroExodusVR\tools")
from apply_ru import PE  # noqa: E402
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

P = r"F:\SteamLibrary\steamapps\common\Metro Exodus\MetroExodus.exe"
data = Path(P).read_bytes()
pe = PE(data)
disp = int(sys.argv[1], 0)
text = next(s for s in pe.sections if s["name"] == ".text")
blob = data[text["raw"] : text["raw"] + text["rawsize"]]

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
md.skipdata = True
insns = list(md.disasm(blob, text["va"]))
print(f".text instructions: {len(insns)}; looking for dword [reg+{disp:#x}] + shr 0x18")

W = 16
hits = []
for i, ins in enumerate(insns):
    if ins.mnemonic != "shr" or "0x18" not in ins.op_str:
        continue
    for j in range(max(0, i - W), i):
        b = insns[j]
        if b.mnemonic not in ("mov", "movzx", "movsxd"):
            continue
        if not b.op_str.split(",")[0].strip().startswith(("e", "r")):
            continue
        for op in b.operands:
            if op.type != X86_OP_MEM or op.mem.base == 0 or op.mem.disp != disp:
                continue
            if op.size != 4:
                continue
            hits.append((b.address, b.mnemonic, b.op_str, ins.address))
            break
        else:
            continue
        break

print(f"hits: {len(hits)}")
for a, mn, ops, s in hits:
    print(f"{a:#x}  {mn} {ops}    shr @ {s:#x}")
