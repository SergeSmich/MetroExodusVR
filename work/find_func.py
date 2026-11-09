"""Find the function start before an address by trying MSVC prologue patterns
and keeping the closest candidate whose linear disasm passes through addr.

python work/find_func.py 0xc47077
"""

import sys
from pathlib import Path

sys.path.insert(0, r"F:\Projects\MetroExodusVR\tools")
from apply_ru import PE  # noqa: E402
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

P = r"F:\SteamLibrary\steamapps\common\Metro Exodus\MetroExodus.exe"
data = Path(P).read_bytes()
pe = PE(data)

addr = int(sys.argv[1], 0)
LO = max(0x1000, addr - 0x1200)

PROLOGUES = [
    b"\x40\x55",  # push rbp
    b"\x48\x89\x5c\x24",  # mov [rsp+x], rbx
    b"\x48\x8b\xc4",  # mov rax, rsp
    b"\x55\x48\x8b\xec",  # push rbp; mov rbp, rsp
    b"\x48\x81\xec",  # sub rsp, imm32
    b"\x48\x83\xec",  # sub rsp, imm8
    b"\x41\x57",  # push r15
    b"\x4c\x89\x44\x24",  # mov [rsp+x], r8
]

md = Cs(CS_ARCH_X86, CS_MODE_64)


def passes(cand):
    off = pe.rva_to_off(cand)
    if off is None:
        return False
    blob = data[off : off + min(0x3000, 0x400000 - cand)]
    n = 0
    for ins in md.disasm(blob, cand):
        if ins.address == addr:
            return True
        if ins.address > addr or n > 1200:
            return False
        n += 1
    return False


cands = []
for pat in PROLOGUES:
    i = LO
    while True:
        j = data.find(pat, pe.rva_to_off(i), pe.rva_to_off(addr))
        if j < 0:
            break
        # map file offset back to rva by scanning sections
        rva = None
        for s in pe.sections:
            if s["raw"] <= j < s["raw"] + s["rawsize"]:
                rva = j - s["raw"] + s["va"]
                break
        if rva is not None and LO <= rva <= addr:
            cands.append(rva)
        i = (rva or i) + 1
        if i >= addr:
            break

cands = sorted(set(cands))
ok = [c for c in cands if passes(c)]
start = max(ok) if ok else None
print(f"target {addr:#x}: {len(cands)} prologue candidates, {len(ok)} pass")
print(f"start = {start:#x}" if start else "start not found")
