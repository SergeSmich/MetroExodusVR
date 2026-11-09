"""Ad-hoc: dump the live font_name record (0x98) and look for a resolved handle."""

import ctypes
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import list_fonts as lf

REC = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x217DC8E6520
pid = lf.find_pid()
h = lf.open_proc(pid)
mods = lf.modules(h)
base = [b for p, b, s in mods if p.lower().endswith("\\metroexodus.exe")][0]


def read(a, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not lf.k32.ReadProcessMemory(h, ctypes.c_void_p(a), buf, n, ctypes.byref(got)):
        return None
    return buf.raw[: got.value]


banks = [struct.unpack("<Q", read(base + 0x175F140 + i * 8, 8))[0] for i in range(32)]
fonts = struct.unpack("<Q", read(base + 0x1733260, 8))[0]
font_vals = struct.unpack("<8I", read(fonts, 0x20))
print(f"rec {REC:#x}")
print(f"font slots: " + " ".join(f"{v:#010x}" for v in font_vals))

raw = read(REC, 0x98)
print("raw:")
for i in range(0, 0x98, 0x10):
    chunk = raw[i : i + 0x10]
    print(
        f"  +{i:03x}  {chunk.hex(' ')}  "
        + "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
    )


def name_at(addr):
    hdr = read(addr, 0x14)
    if not hdr:
        return None
    nlen = struct.unpack_from("<H", hdr, 0x10)[0]
    if not (0 < nlen <= 0x200):
        return None
    s = read(addr + 0x14, nlen)
    return s


for off in range(0, 0x98, 4):
    v = struct.unpack_from("<I", raw, off)[0]
    if not v:
        continue
    bank, o = v >> 24, v & 0xFFFFFF
    tag = ""
    if v in font_vals:
        tag = " == FONT SLOT"
    if bank < 32 and o < 0x1000:
        tag += f" (looks like handle bank={bank} off={o:#x})"
    print(f"  +{off:03x} = {v:#010x}{tag}")

for off in range(0, 0x98 - 8, 8):
    v = struct.unpack_from("<Q", raw, off)[0]
    if v > 0x10000:
        nm = name_at(v)
        if nm:
            print(f"  q+{off:03x} -> {v:#x} name={nm[:40]!r}")
