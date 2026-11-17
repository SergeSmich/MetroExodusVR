"""Reconstruct the mod's menu page order from caption sites and page-id leas.

Read-only.  Prints, in code order, the page ids (mevr_*) and the caption
literals each page registers, so a review document can group the strings by
menu page.
"""

from __future__ import annotations

import json
import struct
import sys
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
    base = struct.unpack_from("<Q", data, opt + 24)[0]
    sec = opt + size_opt
    out = []
    for i in range(nsec):
        o = sec + i * 40
        name = data[o : o + 8].rstrip(b"\0").decode("latin-1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
        out.append((name, base + vaddr, vaddr, rawsize, rawptr, vsize))
    return base, out


def off2rva(secs, off):
    for _, _, vaddr, rawsize, rawptr, _ in secs:
        if rawptr <= off < rawptr + rawsize:
            return vaddr + (off - rawptr)
    return None


def rva2off(secs, rva):
    for _, _, vaddr, rawsize, rawptr, vsize in secs:
        if vaddr <= rva < vaddr + max(rawsize, vsize):
            return rawptr + (rva - vaddr)
    return None


def main() -> None:
    data = DLL.read_bytes()
    base, secs = sections(data)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))["plan"]

    # page id strings
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

    # only page ids: the ones whose code site sits in the big builder function
    pages = {k: v for k, v in ids.items() if k not in ("mevr_description",)}
    by_rva = {}
    for k, v in pages.items():
        by_rva.setdefault(v, []).append(k)

    # scan lea r64, [rip+disp32]
    refs = []
    modrms = {0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D}
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
            refs.append((rva, by_rva[target][0]))
    refs.sort()

    events = [(r, "PAGE", p) for r, p in refs]
    for it in plan:
        for site, kind in it["sites"]:
            events.append((site, kind, it["text"]))
    events.sort()

    for site, kind, text in events:
        if kind == "PAGE":
            print(f"\n=== PAGE {text}  (site {site:#x})")
        else:
            print(f"  {site:#08x} {kind:4s} {text}")


if __name__ == "__main__":
    main()
