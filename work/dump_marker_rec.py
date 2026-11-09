"""Ad-hoc: dump the record copy the hook left in the marker (bag13)."""

import ctypes
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import list_fonts as lf

MARKER_RVA = 0xC2885C
pid = lf.find_pid()
h = lf.open_proc(pid)
mods = lf.modules(h)
dll = [b for p, b, s in mods if p.lower().endswith("metroexodusvr.dll")][0]


def read(a, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not lf.k32.ReadProcessMemory(h, ctypes.c_void_p(a), buf, n, ctypes.byref(got)):
        return None
    return buf.raw[: got.value]


r = read(dll + MARKER_RVA + 0x1A60, 0x98)
print(f"marker {dll + MARKER_RVA:#x} rec copy:")
for i in range(0, 0x98, 0x10):
    c = r[i : i + 0x10]
    txt = "".join(chr(x) if 32 <= x < 127 else "." for x in c)
    print(f"  +{i:03x}  {c.hex(' ')}  {txt}")
print("kind      =", r[0])
print("qword0    =", hex(struct.unpack_from("<Q", r, 0)[0]))
print("name ptr  =", hex(struct.unpack_from("<Q", r, 8)[0]))
print("name len  =", struct.unpack_from("<Q", r, 0x18)[0])
print("name cap  =", struct.unpack_from("<Q", r, 0x20)[0])
print("val len   =", struct.unpack_from("<Q", r, 0x70)[0])
print("val cap   =", struct.unpack_from("<Q", r, 0x78)[0])
print(
    "tail      = " + " ".join(f"{v:#010x}" for v in struct.unpack_from("<6I", r, 0x80))
)
