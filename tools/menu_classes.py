#!/usr/bin/env python3
"""Parse Metro's ``menu_handles_storage.bin`` into class -> property -> default.

The file is a flat stream of NUL terminated tokens.  A definition looks like

    <Property> \\0 <Type> \\0 <default, binary, size by type> ...

with two composite types:

    choose \\0 <Property> \\0 <variant> \\0 <Type> \\0 <default>
    array  \\0 <Property> \\0 count \\0 u32 \\0 <count: u32>

A *class* is not named in the stream; it starts at ``render_mode``/``on_activate``
and ends when the property sequence stops.  What the parser therefore produces
is the ordered property list of each block plus, for every block that has one,
the literal ``font_name`` default.  ``tools/menu_classes.py --fonts`` prints only
those, which is what the translation work needs.

Usage:
    python tools/menu_classes.py [work/menu_handles_storage.bin] [--fonts]
"""

import sys
from pathlib import Path

TYPES = {
    "u8": 1, "s8": 1, "bool": 1, "bool8": 1,
    "u16": 2, "s16": 2,
    "u32": 4, "s32": 4, "fp32": 4,
    "u64": 8, "s64": 8, "fp64": 8,
    "color, u32": 4,
    "vec2f": 8, "vec3f": 12, "vec4f": 16,
    "vec2i": 8, "vec3i": 12, "vec4i": 16,
}


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def cstr(self):
        if self.p >= len(self.d):
            return None
        e = self.d.find(b"\0", self.p)
        if e < 0:
            return None
        s = self.d[self.p:e]
        self.p = e + 1
        return s

    def skip(self, n):
        self.p += n

    def u32(self):
        v = int.from_bytes(self.d[self.p:self.p + 4], "little")
        self.p += 4
        return v


IDENT_OK = set(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def printable(s):
    return s is not None and 0 < len(s) <= 72 and all(32 <= c < 127 for c in s)


def is_ident(s):
    """Property and class names are plain identifiers.

    Structural bytes (array flags, single byte enum values) also happen to be
    "printable" sometimes, so requiring an identifier is what keeps the stream
    aligned when a default is followed by a value byte instead of a name.
    """
    return (s is not None and 0 < len(s) <= 72 and s[:1].isalpha()
            and all(c in IDENT_OK for c in s))


def parse(data):
    """Yield (property_name, type, default) triples in file order."""
    r = Reader(data)
    while True:
        # A property name is preceded by its length byte.  Several byte-sized
        # defaults and array headers sit in the same stream, so this is what
        # keeps the reader aligned.
        skip_prefix(r)
        name = r.cstr()
        if name is None:
            return
        if not is_ident(name):
            # binary payload of the previous property (enum byte, array flags):
            # not a name, so it cannot start a definition.
            continue
        typ = r.cstr()
        if typ is None:
            return
        t = typ.decode("latin-1", "replace")
        if t == "choose":
            # <name> \0 choose \0 <variant name> \0 <variant type> \0 <default>
            # e.g. font_name \0 choose \0 font_name \0 stringz \0 menu \0
            variant = r.cstr()
            real = r.cstr()
            if real is None:
                return
            rt = real.decode("latin-1", "replace")
            dflt = read_default(r, rt)
            # A "choose" entry is followed by a 7 byte tail:
            #   <u8 1><u32 0><u8 0x69><u8 2><u8 1>  (constant in this file)
            # Only skip it when it is actually there, so that a format change
            # degrades to a "junk token" instead of silently misaligning.
            tail = r.d[r.p:r.p + 7]
            if len(tail) == 7 and tail[0] == 1 and tail[1:5] == b"\0\0\0\0" and tail[5:7] == b"i\x02":
                r.p += 7
            yield (name.decode("latin-1", "replace"), rt, dflt)
        elif t == "array":
            # <name> \0 array \0 <u32 flags> <u32 count> then a repeated
            # "\0 <element count> <name> \0 count \0 u32 \0" header.
            flags = r.u32()
            count = r.u32()
            yield (name.decode("latin-1", "replace"), t, count)
        elif t in TYPES:
            yield (name.decode("latin-1", "replace"), t, read_default(r, t))
        elif t == "stringz":
            yield (name.decode("latin-1", "replace"), t, read_default(r, t))
        else:
            # unknown type token: treat as opaque, keep going
            yield (name.decode("latin-1", "replace"), t, None)


def skip_prefix(r):
    """Step over a length byte that introduces the next property name."""
    d, p = r.d, r.p
    if p >= len(d) or d[p] == 0:
        return
    n = d[p]
    end = p + 1 + n
    if end < len(d) and d[end] == 0:
        chunk = d[p + 1:end]
        if chunk and is_ident(chunk):
            r.p += 1


def read_default(r, t):
    if t == "stringz":
        s = r.cstr()
        return s.decode("latin-1", "replace") if s is not None else None
    n = TYPES.get(t)
    if n:
        raw = r.d[r.p:r.p + n]
        r.skip(n)
        return raw.hex()
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = Path(args[0]) if args else Path("work/menu_handles_storage.bin")
    data = path.read_bytes()
    from collections import Counter
    props = list(parse(data))
    print(f"{path}: {len(props)} property entries")
    names = Counter(p[0] for p in props)
    print(f"distinct property names: {len(names)}")
    fn = [(i, p) for i, p in enumerate(props) if p[0] == "font_name"]
    print(f"font_name entries: {len(fn)}")
    c = Counter(p[2] for _, p in fn)
    for k, v in c.most_common():
        print(f"   {k!r:14} {v}")

    # Class blocks are delimited by their first property, "render_mode".
    anchors = [i for i, p in enumerate(props) if p[0] == "render_mode"]
    blocks = [props[a:b] for a, b in zip(anchors, anchors[1:] + [len(props)])]
    with_cap = [b for b in blocks if any(p[0] == "caption" for p in b)]
    empty = [b for b in with_cap
             if any(p[0] == "font_name" and p[2] == "" for p in b)]
    print(f"class blocks: {len(blocks)}; with a caption: {len(with_cap)};"
          f" of those with an empty font_name: {len(empty)}")


if __name__ == "__main__":
    main()
