"""Build the settings table (id -> caption -> option values) from the DLL.

Read-only.  Setting ids are the `mevr_*` strings referenced by `lea` right
before the caption literal; every literal between two ids is an option value
(or a slider format) registered for the setting above it.

    python work/menu_model.py > work/menu_model.json
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = Path(
    r"F:\SteamLibrary\steamapps\common\Metro Exodus\versions\0.9.3"
    r"\MetroExodusVR.dll.bak-093-orig"
)
PLAN = ROOT / "kit093" / "ru" / "plan-0.9.3.json"


def sections(data: bytes):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = pe + 24
    size_opt = struct.unpack_from("<H", data, pe + 20)[0]
    sec = opt + size_opt
    out = []
    for i in range(nsec):
        o = sec + i * 40
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
        out.append((vaddr, rawsize, rawptr, vsize))
    return out


def off2rva(secs, off):
    for vaddr, rawsize, rawptr, _ in secs:
        if rawptr <= off < rawptr + rawsize:
            return vaddr + (off - rawptr)
    return None


def main() -> None:
    data = DLL.read_bytes()
    secs = sections(data)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))["plan"]

    ids = {}
    i = 0
    while True:
        i = data.find(b"mevr_", i)
        if i < 0:
            break
        j = i
        while j < len(data) and (data[j : j + 1].isalnum() or data[j : j + 1] == b"_"):
            j += 1
        s = data[i:j].decode("latin-1")
        rva = off2rva(secs, i)
        if rva and s not in ids:
            ids[s] = rva
        i = j

    by_rva = {v: k for k, v in ids.items()}
    modrms = {0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D}
    refs = []
    for i in range(len(data) - 7):
        if data[i] not in (0x48, 0x49, 0x4C, 0x4D) or data[i + 1] != 0x8D:
            continue
        if data[i + 2] not in modrms:
            continue
        disp = struct.unpack_from("<i", data, i + 3)[0]
        rva = off2rva(secs, i)
        if rva is None:
            continue
        target = rva + 7 + disp
        if target in by_rva:
            refs.append((rva, by_rva[target]))

    events = [(r, "ID", p) for r, p in refs if 0xB9000 <= r <= 0xC4000]
    for it in plan:
        for site, kind in it["sites"]:
            if 0xB9000 <= site <= 0xC4000:
                events.append((site, kind, it))
    events.sort(key=lambda e: e[0])

    lits = [(site, val) for site, kind, val in events if kind != "ID"]
    clusters = []
    for site, kind, val in events:
        if kind != "ID":
            continue
        near = min(lits, key=lambda e: abs(e[0] - site))
        if abs(near[0] - site) > 0x40:
            continue
        clusters.append(
            {
                "id": val,
                "caption": near[1]["text"],
                "addr": near[1]["addr"],
                "lo": min(site, near[0]),
                "hi": max(site, near[0]),
                "values": [],
            }
        )
    clusters.sort(key=lambda c: c["lo"])
    used = {(c["lo"], c["caption"]) for c in clusters}
    cap_sites = set()
    for c in clusters:
        for s, v in lits:
            if v["text"] == c["caption"] and v["addr"] == c["addr"]:
                cap_sites.add(s)
    for c, nxt in zip(clusters, clusters[1:] + [None]):
        end = nxt["lo"] if nxt else 1 << 60
        for s, v in lits:
            if c["hi"] < s < end and s not in cap_sites:
                c["values"].append({"text": v["text"], "addr": v["addr"]})
    items = clusters

    json.dump(
        items,
        open(ROOT / "work" / "menu_model.json", "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    for it in items:
        vals = ", ".join(v["text"] for v in it["values"]) or "-"
        print(f"{it['id']:32s} {str(it['caption']):28s} {vals}")


if __name__ == "__main__":
    main()
