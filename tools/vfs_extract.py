"""Extract a single file from a Metro Exodus VFS package (content.vfx registry).

Usage:
  python tools/vfs_extract.py <vfx-registry> <file-path-in-vfs> <out-file>
e.g.
  python tools/vfs_extract.py content.vfx "content\\localization\\stable_ru.lng" ru.lng
"""

import os
import struct
import sys

FLAG_FOLDER = 8
FLAG_NEW = 4


def lz4_block_decode(src, dst, prefix_len=0):
    """Decode one raw LZ4 block appending to bytearray dst.

    prefix_len is the offset in dst where the *current* block starts; matches may
    reference data before it (up to 64 KiB back), which is what
    LZ4_decompress_fast_withPrefix64k allows.
    """
    i = 0
    n = len(src)
    out_start = len(dst)
    while i < n:
        token = src[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]
                i += 1
                lit += b
                if b != 255:
                    break
        if lit:
            dst += src[i : i + lit]
            i += lit
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8)
        i += 2
        if off == 0:
            break
        mlen = token & 0x0F
        if mlen == 15:
            while True:
                b = src[i]
                i += 1
                mlen += b
                if b != 255:
                    break
        mlen += 4
        start = len(dst) - off
        if start < 0:
            raise ValueError("bad offset")
        for k in range(mlen):
            dst.append(dst[start + k])
    return len(dst) - out_start


def decompress_stream(comp):
    dst = bytearray()
    p = 0
    while p < len(comp):
        block_size, block_usize = struct.unpack_from("<II", comp, p)
        p += 8
        block = comp[p : p + block_size - 8]
        p += block_size - 8
        got = lz4_block_decode(block, dst)
        if got != block_usize:
            raise ValueError("block size mismatch %d != %d" % (got, block_usize))
    return bytes(dst)


class Stream:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def raw(self, n):
        v = self.d[self.p : self.p + n]
        self.p += n
        return v

    def strz(self):
        e = self.d.index(b"\x00", self.p)
        s = self.d[self.p : e]
        self.p = e + 1
        return s.decode("utf-8", "replace")

    def xname(self):
        hdr = self.u16()
        ln = hdr & 0xFF
        mask = (hdr >> 8) & 0xFF
        out = bytearray()
        for _ in range(ln - 1):
            out.append(self.d[self.p] ^ mask)
            self.p += 1
        self.p += 1
        return out.decode("latin-1")


def parse_registry(path):
    data = open(path, "rb").read()
    s = Stream(data)
    version = s.u32()
    s.u32()  # compression
    if version >= 3:
        s.strz()
    s.raw(16)
    npak = s.u32()
    nfiles = s.u32()
    ndup = s.u32()
    paks = []
    for _ in range(npak):
        name = s.strz()
        nlev = s.u32()
        levels = [s.strz() for _ in range(nlev)]
        chunk = s.u32()
        paks.append({"name": name, "levels": levels, "chunk": chunk})
    files = []
    for i in range(nfiles):
        flags = s.u16()
        f = {"flags": flags, "folder": bool(flags & FLAG_FOLDER)}
        if f["folder"]:
            f["num"] = s.u16()
            f["first"] = s.u32()
        else:
            f["pak"] = s.u16()
            f["off"] = s.u32()
            f["usize"] = s.u32()
            f["csize"] = s.u32()
        f["name"] = s.xname()
        files.append(f)
    return {"version": version, "paks": paks, "files": files}


def build_paths(files):
    out = []

    def walk(idx, prefix):
        f = files[idx]
        if f["folder"]:
            name = f["name"]
            newpref = (prefix + "\\" + name) if (prefix and name) else (prefix or name)
            for ci in range(f["first"], f["first"] + f["num"]):
                if ci < len(files):
                    walk(ci, newpref)
        else:
            path = (prefix + "\\" + f["name"]) if prefix else f["name"]
            out.append((path, f))

    walk(0, "")
    return out


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    regpath, want, outpath = sys.argv[1], sys.argv[2].lower(), sys.argv[3]
    base = os.path.dirname(os.path.abspath(regpath))
    reg = parse_registry(regpath)
    hit = None
    for p, f in build_paths(reg["files"]):
        if p.lower() == want:
            hit = (p, f)
            break
    if not hit:
        print("not found:", want)
        return 2
    p, f = hit
    pak = reg["paks"][f["pak"]]
    pakpath = os.path.join(base, pak["name"])
    with open(pakpath, "rb") as fh:
        fh.seek(f["off"])
        comp = fh.read(f["csize"])
    if f["csize"] == f["usize"]:
        data = comp
    else:
        data = decompress_stream(comp)
    if len(data) != f["usize"]:
        print("WARN size %d != %d" % (len(data), f["usize"]))
    with open(outpath, "wb") as fh:
        fh.write(data)
    print("extracted %s -> %s (%d bytes)" % (p, outpath, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
