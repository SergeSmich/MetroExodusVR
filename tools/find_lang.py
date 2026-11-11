"""Find where Metro Exodus stores localized text and in which encoding."""

import os, sys, glob

BASE = str(re_paths.GAME)

words = ["Настройки", "Графика", "Игра", "Звук", "Управление", "Язык"]
encs = ["utf-8", "utf-16-le", "cp1251"]
patterns = {}
for w in words:
    for e in encs:
        patterns[(w, e)] = w.encode(e)

files = []
for root, dirs, names in os.walk(BASE):
    # skip steam shader caches / huge dirs at top
    for n in names:
        p = os.path.join(root, n)
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz < 1024:
            continue
        files.append((sz, p))
files.sort(reverse=True)

print("files:", len(files))
print("top 25 by size:")
for sz, p in files[:25]:
    print("  %10.1f MB  %s" % (sz / 1048576, os.path.relpath(p, BASE)))


def scan(p, limit):
    hits = {}
    with open(p, "rb") as f:
        data = f.read(limit)
    for (w, e), pat in patterns.items():
        c = data.count(pat)
        if c:
            hits[(w, e)] = c
    return hits


# Pass 1: all files, first 64 MB each
LIMIT = 64 * 1048576
found = {}
for sz, p in files:
    h = scan(p, min(sz, LIMIT))
    if h:
        found[p] = h
        print("\nHIT %s (%.1f MB)" % (os.path.relpath(p, BASE), sz / 1048576))
        for (w, e), c in h.items():
            print("   %-12s %-9s x%d" % (w, e, c))

if not found:
    print("\nNo hits in first 64MB of any file.")

# Also look for localization file names in headers
print("\n--- filename probes ---")
probes = [b"localization", b".lng", b"localization.lng", b"lng"]
for sz, p in files[:60]:
    with open(p, "rb") as f:
        head = f.read(16 * 1048576)
    for pr in probes:
        if pr in head:
            print(
                "%s: contains %r at %s"
                % (os.path.relpath(p, BASE), pr, [head.find(pr)])
            )
            break
