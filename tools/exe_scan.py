"""Scan a PE image for raw byte patterns and report file offset + RVA.

Used to hand opencode greppable fingerprints when the byte stream -> glyph
path has to be located in ``MetroExodus.exe`` (Arena has no exe and no
disassembler for it, so the search is specified as patterns, not addresses).

Patterns are hex strings; ``??`` matches any byte.  Expected-hit counts are
for a ~40 MB image, so anything that is not a near-unique pattern is useless.

Usage::

    python tools/exe_scan.py MetroExodus.exe 56 9A 0F 8F
    python tools/exe_scan.py MetroExodus.exe 40 DE 00 00 80 24 FF FF tcmap

    # the font-table reader: crc32("tcmap") and the escape origin 0xDE40
    python tools/exe_scan.py MetroExodus.exe --all-font-marks
"""

import argparse
import struct
import sys
from pathlib import Path

# crc32("tcmap"), little-endian: the reflection id of the glyph-table field in
# fonts_*.bin.  The exe must know this name to (de)serialise the descriptor.
MARK_TCMAP_CRC = "56 9A 0F 8F"
# 56896 = 0xDE40, the origin of the two-byte charmap escape.
MARK_ESCAPE_SUB = "40 DE 00 00"
MARK_ESCAPE_ADD = "C0 21 FF FF"  # -56896 as imm32 (`add eax, -56896`)
# 56641 = 0xDE41, the value our own codec uses (see ENCODING_NOTES.md 9.5).
MARK_ESCAPE_LEGACY = "41 DE 00 00"
# the literal field name, in case the exe keeps strings and not crcs.
MARK_TCMAP_STR = "tcmap"


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    size_opt = struct.unpack_from("<H", data, pe + 20)[0]
    sect = pe + 24 + size_opt
    out = []
    for i in range(nsec):
        o = sect + 40 * i
        name = bytes(data[o : o + 8]).rstrip(b"\0").decode("latin-1")
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, o + 8)
        out.append((name, vaddr, vsize, raddr, rsize))
    return out


def to_bytes(spec):
    spec = spec.strip()
    if spec.startswith('"') or spec.startswith("'"):
        return spec[1:-1].encode("latin-1")
    if all(c in "0123456789abcdefABCDEF ?" for c in spec.replace(" ", "")):
        toks = spec.split()
        if all(len(t) == 2 for t in toks):
            return bytes(-1 if t == "??" else int(t, 16) for t in toks)
    return spec.encode("latin-1")


def find(data, pat):
    hits = []
    step = 1
    i = data.find(pat, 0)
    while i >= 0:
        hits.append(i)
        i = data.find(pat, i + step)
    return hits


def off_to_rva(secs, off):
    for _name, vaddr, vsize, raddr, rsize in secs:
        if raddr <= off < raddr + max(rsize, 1):
            return vaddr + (off - raddr)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image")
    ap.add_argument("patterns", nargs="*")
    ap.add_argument("--all-font-marks", action="store_true",
                    help="the four patterns that locate the glyph-table reader")
    ap.add_argument("--context", type=int, default=0,
                    help="print N bytes around each hit")
    args = ap.parse_args(argv)

    pats = list(args.patterns)
    if args.all_font_marks or not pats:
        pats = [MARK_TCMAP_CRC, MARK_ESCAPE_SUB, MARK_ESCAPE_ADD,
                MARK_ESCAPE_LEGACY, MARK_TCMAP_STR]

    data = Path(args.image).read_bytes()
    secs = sections(data)
    print(f"{Path(args.image).name}: {len(data)} bytes, {len(secs)} sections")
    print("  " + "  ".join(f"{n}(rva {v:#x})" for n, v, _vs, _r, _rs in secs))
    print()
    for spec in pats:
        pat = to_bytes(spec)
        hits = find(data, pat)
        print(f"pattern {spec!r} ({len(pat)} bytes): {len(hits)} hit(s)")
        for off in hits[:40]:
            rva = off_to_rva(secs, off)
            where = ""
            for name, vaddr, vsize, raddr, rsize in secs:
                if raddr <= off < raddr + max(rsize, 1):
                    where = name
            ctx = ""
            if args.context:
                lo = max(0, off - args.context)
                hi = min(len(data), off + len(pat) + args.context)
                ctx = "  " + data[lo:hi].hex(" ")
            print(f"    file {off:#010x}  rva {rva:#010x}  [{where}]{ctx}")
        if len(hits) > 40:
            print(f"    ... {len(hits) - 40} more")
        print()


if __name__ == "__main__":
    sys.exit(main())
