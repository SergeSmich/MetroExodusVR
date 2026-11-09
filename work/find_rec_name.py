"""Ad-hoc: find where the matched record's name/value live near rec_ptr_pre."""

import ctypes
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import list_fonts as lf

REC = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x217DC8E6520
pid = lf.find_pid()
h = lf.open_proc(pid)


def read(a, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not lf.k32.ReadProcessMemory(h, ctypes.c_void_p(a), buf, n, ctypes.byref(got)):
        return None
    return buf.raw[: got.value]


for back in (0x200, 0x400, 0x800):
    base = REC - back
    raw = read(base, back + 0x400)
    if raw is None:
        print(f"[{base:#x}] unreadable")
        continue
    print(f"--- window {base:#x} .. {base + len(raw):#x}")
    for needle in (b"font_name", b"menu", b"override_font_name"):
        start = 0
        hits = 0
        while hits < 6:
            i = raw.find(needle, start)
            if i < 0:
                break
            print(
                f"  {needle!r} at {base + i:#x} (rec{base + i - REC:+#x}) ctx={raw[max(0, i - 0x10) : i + 0x20]!r}"
            )
            start = i + 1
            hits += 1

print("--- record itself")
raw = read(REC, 0x98)
for i in range(0, 0x98, 0x10):
    chunk = raw[i : i + 0x10]
    print(
        f"  +{i:03x}  {chunk.hex(' ')}  "
        + "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
    )
