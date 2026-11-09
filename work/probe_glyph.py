"""Live probe: does the control (from the hook marker) reference our caption
literal directly, or a copy?

Reads the control object memory and the property bag, walks every record's
value std::string (SSO-aware), and reports where each pointer lands:
  module RVA (which section), heap copy, or inline SSO bytes.

Usage: python work/probe_glyph.py
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

CAPTION_LITS = {
    # RVA -> what it was at assemble time (from the bag marker dump)
}


def read(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return buf.raw[: got.value] if ok else b""


def main():
    pid = R.find_pid()
    h, mods = R.modules(pid)
    base = size = None
    for path, b, sz in mods:
        if path.lower().endswith("metroexodusvr.dll"):
            base, size = b, sz
            print(f"pid {pid} dll base {base:#x} size {sz:#x}")
            break
    if base is None:
        print("DLL not found")
        return

    mrk = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0xC27F3F
    m = read(h, base + mrk, 0x40)
    calls = int.from_bytes(m[0:4], 'little')
cap = int.from_bytes(m[4:8], 'little')
set_ok = m[0x24]
    control = struct.unpack_from("<Q", m, 8)[0]
    beg = struct.unpack_from("<Q", m, 0x10)[0]
    end = struct.unpack_from("<Q", m, 0x18)[0]
    nrec = struct.unpack_from("<Q", m, 0x20)[0]
    caller = struct.unpack_from("<Q", m, 0x28)[0]
    print(
        f"calls={calls} caption={cap} set_ok={set_ok} control={control:#x} "
        f"bag={beg:#x}..{end:#x} nrec={nrec} caller(mod+{caller - base:#x})"
    )
    if not control:
        print("no control captured")
        return

    LIT_VA = base + 0x49F708  # the TURN MODE literal slot (calibration row 2)

    # ---- control memory ------------------------------------------------------
    ctrl = read(h, control, 0x800)
    print(f"\n[control {control:#x}] readable {len(ctrl)}/0x800")
    hits = []
    for off in range(0, len(ctrl) - 8, 8):
        v = struct.unpack_from("<Q", ctrl, off)[0]
        if v == LIT_VA:
            hits.append(off)
    print(
        f"  pointer to literal {LIT_VA:#x} inside control: at {[hex(o) for o in hits]}"
    )
    # std::string candidates (ptr, size) pairs pointing into the module .rdata/.ru
    lo, hi = base, base + 0x1000000
    for off in range(0, len(ctrl) - 0x18, 8):
        p, n = struct.unpack_from("<QQ", ctrl, off)
        if lo <= p < hi and 0 < n < 0x30:
            s = read(h, p, n + 1)
            if len(s) >= n and all(32 <= b < 127 or b > 0x7F for b in s[:n]):
                rva = p - base
                print(
                    f"  str? ctrl+{off:#x} ptr->{rva:#x} len {n}: "
                    f"{s[:n].decode('utf-8', 'replace')}"
                )

    # ---- bag walk -------------------------------------------------------------
    if not (beg and end and beg < end):
        print("\n(no bag)")
        return
    bag = read(h, beg, end - beg)
    stride = 0x98
    n = (len(bag)) // stride
    print(f"\n[bag {beg:#x}..{end:#x}] {len(bag):#x} bytes, {n} records")

    def as_str(h, addr, raw):
        p, slen = struct.unpack_from("<QQ", raw, 0)
        sso = raw[0x10:0x20].split(b"\0", 1)[0]
        if slen < 0x10 and slen > 0:
            return ("sso", sso[:slen], None)
        if slen >= 0x10:
            data = read(h, p, min(slen, 0x40))
            return ("heap", data[: min(slen, 40)], p)
        return ("empty", b"", None)

    for i in range(n):
        rec = bag[i * stride : (i + 1) * stride]
        kind = rec[0]
        nname = as_str(h, 0, rec[0x08:0x60])
        nval = as_str(h, 0, rec[0x60:0x98])
        nm = nname[1][:15].decode("latin1")
        vs = nval[1][:15].decode("latin1")
        where = nval[0]
        va = f"@{nval[2]:#x}" if nval[2] else ""
        mark = ""
        if nname[0] == "sso" and nname[1].startswith(b"font_name"):
            mark = "  <<< font"
        if nname[0] == "sso" and nname[1].startswith(b"caption"):
            mark = "  <<< caption"
        print(f" {i:2d} kind={kind} name={nm!r} value[{where}]{va}={vs!r}{mark}")


main()
