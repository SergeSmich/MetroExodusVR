"""Ad-hoc: dump the live font-manager bucket array and a few raw nodes."""

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
    return lf.k32.ReadProcessMemory and (lambda r: r)(None) if False else _read(a, n)


def _read(a, n):
    import ctypes

    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not lf.k32.ReadProcessMemory(h, ctypes.c_void_p(a), buf, n, ctypes.byref(got)):
        return None
    return buf.raw[: got.value]


fonts = struct.unpack("<Q", _read(base + 0x1733260, 8))[0]
print(f"Fonts*           = {fonts:#x}")
if fonts:
    raw = _read(fonts, 0x28)
    print(
        "Fonts dwords     = "
        + " ".join(f"{v:#010x}" for v in struct.unpack("<10I", raw))
    )

banks = []
for i in range(8):
    banks.append(struct.unpack("<Q", _read(base + 0x175F140 + i * 8, 8))[0])
print("banks            = " + " ".join(f"{b:#x}" for b in banks))

mgr = struct.unpack("<Q", _read(base + 0x175F138, 8))[0]
print(f"manager          = {mgr:#x}")

for name in (b"menu", b"arial", b"regular", b"console"):
    idx = zlib.crc32(name) % 0x4115
    group = idx // 130
    print(
        f"{name!r}: crc={zlib.crc32(name):#010x} idx={idx} group={group} chunk={mgr + (group + 0x20AB) * 16:#x}"
    )

# walk all bucket slots, print raw node headers
found = 0
for k in range(0x4115):
    p = _read(mgr + k * 8, 8)
    if not p:
        continue
    node = struct.unpack("<Q", p)[0]
    chain = 0
    while node and chain < 8:
        hdr = _read(node, 0x30)
        if hdr is None:
            break
        nxt, ref, h2, h3 = struct.unpack("<QIIQ", hdr[:0x18])
        nlen = struct.unpack("<H", hdr[0x10:0x12])[0]
        flag = hdr[0x12]
        bank = hdr[0x13]
        nm = hdr[0x14:0x30]
        if found < 40:
            print(
                f"slot={k:#06x} node={node:#x} next={nxt:#x} ref={ref} "
                f"u10={nlen} f={flag} b={bank} raw={nm!r}"
            )
        found += 1
        node = nxt
        chain += 1
print("total nodes      =", found)
