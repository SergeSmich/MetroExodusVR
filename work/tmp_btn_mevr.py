"""Find who creates the mod's VR caption element and with which style.

The A-0033 probe says the matched caption control is an object whose inline
std::string is "btn_mevr_vr".  The literal must be referenced by the widget
builder; the arguments next to that call are where the class/style/font is
chosen.
"""

import struct

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

DLL = r"work\0.9.1\MetroExodusVR.dll.orig"
NEEDLE = b"btn_mevr_vr\x00"

pe = pefile.PE(DLL)
data = open(DLL, "rb").read()
base = pe.OPTIONAL_HEADER.ImageBase


def rva_of(off):
    return pe.get_rva_from_offset(off)


def off_of(rva):
    return pe.get_offset_from_rva(rva)


hits = []
pos = 0
while True:
    pos = data.find(NEEDLE, pos)
    if pos < 0:
        break
    hits.append(pos)
    pos += 1
print("literal offsets:", [hex(h) for h in hits])

text = next(s for s in pe.sections if s.Name.startswith(b".text"))
tstart, tsize = text.VirtualAddress, text.Misc_VirtualSize
traw = data[text.PointerToRawData : text.PointerToRawData + tsize]

refs = []
for lit in hits:
    lit_rva = rva_of(lit)
    for off in range(tsize - 8):
        if traw[off] not in (0x48, 0x4C):
            continue
        if traw[off + 1] != 0x8D:  # lea
            continue
        modrm = traw[off + 2]
        if (modrm & 0xC7) != 0x05:
            continue
        disp = struct.unpack_from("<i", traw, off + 3)[0]
        target = tstart + off + 7 + disp
        if target == lit_rva:
            refs.append(tstart + off)
print("lea refs:", [hex(r) for r in refs])

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
for ref in refs:
    print(f"\n=== site {ref:#x} ===")
    start = max(tstart, ref - 0x120)
    blob = data[off_of(start) : off_of(start) + 0x220]
    for ins in md.disasm(blob, start):
        mark = " <== literal" if ins.address == ref else ""
        print(f"  {ins.address:6x}  {ins.mnemonic:<8} {ins.op_str}{mark}")
        if ins.address > ref + 0xE0:
            break
