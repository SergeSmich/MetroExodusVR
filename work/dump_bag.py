"""Dump the caption-setter property bag snapshot from the cave marker.

Usage: python work/dump_bag.py <marker_rva_hex>

Marker layout (see tools/apply_ru.py build_caption_font_hook, bag6+):
  header:
    +0x00 calls dword, +0x04 caption matches dword, +0x24 result of the set
    +0x2c last caption len, +0x30..0x40 last caption sample (16 bytes)
    +0x40 qword [control+0x60], +0x25 gate [control+0xac]&1
    +0x48 raw records (stride 0x98, up to 40)
    +0x08 last control, +0x10 bag begin, +0x18 bag end, +0x20 record count
    +0x28 caller return address
    +0x40 raw record copies, stride 0x98, up to 40 (bag end - bag begin)
  record (verbatim copy of the live record):
    kind      @+0x00
    name      std::string {ptr @+0x08, len @+0x18, cap @+0x20, sso @+0x08}
    value     std::string {ptr @+0x60, len @+0x70, cap @+0x78, sso @+0x60}
SSO content is stored inline in the copy (safe); heap pointers are dereferenced
only when the target is still readable (authors run this elevated).
"""

import ctypes
import struct
import sys

sys.path.insert(0, r"F:\Projects\MetroExodusVR\work")
import read_marker as R  # noqa: E402

MARKER_SIZE = 0x1C00
RAW_OFF = 0x48
REC_STRIDE = 0x98
MAX_RECORDS = 40


def sso(raw):
    return raw.split(b"\0", 1)[0]


def fmt(raw):
    return "".join(chr(b) if 32 <= b < 127 else "." for b in raw)


def main():
    marker = int(sys.argv[1], 0)
    pid = R.find_pid()
    h, mods = R.modules(pid)
    base = None
    for path, b, size in mods:
        if path.lower().endswith("metroexodusvr.dll"):
            base = b
            print(f"pid {pid} module {path} base {b:#x} size {size:#x}")
            break
    if base is None:
        raise SystemExit("module not found")

    size = MARKER_SIZE
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    ok = R.k32.ReadProcessMemory(
        h, ctypes.c_void_p(base + marker), buf, size, ctypes.byref(got)
    )
    if not ok:
        raise SystemExit(f"read failed, err {ctypes.get_last_error()}")
    d = buf.raw[: got.value]

    calls = int.from_bytes(d[0:4], 'little')
    caption = int.from_bytes(d[4:8], 'little')
    res = d[0x24]
    gate = d[0x25]
    q60 = int.from_bytes(d[0x40:0x48], 'little')
    cap_len = int.from_bytes(d[0x2c:0x30], 'little')
    cap_sample = d[0x30:0x40]
    control = int.from_bytes(d[8:16], "little")
    begin = int.from_bytes(d[0x10:0x18], "little")
    end = int.from_bytes(d[0x18:0x20], "little")
    count = int.from_bytes(d[0x20:0x24], "little")
    caller = int.from_bytes(d[0x28:0x30], "little")
    print(f"calls={calls} caption={caption} set_ok={res}")
    print(f"last caption len={cap_len} sample={cap_sample!r}")
    print(f"gate [c+0xac]&1={gate} qword [c+0x60]={q60:#018x} (hi32={q60 >> 32:#x})")
    print(f"control={control:#x} begin={begin:#x} end={end:#x}")
    span = end - begin if end > begin else 0
    print(f"records in bag: {span // REC_STRIDE if span else 0} (dumped {count})")
    print(f"caller={caller:#x} (module+{caller - base:#x})")

    def deref_str(ptr, ln, cap, inline):
        """Return ('sso', bytes) or ('heap', bytes) or ('dead', None)."""
        if ln == 0:
            return ("empty", b"")
        if ln < 0x10 and cap < 0x10:
            return ("sso", sso(inline[:ln]))
        # heap pointer: try a live read, heap may still be alive
        if ptr:
            missing = 0
            try:
                pbuf = ctypes.create_string_buffer(ln + 1)
                pgot = ctypes.c_size_t()
                if (
                    R.k32.ReadProcessMemory(
                        h, ctypes.c_void_p(ptr), pbuf, ln + 1, ctypes.byref(pgot)
                    )
                    and pgot.value >= ln
                ):
                    return ("heap", pbuf.raw[:ln])
            except OSError:
                missing = 1
            return ("dead", f"{ptr:#x} len={ln}")
        return ("dead", None)

    for i in range(min(count, MAX_RECORDS)):
        e = d[RAW_OFF + i * REC_STRIDE : RAW_OFF + (i + 1) * REC_STRIDE]
        if not e:
            break
        kind = e[0]
        n_ptr, n_ptr_hi = struct.unpack_from("<QQ", e, 0x08)
        n_len, n_cap = struct.unpack_from("<QQ", e, 0x18)
        v_ptr, v_ptr_hi = struct.unpack_from("<QQ", e, 0x60)
        v_len, v_cap = struct.unpack_from("<QQ", e, 0x70)
        nsrc, nval = deref_str(n_ptr, n_len, n_cap, e[0x08:0x18])
        vsrc, vval = deref_str(v_ptr, v_len, v_cap, e[0x60:0x70])
        ns = nval.decode("latin1", "replace") if isinstance(nval, bytes) else "?"
        vs = vval.decode("latin1", "replace") if isinstance(vval, bytes) else "?"
        print(f"{i:2d} kind={kind} name[{nsrc}]={ns!r} value[{vsrc}]={vs!r}")


if __name__ == "__main__":
    main()
