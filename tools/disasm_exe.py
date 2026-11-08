"""Disassemble a range of MetroExodus.exe with string/call annotations.

Usage: python tools/disasm_exe.py <start-hex> [end-hex]
"""

import sys
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402
re_paths.require(str(re_paths.EXE))


EXE = str(re_paths.EXE)
pe = pefile.PE(EXE, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
data = open(EXE, "rb").read()
sections = [
    (
        s.Name.rstrip(b"\x00").decode(),
        s.VirtualAddress,
        s.Misc_VirtualSize,
        s.PointerToRawData,
        s.SizeOfRawData,
        bool(s.Characteristics & 0x20000000),
    )
    for s in pe.sections
]


def rva_to_off(rva):
    for name, va, vs, raw, rs, ex in sections:
        if va <= rva < va + max(vs, rs):
            d = rva - va
            if d < rs:
                return raw + d
    return None


def read_cstr(rva, limit=120):
    off = rva_to_off(rva)
    if off is None:
        return None
    end = data.find(b"\x00", off, off + limit)
    if end < 0:
        return None
    raw = data[off:end]
    if len(raw) < 3:
        return None
    printable = sum(1 for c in raw if 32 <= c < 127)
    if printable < len(raw) * 0.9:
        return None
    return raw.decode("latin-1")


def main():
    start = int(sys.argv[1], 16)
    end = int(sys.argv[2], 16) if len(sys.argv) > 2 else start + 0x400
    off = rva_to_off(start)
    code = data[off : off + (end - start)]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    for ins in md.disasm(code, start):
        note = ""
        if ins.id:
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    t = ins.address + ins.size + op.mem.disp
                    s = read_cstr(t)
                    if s:
                        note += "  ; %r" % s[:90]
                elif op.type == X86_OP_IMM:
                    v = op.imm & 0xFFFFFFFFFFFFFFFF
                    if 0x1000 <= v < 0x1608000:
                        note += "  ; sub_%X" % v
        if ins.id == 0:
            print(
                "  0x%X  .byte 0x%02x" % (ins.address, ins.bytes[0] if ins.bytes else 0)
            )
        else:
            print(
                "  0x%X  %-40s%s" % (ins.address, ins.mnemonic + " " + ins.op_str, note)
            )


if __name__ == "__main__":
    main()
