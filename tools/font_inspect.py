"""Inspect the Metro ``fonts_*.bin`` reflection tree (fonts_ru/us)."""

import struct
import sys
import zlib
from pathlib import Path

EXE = r"F:\SteamLibrary\steamapps\common\Metro Exodus\MetroExodus.exe"
ROOT = Path(__file__).resolve().parent.parent


def crc32(s):
    return zlib.crc32(s.encode()) & 0xFFFFFFFF


def read_exe():
    d = Path(EXE).read_bytes()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    n = struct.unpack_from("<H", d, pe + 6)[0]
    opt = struct.unpack_from("<H", d, pe + 20)[0]
    so = pe + 24 + opt
    secs = []
    for i in range(n):
        o = so + 40 * i
        vs, va, rs, raw = struct.unpack_from("<IIII", d, o + 8)
        secs.append((va, vs, raw, rs))
    return d, secs


def exe_rva_to_off(secs, rva):
    for va, vs, raw, rs in secs:
        if va <= rva < va + max(vs, rs):
            return raw + (rva - va)
    return None


def cstr(d, off):
    e = d.index(b"\0", off)
    return d[off:e].decode("latin-1")


def main():
    d, secs = read_exe()
    targets = [
        0x14805FC,
        0x14805F8,
        0x1480678,
        0x1480694,
        0x14806A0,
        0x14806A8,
        0x14806B4,
        0x1480A0B,
    ]
    print("candidate metric field names:")
    for t in targets:
        o = exe_rva_to_off(secs, t)
        print(f"  {t:#x} -> {cstr(d, o) if o else '?'}")

    # discover from the disassembly lea targets directly
    import subprocess

    dis = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "exe_disasm.py"), "0xdc41d0", "0xdc4280"],
        capture_output=True,
        text=True,
    ).stdout
    print(dis)


if __name__ == "__main__":
    main()
