"""Ad-hoc: resolve the Fonts handles and search the interner for font names."""

import ctypes
import struct
import sys
import zlib

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import list_fonts as lf

pid = lf.find_pid()
h = lf.open_proc(pid)
mods = lf.modules(h)
base = [b for p, b, s in mods if p.lower().endswith("\\metroexodus.exe")][0]
print(f"pid {pid} base {base:#x}")


def read(a, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not lf.k32.ReadProcessMemory(h, ctypes.c_void_p(a), buf, n, ctypes.byref(got)):
        return None
    return buf.raw[: got.value]


def node_name(addr):
    hdr = read(addr, 0x14)
    if hdr is None:
        return None
    nlen = struct.unpack_from("<H", hdr, 0x10)[0]
    if nlen > 0x200:
        return None
    raw = read(addr + 0x14, nlen)
    return raw


banks = [struct.unpack("<Q", read(base + 0x175F140 + i * 8, 8))[0] for i in range(32)]
print("banks:")
for i, b in enumerate(banks):
    print(f"  [{i:2d}] {b:#x}")

fonts = struct.unpack("<Q", read(base + 0x1733260, 8))[0]
raw = read(fonts, 0x20)
vals = struct.unpack("<8I", raw)
print(f"Fonts* {fonts:#x} dwords: " + " ".join(f"{v:#010x}" for v in vals))
labels = ["pad", "regular", "arial", "menu", "console", "?", "?", "?"]
for lab, v in zip(labels, vals):
    if not v:
        print(f"  {lab:8s} = 0")
        continue
    bank = v >> 24
    off = v & 0xFFFFFF
    node = banks[bank] + off if bank < len(banks) else 0
    nm = node_name(node) if node else None
    print(f"  {lab:8s} = {v:#010x} bank={bank} off={off:#x} node={node:#x} name={nm!r}")

mgr = struct.unpack("<Q", read(base + 0x175F138, 8))[0]
wanted = {b"menu", b"arial", b"regular", b"console", b"main_menu"}
hits = []
for k in range(0x4115):
    p = read(mgr + k * 8, 8)
    if not p:
        continue
    node = struct.unpack("<Q", p)[0]
    while node:
        hdr = read(node, 0x14)
        if hdr is None:
            break
        nxt = struct.unpack_from("<Q", hdr, 0)[0]
        nlen = struct.unpack_from("<H", hdr, 0x10)[0]
        if 0 < nlen <= 0x100:
            raw = read(node + 0x14, nlen)
            if raw in wanted:
                hits.append((raw, node, hdr[0x13], k, zlib.crc32(raw) % 0x4115))
        node = nxt
print("font-name hits:")
for raw, node, bank, slot, idx in hits:
    print(f"  {raw!r} node={node:#x} bank={bank} slot={slot:#06x} idx={idx}")
