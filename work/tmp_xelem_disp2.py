"""Narrow packed-ref consumers of [reg+disp]: require the standard resolution
idiom nearby (and r,0xffffff / mov r,[table+r*8] / shr r,0x18).

python work/tmp_xelem_disp2.py 0x60
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
print(f"instructions {len(insns)}; field +{disp:#x}")

reads = []
for j, b in enumerate(insns):
    if b.mnemonic not in ("mov", "movzx", "movsxd"):
        continue
    if not b.op_str.split(",")[0].strip().startswith(("e", "r")):
        continue
    for op in b.operands:
        if (
            op.type == X86_OP_MEM
            and op.mem.base
            and op.mem.disp == disp
            and op.size == 4
        ):
            reads.append(j)
            break

print(f"dword reads: {len(reads)}")
hits = []
for j in reads:
    ok_and = ok_tbl = ok_shr = False
    for k in range(j + 1, min(len(insns), j + 16)):
        q = insns[k]
        if q.mnemonic == "and" and "0xffffff" in q.op_str:
            ok_and = True
        if q.mnemonic == "shr" and "0x18" in q.op_str:
            ok_shr = True
        for op in q.operands:
            if op.type == X86_OP_MEM and op.mem.scale == 8:
                ok_tbl = True
        if q.mnemonic in ("ret",):
            break
    if ok_shr and (ok_and or ok_tbl):
        hits.append((insns[j].address, insns[j].mnemonic, insns[j].op_str))

print(f"packed-ref-like: {len(hits)}")
for a, mn, ops in hits:
    print(f"{a:#x}  {mn} {ops}")
