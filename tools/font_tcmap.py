"""Extract the ``tcmap`` array from a Metro Exodus ``fonts_*.bin`` blob.

``content\\config.bin`` (from the game VFS) is a container of
``(crc32 name, size)`` chunks; ``content\\scripts\\fonts_ru.bin`` /
``fonts_us.bin`` hold the font descriptors.  Each descriptor is a Metro
reflection-serialized object whose ``tcmap`` field maps a charmap index (the
single-byte string encoding used by ``.lng`` files) to a glyph index in the
font's BC7 atlas.

Usage: python tools/font_tcmap.py work/fonts_ru.bin [--dump]
"""

import struct
import sys
import zlib
from pathlib import Path


def crc32(s):
    return zlib.crc32(s.encode()) & 0xFFFFFFFF


def parse_archive(d):
    assert d[0] & 4, "expected a strings-table bin archive"
    pos = 1
    chunks = []
    while pos + 8 <= len(d):
        cid, size = struct.unpack_from("<II", d, pos)
        pos += 8
        chunks.append((cid, pos, size))
        pos += size
    stable = []
    for cid, off, size in chunks:
        if cid == 2:
            n = struct.unpack_from("<I", d, off)[0]
            p = off + 4
            for _ in range(n):
                e = d.index(b"\0", p)
                stable.append(d[p:e].decode("latin-1"))
                p = e + 1
    return chunks, stable


def find_tcmap(data, name="tcmap"):
    needle = struct.pack("<I", crc32(name))
    hits = []
    off = 0
    while True:
        i = data.find(needle, off)
        if i < 0:
            break
        hits.append(i)
        off = i + 1
    return hits


def main():
    path = Path(sys.argv[1])
    d = path.read_bytes()
    chunks, stable = parse_archive(d)
    print("chunks:", [(c, hex(o), s) for c, o, s in chunks])
    print("strings:", len(stable))
    data = d[chunks[0][1] : chunks[0][1] + chunks[0][2]]
    hits = find_tcmap(data)
    print(f"tcmap crc hits in chunk 1: {[hex(h) for h in hits]}")
    for h in hits:
        size, flags = struct.unpack_from("<IB", data, h + 4)
        body = h + 9
        payload = data[body : body + size - 1]
        print(f"  hit {h:#x} size {size} flags {flags:#x} payload {len(payload)}")
        if len(payload) >= 4:
            count = struct.unpack_from("<I", payload, 0)[0]
            print(f"  count {count} payload_rem {len(payload) - 4}")
            if count and 4 + count * 2 <= len(payload):
                vals = struct.unpack_from("<%dH" % count, payload, 4)
                print(f"  first {vals[:16]}")
                print(f"  max {max(vals)} min {min(vals)}")
                if "--dump" in sys.argv:
                    print("  values: " + " ".join(str(v) for v in vals))


if __name__ == "__main__":
    main()
