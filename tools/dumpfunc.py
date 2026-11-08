import json, sys
from capstone import *
from capstone.x86 import *

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402
re_paths.require(str(re_paths.DLL))

ROOT = str(re_paths.ROOT)
DLL = str(re_paths.DLL)
PE = json.load(open(str(re_paths.PE_ANALYSIS), encoding="utf-8"))
FUNCS = json.load(open(str(re_paths.FUNCS), encoding="utf-8"))["funcs"]
data = open(DLL, "rb").read()


def off(r):
    for s in PE["sections"]:
        if s["va"] <= r < s["va"] + max(s["vsize"], s["rawsize"]):
            d = r - s["va"]
            return None if d >= s["rawsize"] else s["raw"] + d


def func_of(rva):
    for a, b, _ in FUNCS:
        if a <= rva < b:
            return a, b
    return rva, rva + 0x400


md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

lo, hi = func_of(int(sys.argv[1], 16))
o = off(lo)
if len(sys.argv) > 2:
    hi = min(hi, int(sys.argv[2], 16))
print(f"func {lo:#x}..{hi:#x}")
for i in md.disasm(data[o : off(hi)], lo):
    ex = ""
    for op in i.operands:
        if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
            t = i.address + i.size + op.mem.disp
            ex = f" -> {t:#x}"
            oo = off(t)
            if oo is not None:
                e = data.find(b"\0", oo, oo + 80)
                if e > 0:
                    try:
                        ex += " " + repr(data[oo:e].decode("latin-1"))
                    except Exception:
                        pass
        elif op.type == X86_OP_IMM and op.size == 8 and op.imm > 0x1000:
            ex += f" imm={op.imm:#x}"
    print(f"{i.address:#08x} {i.bytes.hex():<26} {i.mnemonic} {i.op_str}{ex}")
