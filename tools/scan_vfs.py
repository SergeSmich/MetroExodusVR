import sys, struct, os


def scan(path, needles, max_mb=4096, chunk=8 << 20):
    if not os.path.exists(path):
        print("MISSING", path)
        return
    pats = {}
    for enc in ("utf-8", "utf-16-le", "cp1251"):
        for n in needles:
            try:
                pats[(enc, n)] = n.encode(enc)
            except Exception:
                pass
    hits = {k: 0 for k in pats}
    total = 0
    with open(path, "rb") as f:
        prev = b""
        while True:
            data = f.read(chunk)
            if not data:
                break
            total += len(data)
            buf = prev + data
            for k, p in pats.items():
                i = 0
                while True:
                    j = buf.find(p, i)
                    if j < 0:
                        break
                    hits[k] += 1
                    i = j + len(p)
            prev = buf[-64:]
            if total >= max_mb * 1024 * 1024:
                break
    print(f"SCANNED {total / 1048576:.1f} MB {path}")
    for (enc, n), c in hits.items():
        if c:
            print(f"   {enc:9s} {n!r}: {c}")


if __name__ == "__main__":
    base = str(re_paths.GAME)
    files = sys.argv[1:]
    if not files:
        files = [
            os.path.join(base, "patch_00.vfs0"),
            os.path.join(base, "content_platform.vfs0"),
        ]
    for p in files:
        scan(p, ["Настройки", "Игра", "Параметры", "Графика"])
