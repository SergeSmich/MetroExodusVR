"""Dump disassembly context around xrefs to selected strings."""

import json, sys
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP

DLL = r"F:\Projects\MetroExodusVR\work\0.9.0\versions\0.9.0\MetroExodusVR.dll"
A = json.load(open(r"F:\Projects\MetroExodusVR\work\xrefs.json", encoding="utf-8"))
strings = {int(k): v for k, v in A["strings"].items()}
lea = {int(k): v for k, v in A["lea"].items()}
ptr = {int(k): v for k, v in A["ptr"].items()}
mid = {int(k): v for k, v in A["mid"].items()}

pe = pefile.PE(DLL, fast_load=True)
image_base = pe.OPTIONAL_HEADER.ImageBase
data = open(DLL, "rb").read()

sections = []
for s in pe.sections:
    sections.append(
        (
            s.Name.rstrip(b"\x00").decode(),
            s.VirtualAddress,
            s.Misc_VirtualSize,
            s.PointerToRawData,
            s.SizeOfRawData,
            bool(s.Characteristics & 0x20000000),
        )
    )


def rva_to_off(rva):
    for name, va, vsize, raw, rawsize, ex in sections:
        if va <= rva < va + max(vsize, rawsize):
            d = rva - va
            if d < rawsize:
                return raw + d
    return None


def find_str(text):
    return [rva for rva, t in strings.items() if t == text]


def dump(rva, before=20, after=25):
    off = rva_to_off(rva)
    if off is None:
        print("  (no file offset)")
        return
    text_sec = next((s for s in sections if s[5] and s[0] == ".text"), None)
    # disassemble a window starting earlier; alignment may be off, so start at rva-64
    start_rva = max(text_sec[1], rva - 96)
    code = data[rva_to_off(start_rva) : rva_to_off(start_rva) + 192]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    insns = list(md.disasm(code, start_rva))
    # locate instruction at rva
    idx = None
    for i, ins in enumerate(insns):
        if ins.address == rva:
            idx = i
            break
    if idx is None:
        print(
            "  (insn not found at 0x%X; %d decoded from 0x%X)"
            % (rva, len(insns), start_rva)
        )
        for ins in insns[:10]:
            print("   0x%X %s %s" % (ins.address, ins.mnemonic, ins.op_str))
        return
    for ins in insns[max(0, idx - before) : idx + after]:
        mark = ">>" if ins.address == rva else "  "
        note = ""
        if ins.id == 0:
            b = ins.bytes[0] if ins.bytes else 0
            print("   %s 0x%X  .byte 0x%02x" % (mark, ins.address, b))
            continue
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                t = (ins.address + ins.size + op.mem.disp) & 0xFFFFFFFFFFFFFFFF
                if t in strings:
                    note += "  ; -> 0x%X %r" % (t, strings[t][:60])
                else:
                    # inside a string?
                    for base_rva in strings:
                        if (
                            base_rva <= t < base_rva + len(strings[base_rva])
                            and t - base_rva < 40
                        ):
                            note += "  ; -> 0x%X inside %r +%d" % (
                                t,
                                strings[base_rva][:40],
                                t - base_rva,
                            )
                            break
            elif op.type == X86_OP_IMM:
                v = op.imm & 0xFFFFFFFFFFFFFFFF
                if v in strings:
                    note += "  ; imm -> %r" % strings[v][:60]
        print(
            "   %s 0x%X  %-28s %s%s"
            % (mark, ins.address, ins.mnemonic + " " + ins.op_str, "", note)
        )


def show(text):
    print("\n" + "=" * 100)
    print("STRING %r" % text)
    for rva in find_str(text):
        print(
            " rva=0x%X  lea=%d ptr=%d mid=%d"
            % (rva, len(lea.get(rva, [])), len(ptr.get(rva, [])), len(mid.get(rva, [])))
        )
        for e in lea.get(rva, []):
            print("  LEA/IMM xref at 0x%X: %s %s" % (e[0], e[1], e[2]))
            dump(e[0])
        for slot in ptr.get(rva, []):
            print("  PTR slot 0x%X -> 0x%X" % (slot, image_base + rva))
        print("  mid (references into middle):", mid.get(rva, [])[:5])


if __name__ == "__main__":
    texts = sys.argv[1:] or [
        "VR HINTS",
        "TURN MODE",
        "GAME",
        "MANUAL RELOADING",
        "mevr_manual_reload",
        "Basics",
    ]
    for t in texts:
        show(t)
