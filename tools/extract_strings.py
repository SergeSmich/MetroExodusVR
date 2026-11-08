import json, re, sys, os

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402


def extract(path, min_len=3):
    with open(path, "rb") as f:
        data = f.read()
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}", data):
        out.append({"off": m.start(), "s": m.group().decode("ascii")})
    return data, out


def main():
    path = str(re_paths.DLL)
    data, strings = extract(path)
    print("total strings:", len(strings))
    out_json = str(re_paths.WORK / "strings_ascii.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(strings, f, ensure_ascii=False, indent=0)
    print("saved", out_json)

    # Show cluster around specific known UI anchors
    anchors = [
        "Foveated",
        "Manual Reloading",
        "VR HINTS",
        "RegisterSettings total",
        "Turns off the game",
    ]
    for a in anchors:
        print("\n=== anchor", a)
        for i, e in enumerate(strings):
            if a in e["s"]:
                lo = max(0, i - 8)
                hi = min(len(strings), i + 12)
                print(f"--- at index {i} offset 0x{e['off']:X}")
                for j in range(lo, hi):
                    print(
                        f"  [{j}] 0x{strings[j]['off']:08X} {strings[j]['s'][:150]!r}"
                    )
                break


if __name__ == "__main__":
    main()
