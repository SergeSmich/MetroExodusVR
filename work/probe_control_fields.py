"""Read control+0..0x100 std::string fields live: [+0x60], [+0x68], [+0x70],
[+0x78] as {ptr, len(,cap)} pairs — Arena A-0016 §7.1 (zero-risk read).

Usage: python work/probe_control_fields.py [marker_rva]
"""

from __future__ import annotations

import ctypes
import struct
import sys

sys.path.insert(0, r"F:\Projects\MetroExodusVR\work")
import read_marker as R  # noqa: E402

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.ReadProcessMemory.restype = ctypes.c_int
k32.ReadProcessMemory.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def read(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return buf.raw[: got.value] if ok else b""


def main():
    pid = R.find_pid()
    h, mods = R.modules(pid)
    base = next(b for p, b, s in mods if p.lower().endswith("metroexodusvr.dll"))
    print(f"pid {pid} dll base {base:#x}")

    mrk = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0xC27F18
    m = read(h, base + mrk, 0x40)
    control = struct.unpack_from("<Q", m, 8)[0]
    print(f"calls={int.from_bytes(m[0:4], 'little')} caption={int.from_bytes(m[4:8], 'little')} set_ok={m[0x24]} control={control:#x}")

    ctrl = read(h, control, 0x200)
    print(f"control readable {len(ctrl)}/0x200")
    if not ctrl:
        return
    b0ac = ctrl[0xAC] if len(ctrl) > 0xAC else -1
    q60 = struct.unpack_from("<Q", ctrl, 0x60)[0]
    print(f"  GATE [c+0xac]={b0ac:#04x} bit0={b0ac & 1}")
    print(f"  QWORD [c+0x60]={q60:#018x} hi32={q60 >> 32:#010x} lo32={q60 & 0xFFFFFFFF:#010x}")
    for off in (0x50, 0x58, 0x60, 0x68, 0x70, 0x78, 0x80, 0x88, 0x90, 0x98, 0xA0):
        tri = struct.unpack_from("<QQQ", ctrl, off)
        ptr, a, b = tri
        # candidate: pointer into module, len plausible, or SSO inline string at off+?
        s = ""
        if base <= ptr < base + 0x1000000 and 0 < a < 0x200:
            data = read(h, ptr, min(a + 1, 0x60))
            s = f" -> RVA {ptr - base:#x} len={a}: {data[: min(a, 48)]!r}"
        inl = ctrl[off : off + 16].split(b"\0", 1)[0]
        print(
            f"  c+{off:#04x}: ptr={ptr:#18x} a={a:#x} b={b:#x}"
            f"{'  inline:' + repr(inl) if inl else ''}{s}"
        )
    # raw dump 0x40..0xa8 for the full picture
    raw = ctrl[:0xA8]
    for i in range(0, len(raw), 16):
        ch = raw[i : i + 16]
        hxs = " ".join(f"{c:02x}" for c in ch)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in ch)
        print(f"  {i:04x}  {hxs:<47}  {asc}")


main()
