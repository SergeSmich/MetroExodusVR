"""Decisive 0.9.3 test: encode all nine nav captions with live-font glyph indices
and force a re-resolve, with kind-table slot 4 pointed at the identity handler.
"""

import sys, struct, time

sys.path.insert(0, r"F:\Projects\MetroExodusVR\work")
import grab_window as G
from find_textobj import Proc, module_base, scan
from probe_page import pid_of
from cap_poke import write_bytes

WORDS = {
    "btn_link_mevr_game": "ИГРА",
    "btn_link_mevr_movement": "ДВИЖЕНИЕ",
    "btn_link_mevr_body": "ТЕЛО",
    "btn_link_mevr_hands": "РУКИ",
    "btn_link_mevr_weapons": "ОРУЖИЕ",
    "btn_link_mevr_scopes": "ПРИЦЕЛЫ",
    "btn_link_mevr_hud": "HUD",
    "btn_link_mevr_comfort": "КОМФОРТ",
    "btn_link_mevr_vibration_page": "ВИБРАЦИЯ",
}

pid = pid_of()
p = Proc(pid)
exe = module_base(pid, "MetroExodus.exe")

mgr = struct.unpack("<Q", p.read(exe + 0x1765A68, 8))[0]
head = p.read(mgr, 0x40)
tbl = struct.unpack_from("<Q", head, 8)[0]
cnt = struct.unpack_from("<H", head, 0x12)[0]
live = list(struct.unpack(f"<{cnt}H", p.read(tbl, cnt * 2)))
inv = {}
for i, c in enumerate(live):
    inv.setdefault(c, i)


def pool_of(ref):
    tag, off = ref >> 24, ref & 0xFFFFFF
    pool = p.q(exe + 0x175F140 + tag * 8)
    return pool + off if pool else None


def name_of(obj):
    ref = p.d(obj + 0x50)
    if not ref:
        return ""
    b = pool_of(ref)
    h = p.read(b, 0x30)
    ln = struct.unpack_from("<H", h, 0x10)[0]
    return h[0x14 : 0x14 + ln].decode("latin-1")


# make sure slot 4 is the identity handler
slot = exe + 0xB8DC60 + 16
print("slot4", hex(p.d(slot) or 0))
if (p.d(slot) or 0) != 0xB8DBE9:
    write_bytes(p, slot, struct.pack("<I", 0xB8DBE9))

hits, _ = scan(p, exe, None, True)
nodes = {}
for obj, s, *_ in hits:
    nm = name_of(obj)
    if nm in WORDS:
        nodes.setdefault(nm, []).append(obj)
print("nodes", {k: len(v) for k, v in nodes.items()})

for nm, objs in nodes.items():
    word = WORDS[nm]
    idx = bytes(inv[ord(ch)] for ch in word)
    for obj in objs:
        ref = p.d(obj + 0xD0)
        base = pool_of(ref)
        write_bytes(p, base + 0x14, idx + b"\0")
        write_bytes(p, base + 0x10, struct.pack("<H", len(idx)))
        # force re-resolve: clear the flag, keep kind 6
        write_bytes(p, obj + 0xD8, struct.pack("<I", 0))
        write_bytes(p, obj + 0xD4, struct.pack("<I", (ref & ~7) | 6))
        print(f"  {nm} obj={obj:#x} ref={ref:#x} idx={idx.hex()}")

time.sleep(1.0)
ok, im = G.grab(G.find_window())
im.save(r"F:\Projects\MetroExodusVR\work\shots\v093_panel_idx.png")
print("shot", ok)
for nm, objs in nodes.items():
    o = objs[0]
    print(f"  {nm}: d8={p.d(o + 0xD8)} d4={p.d(o + 0xD4):#x}")
