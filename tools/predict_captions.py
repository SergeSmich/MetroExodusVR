#!/usr/bin/env python3
"""Predict what a whole translation file looks like on screen.

``tools/font_table.py`` answers the question for one string.  This one answers
it for every row of ``kit091/ru/strings-0.9.1.tsv`` (or any file with the same
three columns), for one ``(encoding, font)`` pair, and prints the rows that
would **not** come out right.  That turns "the captions are unreadable" into a
list of strings and a count, and it makes an encoding/font claim falsifiable
against a screenshot that already exists.

The model is A-0029: a caption's bytes are *indices into the drawing font's
glyph table*, never codepoints.  A font whose table has ``len(charmap)``
entries (271 for RU) was baked from the localization charmap; one with 256
entries is the identity over Latin-1 (``arial`` is one of those).  So:

    charmap bytes + a charmap-baked font  -> correct Cyrillic
    charmap bytes + arial                 -> Latin garbage
    utf-8 bytes   + arial                 -> empty (no ink above 0x7e)
    utf-8 bytes   + a charmap-baked font  -> wrong Cyrillic

Usage::

    python tools/predict_captions.py --bin work/fonts_ru.bin \
        --strings kit091/ru/strings-0.9.1.tsv --encoding charmap --font menu
    python tools/predict_captions.py --encoding utf-8 --font arial --show 20
    python tools/predict_captions.py --all          # the four combinations
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import font_table as ft  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BIN = ROOT / "work" / "fonts_ru.bin"
DEFAULT_STRINGS = ROOT / "kit091" / "ru" / "strings-0.9.1.tsv"

COMBOS = (
    ("charmap", "menu"),
    ("charmap", "regular"),
    ("charmap", "arial"),
    ("utf-8", "menu"),
    ("utf-8", "regular"),
    ("utf-8", "arial"),
)


def read_strings(path):
    """Yield ``(rva, original, translation)``; skips comments and blanks."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        out.append((parts[0].strip(), parts[1], parts[2]))
    return out


def draw(font, enc, charmap, origin=ft.ESCAPE_ORIGIN):
    """Render an encoded string the way the engine would: bytes -> glyphs."""
    glyph = ft.bake(font, charmap)
    out = []
    for idx, _n in ft.iter_indices(enc, origin):
        if idx < 0:
            out.append("<bad escape>")
        elif not ft.has_ink(font, idx):
            out.append(ft._BLANK)
        else:
            out.append(glyph(idx) or "<?>")
    return "".join(out)


def run(fonts, rows, charmap, encoding, font_name, show=0, only_bad=False):
    font = ft.pick(fonts, font_name)
    good = bad = skipped = 0
    lines = []
    for rva, _orig, ru in rows:
        try:
            enc = ft.encode(ru, encoding, charmap)
        except (SystemExit, UnicodeEncodeError) as exc:
            skipped += 1
            lines.append(f"  {rva}  {ru!r}  -> not encodable: {exc}")
            continue
        drawn = draw(font, enc, charmap)
        ok = drawn == ru
        good += ok
        bad += not ok
        if not ok and (only_bad or show):
            lines.append(f"  {rva}  want {ru!r}\n         got  {drawn!r}")
    kind = (
        "charmap-baked"
        if font["count"] == len(charmap)
        else ("identity/Latin-1" if font["count"] == 256 else "unknown")
    )
    print(
        f"{encoding:8s} + {font_name:9s} ({kind}): "
        f"{good} correct, {bad} wrong, {skipped} unencodable, "
        f"{len(rows)} rows"
    )
    for line in lines[: show or None]:
        print(line)
    return good, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bin", default=str(DEFAULT_BIN))
    ap.add_argument("--strings", default=str(DEFAULT_STRINGS))
    ap.add_argument("--charmap", default=str(ROOT / "ru" / "charmap.txt"))
    ap.add_argument("--encoding", default="charmap")
    ap.add_argument("--font", default="menu")
    ap.add_argument("--show", type=int, default=0, metavar="N")
    ap.add_argument("--only-bad", action="store_true")
    ap.add_argument("--all", action="store_true", help="run every combination")
    args = ap.parse_args(argv)

    bin_path = Path(args.bin)
    if not bin_path.is_file():
        print(
            f"ERROR {bin_path} not found. It is game data and is not committed;\n"
            "      take it from collab/runs/L-0002/ (opencode) or from the VFS."
        )
        return 2
    str_path = Path(args.strings)
    if not str_path.is_file():
        print(f"ERROR {str_path} not found; pass --strings")
        return 2

    fonts = ft.parse(bin_path)
    charmap = ft.load_charmap(args.charmap)
    rows = read_strings(str_path)

    if args.all:
        for enc, font in COMBOS:
            run(fonts, rows, charmap, enc, font, show=args.show,
                only_bad=args.only_bad)
        return 0
    run(fonts, rows, charmap, args.encoding, args.font, show=args.show,
        only_bad=args.only_bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
