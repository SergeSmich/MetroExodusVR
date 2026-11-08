"""Dump font descriptors from Metro ``fonts_*.bin`` (names, floats, tcmap)."""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def chunks(d):
    pos = 1
    out = []
    while pos + 8 <= len(d):
        cid, size = struct.unpack_from("<II", d, pos)
        pos += 8
        out.append((cid, pos, size))
        pos += size
    return out


def strings(d, off, size):
    n = struct.unpack_from("<I", d, off)[0]
    p = off + 4
    out = []
    for _ in range(n):
        e = d.index(b"\0", p)
        out.append(d[p:e].decode("latin-1"))
        p = e + 1
    return out


def describe(path):
    d = path.read_bytes()
    cs = chunks(d)
    data = d[cs[0][1] : cs[0][1] + cs[0][2]]
    stable = strings(d, cs[1][1], cs[1][2])
    root_crc, root_size, root_flags = struct.unpack_from("<IIB", data, 0)
    n = struct.unpack_from("<I", data, 9)[0]
    print(
        f"{path.name}: root {root_crc:#x} size {root_size} entries {n} strings {len(stable)}"
    )
    p = 13
    for i in range(n):
        crc, size, flags = struct.unpack_from("<IIB", data, p)
        body = p + 9
        end = body + size - 1
        refs = struct.unpack_from("<3I", data, body)
        fl = struct.unpack_from("<3f", data, body + 12)
        tcmap_pos = body + 24
        tcrc, tsize, tflags = struct.unpack_from("<IIB", data, tcmap_pos)
        count = struct.unpack_from("<I", data, tcmap_pos + 9)[0]
        print(
            f"  [{i:2d}] size {size:6d} refs {refs} -> {[stable[r] if r < len(stable) else '?' for r in refs]}"
            f" floats {fl} tcmap crc {tcrc:#x} size {tsize} count {count}"
        )
        p = end
    print()


def main():
    for name in ("fonts_ru.bin", "fonts_us.bin"):
        describe(ROOT / "work" / name)


if __name__ == "__main__":
    main()
