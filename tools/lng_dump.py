"""Parse a Metro Exodus .lng file: dump charmap and selected strings.

Usage:
  python tools/lng_dump.py work/stable_ru.lng [--chars N] [--find substr] [--key KEY]
"""

import struct
import sys


def load(path):
    data = open(path, "rb").read()
    p = 0
    charmap = None
    strings = []
    while p + 8 <= len(data):
        cid, csize = struct.unpack_from("<II", data, p)
        p += 8
        chunk = data[p : p + csize]
        p += csize
        if cid == 1:
            charmap = list(struct.unpack("<%dH" % (csize // 2), chunk))
        elif cid == 2:
            q = 0
            while q < len(chunk):
                e = chunk.index(b"\x00", q)
                key = chunk[q:e].decode("utf-8", "replace")
                q = e + 1
                e = chunk.index(b"\x00", q)
                enc = chunk[q:e]
                q = e + 1
                out = []
                i = 0
                while i < len(enc):
                    ci = enc[i]
                    if ci < 224:
                        out.append(charmap[ci])
                    else:
                        nxt = enc[i + 1]
                        idx = ci * 255 + nxt - 0xDE41
                        out.append(charmap[idx])
                        i += 1
                    i += 1
                strings.append((key, "".join(chr(c) for c in out)))
        else:
            pass
    return charmap, strings


def main():
    path = sys.argv[1]
    charmap, strings = load(path)
    if "--chars" in sys.argv:
        n = int(sys.argv[sys.argv.index("--chars") + 1])
        print("charmap entries:", len(charmap))
        for i, c in enumerate(charmap[:n]):
            print("%3d U+%04X %r" % (i, c, chr(c)))
    if "--find" in sys.argv:
        sub = sys.argv[sys.argv.index("--find") + 1].lower()
        for k, v in strings:
            if sub in k.lower() or sub in v.lower():
                print("%-40s %s" % (k, v))
    if "--key" in sys.argv:
        key = sys.argv[sys.argv.index("--key") + 1]
        for k, v in strings:
            if k == key:
                print("%-40s %s" % (k, v))
    if "--stats" in sys.argv:
        print("strings:", len(strings), "chars:", len(charmap))


if __name__ == "__main__":
    main()
