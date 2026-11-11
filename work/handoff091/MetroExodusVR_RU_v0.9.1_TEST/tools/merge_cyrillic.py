"""EXPERIMENTAL: merge Cyrillic outlines into the mod's four embedded TTFs.

The v0.9.1 resources are confirmed Latin-only TrueType fonts.  This utility
adds Cyrillic outlines from local Windows Arial files and checks the saved cmap.
That only proves the font files contain glyphs; it does NOT prove the VR mod's
custom UI selects those glyphs.  Existing encoding notes say the UI uses a US
charmap, so this font merge alone is not a confirmed fix.

No donor font is redistributed.  Expected source DLL SHA-256 is pinned to the
analyzed official v0.9.1 build.

Usage:
  python tools/merge_cyrillic.py [--src DLL] [--out DIR]
"""

import argparse
import hashlib
import sys
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "work" / "0.9.1" / "versions" / "0.9.1" / "MetroExodusVR.dll"
EXPECTED_SOURCE_SHA256 = "fbbf2812bc7c3304a22829249aba334c812a326baf75fc5c2a75e559202c40b4"
FONT_DIR = ROOT / "build" / "fonts"

WINDIR = Path(r"C:\Windows\Fonts")
DONOR = {
    "regular": WINDIR / "arial.ttf",
    "bold": WINDIR / "arialbd.ttf",
}

# resource name -> (donor key, horizontal scale)
FONTS = {
    "INFO_BARLOW_CONDENSED_SEMIBOLD": ("bold", "match"),
    "INFO_INTER_MEDIUM": ("regular", 1.0),
    "INFO_INTER_REGULAR": ("regular", 1.0),
    "INFO_INTER_SEMIBOLD": ("bold", 1.0),
}

CYRILLIC = list(range(0x0400, 0x0460))


def resource_entries(pe, data):
    """Yield (path, rva, size) for every leaf resource in the PE."""
    e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
    opt = e_lfanew + 24
    magic = int.from_bytes(data[opt : opt + 2], "little")
    dd = opt + (112 if magic == 0x20B else 96)
    rsrc_rva = int.from_bytes(data[dd + 8 * 2 : dd + 8 * 2 + 4], "little")
    base = pe.rva_to_off(rsrc_rva)
    if base is None:
        raise RuntimeError("no resource directory")

    def name_at(off):
        ln = int.from_bytes(data[base + off : base + off + 2], "little")
        raw = data[base + off + 2 : base + off + 2 + ln * 2]
        return raw.decode("utf-16-le")

    def walk(dir_off, path):
        n_named = int.from_bytes(
            data[base + dir_off + 12 : base + dir_off + 14], "little"
        )
        n_id = int.from_bytes(data[base + dir_off + 14 : base + dir_off + 16], "little")
        for i in range(n_named + n_id):
            e = base + dir_off + 16 + i * 8
            name_field = int.from_bytes(data[e : e + 4], "little")
            data_field = int.from_bytes(data[e + 4 : e + 8], "little")
            nm = (
                name_at(name_field & 0x7FFFFFFF)
                if name_field & 0x80000000
                else f"#{name_field}"
            )
            if data_field & 0x80000000:
                yield from walk(data_field & 0x7FFFFFFF, path + [nm])
            else:
                de = base + data_field
                rva = int.from_bytes(data[de : de + 4], "little")
                size = int.from_bytes(data[de + 4 : de + 8], "little")
                yield path + [nm], rva, size

    yield from walk(0, [])


def extract_fonts(src):
    sys.path.insert(0, str(ROOT / "tools"))
    from apply_ru import PE

    data = Path(src).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"unsupported MetroExodusVR.dll SHA-256 {digest}; "
            f"expected v0.9.1 {EXPECTED_SOURCE_SHA256}"
        )
    pe = PE(data)
    found = {}
    for path, rva, size in resource_entries(pe, data):
        name = next((x for x in path if x in FONTS), None)
        if name is not None:
            off = pe.rva_to_off(rva)
            if off is None:
                raise RuntimeError(f"{name}: resource data not mapped")
            found[name] = bytes(data[off : off + size])
            print(f"{name}: rva {rva:#x} size {size}")
    missing = set(FONTS) - set(found)
    if missing:
        raise RuntimeError(f"fonts not found in resources: {sorted(missing)}")
    return {name: (found[name],) + FONTS[name] for name in FONTS}


def width_scale(base, donor):
    """Median advance ratio (base/donor) over the shared ASCII letters."""
    bc = base.getBestCmap()
    dc = donor.getBestCmap()
    bh = base["hmtx"]
    dh = donor["hmtx"]
    bupm = base["head"].unitsPerEm
    dupm = donor["head"].unitsPerEm
    ratios = []
    for cp in (
        list(range(0x30, 0x3A)) + list(range(0x41, 0x5B)) + list(range(0x61, 0x7B))
    ):
        if cp in bc and cp in dc:
            b = bh[bc[cp]][0] / bupm
            d = dh[dc[cp]][0] / dupm
            if d:
                ratios.append(b / d)
    ratios.sort()
    return ratios[len(ratios) // 2]


def merge(base_path, donor_path, xscale):
    base = TTFont(base_path)
    donor = TTFont(donor_path)
    if "glyf" not in base or "glyf" not in donor:
        raise RuntimeError("only TrueType outlines are supported")

    if xscale == "match":
        xscale = width_scale(base, donor)
    yscale = base["head"].unitsPerEm / donor["head"].unitsPerEm

    bcmap = base.getBestCmap()
    dcmap = donor.getBestCmap()
    glyphs = base["glyf"]
    hmtx = base["hmtx"]
    donor_set = donor.getGlyphSet()
    order = list(base.getGlyphOrder())
    unicode_tables = [
        table for table in base["cmap"].tables
        if table.isUnicode() and table.format in (4, 12)
    ]
    if not unicode_tables:
        raise RuntimeError("base font has no Unicode cmap format 4/12")

    added = 0
    mapped = 0
    for cp in CYRILLIC:
        if cp in bcmap or cp not in dcmap:
            continue
        dname = dcmap[cp]
        gname = "uni%04X" % cp
        if gname not in glyphs:
            rec = DecomposingRecordingPen(donor_set)
            donor_set[dname].draw(rec)
            pen = TTGlyphPen(None)
            rec.replay(TransformPen(pen, Transform().scale(xscale, yscale)))
            glyph = pen.glyph()
            glyph.recalcBounds(glyphs)
            glyphs[gname] = glyph
            adv, _lsb = donor["hmtx"][dname]
            hmtx[gname] = (
                round(adv * xscale),
                glyph.xMin if glyph.numberOfContours else 0,
            )
            order.append(gname)
            added += 1
        for table in unicode_tables:
            table.cmap[cp] = gname
        mapped += 1

    base.setGlyphOrder(order)
    base["maxp"].numGlyphs = len(order)
    # OS/2 Unicode range bit 9 of ulUnicodeRange1 denotes Cyrillic.
    try:
        os2 = base["OS/2"]
        os2.ulUnicodeRange1 |= 1 << 9
        os2.usFirstCharIndex = min(os2.usFirstCharIndex, min(CYRILLIC))
        os2.usLastCharIndex = max(os2.usLastCharIndex, max(CYRILLIC))
    except Exception:
        pass
    return base, added, mapped, xscale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(FONT_DIR))
    args = ap.parse_args()

    fonts = extract_fonts(args.src)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = out_dir / "src"
    tmp_dir.mkdir(exist_ok=True)

    for name, (blob, donor_key, scale) in fonts.items():
        raw = tmp_dir / f"{name}.ttf"
        raw.write_bytes(blob)
        donor = DONOR[donor_key]
        if not donor.exists():
            raise SystemExit(f"missing donor font {donor}")
        font, added, mapped, used = merge(str(raw), str(donor), scale)
        out = out_dir / f"{name}.ttf"
        font.save(str(out))
        check = TTFont(str(out))
        cmap = check.getBestCmap()
        donor_font = TTFont(str(donor))
        donor_cmap = donor_font.getBestCmap()
        missing = [cp for cp in CYRILLIC if cp in donor_cmap and cp not in cmap]
        if missing:
            raise RuntimeError(
                f"{out.name}: saved font is missing Cyrillic cmap entries: "
                + ", ".join(f"U+{cp:04X}" for cp in missing)
            )
        check.close()
        donor_font.close()
        print(
            f"{out.name}: +{added} outlines, {mapped} cmap mappings, "
            f"xscale {used:.3f}, {out.stat().st_size} bytes"
        )
    print(f"fonts written to {out_dir}")


if __name__ == "__main__":
    main()
