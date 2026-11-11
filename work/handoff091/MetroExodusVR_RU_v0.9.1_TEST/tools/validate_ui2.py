#!/usr/bin/env python3
"""Static validation of the v0.9.1 UI2 catalog (not a runtime glyph test)."""
import argparse
import json
import re
import struct
from pathlib import Path

import apply_ru as A

ROOT = Path(__file__).resolve().parent.parent
IMAGE_BASE = A.IMAGE_BASE


def load_charmap():
    chars = set()
    for line in (ROOT / "ru" / "charmap.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("U+"):
            chars.add(int(line[2:], 16))
    return chars


def check_text(label, orig, ru, charmap, errors):
    for ch in ru:
        if ch in "\n\t\r":
            continue
        if ord(ch) not in charmap:
            errors.append(f"{label}: glyph not in game RU charmap: {ch!r} U+{ord(ch):04X}")
    tokens_orig = set(re.findall(r"<[^<>]+>", orig))
    tokens_ru = set(re.findall(r"<[^<>]+>", ru))
    if tokens_orig != tokens_ru:
        errors.append(f"{label}: token mismatch missing={tokens_orig - tokens_ru} extra={tokens_ru - tokens_orig}")
    for mark in "[]":
        if orig.count(mark) != ru.count(mark):
            errors.append(f"{label}: {mark!r} count differs")
    if orig.count("\n") != ru.count("\n"):
        errors.append(f"{label}: newline count differs")


def read_pair(data, pe, slot):
    off = pe.rva_to_off(slot)
    if off is None:
        return None
    return struct.unpack_from("<QQ", data, off)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dll", type=Path, default=A.DEFAULT_SRC, help="original v0.9.1 MetroExodusVR.dll")
    args = ap.parse_args()
    data = json.loads(A.UI2_JSON.read_text(encoding="utf-8"))
    dll = args.dll.read_bytes()
    pe = A.PE(dll)
    charmap = load_charmap()
    errors = []

    # Validate the native page-caption translations against the same character
    # repertoire and preserve their markup/newline structure.
    for addr, orig, ru in A.parse_tsv(A.STRINGS_TSV):
        check_text(f"strings.tsv@{addr:#x}", orig, ru, charmap, errors)

    for table, entries in data.items():
        base, stride, body_off, _has_len, title_off = A.UI2_TABLES[table]
        seen = set()
        for item in entries:
            i = item["index"]
            if i in seen:
                errors.append(f"{table}[{i}]: duplicate catalog index")
            seen.add(i)
            slot = base + i * stride
            if title_off is not None:
                pair = read_pair(dll, pe, slot + title_off)
                if pair is None:
                    errors.append(f"{table}[{i}]: title slot is unmapped")
                else:
                    ptr, _length = pair
                    actual = pe.read_cstr(ptr - IMAGE_BASE, 400) if IMAGE_BASE <= ptr < IMAGE_BASE + 0x2000000 else ""
                    if actual != item["orig_title"]:
                        errors.append(f"{table}[{i}]: title mismatch: {actual!r}")
                    check_text(f"{table}[{i}].title", item["orig_title"], item["ru_title"], charmap, errors)
            pair = read_pair(dll, pe, slot + body_off)
            if pair is None:
                errors.append(f"{table}[{i}]: body slot is unmapped")
                continue
            ptr, _length = pair
            actual = pe.read_cstr(ptr - IMAGE_BASE, 30000) if IMAGE_BASE <= ptr < IMAGE_BASE + 0x2000000 else ""
            if actual != item["orig"]:
                errors.append(f"{table}[{i}]: original text mismatch: {actual[:100]!r}")
            check_text(f"{table}[{i}]", item["orig"], item["ru"], charmap, errors)

    if errors:
        for err in errors:
            print("ERROR", err)
        return 1
    print("UI2 catalog checks passed (static only)")
    for table, entries in data.items():
        print(f"  {table}: {len(entries)} entries")
    print("WARNING: this does not test byte decoding, glyph selection, or layout in the game.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
