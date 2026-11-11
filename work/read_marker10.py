"""Dump the caption-font hook marker from the running game (bag15).

Usage: python work/read_marker10.py [marker_rva_hex] [pid]

bag15 is a READ-ONLY probe (A-0028 §2): it never writes to a game object.
Marker layout (offsets from marker base, marker size 0x2000):
  0x0000 dword  setter calls seen        (inc [marker])
  0x0020 dword  records copied into marker
  0x002c dword  matched captions (recognizer hits)
  0x0048..     first 40 records x 0x98 (raw copy)
  0x1988 dword  value len of the last matching font_name record
  0x198c byte[8] value bytes of that record
  0x1998 qword  vtable of the first control that had a font_name record
  0x19e0 dword  low dword of the control tag ([ctrl])
  0x19e4 dword  low dword of [ctrl+0x60]
  0x19e8 dword  records found (font_name matches)
  0x19ec dword[6] tail [rec+0x80 .. +0x97]
  0x1a04 dword  0xffffffff (slot search removed in bag11)
  0x1a0c dword  "seen first record" flag
  0x1a14 dword  reentrancy depth
  0x1a18 dword  reentry hits
  0x1a1c qword  exe base (PEB)
  0x1a24 qword  control pointer
  0x1a2c qword  Fonts* singleton [exe+0x1733260]
  0x1a34 dword[8] Fonts dwords (last non-zero seen):
                  [0] pad, [1] regular, [2] arial, [3] menu, [4] console
  0x1a54 qword  first font_name record pointer
  0x1a60 rec    0x98 raw copy of the first font_name record
  0x1bc8 qword  bag begin before scan
  0x1bd0 qword  bag end before scan
  0x1be4 dword  resolver probe: menu handle
  0x1be8 dword  resolver probe: arial handle
  0x1bec dword  resolver probe: regular handle
  0x1bf0 qword  resolver probe: font manager pointer
  0x1bf8 dword  resolver probe: calls
  --- bag15 / A-0028 §2.1: the WORKING element (name == "local_text") -------
  0x1c00 dword  how many local_text calls were seen
  0x1c08 qword  control of the first local_text call
  0x1c10 dword  font_name record len of that control (0xffffffff = absent)
  0x1c14 16B    first bytes of that record's value
  0x1c40 dword  dword-scan offset on the local_text control (0xffffffff = none)
  0x1c44 dword  dword-scan slot 1..4 (regular/arial/menu/console)
  0x1c60 dword  local_text value len
  0x1c64 16B    local_text value bytes
  --- bag15 / A-0028 §2.1: OUR matched caption control ----------------------
  0x1c24 dword  its original font_name record len (0xffffffff = absent)
  0x1c28 16B    its original record value
  0x1c38 dword  dword-scan offset on our control (0xffffffff = none)
  0x1c3c dword  dword-scan slot 1..4
  0x1c48 dword  first matched caption seen (sentinel primed)
  0x1c4c dword  first existing font_name record captured
"""

import ctypes
import struct
import sys
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
DEFAULT_RVA = 0xC28A8C  # bag15 (bag14 was 0xC2885C)


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wintypes.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
psapi.EnumProcessModulesEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD,
]
psapi.GetModuleInformation.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(MODULEINFO),
    wintypes.DWORD,
]
psapi.GetModuleFileNameExW.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.LPWSTR,
    wintypes.DWORD,
]
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]


def find_pid(name="MetroExodus.exe"):
    import os

    out = os.popen(f'tasklist /FI "IMAGENAME eq {name}" /FO CSV /NH').read()
    for line in out.splitlines():
        parts = [x.strip('"') for x in line.split('","')]
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[1])
    return None


def modules(pid):
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise OSError(ctypes.get_last_error())
    out = []
    arr = (ctypes.c_void_p * 4096)()
    need = wintypes.DWORD()
    if not psapi.EnumProcessModulesEx(
        h, arr, ctypes.sizeof(arr), ctypes.byref(need), 3
    ):
        raise OSError(ctypes.get_last_error())
    n = need.value // ctypes.sizeof(ctypes.c_void_p)
    for i in range(n):
        mi = MODULEINFO()
        if not psapi.GetModuleInformation(
            h, arr[i], ctypes.byref(mi), ctypes.sizeof(mi)
        ):
            continue
        buf = ctypes.create_unicode_buffer(512)
        if psapi.GetModuleFileNameExW(h, arr[i], buf, 512):
            out.append((buf.value, mi.lpBaseOfDll, mi.SizeOfImage))
    return h, out


def main():
    rva = int(sys.argv[1], 0) if len(sys.argv) > 1 else DEFAULT_RVA
    pid = int(sys.argv[2]) if len(sys.argv) > 2 else find_pid()
    if not pid:
        raise SystemExit("MetroExodus.exe not running")
    h, mods = modules(pid)
    target = None
    for path, base, size in mods:
        if path.lower().endswith("metroexodusvr.dll"):
            target = (path, base, size)
            break
    if not target:
        raise SystemExit("MetroExodusVR.dll not found in process")
    path, base, size = target
    print(f"pid {pid} module {path}")
    print(f"base {base:#x} size {size:#x} marker {base + rva:#x}")

    n = 0x2000
    buf = ctypes.create_string_buffer(n)
    rd = ctypes.c_size_t()
    addr = base + rva
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(rd)):
        raise SystemExit(f"ReadProcessMemory failed: {ctypes.get_last_error()}")
    b = buf.raw

    def d(o):
        return struct.unpack_from("<I", b, o)[0]

    def q(o):
        return struct.unpack_from("<Q", b, o)[0]

    def s(o, ln):
        return b[o : o + ln]

    def show(off, ln):
        v = d(off)
        txt = "" if v == 0xFFFFFFFF else f"  value={s(off + 4, min(ln, 16))!r}"
        return f"{v:#010x}{txt}"

    print(f"calls            = {d(0x0000)}")
    print(f"recs_copied      = {d(0x0020)}")
    print(f"matched          = {d(0x002C)}")
    print(f"vlen             = {d(0x1988)}")
    print(f"value            = {s(0x198C, 8)!r}")
    print(f"first_ctrl_vtbl  = {q(0x1998):#x}")
    print(f"records_found    = {d(0x19E8)}")
    print(f"tag              = {d(0x19E0):#010x}")
    print(f"ctrl_q60         = {d(0x19E4):#010x}")
    tail = [d(0x19EC + 4 * i) for i in range(6)]
    print("tail[+0x80..97]  = " + " ".join(f"{v:#010x}" for v in tail))
    print(f"seen_flag        = {d(0x1A0C)}")
    print(f"depth            = {d(0x1A14)}")
    print(f"reentry_hits     = {d(0x1A18)}")
    print(f"exe_base         = {q(0x1A1C):#x}")
    print(f"control          = {q(0x1A24):#x}")

    # live Fonts* registry
    fonts_ptr = q(0x1A2C)
    print(f"fonts_ptr        = {fonts_ptr:#x}")
    fonts = [d(0x1A34 + 4 * i) for i in range(8)]
    labels = ["pad", "regular", "arial", "menu", "console", "?", "?", "?"]
    for i, v in enumerate(fonts):
        print(f"  fonts[{i}] {labels[i]:<8} = {v:#010x}")

    print(f"rec_ptr_pre      = {q(0x1A54):#x}")
    print(f"bag_begin_pre    = {q(0x1BC8):#x}")
    print(f"bag_end_pre      = {q(0x1BD0):#x}")
    print(f"rec_kind_pre     = {b[0x1A60]}")
    print(
        f"rec_vlen_pre     = {int.from_bytes(b[0x1A60 + 0x70 : 0x1A60 + 0x78], 'little')}"
    )
    print(f"rec_value_pre    = {b[0x1A60 + 0x60 : 0x1A60 + 0x68]!r}")

    # resolver probe (bag12)
    print(f"res_menu         = {d(0x1BE4):#010x}")
    print(f"res_arial        = {d(0x1BE8):#010x}")
    print(f"res_regular      = {d(0x1BEC):#010x}")
    print(f"font_manager     = {q(0x1BF0):#x}")
    print(f"probes           = {d(0x1BF8)}")

    # bag15 §2.1: the working element vs ours
    print("--- A-0028 §2.1: local_text (working) ---")
    print(f"val_count        = {d(0x1C00)}")
    print(f"val_ctl          = {q(0x1C08):#x}")
    print(f"val_fn_len       = {show(0x1C10, 16)}")
    print(f"val_text_len     = {show(0x1C60, 16)}")
    so, ss = d(0x1C40), d(0x1C44)
    print(
        f"scan_work        = off {so:#x}"
        + (" (none)" if so == 0xFFFFFFFF else f", slot {ss} {labels[ss]}")
    )
    print("--- A-0028 §2.1: our matched caption ---")
    print(f"cap_seen         = {d(0x1C48)}")
    print(f"cap_fn_flag      = {d(0x1C4C)}")
    print(f"cap_fn_len       = {show(0x1C24, 16)}")
    so, ss = d(0x1C38), d(0x1C3C)
    print(
        f"scan_ours        = off {so:#x}"
        + (" (none)" if so == 0xFFFFFFFF else f", slot {ss} {labels[ss]}")
    )

    # dump the raw marker next to the repo for offline parsing
    from pathlib import Path

    out = Path(__file__).with_name("marker15.bin")
    out.write_bytes(b)
    print(f"raw -> {out}")


if __name__ == "__main__":
    main()
