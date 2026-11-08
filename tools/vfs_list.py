"""Minimal Metro Exodus VFX/VFS registry lister (ports MetroTools logic).

Usage:
  python tools/vfs_list.py [--patches] [--find substr]
Reads content.vfx (+ patch_*.vfx) and prints package names + matching paths.
"""

import os
import struct
import sys

BASE = str(re_paths.GAME)
PATCHES = [
    "patch.vfx0",
    "patch_00.vfx",
    "patch_01_shared.vfx",
    "patch_01.vfx",
    "patch_02.vfx",
    "patch_03.vfx",
    "patch_04.vfx",
]
FLAG_FOLDER = 8
FLAG_NEW = 4


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

    def i8(self):
        v = self.d[self.p]
        self.p += 1
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
        n = hdr & 0xFF
        mask = (hdr >> 8) & 0xFF
        out = bytearray()
        for _ in range(n - 1):
            out.append(self.i8() ^ mask)
        self.p += 1
        return out.decode("latin-1")


def parse(path):
    data = open(path, "rb").read()
    s = Stream(data)
    version = s.u32()
    comp = s.u32()
    content_version = ""
    if version >= 3:
        content_version = s.strz()
    guid = s.raw(16)
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
        f = {"idx": i, "flags": flags, "name": ""}
        if flags & FLAG_FOLDER:
            f["num"] = s.u16()
            f["first"] = s.u32()
            f["folder"] = True
        else:
            f["pak"] = s.u16()
            f["off"] = s.u32()
            f["usize"] = s.u32()
            f["csize"] = s.u32()
            f["folder"] = False
        f["name"] = s.xname()
        files.append(f)
    # duplicates (name omitted)
    for _ in range(ndup):
        flags = s.u16()
        if flags & FLAG_FOLDER:
            s.u16()
            s.u32()
        else:
            s.u16()
            s.u32()
            s.u32()
            s.u32()
            s.u32()
    return {
        "version": version,
        "comp": comp,
        "content_version": content_version,
        "guid": guid.hex(),
        "paks": paks,
        "files": files,
        "ndup": ndup,
        "path": path,
    }


def build_paths(files):
    """Return list of (path, file_dict) via DFS from root folder (idx 0)."""
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

    if files:
        walk(0, "")
    return out


def load_all(use_patches):
    regs = []
    base = os.path.join(BASE, "content.vfx")
    regs.append(parse(base))
    if use_patches:
        for p in PATCHES:
            fp = os.path.join(BASE, p)
            if os.path.exists(fp):
                try:
                    regs.append(parse(fp))
                except Exception as e:
                    print("  !! failed", p, e)
    return regs


def main():
    use_patches = "--patches" in sys.argv
    find = None
    if "--find" in sys.argv:
        find = sys.argv[sys.argv.index("--find") + 1].lower()
    regs = load_all(use_patches)
    for r in regs:
        print(
            "=== %s  v%d comp=%d files=%d paks=%d"
            % (
                os.path.basename(r["path"]),
                r["version"],
                r["comp"],
                len(r["files"]),
                len(r["paks"]),
            )
        )
        print("    packages:", ", ".join(p["name"] for p in r["paks"]))
        paths = build_paths(r["files"])
        if find:
            hits = [(p, f) for (p, f) in paths if find in p.lower()]
            print("    matches for %r: %d" % (find, len(hits)))
            for p, f in hits[:200]:
                print(
                    "      %-70s pak=%s off=%d u=%d c=%d"
                    % (p, f["pak"], f["off"], f["usize"], f["csize"])
                )
        else:
            print("    total files:", len(paths))
            for p, f in paths[:50]:
                print("      ", p)


if __name__ == "__main__":
    main()
