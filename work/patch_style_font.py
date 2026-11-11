"""Patch the *live* MetroExodus.exe image so the default UI style takes the
`menu` font reference instead of the (empty) `regular` one.

Hypothesis being tested (L-0035 / A-0027 follow-up):

    style ctor  exe 0x4bbd90
        0x4bc0f2  call Fonts::Get()      -> rax = &Fonts
        0x4bc0fb  lea  rdx, [rax + 4]    -> &Fonts.regular   (== 0 at runtime)
        0x4bc0ff  call 0x6ac40           -> copy ref into [style+0x08], [style+0x10]
        0x4bc104  call Fonts::Get()
        0x4bc10d  lea  rdx, [rax + 4]    -> same empty ref into [style+0x18]
        0x4bc121  call Fonts::Get()
        0x4bc126  lea  rdx, [rax + 0xc]  -> &Fonts.menu     (Cyrillic font, ru)

so the style gets a null font reference and every control draws with the
identity glyph table.  Changing the displacement of the two `lea rdx,[rax+4]`
instructions from 0x04 to 0x0c (menu) should be enough to see Cyrillic.

The file on disk is not touched: the patch is two bytes inside the mapped
image (VirtualProtectEx on the .text page, write, restore, FlushInstructionCache)
and it is gone as soon as the game exits.

Usage:
    python work/patch_style_font.py            # wait for the game, then patch
    python work/patch_style_font.py --timeout 300
    python work/patch_style_font.py --verify-only
"""

import ctypes
import sys
import time
from ctypes import wintypes

import psutil

# rva, original 4 bytes (lea rdx, [rax+4]), byte index of the displacement
SITES = [
    (0x4BC0FB, b"\x48\x8d\x50\x04", 3),
    (0x4BC10D, b"\x48\x8d\x50\x04", 3),
]
# untouched reference site: already `lea rdx,[rax+0xc]`
KEEP = (0x4BC12A, b"\x48\x8d\x50\x0c")
NEW_DISP = 0x0C

PROCESS_NAME = "metroexodus.exe"
MODULE_NAME = "metroexodus.exe"

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.WriteProcessMemory.restype = wintypes.BOOL
k32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.VirtualProtectEx.restype = wintypes.BOOL
k32.VirtualProtectEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
k32.FlushInstructionCache.restype = wintypes.BOOL
k32.FlushInstructionCache.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    ctypes.c_size_t,
]

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PAGE_EXECUTE_READWRITE = 0x40

ACCESS = (
    PROCESS_QUERY_INFORMATION
    | PROCESS_VM_READ
    | PROCESS_VM_WRITE
    | PROCESS_VM_OPERATION
)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def find_game():
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if (p.info["name"] or "").lower() == PROCESS_NAME:
                return p
        except psutil.Error:
            continue
    return None


def base_via_toolhelp(pid):
    """Module base through TH32CS_SNAPMODULE (no extra dependency)."""
    TH32CS_SNAPMODULE = 0x00000008
    TH32CS_SNAPMODULE32 = 0x00000010
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class MODULEENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("th32ModuleID", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("GlblcntUsage", wintypes.DWORD),
            ("ProccntUsage", wintypes.DWORD),
            ("modBaseAddr", ctypes.c_void_p),
            ("modBaseSize", wintypes.DWORD),
            ("hModule", wintypes.HMODULE),
            ("szModule", wintypes.WCHAR * 256),
            ("szExePath", wintypes.WCHAR * 260),
        ]

    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    k32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]

    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == INVALID_HANDLE_VALUE or not snap:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot")
    try:
        me = MODULEENTRY32W()
        me.dwSize = ctypes.sizeof(MODULEENTRY32W)
        ok = k32.Module32FirstW(snap, ctypes.byref(me))
        while ok:
            if me.szModule.lower() == MODULE_NAME:
                return int(me.modBaseAddr or 0), me.modBaseSize
            ok = k32.Module32NextW(snap, ctypes.byref(me))
    finally:
        k32.CloseHandle(snap)
    return None, 0


def read(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        raise OSError(ctypes.get_last_error(), f"ReadProcessMemory {addr:#x}")
    return buf.raw[: got.value]


def write(h, addr, blob, page_mask=True):
    buf = ctypes.create_string_buffer(blob, len(blob))
    if page_mask:
        page = addr & ~0xFFF
        span = ((addr + len(blob) - 1) & ~0xFFF) - page + 0x1000
        old = wintypes.DWORD()
        if not k32.VirtualProtectEx(
            h, ctypes.c_void_p(page), span, PAGE_EXECUTE_READWRITE, ctypes.byref(old)
        ):
            raise OSError(ctypes.get_last_error(), "VirtualProtectEx")
        try:
            done = ctypes.c_size_t()
            if not k32.WriteProcessMemory(
                h, ctypes.c_void_p(addr), buf, len(blob), ctypes.byref(done)
            ):
                raise OSError(ctypes.get_last_error(), f"WriteProcessMemory {addr:#x}")
        finally:
            tmp = wintypes.DWORD()
            k32.VirtualProtectEx(
                h, ctypes.c_void_p(page), span, old.value, ctypes.byref(tmp)
            )
            k32.FlushInstructionCache(h, ctypes.c_void_p(addr), len(blob))
        return
    done = ctypes.c_size_t()
    if not k32.WriteProcessMemory(
        h, ctypes.c_void_p(addr), buf, len(blob), ctypes.byref(done)
    ):
        raise OSError(ctypes.get_last_error(), f"WriteProcessMemory {addr:#x}")


def check_sites(h, base):
    report = []
    for rva, orig, _idx in SITES:
        report.append((rva, read(h, base + rva, 4), orig))
    return report


def check_after(h, base):
    report = []
    for rva, orig, _idx in SITES:
        report.append((rva, read(h, base + rva, 4), orig[:3] + bytes([NEW_DISP])))
    return report


def check_keep(h, base):
    rva, orig = KEEP
    return rva, read(h, base + rva, 4), orig


def main(argv):
    timeout = 300
    verify_only = "--verify-only" in argv
    for i, a in enumerate(argv):
        if a == "--timeout" and i + 1 < len(argv):
            timeout = int(argv[i + 1])

    t0 = time.time()
    proc = None
    while time.time() - t0 < timeout:
        proc = find_game()
        if proc is not None:
            break
        time.sleep(0.05)
    if proc is None:
        log(f"no {PROCESS_NAME} within {timeout}s")
        return 2

    pid = proc.pid
    log(f"pid {pid} appeared after {time.time() - t0:.2f}s")

    base = None
    while base is None and time.time() - t0 < timeout:
        try:
            base, size = base_via_toolhelp(pid)
        except OSError as exc:
            log(f"module list not ready: {exc}")
            base = None
            time.sleep(0.05)
    if base is None:
        log("module base not found")
        return 3

    h = k32.OpenProcess(ACCESS, False, pid)
    if not h:
        log(f"OpenProcess failed {ctypes.get_last_error()}")
        return 4
    try:
        # Wait until the .text page holds the expected bytes (image mapped but
        # still being relocated) - usually instant after the module appears.
        for _ in range(200):
            try:
                ok = read(h, base + SITES[0][0], 4) == SITES[0][1]
            except OSError:
                ok = False
            if ok:
                break
            time.sleep(0.02)

        before = check_sites(h, base, expect_new=False)
        log(f"exe base {base:#x}  size {size:#x}")
        for rva, cur, want, ok in before:
            log(
                f"  {rva:#08x} {cur.hex(' ')} (want {want.hex(' ')}) {'ok' if ok else 'MISMATCH'}"
            )

        if verify_only:
            return 0

        if not all(ok for _rva, _cur, _want, ok in before):
            log("unexpected bytes, refusing to patch")
            return 5

        for rva, orig, idx in SITES:
            write(h, base + rva + idx, bytes([NEW_DISP]))
            log(f"patched {rva:#08x}+{idx}: {orig[idx]:#04x} -> {NEW_DISP:#04x}")

        after = check_sites(h, base, expect_new=True)
        good = all(ok for _rva, _cur, _want, ok in after)
        for rva, cur, want, ok in after:
            log(
                f"  {rva:#08x} {cur.hex(' ')} (want {want.hex(' ')}) {'ok' if ok else 'FAIL'}"
            )
        log("result " + ("PATCHED" if good else "VERIFY FAILED"))
        return 0 if good else 6
    finally:
        k32.CloseHandle(h)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
