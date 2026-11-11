"""Read the A-0033 probe marker out of the live game.

The 0.9.1 cave writes its findings into MetroExodusVR.dll + marker RVA:

    python work/probe_marker.py 0xbf50ac

Fields are the ones A-0033 §4 lists, plus the raw dumps: the two 0x20 copies
of the Fonts array, the bank table, the four font nodes and the first 0x100
bytes of a caption control and of a local_text control.
"""

import ctypes
import sys
from ctypes import wintypes

import psutil

DEFAULT_RVA = 0xBF50AC

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

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
    ctypes.c_void_p,
    wintypes.DWORD,
]
psapi.GetModuleBaseNameW.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.LPWSTR,
    wintypes.DWORD,
]


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wintypes.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


def find_pid():
    for p in psutil.process_iter(["pid", "name"]):
        if (p.info["name"] or "").lower() == "metroexodus.exe":
            return p.pid
    return 0


def module_base(h, name):
    arr = (wintypes.HMODULE * 1024)()
    need = wintypes.DWORD()
    if not psapi.EnumProcessModulesEx(
        h, arr, ctypes.sizeof(arr), ctypes.byref(need), 0x03
    ):
        raise OSError(ctypes.get_last_error(), "EnumProcessModulesEx")
    count = need.value // ctypes.sizeof(wintypes.HMODULE)
    for i in range(count):
        buf = ctypes.create_unicode_buffer(260)
        if not psapi.GetModuleBaseNameW(h, arr[i], buf, 260):
            continue
        if buf.value.lower() == name.lower():
            mi = MODULEINFO()
            psapi.GetModuleInformation(h, arr[i], ctypes.byref(mi), ctypes.sizeof(mi))
            return int(mi.lpBaseOfDll or 0)
    return 0


def main(argv):
    rva = int(argv[1], 16) if len(argv) > 1 else DEFAULT_RVA
    pid = find_pid()
    if not pid:
        print("no MetroExodus.exe")
        return 2
    h = k32.OpenProcess(0x0410, False, pid)
    if not h:
        print(f"OpenProcess failed {ctypes.get_last_error()}")
        return 3

    def rd(addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(
            h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)
        ):
            return b""
        return buf.raw[: got.value]

    dll = module_base(h, "MetroExodusVR.dll")
    exe = module_base(h, "MetroExodus.exe")
    print(f"pid {pid} exe {exe:#x} dll {dll:#x} marker {dll + rva:#x}")
    if not dll:
        return 4

    def u32(off):
        return int.from_bytes(rd(dll + rva + off, 4), "little")

    def u64(off):
        return int.from_bytes(rd(dll + rva + off, 8), "little")

    tagged = [
        (0x1C70, "write_calls"),
        (0x1C74, "write_ok"),
        (0x1C78, "write_fail"),
        (0x1C7C, "write_last"),
        (0x1A1C, "exe_base64"),
        (0x1A2C, "fonts_ptr64"),
        (0x2180, "SUBST_CTLS"),
        (0x2184, "SUBST_FOUND"),
        (0x2188, "SUBST_FIRST"),
        (0x218C, "SUBST_LAST"),
        (0x2190, "SUBST_WRITES"),
        (0x2194, "SUBST_NOREF"),
        (0x2198, "SWAP_FIXES"),
        (0x219C, "STATIC_DONE"),
        (0x21A0, "CTL_FLAGS"),
    ]
    for off, label in tagged:
        if off >= 0x1A00 and off < 0x1C00 and off in (0x1A1C, 0x1A2C):
            val = u64(off)
        else:
            val = u32(off)
        print(f"  +{off:#06x} {label:<12} {val:#x} ({val})")

    print("  Fonts inline  " + rd(dll + rva + 0x1F00, 0x20).hex(" "))
    print("  Fonts deref   " + rd(dll + rva + 0x1F20, 0x20).hex(" "))
    print(f"  Fonts pointer {u64(0x1F40):#x}")

    banks = rd(dll + rva + 0x1F80, 0x100)
    print("  banks:")
    for i in range(32):
        q = int.from_bytes(banks[i * 8 : i * 8 + 8], "little")
        if q:
            print(f"    [{i:02x}] {q:#014x}")

    print("  nodes:")
    for i, slot in enumerate(("regular", "arial", "menu", "console")):
        base = 0x2080 + i * 0x40
        node = u64(base)
        refc = u32(base + 8)
        nlen = u32(base + 0xC)
        name = rd(dll + rva + base + 0x10, 32).split(b"\x00")[0]
        print(
            f"    {slot:<8} node {node:#014x} refc {refc:#x} nlen {nlen:#x} "
            f"name {name!r}"
        )

    def node_name(ref):
        """Decode (bank << 24) | off into the name stored at bank + off."""
        idx, delta = ref >> 24, ref & 0xFFFFFF
        if idx > 31:
            return None
        bank = int.from_bytes(banks[idx * 8 : idx * 8 + 8], "little")
        if not bank:
            return None
        blob = rd(bank + delta, 0x40)
        if len(blob) < 0x34:
            return None
        name = blob[0x14:0x34].split(b"\x00")[0]
        if not name or len(name) > 24:
            return None
        if not all(0x20 <= b < 0x7F for b in name):
            return None
        return name.decode("ascii")

    for off, label in ((0x1D00, "caption control"), (0x1E00, "local_text control")):
        blob = rd(dll + rva + off, 0x100)
        print(f"  {label} ({len(blob)} B):")
        for row in range(0, 0x100, 16):
            chunk = blob[row : row + 16]
            words = " ".join(
                f"{int.from_bytes(chunk[i : i + 4], 'little'):08x}"
                for i in range(0, 16, 4)
            )
            print(f"    +{row:03x}  {chunk.hex(' '):<48} {words}")
        print(f"  {label}: ref-like dwords")
        for row in range(0, 0x100, 4):
            ref = int.from_bytes(blob[row : row + 4], "little")
            if ref == 0:
                continue
            name = node_name(ref) if ref else None
            if name:
                print(f"    +{row:03x} {ref:#010x} -> node {name!r}")

    print("  slots decoded:")
    for base in (0x1F00, 0x1F20):
        for slot_off, slot in (
            (0x04, "regular"),
            (0x08, "arial"),
            (0x0C, "menu"),
            (0x10, "console"),
        ):
            ref = int.from_bytes(rd(dll + rva + base + slot_off, 4), "little")
            name = node_name(ref) if ref else None
            print(f"    copy {base:#06x} {slot:<8} {ref:#010x} -> {name!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
