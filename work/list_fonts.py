"""Enumerate live font names from the exe font manager (read-only).

Manager layout (exe 0xab20d0 / 0xab2310):
  [manager + idx*8]            node head, idx = hash % 0x4115
  [manager + 0x208a8 + b*4]    129 locks
  [manager + 0x20ab0]          129 * 16 byte buckets
node:
  +0x00 next, +0x08 refcount, +0x0c hash, +0x10 name len (u16),
  +0x12 flag, +0x13 bank byte, +0x14 name bytes
Handle = (bank << 24) | (node_va - bank_base[bank]), bank_base at exe+0x175f140.
"""

import ctypes
import struct
import sys
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wintypes.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
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


def find_pid(name="MetroExodus.exe"):
    import os

    out = os.popen(f'tasklist /FI "IMAGENAME eq {name}" /FO CSV /NH').read()
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == name.lower():
            return int(parts[1])
    return None


def open_proc(pid):
    return k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)


def modules(h):
    need = wintypes.DWORD()
    arr = (ctypes.c_void_p * 1024)()
    if not psapi.EnumProcessModulesEx(
        h, arr, ctypes.sizeof(arr), ctypes.byref(need), 3
    ):
        raise OSError("EnumProcessModulesEx")
    out = []
    for i in range(need.value // ctypes.sizeof(ctypes.c_void_p)):
        mi = MODULEINFO()
        if not psapi.GetModuleInformation(
            h, arr[i], ctypes.byref(mi), ctypes.sizeof(mi)
        ):
            continue
        buf = ctypes.create_unicode_buffer(512)
        psapi.GetModuleFileNameExW(h, arr[i], buf, 512)
        out.append((buf.value, mi.lpBaseOfDll, mi.SizeOfImage))
    return out


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "MetroExodus.exe"
    pid = find_pid(name)
    if pid is None:
        raise SystemExit(f"no process {name}")
    h = open_proc(pid)
    if not h:
        raise SystemExit("OpenProcess failed")

    def read(addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(
            h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)
        ):
            return None
        return buf.raw[: got.value]

    mods = modules(h)
    exe = None
    for path, base, size in mods:
        if path.lower().endswith("\\metroexodus.exe"):
            exe = (base, size, path)
    if exe is None:
        raise SystemExit("exe module not found")
    base = exe[0]
    print(f"pid {pid} exe base {base:#x}")

    ptr = read(base + 0x175F138, 8)
    if ptr is None:
        raise SystemExit("manager pointer unreadable")
    mgr = struct.unpack("<Q", ptr)[0]
    print(f"manager          = {mgr:#x}")
    if not mgr:
        raise SystemExit("manager is null (font system not created)")

    banks = []
    for i in range(8):
        v = read(base + 0x175F140 + i * 8, 8)
        banks.append(struct.unpack("<Q", v)[0] if v else 0)
    print("bank bases       = " + " ".join(f"{b:#x}" for b in banks))

    total = 0
    names = []
    for idx in range(0x4115):
        p = read(mgr + idx * 8, 8)
        if not p:
            continue
        node = struct.unpack("<Q", p)[0]
        while node:
            hdr = read(node, 0x14)
            if hdr is None:
                break
            nxt, refcnt, hashv, nlen, flag, bank = struct.unpack("<QIIHBB", hdr)
            if nlen > 0x100:
                print(f"  suspicious node {node:#x} len={nlen}")
                break
            raw = read(node + 0x14, nlen + 1) or b""
            s = raw.split(b"\x00")[0]
            names.append((s, bank, node, hashv, refcnt, idx))
            total += 1
            node = nxt

    print(f"nodes            = {total}")
    for s, bank, node, hashv, refcnt, idx in sorted(names):
        try:
            txt = s.decode("ascii")
        except UnicodeDecodeError:
            txt = s.decode("latin-1")
        print(
            f"  bank={bank} slot={idx:#06x} node={node:#x} ref={refcnt} "
            f"hash={hashv:#010x} {txt!r}"
        )


if __name__ == "__main__":
    main()
