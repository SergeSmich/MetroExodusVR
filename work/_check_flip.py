"""Verify in the live process that the init cave flipped the kind-4 slot.

Read-only: OpenProcess + ReadProcessMemory, no writes, no input.

    python work/_check_flip.py
"""

import ctypes
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010


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


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def find_pid(name="MetroExodus.exe"):
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(pe)
    ok = k32.Process32FirstW(snap, ctypes.byref(pe))
    while ok:
        if pe.szExeFile.lower() == name.lower():
            k32.CloseHandle(snap)
            return int(pe.th32ProcessID)
        ok = k32.Process32NextW(snap, ctypes.byref(pe))
    k32.CloseHandle(snap)
    return None


def modules(pid):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    me = MODULEENTRY32W()
    me.dwSize = ctypes.sizeof(me)
    out = []
    ok = k32.Module32FirstW(snap, ctypes.byref(me))
    while ok:
        out.append(
            (me.szModule, int(me.modBaseAddr), int(me.modBaseSize), me.szExePath)
        )
        ok = k32.Module32NextW(snap, ctypes.byref(me))
    k32.CloseHandle(snap)
    return out


def read(h, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(
        h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)
    ):
        raise OSError(ctypes.get_last_error())
    return bytes(buf[: got.value])


def main():
    pid = find_pid()
    if not pid:
        print("MetroExodus.exe not running")
        return 1
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print("OpenProcess failed", ctypes.get_last_error())
        return 1
    mods = modules(pid)
    exe = [m for m in mods if m[0].lower() == "metroexodus.exe"][0]
    dll = [m for m in mods if m[0].lower() == "metroexodusvr.dll"]
    print(f"pid {pid} exe base {exe[1]:#x} size {exe[2]:#x}")
    print("mod dll:", dll[0][1:4] if dll else "NOT LOADED")
    base = exe[1]
    for name, rva in (
        ("table+0", 0xB8DC60),
        ("kind4 slot", 0xB8DC70),
        ("kind6 code", 0xB8DBE9),
    ):
        val = int.from_bytes(read(h, base + rva, 4), "little")
        print(f"  {name:12s} exe+{rva:#x} = {val:#x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
