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


def base_via_psapi(h):
    """Main module base via K32EnumProcessModulesEx (module 0 is the exe)."""
    LIST_MODULES_ALL = 0x03
    arr = (wintypes.HMODULE * 1024)()
    need = wintypes.DWORD()
    if not k32.K32EnumProcessModulesEx(
        h, arr, ctypes.sizeof(arr), ctypes.byref(need), LIST_MODULES_ALL
    ):
        raise OSError(ctypes.get_last_error(), "K32EnumProcessModulesEx")
    if not need.value:
        return 0
    return int(arr[0] or 0)


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

    h = None
    while not h and time.time() - t0 < timeout:
        h = k32.OpenProcess(ACCESS, False, pid)
        if not h:
            time.sleep(0.03)
    if not h:
        log(f"OpenProcess failed {ctypes.get_last_error()}")
        return 4

    base = 0
    tries = 0
    while not base and time.time() - t0 < timeout:
        tries += 1
        try:
            base = base_via_psapi(h)
        except OSError as exc:
            if tries % 20 == 1:
                log(f"module list not ready ({tries}): {exc}")
            base = 0
        if not base:
            time.sleep(0.03)
    if not base:
        log("module base not found")
        k32.CloseHandle(h)
        return 3

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

        before = check_sites(h, base)
        log(f"exe base {base:#x}")
        for rva, cur, want in before:
            log(
                f"  {rva:#08x} {cur.hex(' ')} (want {want.hex(' ')}) "
                f"{'ok' if cur == want else 'MISMATCH'}"
            )
        keep_rva, keep_cur, keep_want = check_keep(h, base)
        log(
            f"  {keep_rva:#08x} {keep_cur.hex(' ')} (want {keep_want.hex(' ')}) "
            f"{'ok' if keep_cur == keep_want else 'note: reference site differs'}"
        )

        if verify_only:
            return 0

        if not all(cur == want for _rva, cur, want in before):
            log("unexpected bytes, refusing to patch")
            return 5

        for rva, orig, idx in SITES:
            write(h, base + rva + idx, bytes([NEW_DISP]))
            log(f"patched {rva:#08x}+{idx}: {orig[idx]:#04x} -> {NEW_DISP:#04x}")

        after = check_after(h, base)
        good = all(cur == want for _rva, cur, want in after)
        for rva, cur, want in after:
            log(
                f"  {rva:#08x} {cur.hex(' ')} (want {want.hex(' ')}) "
                f"{'ok' if cur == want else 'FAIL'}"
            )
        log("result " + ("PATCHED" if good else "VERIFY FAILED"))
        return 0 if good else 6
    finally:
        k32.CloseHandle(h)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
