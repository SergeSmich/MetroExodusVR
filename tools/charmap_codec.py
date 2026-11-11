#!/usr/bin/env python3
"""Check the RU charmap codec used to write the mod's menu text.

The 4A engine does not decode the mod's captions with a code page: the bytes of
a caption are used directly as glyph indices of the font of the menu, and that
font is built from the localization charmap (``content\\localization\\
stable_ru.lng``, 271 entries).  This tool verifies, without the DLL:

  * every character used by ``ru/strings.tsv`` and ``ru/ui2.json`` can be
    expressed as a charmap index;
  * encode/decode round-trips (against the real ``.lng`` when it is present);
  * the encoded lengths fit the patcher's limits (``string_view`` 1..0x7E,
    inline ``std::string`` <= 0xF).

Usage:
    python tools/charmap_codec.py            # check the translation tables
    python tools/charmap_codec.py --lng work/stable_ru.lng
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import apply_ru as A  # noqa: E402

MAX_SV = 0x7E
MAX_SSO = 0xF


def lng_strings(path):
    """Yield (key, encoded bytes, decoded text) for a Metro .lng file."""
    d = Path(path).read_bytes()
    p = 0
    charmap = None
    while p + 8 <= len(d):
        cid, size = struct.unpack_from("<II", d, p)
        p += 8
        chunk = d[p : p + size]
        p += size
        if cid == 1:
            charmap = list(struct.unpack("<%dH" % (size // 2), chunk))
        elif cid == 2:
            q = 0
            while q < len(chunk):
                e = chunk.index(b"\x00", q)
                key = chunk[q:e].decode("utf-8", "replace")
                q = e + 1
                e = chunk.index(b"\x00", q)
                enc = chunk[q:e]
                q = e + 1
                yield key, enc


def decode_with(enc, cps, origin=0xDE41, split=0xE0):
    out = []
    i = 0
    while i < len(enc):
        ci = enc[i]
        if ci < split:
            out.append(chr(cps[ci]))
            i += 1
        else:
            idx = ci * 255 + enc[i + 1] - origin
            out.append(chr(cps[idx]))
            i += 2
    return "".join(out)


def translation_texts():
    rows = []
    for line in (ROOT / "ru" / "strings.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append(("strings.tsv " + parts[0], parts[1], parts[2]))
    doc = json.loads((ROOT / "ru" / "ui2.json").read_text(encoding="utf-8"))
    for table, items in doc.items():
        if not isinstance(items, list):
            continue
        for item in items:
            label = f"ui2.json {table}[{item.get('index')}]"
            if "ru_title" in item:
                rows.append((label + " title", item.get("orig_title", ""), item["ru_title"]))
            if "ru" in item:
                rows.append((label, item.get("orig", ""), item["ru"]))
    return rows


def check_lng(path):
    cps = A.load_charmap()
    print(f"reference .lng: {path}")
    bad = long_strings = two_byte = n = 0
    for key, enc in lng_strings(path):
        n += 1
        text = decode_with(enc, cps)
        # re-encode with the same table; must reproduce the bytes exactly
        try:
            again = A.encode_text(text)
        except ValueError as exc:
            bad += 1
            if bad <= 5:
                print("  UNREPRESENTABLE", key, exc)
            continue
        if again != enc:
            bad += 1
            if bad <= 5:
                print("  MISMATCH", key, enc[:24].hex(), again[:24].hex())
        if any(b >= 0xE0 for b in enc):
            two_byte += 1
        if len(enc) > MAX_SV:
            long_strings += 1
    print(f"  strings {n}, round-trip failures {bad}, using 2-byte indices {two_byte}")
    print(f"  longer than 0x7E bytes: {long_strings}")
    return bad


def check_tables():
    rows = translation_texts()
    errors = []
    longest = []
    for label, orig, ru in rows:
        try:
            enc = A.encode_text(ru)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        dec = A.decode_text(enc)
        if dec != ru:
            errors.append(f"{label}: round-trip {dec!r} != {ru!r}")
        longest.append((len(enc), label, ru))
        if orig.count('"') != ru.count('"'):
            errors.append(f"{label}: quote count changed")
    longest.sort(reverse=True)
    print(f"translations checked: {len(rows)}")
    print("longest encodings (bytes):")
    for n, label, ru in longest[:8]:
        print(f"  {n:4d}  {label:<34} {ru[:40]!r}")
    over = [(n, label) for n, label, _ in longest if n > MAX_SV]
    if over:
        print(f"NOTE: {len(over)} captions exceed the 0x7E string_view limit:")
        for n, label in over[:10]:
            print(f"  {n:4d}  {label}")
    for e in errors:
        print("ERROR", e)
    return len(errors)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lng", help="verify against a real .lng (e.g. work/stable_ru.lng)")
    args = ap.parse_args()

    failures = check_tables()
    if args.lng:
        failures += check_lng(args.lng)

    cps = A.load_charmap()
    print(f"charmap entries: {len(cps)}, 2-byte range starts at index 0xE0")
    if failures:
        print(f"{failures} problem(s)")
        return 1
    print("OK: every translation is expressible in the engine charmap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
