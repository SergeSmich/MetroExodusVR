"""For each callback name, find its string in the exe and every qword pointer
to it; print nearby qwords that look like .text addresses.

python work/tmp_cb.py
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, r"F:\Projects\MetroExodusVR\tools")
from apply_ru import PE  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

P = r"F:\SteamLibrary\steamapps\common\Metro Exodus\MetroExodus.exe"
data = Path(P).read_bytes()
pe = PE(data)
secs = pe.sections
text = next(s for s in secs if s["name"] == ".text")
tlo, thi = text["va"], text["va"] + text["rawsize"]


def off2rva(o):
    for s in secs:
        if s["raw"] <= o < s["raw"] + s["rawsize"]:
            return o - s["raw"] + s["va"]
    return None


def rva2off(r):
    for s in secs:
        if s["va"] <= r < s["va"] + s["rawsize"]:
            return r - s["va"] + s["raw"]
    return None


NAMES = [
    "diary_draw_list_item",
    "dlc_shop_draw_list_item",
    "leaderboard_draw_list_item",
    "loader_diary_draw_item",
    "on_draw_item",
]

for name in NAMES:
    b = name.encode()
    print(f"\n=== {name} ===")
    pos = 0
    rvas = []
    while True:
        i = data.find(b + b"\0", pos)
        if i < 0:
            break
        r = off2rva(i)
        if r is not None:
            rvas.append(r)
            print(f"  string @ {r:#x}")
        pos = i + 1
    for r in rvas:
        pat = struct.pack("<Q", r)
        p = 0
        while True:
            j = data.find(pat, p)
            if j < 0:
                break
            p = j + 1
            where = off2rva(j)
            if where is None:
                continue
            lo = max(0, j - 0x20)
            hi = min(len(data), j + 0x28)
            near = []
            for k in range(lo - lo % 8, hi, 8):
                if k + 8 > len(data):
                    break
                q = struct.unpack_from("<Q", data, k)[0]
                if tlo <= q < thi:
                    near.append((off2rva(k), q))
            if near:
                print(
                    f"  ptr {where:#x}: text qwords -> "
                    + ", ".join(f"{a:#x}->{q:#x}" for a, q in near)
                )
