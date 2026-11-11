"""Read the caption-font-hook marker out of a live MetroExodus process.

The cave writes its counters into MetroExodusVR.dll + marker RVA.  Reading it
while the game is up is the only way to tell "the write never happened" from
"the engine ignored the new font" without another round through the chat.

The marker RVA moves with the cave options (it sits after the code), so the
build prints it ("marker +0x...").  Defaults: 0xBF4DAC for the property-only
build, 0xBF4D8C for the ``--swap-arial-slot`` build.  Override on the command
line: ``python work/marker_live.py <hex-rva>``.
"""

import ctypes
import struct
import sys
from ctypes import wintypes

import psutil

MARKER_RVA = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0xBF4D8C

FIELDS = [
    (0x1C00, "<I", "probe_calls"),
    (0x1C08, "<Q", "val_ctl"),
    (0x1C10, "<I", "found_any"),
    (0x1C14, "<I", "set_ok_any"),
    (0x1C40, "<I", "res_menu"),
    (0x1C44, "<I", "res_ok"),
    (0x1C48, "<I", "res_flag48"),
    (0x1C60, "<I", "val_text_len"),
    (0x1C64, "<Q", "val_q64"),
    (0x1C6C, "<Q", "val_q6c"),
    (0x1C70, "<I", "set_calls"),
    (0x1C74, "<I", "set_ok"),
    (0x1C78, "<I", "set_fail"),
    (0x1C7C, "<I", "set_last"),
    (0x1C80, "<I", "swap_done"),
    (0x1C84, "<I", "swap_old_ref"),
    (0x1C88, "<I", "swap_new_ref"),
    (0x1A1C, "<Q", "exe_base"),
    (0x1A2C, "<Q", "fonts_ptr"),
    (0x1A34, "<I", "font_h0_regular?"),
    (0x1A38, "<I", "font_h1_arial?"),
    (0x1A3C, "<I", "font_h2_menu?"),
    (0x1A40, "<I", "font_h3_console?"),
]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.CloseHandle.argtypes = [wintypes.HANDLE]

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


def find_game():
    for p in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if (p.info["name"] or "").lower() == "metroexodus.exe":
                return p
        except psutil.Error:
            continue
    return None


def module_base(proc, needle="metroexodusvr.dll"):
    try:
        for m in proc.memory_maps(grouped=False):
            path = (getattr(m, "path", "") or "").lower()
            if path.endswith(needle):
                return int(m.addr.split("-")[0], 16)
    except psutil.Error:
        pass
    # fallback: enumerate with the toolhelp snapshot (handles truncated by
    # ctypes as long as argtypes are set, which was the old probe bug)
    return None


def toolhelp_base(pid, needle="metroexodusvr.dll"):
    TH32CS_SNAPMODULE = 0x8
    TH32CS_SNAPMODULE32 = 0x10

    class MODULEENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("th32ModuleID", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("GlblcntUsage", wintypes.DWORD),
            ("ProccntUsage", wintypes.DWORD),
            ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
            ("modBaseSize", wintypes.DWORD),
            ("hModule", wintypes.HMODULE),
            ("szModule", ctypes.c_char * 256),
            ("szExePath", ctypes.c_char * 260),
        ]

    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Module32First.restype = wintypes.BOOL
    k32.Module32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
    k32.Module32Next.restype = wintypes.BOOL
    k32.Module32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]

    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == wintypes.HANDLE(-1).value:
        return None
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(me)
        ok = k32.Module32First(snap, ctypes.byref(me))
        while ok:
            if me.szModule.decode("mbcs", "replace").lower() == needle:
                return ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value
            ok = k32.Module32Next(snap, ctypes.byref(me))
    finally:
        k32.CloseHandle(snap)
    return None


def main():
    proc = find_game()
    if not proc:
        print("no MetroExodus.exe")
        return 1
    base = module_base(proc) or toolhelp_base(proc.pid)
    if not base:
        print(f"pid {proc.pid}: MetroExodusVR.dll not found")
        return 1
    print(f"pid {proc.pid}  dll base {base:#x}  marker {base + MARKER_RVA:#x}")

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, proc.pid)
    if not h:
        print(f"OpenProcess failed: {ctypes.get_last_error()}")
        return 1
    try:
        buf = ctypes.create_string_buffer(0x1D00)
        got = ctypes.c_size_t(0)
        ok = k32.ReadProcessMemory(
            h, ctypes.c_void_p(base + MARKER_RVA), buf, len(buf), ctypes.byref(got)
        )
        if not ok:
            print(f"ReadProcessMemory failed: {ctypes.get_last_error()}")
            return 1
        raw = buf.raw[: got.value]
        print(f"read {len(raw)} bytes")
        head = struct.unpack_from("<8I", raw, 0)
        print("head dwords: " + " ".join(f"{v:#x}" for v in head))
        for off, fmt, name in FIELDS:
            size = struct.calcsize(fmt)
            val = struct.unpack_from(fmt, raw, off)[0]
            print(f"  +{off:#06x}  {name:<14} {val:#x}  ({val})")

        # whatever else is non-zero in the counter area, as dwords
        print("dwords +0x1c00..+0x1c80:")
        for off in range(0x1C00, 0x1C90, 0x10):
            row = struct.unpack_from("<4I", raw, off)
            if any(row):
                print(f"  +{off:#06x}  " + " ".join(f"{v:#010x}" for v in row))
    finally:
        k32.CloseHandle(h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
