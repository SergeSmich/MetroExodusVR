"""Dump and compare the live font objects behind the Fonts slots.

The slots are refs (bank << 24) | off into the interner; the node header is
next@0x00, refcount@0x08, bank@0x12, name@0x14.  Somewhere in the node (or in
the object it points to) sits the glyph table that turns a charmap byte into a
glyph: arial's is ASCII-only, menu's has Cyrillic.  Comparing the two dumps
shows which field that is.

    python work/live_font_obj.py
"""

import ctypes
import sys
from ctypes import wintypes

import psutil

TABLE_RVA = 0x175F140
FONTS_PTR_RVA = 0x1733260
SLOTS = [("regular", 0x04), ("arial", 0x08), ("menu", 0x0C), ("console", 0x10)]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]


def find_pid():
    for p in psutil.process_iter(["pid", "name"]):
        if (p.info["name"] or "").lower() == "metroexodus.exe":
            return p.pid
    return 0


def main(argv):
    size = int(argv[1], 0) if len(argv) > 1 else 0x180
    pid = find_pid()
    if not pid:
        print("no MetroExodus.exe")
        return 2
    h = k32.OpenProcess(0x0410, False, pid)
    if not h:
        print("OpenProcess failed")
        return 3

    def rd(addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(
            h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)
        ):
            return b""
        return buf.raw[: got.value]

    arr = (wintypes.HMODULE * 1024)()
    need = wintypes.DWORD()
    k32.K32EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(need), 0x03)
    base = int(arr[0] or 0)
    fonts = int.from_bytes(rd(base + FONTS_PTR_RVA, 8), "little")
    table = base + TABLE_RVA
    print(f"pid {pid} exe {base:#x} Fonts {fonts:#x} table {table:#x}")

    nodes = {}
    for name, off in SLOTS:
        ref = int.from_bytes(rd(fonts + off, 4), "little")
        if not ref:
            continue
        idx, delta = ref >> 24, ref & 0xFFFFFF
        bank = int.from_bytes(rd(table + idx * 8, 8), "little")
        node = bank + delta
        nodes[name] = node
        print(f"  {name:<8} ref {ref:#010x} bank {bank:#014x} node {node:#014x}")

    for name in ("arial", "menu"):
        node = nodes.get(name)
        if not node:
            continue
        blob = rd(node, size)
        print(f"\n=== {name} node {node:#014x} ({len(blob)} B) ===")
        for row in range(0, len(blob), 16):
            chunk = blob[row : row + 16]
            words = " ".join(
                f"{int.from_bytes(chunk[i : i + 4], 'little'):08x}"
                for i in range(0, 16, 4)
            )
            print(f"  +{row:03x}  {chunk.hex(' '):<48} {words}")

        print(f"  --- {name}: pointers and what they point at ---")
        for row in range(0, len(blob), 8):
            q = int.from_bytes(blob[row : row + 8], "little")
            if not 0x10000 < q < 0x7FFFFFFFFFFF:
                continue
            head = rd(q, 0x40)
            if not head:
                continue
            print(f"  +{row:03x} -> {q:#014x}  {head[:32].hex(' ')}")
            print(
                "        q: "
                + " ".join(
                    f"{int.from_bytes(head[i : i + 8], 'little'):#x}"
                    for i in range(0, 0x20, 8)
                )
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
