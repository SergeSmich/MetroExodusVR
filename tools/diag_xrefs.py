import json, struct
import pefile

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402
re_paths.require(str(re_paths.DLL))


DLL = str(re_paths.DLL)
A = json.load(
    open(str(re_paths.PE_ANALYSIS), encoding="utf-8")
)
image_base = A["image_base"]
strings = {int(k): v for k, v in A["strings"].items()}
lea = {int(k): v for k, v in A["lea_xrefs"].items()}
ptr = {int(k): v for k, v in A["ptr_xrefs"].items()}

data = open(DLL, "rb").read()
pe = pefile.PE(DLL, fast_load=True)


def find(s):
    return [va for va, t in strings.items() if t == s]


for needle in [
    "VR HINTS",
    "VR SETTINGS",
    "TURN MODE",
    "MANUAL RELOADING",
    "mevr_manual_reload",
]:
    vas = find(needle)
    for va in vas:
        print("\n=== %r at RVA 0x%X (file 0x%X)" % (needle, va, va - 0x15A00))
        print("  ptr slots:", [hex(x) for x in ptr.get(va, [])])
        print("  lea:", lea.get(va, [])[:5])
        # search all byte offsets for absolute VA or RVA pointer, any alignment
        abs_bytes = struct.pack("<Q", image_base + va)
        rva_bytes = struct.pack("<Q", va)
        hits_abs = []
        hits_rva = []
        start = 0
        while True:
            i = data.find(abs_bytes, start)
            if i < 0:
                break
            hits_abs.append(i)
            start = i + 1
        start = 0
        while True:
            i = data.find(rva_bytes, start)
            if i < 0:
                break
            hits_rva.append(i)
            start = i + 1
        print(
            "  raw occurrences of VA ptr: %d %s"
            % (len(hits_abs), [hex(x) for x in hits_abs[:10]])
        )
        print(
            "  raw occurrences of RVA ptr: %d %s"
            % (len(hits_rva), [hex(x) for x in hits_rva[:10]])
        )

# how many rip-relative targets fall in the UI string range? (recompute from file quickly)
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

s = pe.sections[0]
code = data[s.PointerToRawData : s.PointerToRawData + s.SizeOfRawData]
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
md.skipdata = True
hits = {}
for insn in md.disasm(code, s.VirtualAddress):
    if insn.id == 0:
        continue
    for op in insn.operands:
        if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
            t = (insn.address + insn.size + op.mem.disp) & 0xFFFFFFFFFFFFFFFF
            if 0x498000 <= t < 0x4A3000:
                hits[t] = hits.get(t, 0) + 1

print(
    "\nRIP-relative targets into UI range: %d distinct, %d total"
    % (len(hits), sum(hits.values()))
)
for t, n in list(hits.items())[:20]:
    print("  target 0x%X x%d -> in strings: %s" % (t, n, repr(strings.get(t))[:70]))
