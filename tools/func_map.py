"""Function map from .pdata + call graph helpers for MetroExodusVR.dll."""

import json, struct, bisect
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

DLL = r"F:\Projects\MetroExodusVR\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
XREFS = r"F:\Projects\MetroExodusVR\work\xrefs.json"

pe = pefile.PE(DLL)
data = open(DLL, "rb").read()
base = pe.OPTIONAL_HEADER.ImageBase

# ---- function table from .pdata ----
funcs = []
for s in pe.sections:
    if s.Name.rstrip(b"\x00") == b".pdata":
        raw = s.PointerToRawData
        n = s.Misc_VirtualSize // 12
        for i in range(n):
            beg, end, unw = struct.unpack_from("<III", data, raw + i * 12)
            if beg and end > beg:
                funcs.append((beg, end, unw))
        break
funcs.sort()
starts = [f[0] for f in funcs]
print("functions in .pdata:", len(funcs))


def containing(addr):
    i = bisect.bisect_right(starts, addr) - 1
    if i < 0:
        return None
    b, e, u = funcs[i]
    if b <= addr < e:
        return (b, e)
    return None


def name_of(addr):
    f = containing(addr)
    return f[0] if f else None


# ---- disassemble .text and collect calls ----
text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
code = data[text.PointerToRawData : text.PointerToRawData + text.SizeOfRawData]
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
md.skipdata = True
calls = {}  # target_rva -> [call_rva]
insn_func = {}  # call_rva -> func start
n = 0
for ins in md.disasm(code, text.VirtualAddress):
    if ins.id == 0:
        continue
    n += 1
    if ins.mnemonic == "call" and ins.operands and ins.operands[0].type == X86_OP_IMM:
        t = ins.operands[0].imm & 0xFFFFFFFFFFFFFFFF
        if t < base + 0x20000000:
            trva = t - base if t >= base else t
            calls.setdefault(trva, []).append(ins.address)
print("insns:", n, "call targets:", len(calls))
json.dump(
    {"funcs": funcs, "calls": {str(k): v for k, v in calls.items()}},
    open(r"F:\Projects\MetroExodusVR\work\funcs.json", "w"),
)

A = json.load(open(XREFS, encoding="utf-8"))
strings = {int(k): v for k, v in A["strings"].items()}
lea = {int(k): v for k, v in A["lea"].items()}


def find_string(text):
    return [va for va, t in strings.items() if t == text]


def func_of_insn(addr):
    return containing(addr)


def report(text):
    vas = find_string(text)
    print("\n=== %r ===" % text)
    for va in vas:
        for e in lea.get(va, []):
            ins_rva = e[0]
            print(
                "  xref insn 0x%X in func %s"
                % (ins_rva, tuple(hex(x) for x in (containing(ins_rva) or (0, 0))))
            )
            fs = containing(ins_rva)
            if fs:
                callers = calls.get(fs[0], [])
                print(
                    "    callers of func 0x%X: %s" % (fs[0], [hex(c) for c in callers])
                )


for t in [
    "utf8_to_wide get size error: ",
    "utf8_to_wide convert string error: ",
    "RegisterOption('{}'): {:.3f} ms",
    "the game has no option of that name",
]:
    report(t)

# also: callers of any function that contains a given string xref
