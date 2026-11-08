#!/usr/bin/env python3
"""Validate ru/ui2.json against the DLL tables and the game's Russian charmap."""

import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import apply_ru as A  # noqa: E402

IB = 0x180000000
TABLES = {
    table: (base, stride, body_off, title_off)
    for table, (base, stride, body_off, _sv, title_off) in A.UI2_TABLES.items()
}


def lng_charmap(path):
    """Charmap chunk of a Metro .lng (chunk id 1 holds u16 codepoints)."""
    d = Path(path).read_bytes()
    p = 0
    while p + 8 <= len(d):
        cid, size = struct.unpack_from("<II", d, p)
        p += 8
        if cid == 1:
            return list(struct.unpack("<%dH" % (size // 2), d[p : p + size]))
        p += size
    raise ValueError(f"{path}: no charmap chunk")


def load_charmap():
    """Codepoints the localization charmap can express.

    ``ru/charmap.txt`` is authoritative (it is what the patcher encodes with);
    ``work/stable_ru.lng`` is only a cross-check when it is present.
    """
    cps = set(A.load_charmap())
    lng = ROOT / "work" / "stable_ru.lng"
    if lng.is_file():
        from_lng = set(lng_charmap(lng))
        if from_lng != cps:
            print(
                f"NOTE: ru/charmap.txt and {lng.name} disagree "
                f"({len(cps ^ from_lng)} codepoints); the patcher uses ru/charmap.txt"
            )
            cps |= from_lng
    return cps


def check_text(label, orig, ru, charmap, errors):
    for ch in ru:
        if ch in "\n\t":
            continue
        if ord(ch) not in charmap:
            errors.append(f"{label}: char {ch!r} U+{ord(ch):04X} not in charmap")
    toks_o = set(re.findall(r"<[^<>]+>", orig))
    toks_r = set(re.findall(r"<[^<>]+>", ru))
    if toks_o != toks_r:
        errors.append(
            f"{label} token mismatch missing={toks_o - toks_r} extra={toks_r - toks_o}"
        )
    if orig.count("[") != ru.count("["):
        errors.append(f"{label}: '[' count mismatch")
    if orig.count("]") != ru.count("]"):
        errors.append(f"{label}: ']' count mismatch")
    if orig.count("\n") != ru.count("\n"):
        errors.append(f"{label}: newline count mismatch")


def read_slot(d, pe, slot):
    off = pe.rva_to_off(slot)
    if off is None:
        return None
    return struct.unpack_from("<QQ", d, off)


def main():
    data = json.loads((ROOT / "ru" / "ui2.json").read_text(encoding="utf-8"))
    charmap = load_charmap()
    errors = []
    tables_only = not Path(A.DEFAULT_SRC).is_file()
    if tables_only:
        print(f"NOTE: {A.DEFAULT_SRC} not found; checking ru/ui2.json without the DLL")
        for table, entries in data.items():
            for e in entries:
                label = f"{table}[{e['index']}]"
                if "ru_title" in e:
                    check_text(
                        label + ".title", e["orig_title"], e["ru_title"], charmap, errors
                    )
                check_text(label, e["orig"], e["ru"], charmap, errors)
        if errors:
            for x in errors:
                print("ERROR", x)
            return 1
        print("ui2 ok")
        for table, entries in data.items():
            print(f"  {table}: {len(entries)} entries")
        return 0
    d = Path(A.DEFAULT_SRC).read_bytes()
    pe = A.PE(d)

    for table, entries in data.items():
        base, stride, body_off, title_off = TABLES[table]
        seen = set()
        for e in entries:
            i = e["index"]
            if i in seen:
                errors.append(f"{table}[{i}]: duplicate index")
            seen.add(i)
            slot = base + i * stride
            if title_off is not None:
                pair = read_slot(d, pe, slot + title_off)
                if pair is None:
                    errors.append(f"{table}[{i}]: title slot not mapped")
                else:
                    ptr, _ln = pair
                    actual = (
                        pe.read_cstr(ptr - IB, 400)
                        if IB <= ptr < IB + 0x2000000
                        else ""
                    )
                    if actual != e["orig_title"]:
                        errors.append(
                            f"{table}[{i}] title mismatch\n"
                            f"  expect={e['orig_title']!r}\n  actual={actual!r}"
                        )
                    check_text(
                        f"{table}[{i}].title",
                        e["orig_title"],
                        e["ru_title"],
                        charmap,
                        errors,
                    )
            pair = read_slot(d, pe, slot + body_off)
            if pair is None:
                errors.append(f"{table}[{i}]: body slot not mapped")
                continue
            ptr, _ln = pair
            if not (IB <= ptr < IB + 0x2000000):
                errors.append(f"{table}[{i}]: bad ptr {ptr:#x}")
                continue
            actual = pe.read_cstr(ptr - IB, 20000)
            if actual != e["orig"]:
                errors.append(
                    f"{table}[{i}] orig mismatch\n  expect={e['orig']!r}\n  actual={actual!r}"
                )
            check_text(f"{table}[{i}]", e["orig"], e["ru"], charmap, errors)

    if errors:
        for x in errors:
            print("ERROR", x)
        return 1
    print("ui2 ok")
    for table, entries in data.items():
        print(f"  {table}: {len(entries)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
