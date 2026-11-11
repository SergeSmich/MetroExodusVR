"""Analyze MetroExodusVR.dll: PE layout, string table, and cross-references
to strings from code (RIP-relative LEA) and data (absolute pointers)."""

import sys, json, struct
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402
re_paths.require(str(re_paths.DLL))


DLL = str(re_paths.DLL)

pe = pefile.PE(DLL, fast_load=True)
image_base = pe.OPTIONAL_HEADER.ImageBase
print("image base: 0x%X" % image_base)
print("sections:")
for s in pe.sections:
    name = s.Name.rstrip(b"\x00").decode("ascii", "replace")
    print(
        "  %-8s VA=0x%08X vSize=0x%08X rawOff=0x%08X rawSize=0x%08X flags=0x%08X"
        % (
            name,
            image_base + s.VirtualAddress,
            s.Misc_VirtualSize,
            s.PointerToRawData,
            s.SizeOfRawData,
            s.Characteristics,
        )
    )

with open(DLL, "rb") as f:
    data = f.read()

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
            "write": bool(s.Characteristics & 0x80000000),
        }
    )


def va_to_off(va):
    for s in sections:
        if s["va"] <= va < s["va"] + max(s["vsize"], s["rawsize"]):
            delta = va - s["va"]
            if delta < s["rawsize"]:
                return s["raw"] + delta
    return None


def off_to_va(off):
    for s in sections:
        if s["raw"] <= off < s["raw"] + s["rawsize"]:
            return s["va"] + (off - s["raw"])
    return None


# --- extract null-terminated printable strings from all sections ---
strings = {}
for s in sections:
    start = s["raw"]
    end = min(len(data), start + s["rawsize"])
    i = start
    while i < end:
        b = data[i]
        if 0x20 <= b <= 0x7E or b == 9:
            j = i
            while j < end and (0x20 <= data[j] <= 0x7E or data[j] == 9):
                j += 1
            if j - i >= 2 and data[j : j + 1] == b"\x00":
                va = s["va"] + (i - s["raw"])
                strings[va] = data[i:j].decode("ascii")
            i = j
        else:
            i += 1

print("total null-terminated strings:", len(strings))

# --- disassemble executable sections, collect LEA rip-relative xrefs ---
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
md.skipdata = True
lea_xrefs = {}
other_imm = {}

for s in sections:
    if not s["exec"]:
        continue
    start = s["raw"]
    end = min(len(data), start + s["rawsize"])
    code = data[start:end]
    n = 0
    for insn in md.disasm(code, s["va"]):
        n += 1
        if insn.id == 0:
            continue
        for op in insn.operands:
            if op.type == 3:  # X86_OP_IMM
                v = op.imm & 0xFFFFFFFFFFFFFFFF
                if v in strings:
                    other_imm.setdefault(v, []).append(
                        (insn.address, insn.mnemonic, insn.op_str)
                    )
            elif op.type == 2:  # X86_OP_MEM
                if op.mem.base == 41 and op.mem.index == 0:  # RIP
                    target = (
                        insn.address + insn.size + op.mem.disp
                    ) & 0xFFFFFFFFFFFFFFFF
                    if target in strings:
                        lea_xrefs.setdefault(target, []).append(
                            (insn.address, insn.mnemonic, insn.op_str)
                        )
    print("disassembled %s: %d insns" % (s["name"], n))

print("strings with LEA xrefs:", len(lea_xrefs))
print("strings with immediate xrefs:", len(other_imm))

# --- scan data sections for absolute 8-byte pointers into string table ---
ptr_xrefs = {}
for s in sections:
    if s["exec"]:
        continue
    start = s["raw"]
    end = min(len(data), start + s["rawsize"])
    width = (end - start) // 8 * 8
    if width <= 0:
        continue
    arr = struct.unpack_from("<%dQ" % (width // 8), data, start)
    for idx, v in enumerate(arr):
        if image_base <= v < image_base + 0x20000000:
            rva = v - image_base
            if rva in strings:
                ptr_xrefs.setdefault(rva, []).append(s["va"] + idx * 8)

print("strings with pointer xrefs:", len(ptr_xrefs))

# --- save results ---
out = {
    "image_base": image_base,
    "sections": sections,
    "strings": {str(k): v for k, v in strings.items()},
    "lea_xrefs": {str(k): v for k, v in lea_xrefs.items()},
    "imm_xrefs": {str(k): v for k, v in other_imm.items()},
    "ptr_xrefs": {str(k): v for k, v in ptr_xrefs.items()},
}
with open(
    str(re_paths.PE_ANALYSIS), "w", encoding="utf-8"
) as f:
    json.dump(out, f, ensure_ascii=False)
print("saved work/pe_analysis.json")

# --- report on the known UI cluster ---
lo, hi = 0x4983E0, 0x4A2C18
sel = sorted(v for v in strings if lo <= v < hi)
print("\nUI cluster strings: %d" % len(sel))
no_xref = 0
for va in sel[:40]:
    lea = lea_xrefs.get(va, [])
    ptr = ptr_xrefs.get(va, [])
    imm = other_imm.get(va, [])
    if not lea and not ptr and not imm:
        no_xref += 1
    print(
        "  0x%08X lea=%-3d ptr=%-3d imm=%-3d  %r"
        % (va, len(lea), len(ptr), len(imm), strings[va][:70])
    )

missing = [
    va
    for va in sel
    if va not in lea_xrefs and va not in ptr_xrefs and va not in other_imm
]
print("\ncluster strings without any xref: %d / %d" % (len(missing), len(sel)))
for va in missing[:30]:
    print("  no-xref 0x%08X %r" % (va, strings[va][:80]))
