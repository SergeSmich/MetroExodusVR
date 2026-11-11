"""Metro Exodus font glyph tables (``tcmap``): parse, dump, predict, verify.

The fonts the *game* draws text with are not TTFs at runtime.
``content\\scripts\\fonts_ru.bin`` / ``fonts_us.bin`` (in the VFS) hold one
reflection descriptor per font alias, and each descriptor carries a ``tcmap``
array of **23-byte glyph records addressed by the raw byte of the string**.
There is no codepoint, no decoder and no TTF anywhere in that chain, which is
why patching a TTF cannot change what a native caption shows.

Record layout (23 bytes).  The stride is proven, the field names are read off
the data::

    +0x00   9 bytes  constant prefix (serialisation header, same in every
                     record of every font)
    +0x09   u16      u     cell x in the atlas
    +0x0b   u16      v     cell y in the atlas
    +0x0d   u16      w     ink width
    +0x0f   u16      h     ink height
    +0x11   i16      bx    left bearing (small, -4..+3)
    +0x13   i16      by    top offset: 9 for ascender letters, 20 for
                           x-height letters, 42 for '.', 50 for the blank
    +0x15   u16      adv   pen advance (15 for 'i'/'l', 40 for 'A', 52 for 'W')

Stride proof: for all 34 descriptors ``size == 4 + 23 * count`` exactly, and
in ``font\\font_console`` ``u == 16 * i`` holds for every i in 0..255, so the
stride is 23 with no padding and no drift.

Only the ink/no-ink question matters for the font-swap decision, and that only
needs "record[9:23] is not all zero" — it does not depend on the field names.

Usage::

    python tools/font_table.py work/fonts_ru.bin --list
    python tools/font_table.py work/fonts_ru.bin --dump arial --range 0x20-0x7e
    python tools/font_table.py work/fonts_ru.bin --predict menu \
        --encoding charmap --text "ИГРА"
    python tools/font_table.py work/fonts_ru.bin --predict arial \
        --encoding cp1251 --text "ИГРА"
    python tools/font_table.py work/fonts_ru.bin --coverage
    python tools/font_table.py work/fonts_us.bin --charmap ru/charmap_us.txt \
        --predict menu --encoding charmap --text "\u0412\u041a\u041b"

The two ``.bin`` files are game data and are not committed; take them from
``collab/runs/L-0002/`` (opencode) or from the VFS with ``tools/vfs_extract.py``.
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = 23

# --- the .lng / caption byte stream -----------------------------------------

ESCAPE = 0xE0          # bytes >= this start a two-byte index
ESCAPE_ORIGIN = 0xDE40  # idx = b0 * 255 + b1 - ESCAPE_ORIGIN

# NOTE: tools/apply_ru.py and tools/lng_dump.py currently use 0xDE41.  With
# 0xDE41 the first byte of an escape for idx == 224 is 223, i.e. *below* the
# escape threshold, so the engine would read it as a one-byte index and then
# read the second byte as a separate character.  0xDE40 is the value that puts
# the first byte of every escape at >= 0xE0:
#     idx = (b0 - 0xE0) * 255 + b1 + 0xE0   <=>   b0*255 + b1 - 0xDE40
# No string in stable_ru.lng exercises the escape (0 of 25036), so this has
# never been validated against the engine -- see ENCODING_NOTES.md section 8.
LEGACY_ESCAPE_ORIGIN = 0xDE41


def load_charmap(path=None):
    """index -> codepoint, one entry per line, from ru/charmap.txt."""
    path = Path(path) if path else ROOT / "ru" / "charmap.txt"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(int(line[2:], 16))
    return out


def encode(text, encoding, charmap):
    """Encode ``text`` the way a caption's bytes would be produced."""
    if encoding == "cp1251":
        return text.encode("cp1251")
    if encoding == "utf-8":
        return text.encode("utf-8")
    if encoding != "charmap":
        raise SystemExit(f"unknown encoding {encoding!r}")
    rev = {}
    for i, cp in enumerate(charmap):
        rev.setdefault(cp, i)
    out = bytearray()
    for ch in text:
        i = rev.get(ord(ch))
        if i is None:
            raise SystemExit(f"U+{ord(ch):04X} ({ch!r}) is not in the charmap")
        if i < ESCAPE:
            out.append(i)
        else:
            v = i + ESCAPE_ORIGIN
            out += bytes((v // 255, v % 255))
    return bytes(out)


def iter_indices(enc, origin=ESCAPE_ORIGIN):
    """Walk an encoded byte stream the way the engine reads it.

    Yields ``(index, nbytes)``.  ``index`` is out of range for the font when
    the stream escapes past the end of that font's table.
    """
    i = 0
    while i < len(enc):
        b = enc[i]
        if b < ESCAPE:
            yield b, 1
            i += 1
        else:
            if i + 1 >= len(enc):
                yield -1, 1
                break
            yield b * 255 + enc[i + 1] - origin, 2
            i += 2


# --- fonts_*.bin -------------------------------------------------------------


def chunks_of(data):
    assert data[0] & 4, "expected a bin archive with a strings table"
    pos, out = 1, []
    while pos + 8 <= len(data):
        cid, size = struct.unpack_from("<II", data, pos)
        pos += 8
        out.append((cid, pos, size))
        pos += size
    return out


def parse(path):
    """Return the list of font descriptors of a ``fonts_*.bin``."""
    data = Path(path).read_bytes()
    cs = chunks_of(data)
    blob = data[cs[0][1] : cs[0][1] + cs[0][2]]

    nstr = struct.unpack_from("<I", data, cs[1][1])[0]
    p = cs[1][1] + 4
    strings = []
    for _ in range(nstr):
        e = data.index(b"\0", p)
        strings.append(data[p:e].decode("latin-1"))
        p = e + 1

    count = struct.unpack_from("<I", blob, 9)[0]
    p = 13
    fonts = []
    for i in range(count):
        _crc, size, _flags = struct.unpack_from("<IIB", blob, p)
        body = p + 9
        refs = struct.unpack_from("<3I", blob, body)
        tpos = body + 24
        tcrc, tsize, _tflags = struct.unpack_from("<IIB", blob, tpos)
        n = struct.unpack_from("<I", blob, tpos + 9)[0]
        # size counts from the flags byte: 1 + 4 + 23 * n
        assert tsize == 1 + 4 + RECORD * n, (tcrc, tsize, n)
        recs = blob[tpos + 13 : tpos + 13 + n * RECORD]
        assert len(recs) == n * RECORD
        fonts.append(
            {
                "idx": i,
                "alias": strings[refs[1]] if refs[1] < len(strings) else "?",
                "resource": strings[refs[2]] if refs[2] < len(strings) else "?",
                "count": n,
                "records": recs,
            }
        )
        p = body + size - 1
    return fonts


def record(font, i):
    r = font["records"][i * RECORD : (i + 1) * RECORD]
    u, v, w, h, bx, by, adv = struct.unpack_from("<HHHHhhH", r, 9)
    return {
        "u": u,
        "v": v,
        "w": w,
        "h": h,
        "bx": bx,
        "by": by,
        "adv": adv,
        "inked": r[9:RECORD] != b"\0" * (RECORD - 9),
    }


def has_ink(font, i):
    return 0 <= i < font["count"] and record(font, i)["inked"]


def bake(font, charmap):
    """What the glyph at index ``i`` *is* for this font.

    A font's table is baked from whatever charmap the font was built with:

    * ``count == len(charmap)``  -> the localization charmap (271 for RU,
      203 for US): entry ``i`` is the glyph of ``charmap[i]``;
    * ``count == 256``           -> no localization charmap at all, the table
      is the identity over Latin-1: entry ``i`` is the glyph of ``chr(i)``.

    ``arial`` is the second kind.  That is why reading it *looks* like
    "byte as codepoint": it is not, the byte is still an index, it is only
    that this particular table was baked from the identity charmap.
    """
    if font["count"] == len(charmap):
        return lambda i: chr(charmap[i]) if 0 <= i < len(charmap) else None
    if font["count"] == 256:
        return lambda i: chr(i) if 0 <= i < 256 else None
    return lambda i: None


# --- commands ----------------------------------------------------------------


def cmd_list(fonts, _args):
    print(f"{'alias':16s} {'count':>5s} {'ink':>4s}  resource")
    for f in fonts:
        n = sum(1 for i in range(f["count"]) if record(f, i)["inked"])
        print(f"{f['alias']:16s} {f['count']:5d} {n:4d}  {f['resource']}")


def cmd_dump(fonts, args):
    f = pick(fonts, args.dump)
    print(f"{f['alias']} -> {f['resource']}  count={f['count']}")
    lo, hi = parse_range(args.range, f["count"])
    for i in range(lo, hi):
        r = record(f, i)
        mark = "" if r["inked"] else "   (no ink)"
        print(
            f"  0x{i:02x} ({i:3d})  u={r['u']:4d} v={r['v']:4d} "
            f"w={r['w']:3d} h={r['h']:3d} bx={r['bx']:3d} by={r['by']:3d} "
            f"adv={r['adv']:3d}{mark}"
        )


def cmd_predict(fonts, args):
    f = pick(fonts, args.predict)
    charmap = load_charmap(args.charmap)
    srcmap = load_charmap(args.encode_charmap) if args.encode_charmap else charmap
    glyph = bake(f, charmap)
    enc = encode(args.text, args.encoding, srcmap)
    kind = "charmap-baked" if f["count"] == len(charmap) else (
        "identity/Latin-1" if f["count"] == 256 else "unknown bake")
    print(f"font     : {f['alias']} -> {f['resource']} ({f['count']} entries, {kind})")
    print(f"encoding : {args.encoding}")
    print(f"bytes    : {enc.hex(' ')}")
    out = []
    for idx, _n in iter_indices(enc, args.origin):
        if idx < 0:
            out.append("<truncated escape>")
        elif not has_ink(f, idx):
            out.append(_BLANK)
        else:
            g = glyph(idx)
            out.append(g if g else "<?>")
    print(f"drawn    : {''.join(out)!r}   ({_BLANK} = no ink, nothing is drawn)")


_BLANK = "·"


def cmd_validator(fonts, args):
    """Which translation strings the mod's own declaration validator would refuse.

    The declaration API refuses a caption with a reason string found in .rdata
    (RVA 0x49dbc0 in 0.9.0): 'captions are printable ASCII (at most 127)'.
    Three readings of that sentence are possible, and they differ wildly:

      H1  every byte <= 0x7F              -> refuses 19/193 captions
      H2  0x20 <= every byte <= 0x7E      -> refuses 131/193 captions
      H3  only the length (<= 127)        -> refuses nothing

    Under H1/H2 every CP1251 caption is refused too, which is a second
    explanation for the blank captions of L-0032 -- see A-0030.
    """
    charmap = load_charmap(args.charmap)
    rows = []
    for line in (ROOT / "ru" / "strings.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append((parts[0], parts[1], parts[2]))

    def fails(enc, lo, hi):
        return [b for b in enc if not (lo <= b <= hi)]

    print(f"captions in ru/strings.tsv: {len(rows)}")
    for enc_name in ("charmap", "cp1251"):
        n1 = n2 = n3 = 0
        bad1, bad2 = [], []
        for _rva, _orig, ru in rows:
            try:
                enc = encode(ru, enc_name, charmap)
            except SystemExit:
                continue
            if fails(enc, 0x00, 0x7F):
                n1 += 1
                bad1.append(ru)
            if fails(enc, 0x20, 0x7E):
                n2 += 1
                bad2.append(ru)
            if len(enc) > 127:
                n3 += 1
        print(f"\n  encoding {enc_name}:")
        print(f"    H1 (bytes <= 0x7F) refused      : {n1}/{len(rows)}")
        print(f"    H2 (0x20..0x7E)     refused     : {n2}/{len(rows)}")
        print(f"    H3 (length > 127)   refused     : {n3}/{len(rows)}")
        if args.show and n1:
            print("    H1 offenders:")
            for t in bad1[: args.show]:
                print(f"      {t!r} -> {encode(t, enc_name, charmap).hex(' ')}")


def cmd_accuracy(fonts, args):
    """How much of the translation a font can actually draw."""
    charmap = load_charmap(args.charmap)
    rev = {}
    for i, cp in enumerate(charmap):
        rev.setdefault(cp, i)
    texts = _translation_texts()
    print(f"translation: {len(texts)} strings")
    print(f"{'font':16s} {'correct':>16s} {'no ink':>16s} {'wrong glyph':>16s}  strings with a defect")
    for f in fonts:
        glyph = bake(f, charmap)
        tot = ok = blank = 0
        bad_strings = 0
        for t in texts:
            bad = False
            for ch in t:
                i = rev.get(ord(ch))
                if i is None:
                    continue
                tot += 1
                if not has_ink(f, i):
                    blank += 1
                    bad = True
                    continue
                if glyph(i) == ch:
                    ok += 1
                else:
                    bad = True
            if bad:
                bad_strings += 1
        wrong = tot - ok - blank
        pc = lambda n: f"{n:6d} ({n * 100.0 / tot:4.1f}%)"
        print(f"{f['alias']:16s} {pc(ok):>16s} {pc(blank):>16s} {pc(wrong):>16s}  {bad_strings}")


def _translation_texts():
    texts = []
    for line in (ROOT / "ru" / "strings.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        texts.extend(line.split("\t")[2:])

    def walk(o):
        if isinstance(o, str):
            texts.append(o)
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for x in o.values():
                walk(x)

    walk(json.load(open(ROOT / "ru" / "ui2.json", encoding="utf-8")))
    return texts


def cmd_coverage(fonts, args):
    charmap = load_charmap()
    rev = {}
    for i, cp in enumerate(charmap):
        rev.setdefault(cp, i)

    texts = []
    for line in (ROOT / "ru" / "strings.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        texts.extend(line.split("\t")[2:])

    def walk(o):
        if isinstance(o, str):
            texts.append(o)
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for x in o.values():
                walk(x)

    walk(json.load(open(ROOT / "ru" / "ui2.json", encoding="utf-8")))
    chars = sorted({c for t in texts for c in t})

    absent = [c for c in chars if ord(c) not in rev]
    print(f"translation characters: {len(chars)} distinct")
    print(f"absent from the charmap ({len(charmap)} entries): {len(absent)} {''.join(absent)!r}")
    print()
    print(f"{'font':16s} {'entries':>7s} {'no ink':>6s}  which")
    for f in fonts:
        bad = [c for c in chars if ord(c) in rev and not has_ink(f, rev[ord(c)])]
        print(f"{f['alias']:16s} {f['count']:7d} {len(bad):6d}  {''.join(bad)!r}")


# --- helpers -----------------------------------------------------------------


def pick(fonts, name):
    for f in fonts:
        if f["alias"] == name or f["resource"] == name:
            return f
    raise SystemExit(f"no font {name!r}; try --list")


def parse_range(spec, count):
    if not spec:
        return 0, count
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a, 0), min(int(b, 0) + 1, count)
    i = int(spec, 0)
    return i, min(i + 1, count)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bin", help="fonts_ru.bin / fonts_us.bin")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dump", metavar="FONT")
    ap.add_argument("--range", metavar="A-B")
    ap.add_argument("--predict", metavar="FONT")
    ap.add_argument("--encoding", default="charmap",
                    choices=("charmap", "cp1251", "utf-8"))
    ap.add_argument("--origin", type=lambda s: int(s, 0), default=ESCAPE_ORIGIN,
                    help=f"escape origin for --predict (default {ESCAPE_ORIGIN:#x})")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--accuracy", action="store_true")
    ap.add_argument("--validator", action="store_true")
    ap.add_argument("--show", type=int, default=0, metavar="N",
                    help="with --validator, print N offending strings")
    ap.add_argument("--charmap", help="charmap file (default ru/charmap.txt)")
    ap.add_argument("--encode-charmap",
                    help="charmap used to produce the bytes (default: --charmap)")
    ap.add_argument("--text", help="text for --predict")
    args = ap.parse_args(argv)

    fonts = parse(args.bin)
    if args.list:
        cmd_list(fonts, args)
    if args.dump:
        cmd_dump(fonts, args)
    if args.predict:
        if not args.text:
            ap.error("--predict needs a text argument")
        cmd_predict(fonts, args)
    if args.coverage:
        cmd_coverage(fonts, args)
    if args.accuracy:
        cmd_accuracy(fonts, args)
    if args.validator:
        cmd_validator(fonts, args)
    if not (args.list or args.dump or args.predict or args.coverage
            or args.accuracy or args.validator):
        cmd_list(fonts, args)


if __name__ == "__main__":
    sys.exit(main())
