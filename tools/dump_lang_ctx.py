"""Dump context around CP1251 Russian words found in game VFS files."""

import os

BASE = r"F:\SteamLibrary\steamapps\common\Metro Exodus"

files = [
    r"patch_03.vfs1",
    r"content_43.vfs1",
    r"content_27_textures.vfs0",
    r"patch_04_textures.vfs1",
]
words = [
    "Язык",
    "Игра",
    "Звук",
    "Настройки",
    "Графика",
    "Управление",
    "Субтитры",
    "Интерфейс",
    "Клавиши",
]

for rel in files:
    p = os.path.join(BASE, rel)
    if not os.path.exists(p):
        print("missing", p)
        continue
    with open(p, "rb") as f:
        data = f.read(64 * 1048576)
    print("\n=== %s (first %d MB) ===" % (rel, len(data) // 1048576))
    for w in words:
        pat = w.encode("cp1251")
        start = 0
        count = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            count += 1
            if count <= 3:
                lo = max(0, i - 160)
                hi = min(len(data), i + 200)
                chunk = data[lo:hi].decode("cp1251", errors="replace")
                chunk = "".join(
                    c
                    if (c == "\n" or 0x20 <= ord(c) < 0x7F or 0x400 <= ord(c) <= 0x4FF)
                    else "."
                    for c in chunk
                )
                print("  [%s] offset 0x%X:\n    %s" % (w, i, chunk.replace("\n", " ")))
            start = i + 1
        if count:
            print("  %s: %d hits" % (w, count))
