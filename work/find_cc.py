"""Find function start before addr by CC padding runs (>=2) and print the
bytes at the first 8 bytes of each candidate for eyeballing.

python work/find_cc.py 0xc47077
"""

import sys
from pathlib import Path

sys.path.insert(0, r"F:\Projects\MetroExodusVR\tools")
from apply_ru import PE  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

P = r"F:\SteamLibrary\steamapps\common\Metro Exodus\MetroExodus.exe"
data = Path(P).read_bytes()
pe = PE(data)

addr = int(sys.argv[1], 0)
lo = max(0x1000, addr - 0x1500)

i = addr - 2
found = []
while i >= lo:
    o = pe.rva_to_off(i)
    if o is None:
        i -= 1
        continue
    if data[o] == 0xCC and data[o + 1] == 0xCC:
        # topmost byte of this run is i (walking down), function starts at i+1
        cand = i + 1
        off = pe.rva_to_off(cand)
        found.append((cand, data[off : off + 10].hex(" ")))
        # skip this run
        while (
            i >= lo and pe.rva_to_off(i) is not None and data[pe.rva_to_off(i)] == 0xCC
        ):
            i -= 1
        continue
    i -= 1

for cand, hexs in found[:6]:
    print(f"{cand:#x}: {hexs}")
