"""Verify ru/caption_filter.json against A-0021: SHA-256 + FNV-1a vectors."""

import hashlib
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"F:\Projects\MetroExodusVR\ru\caption_filter.json")
raw = P.read_bytes()
print("sha256:", hashlib.sha256(raw).hexdigest())
print("expected 5db19b331f971c54a7968cbfcc9fb7f89688da5f07f0919dc178d0ac42ddfa51")
print(
    "sha ok:",
    hashlib.sha256(raw).hexdigest()
    == "5db19b331f971c54a7968cbfcc9fb7f89688da5f07f0919dc178d0ac42ddfa51",
)

doc = json.loads(raw.decode("utf-8"))
table = sorted({int(e["hash32"]) & 0xFFFFFFFF for e in doc["entries"]})
print("table size:", len(table))


def fnv(b: bytes) -> int:
    h = 0x811C9DC5
    for x in b:
        h ^= x
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


pos = [
    ("НЕТ", "33 49 3a", 0x44512571),
    ("РЕЗКО", "48 49 4c 40 3f", 0x3412CE3B),
    (
        "УГОЛ РЕЗКОГО ПОВОРОТА",
        "4a 4f 3f 50 01 48 49 4c 40 3f 4f 3f 01 3c 3f 37 3f 48 3f 3a 35",
        0xAAC9273A,
    ),
]
neg = [
    ("FSR", "46 53 52", 0x07AFAB64),
    ("DLSS", "44 4c 53 53", 0x621AAA8B),
    ("TAA", "54 41 41", 0x1E33DE25),
    ("$hints", "24 68 69 6e 74 73", 0xA1DF6FC3),
]

ok = True
for name, hexs, want in pos:
    b = bytes.fromhex(hexs.replace(" ", ""))
    got = fnv(b)
    in_tab = got in table
    good = got == want and in_tab
    ok &= good
    print(
        f"POS {name!r}: fnv={got:#010x} want={want:#010x} in_table={in_tab} {'OK' if good else 'FAIL'}"
    )

for name, hexs, want in neg:
    b = bytes.fromhex(hexs.replace(" ", ""))
    got = fnv(b)
    in_tab = got in table
    good = got == want and not in_tab
    ok &= good
    print(
        f"NEG {name!r}: fnv={got:#010x} want={want:#010x} in_table={in_tab} {'OK' if good else 'FAIL'}"
    )

print("ALL OK" if ok else "MISMATCH")
