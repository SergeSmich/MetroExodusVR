"""List entries of Metro Exodus ``content\\config.bin`` by CRC32 name.

Names come from MetroEX's ``MetroConfigNames.h`` list (``work/metroex_MetroConfigNames.h``).

Usage: python tools/config_dump.py [substring]
"""

import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES_H = ROOT / "work" / "metroex_MetroConfigNames.h"
CONFIG_BIN = ROOT / "work" / "config.bin"


def load_names():
    text = NAMES_H.read_text(encoding="utf-8", errors="replace")
    names = {}
    for m in re.finditer(r'AddName\("(.*?)"\);', text):
        s = m.group(1).replace("\\\\", "\\")
        names[zlib.crc32(s.encode()) & 0xFFFFFFFF] = s
    return names


def main():
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    names = load_names()
    data = CONFIG_BIN.read_bytes()
    pos = 0
    entries = []
    while pos + 8 <= len(data):
        crc, size = struct.unpack_from("<II", data, pos)
        pos += 8
        entries.append((crc, size, pos))
        pos += size
    print(f"entries {len(entries)} end {pos:#x} len {len(data):#x}")
    known = sum(1 for crc, _, _ in entries if crc in names)
    print(f"known names {known}/{len(entries)}")
    for crc, size, off in entries:
        name = names.get(crc)
        if name is None:
            continue
        if needle and needle not in name.lower():
            continue
        print(f"{crc:#010x} {size:8d} {off:#010x} {name}")


if __name__ == "__main__":
    main()
