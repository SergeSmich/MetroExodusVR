"""Correct xref analysis for MetroExodusVR.dll.

Outputs work/xrefs.json with:
 - strings: rva -> text
 - lea:    rva -> [(insn_rva, mnemonic, op_str, target_rva)]
 - imm:    rva -> [...]
 - ptr:    rva -> [slot_rva]
 - mid:    target_rva -> [(insn_rva, op_str, parent_rva, parent_text, offset)]
 - relocs: set of rva that have a base relocation
"""

import json, struct
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP

DLL = r"F:\Projects\MetroExodusVR\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
OUT = r"F:\Projects\MetroExodusVR\work\xrefs.json"

pe = pefile.PE(DLL, fast_load=True)
image_base = pe.OPTIONAL_HEADER.ImageBase
data = open(DLL, "rb").read()

sections = []
for s in pe.sections:
    sections.append(
        {
            "name": s.Name.rstrip(b"\x00").decode("ascii", "replace"),
            "va": s.VirtualAddress,
            "vsize": s.Misc_VirtualSize,
            "raw": s.PointerToRawData,
            "rawsize": s.SizeOfRawData,
            "exec": bool(s.Characteristics & 0x20000000),
        }
    )

print("sections:", [(s["name"], hex(s["va"])) for s in sections])

# ---- strings (null-terminated printable) ----
strings = {}
str_owner = {}  # any rva inside a string -> (string_rva, offset)
for s in sections:
    start, end = s["raw"], min(len(data), s["raw"] + s["rawsize"])
    i = start
    while i < end:
        b = data[i]
        if 0x20 <= b <= 0x7E or b == 9:
            j = i
            while j < end and (0x20 <= data[j] <= 0x7E or data[j] == 9):
                j += 1
            if j - i >= 2 and j < end and data[j] == 0:
                va = s["va"] + (i - s["raw"])
                strings[va] = data[i:j].decode("ascii")
                for k in range(j - i):
                    str_owner[va + k] = (va, k)
            i = j
        else:
            i += 1
print("strings:", len(strings))

# ---- base relocations ----
relocs = set()
try:
    for entry in pe.DIRECTORY_ENTRY_BASERELOC:
        for r in entry.entries:
            if r.type == 3:  # IMAGE_REL_BASED_HIGHLOW not on x64; 10 = DIR64
                pass
            if r.type == 10:  # IMAGE_REL_BASED_DIR64
                relocs.add(r.rva)
except Exception as e:
    print("reloc parse error:", e)
print("DIR64 relocations:", len(relocs))

# ---- disassembly: LEA / IMM xrefs ----
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
md.skipdata = True

lea = {}
imm = {}
mid = {}
n_total = 0

for s in sections:
    if not s["exec"]:
        continue
    code = data[s["raw"] : s["raw"] + s["rawsize"]]
    for insn in md.disasm(code, s["va"]):
        n_total += 1
        if insn.id == 0:
            continue
        for op in insn.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                t = (insn.address + insn.size + op.mem.disp) & 0xFFFFFFFFFFFFFFFF
                if t in strings:
                    lea.setdefault(t, []).append(
                        [insn.address, insn.mnemonic, insn.op_str]
                    )
                elif t in str_owner:
                    parent, off = str_owner[t]
                    mid.setdefault(t, []).append(
                        [insn.address, insn.op_str, parent, strings[parent], off]
                    )
            elif op.type == X86_OP_IMM:
                v = op.imm & 0xFFFFFFFFFFFFFFFF
                if v in strings:
                    imm.setdefault(v, []).append(
                        [insn.address, insn.mnemonic, insn.op_str]
                    )

print("disassembled insns:", n_total)
print("lea xrefs:", len(lea), "imm xrefs:", len(imm), "mid-string targets:", len(mid))

# ---- pointer slots in non-exec sections ----
ptr = {}
for s in sections:
    if s["exec"]:
        continue
    start, end = s["raw"], min(len(data), s["raw"] + s["rawsize"])
    width = (end - start) // 8 * 8
    if width <= 0:
        continue
    arr = struct.unpack_from("<%dQ" % (width // 8), data, start)
    for idx, v in enumerate(arr):
        if image_base <= v < image_base + 0x20000000:
            rva = v - image_base
            if rva in strings:
                ptr.setdefault(rva, []).append(s["va"] + idx * 8)
print("pointer xrefs:", len(ptr))

out = {
    "image_base": image_base,
    "sections": sections,
    "strings": {str(k): v for k, v in strings.items()},
    "lea": {str(k): v for k, v in lea.items()},
    "imm": {str(k): v for k, v in imm.items()},
    "ptr": {str(k): v for k, v in ptr.items()},
    "mid": {str(k): v for k, v in mid.items()},
    "relocs": sorted(relocs),
}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("saved", OUT)

# ---- report ----
for needle in [
    "VR HINTS",
    "TURN MODE",
    "MANUAL RELOADING",
    "GAME",
    "mevr_manual_reload",
]:
    for va, t in strings.items():
        if t == needle:
            print(
                "\n%r rva=0x%X lea=%d ptr=%d imm=%d"
                % (
                    needle,
                    va,
                    len(lea.get(va, [])),
                    len(ptr.get(va, [])),
                    len(imm.get(va, [])),
                )
            )
            for e in (lea.get(va, []) + [("ptr", hex(x)) for x in ptr.get(va, [])])[
                :10
            ]:
                print("   ", e)
