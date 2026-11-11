"""Keep a font-slot alias alive in the running MetroExodus process.

Live experiment: copy one of the four interned font references inside the
*Fonts* singleton over another one, every few milliseconds, so a rebuild of
the registry cannot take it back.

    python work/live_bind_font.py --slot 8 --source 0xc --seconds 20

slot/source are byte offsets inside the Fonts object:
    0x04 regular   0x08 arial   0x0c menu   0x10 console

Address of the Fonts pointer: exe base + 0x1733260 (the accessor 0x39B720
returns the object itself, the pointer is stored next to it).
"""

import ctypes
import sys
import time
from ctypes import wintypes

import psutil

FONTS_PTR_RVA = 0x1733260

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.VirtualProtectEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]

ACCESS = 0x0400 | 0x0010 | 0x0020 | 0x0008


def find_pid():
    for p in psutil.process_iter(["pid", "name"]):
        if (p.info["name"] or "").lower() == "metroexodus.exe":
            return p.pid
    return 0


def base_of(h):
    arr = (wintypes.HMODULE * 1024)()
    need = wintypes.DWORD()
    if not k32.K32EnumProcessModulesEx(
        h, arr, ctypes.sizeof(arr), ctypes.byref(need), 0x03
    ):
        raise OSError(ctypes.get_last_error(), "K32EnumProcessModulesEx")
    return int(arr[0] or 0)


def rd(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        raise OSError(ctypes.get_last_error(), f"read {addr:#x}")
    return buf.raw[: got.value]


def wr(h, addr, blob):
    buf = ctypes.create_string_buffer(blob, len(blob))
    done = ctypes.c_size_t()
    if not k32.WriteProcessMemory(
        h, ctypes.c_void_p(addr), buf, len(blob), ctypes.byref(done)
    ):
        raise OSError(ctypes.get_last_error(), f"write {addr:#x}")


def main(argv):
    slot, source, seconds, wait = 8, 0x0C, 20.0, 0.0
    for i, a in enumerate(argv):
        if a == "--slot":
            slot = int(argv[i + 1], 0)
        elif a == "--source":
            source = int(argv[i + 1], 0)
        elif a == "--seconds":
            seconds = float(argv[i + 1])
        elif a == "--wait":
            wait = float(argv[i + 1])

    pid = 0
    t0 = time.time()
    while True:
        pid = find_pid()
        if pid or time.time() - t0 >= wait:
            break
        time.sleep(0.05)
    if not pid:
        print("no MetroExodus.exe")
        return 2
    print(f"process found after {time.time() - t0:.2f}s")
    h = k32.OpenProcess(ACCESS, False, pid)
    if not h:
        print(f"OpenProcess failed {ctypes.get_last_error()}")
        return 3
    try:
        base = base_of(h)
        ptr_addr = base + FONTS_PTR_RVA
        while time.time() - t0 < wait + seconds:
            fonts = int.from_bytes(rd(h, ptr_addr, 8), "little")
            if 0x10000 < fonts < 0x7FFFFFFFFFFF:
                break
            time.sleep(0.02)
        else:
            print("Fonts pointer never became valid")
            return 4
        src = int.from_bytes(rd(h, fonts + source, 4), "little")
        print(f"pid {pid} exe {base:#x} Fonts {fonts:#x}")
        print(f"source Fonts+{source:#x} = {src:#010x}")
        if not src:
            print("source ref is 0, nothing to copy")
            return 5

        old = wintypes.DWORD()
        page = (fonts + slot) & ~0xFFF
        k32.VirtualProtectEx(h, ctypes.c_void_p(page), 0x2000, 0x04, ctypes.byref(old))
        try:
            t0 = time.time()
            writes = 0
            while time.time() - t0 < seconds:
                if writes and writes % 40 == 0:
                    cur = int.from_bytes(rd(h, fonts + source, 4), "little")
                    if cur:
                        src = cur
                wr(h, fonts + slot, src.to_bytes(4, "little"))
                writes += 1
                time.sleep(0.005)
        finally:
            tmp = wintypes.DWORD()
            k32.VirtualProtectEx(
                h, ctypes.c_void_p(page), 0x2000, old.value, ctypes.byref(tmp)
            )

        print(f"wrote {writes} times")
        print(
            "final Fonts: "
            + " ".join(
                f"+{o:#04x}={int.from_bytes(rd(h, fonts + o, 4), 'little'):#010x}"
                for o in (0x04, 0x08, 0x0C, 0x10)
            )
        )
        return 0
    finally:
        k32.CloseHandle(h)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
