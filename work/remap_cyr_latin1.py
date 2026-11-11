"""Add Cyrillic cmap entries at CP1251 byte positions (0x80..0xFF).

Hypothesis: the VR mod's text renderer treats each byte of the string as a
Unicode code point (identity map, like the exe font `arial` whose 256-entry
table is identity and has zero glyphs above 0x7F).  In that case a CP1251
encoded string is looked up at U+00B0..U+00FF etc., NOT at U+0410.

So: for every byte value that CP1251 maps to a non-ASCII character, point the
font's cmap at the donor glyph for that character.  Keep the original U+04xx
entries as well (harmless and covers the UTF-8 hypothesis).

Usage:
  python work/remap_cyr_latin1.py --fonts work/0.9.1/fonts --donor C:\Windows\Fonts\arial.ttf
"""

import argparse
import pathlib
import sys

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen


def donor_glyph_for(donor, ch):
    cp = ord(ch)
    cmap = donor.getBestCmap()
    name = cmap.get(cp)
    if not name or name not in donor.getGlyphOrder():
        return None
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--donor", required=True)
    args = ap.parse_args()

    donor = TTFont(args.donor, fontNumber=0)
    donor_cmap = donor.getBestCmap()
    donor_set = donor.getGlyphSet()

    # byte -> character under CP1251, only bytes >= 0x80
    pairs = []
    for b in range(0x80, 0x100):
        try:
            ch = bytes([b]).decode("cp1251")
        except UnicodeDecodeError:
            continue  # 0x98 is undefined in CP1251
        if ord(ch) >= 0x100:
            pairs.append((b, ch))

    root = pathlib.Path(args.fonts)
    if not root.is_dir():
        sys.exit(f"no font dir: {root}")

    for path in sorted(root.glob("*.ttf")):
        font = TTFont(str(path))
        base_cmap = font.getBestCmap()
        glyf = font["glyf"]
        from fontTools.pens.ttGlyphPen import TTGlyphPen

        order = list(font.getGlyphOrder())
        tables = [
            t for t in font["cmap"].tables if t.isUnicode() and t.format in (4, 12)
        ]
        if not tables:
            sys.exit(f"{path.name}: no unicode cmap format 4/12")
        added = 0
        mapped = 0
        for b, ch in pairs:
            dname = donor_cmap.get(ord(ch))
            if not dname:
                continue
            gname = "cyr%04X" % b
            if base_cmap.get(b) == gname:
                continue
            if gname not in glyf:
                pen = TTGlyphPen(None)
                rec = DecomposingRecordingPen(donor_set)
                donor_set[dname].draw(rec)
                rec.replay(pen)
                glyph = pen.glyph()
                glyph.recalcBounds(glyf)
                glyf[gname] = glyph
                order.append(gname)
                font["hmtx"][gname] = (donor["hmtx"][dname][0], glyph.xMin)
                added += 1
            for t in tables:
                t.cmap[b] = gname
            mapped += 1
        font.setGlyphOrder(order)
        font["maxp"].numGlyphs = len(order)
        font.save(str(path))
        check = TTFont(str(path))
        cmap = check.getBestCmap()
        missing = [b for b, ch in pairs if ord(ch) in donor_cmap and b not in cmap]
        print(
            f"{path.name}: +{added} glyphs, {mapped} cmap@byte, missing={len(missing)}"
        )
        if missing:
            sys.exit(f"{path.name}: missing byte entries {missing[:8]}")
    print("ok")


if __name__ == "__main__":
    main()
