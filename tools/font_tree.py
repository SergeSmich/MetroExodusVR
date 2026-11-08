"""Dump the reflection tree of a Metro ``fonts_*.bin`` descriptor."""

import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = r"F:\SteamLibrary\steamapps\common\Metro Exodus\MetroExodus.exe"


def build_names():
    d = Path(EXE).read_bytes()
    cand = {}
    for m in re.finditer(rb"[ -~]{1,40}", d):
        s = m.group().decode("latin-1")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ .%/\\-]{0,39}", s):
            cand.setdefault(zlib.crc32(s.encode()) & 0xFFFFFFFF, s)
    return cand


NAMES = build_names()


def name_of(crc):
    return NAMES.get(crc)


def parse_seq(b, p, end, depth, maxdepth=30):
    """Parse a sequence of sections spanning [p, end). Return list or None."""
    out = []
    q = p
    while q < end:
        if q + 9 > end:
            return None
        crc, size = struct.unpack_from("<II", b, q)
        flags = b[q + 8]
        if size < 1 or q + 9 + size - 1 > end:
            return None
        body = q + 9
        blen = size - 1
        out.append((q, crc, size, flags, body, blen))
        q = body + blen
    return out if out else None


def describe(b, p, end, depth=0, budget=None):
    pad = "  " * depth
    # array? (u32 count followed by that many sections)
    if end - p >= 4:
        cnt = struct.unpack_from("<I", b, p)[0]
        if 1 <= cnt <= 4096 and cnt * 9 <= end - p:
            seq = parse_seq(b, p + 4, end, depth)
            if seq is not None and len(seq) == cnt:
                print(f"{pad}ARRAY count={cnt} at {p:#x}")
                for i, (q, crc, size, flags, body, blen) in enumerate(seq[:4]):
                    print(
                        f"{pad}  [{i}] crc {crc:#010x} {name_of(crc)!r} size {size} flags {flags:#x}"
                    )
                    describe_payload(b, body, body + blen, depth + 2)
                if cnt > 4:
                    print(f"{pad}  ...")
                return
    seq = parse_seq(b, p, end, depth)
    if seq is not None:
        for q, crc, size, flags, body, blen in seq:
            print(
                f"{pad}{q:#08x} crc {crc:#010x} size {size:6d} flags {flags:#04x} {name_of(crc)!r}"
            )
            describe_payload(b, body, body + blen, depth + 1)
        return
    print(f"{pad}RAW {end - p} bytes at {p:#x}: {b[p : p + min(32, end - p)].hex(' ')}")


def describe_payload(b, p, end, depth):
    pad = "  " * depth
    if end - p == 0:
        return
    # array of structs
    if end - p >= 4:
        cnt = struct.unpack_from("<I", b, p)[0]
        if 1 <= cnt <= 4096 and 4 + cnt * 23 <= end - p:
            seq = parse_seq(b, p + 4, end, depth)
            if seq is not None and len(seq) == cnt:
                print(f"{pad}ARRAY(count) count={cnt}")
                for i, (q, crc, size, flags, body, blen) in enumerate(seq[:3]):
                    vals = struct.unpack_from("<7H", b, body) if blen >= 14 else ()
                    print(f"{pad}  [{i}] size {size} flags {flags:#x} vals {vals}")
                if cnt > 3:
                    print(f"{pad}  ...")
                return
    seq = parse_seq(b, p, end, depth)
    if seq is not None:
        for q, crc, size, flags, body, blen in seq:
            print(
                f"{pad}{q - p:#06x} crc {crc:#010x} size {size:6d} flags {flags:#04x} {name_of(crc)!r}"
            )
            describe_payload(b, body, body + blen, depth + 1)
        return
    print(f"{pad}RAW {end - p} bytes: {b[p : p + min(48, end - p)].hex(' ')}")


def main():
    path = Path(sys.argv[1])
    d = path.read_bytes()
    # chunk 1
    chunks = []
    pos = 1
    while pos + 8 <= len(d):
        cid, size = struct.unpack_from("<II", d, pos)
        pos += 8
        chunks.append((cid, pos, size))
        pos += size
    cid, off, size = chunks[0]
    block = d[off : off + size]
    crc, ssize = struct.unpack_from("<II", block, 0)
    flags = block[8]
    print(f"root crc {crc:#010x} {name_of(crc)!r} size {ssize} flags {flags:#x}")
    describe(block, 9, 9 + ssize - 1)


if __name__ == "__main__":
    main()
