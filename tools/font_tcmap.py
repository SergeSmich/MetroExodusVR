"""Back-compat shim: ``tcmap`` dumping now lives in ``tools/font_table.py``.

The original version of this script decoded the ``tcmap`` payload as an array
of ``u16`` values, which is wrong: the payload is ``u32 count`` followed by
``count`` records of **23 bytes** each (see ``font_table.RECORD``), so every
number it printed was misaligned noise.  ``A-0007 §6`` flagged it; the real
parser is ``font_table.parse()``.

Kept so that older notes and scripts that call this name still work::

    python tools/font_tcmap.py work/fonts_ru.bin --dump
"""

import sys

from font_table import RECORD, parse, record


def main():
    path = sys.argv[1]
    fonts = parse(path)
    print(f"{path}: {len(fonts)} font descriptors, {RECORD} bytes per glyph record")
    for f in fonts:
        n = sum(1 for i in range(f["count"]) if record(f, i)["inked"])
        print(f"  [{f['idx']:2d}] {f['alias']:16s} {f['count']:3d} entries, "
              f"{n:3d} with ink  -> {f['resource']}")
    if "--dump" in sys.argv:
        for f in fonts:
            print(f"\n--- {f['alias']} ({f['resource']})")
            for i in range(f["count"]):
                r = record(f, i)
                if r["inked"]:
                    print(f"  0x{i:02x}: u={r['u']:4d} v={r['v']:4d} w={r['w']:3d} "
                          f"h={r['h']:3d} bx={r['bx']:3d} by={r['by']:3d} adv={r['adv']:3d}")


if __name__ == "__main__":
    main()
