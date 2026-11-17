"""Find the second-layer (ptr,len) tables in 0.9.3 .rdata.

For every known entry (index i, orig text) of a table the slot is
``base + i*stride + body_off`` and holds (ptr,len).  We look up the text in
0.9.3, then intersect the implied ``base`` over all entries.
"""

import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pefuncs import PE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DLL = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else r"F:\SteamLibrary\steamapps\common\Metro Exodus\versions\0.9.3\MetroExodusVR.dll"
)
UI2 = ROOT / "kit092" / "ru" / "ui2-0.9.2.json"
TABLES = {
    "popups": (0x70, 0x10, True, None),
    "options": (0x20, 0x10, True, None),
    "hints": (0x28, 0x10, False, None),
    "hintpages": (0x20, 0x10, True, 0x00),
}
BASE = 0x180000000


def main():
    p = PE(str(DLL))
    doc = json.loads(UI2.read_text(encoding="utf-8"))

    def find_str(s):
        nb = s.encode("latin-1") + b"\0"
        out = []
        i = 0
        while True:
            k = p.d.find(nb, i)
            if k < 0:
                break
            for n, va, raw, vsz, rsz in p.secs:
                if n in (".rdata", ".data") and raw <= k < raw + rsz:
                    out.append(va + k - raw)
                    break
            i = k + 1
        return out

    # all (ptr,len) pair slots in .rdata/.data
    pairs = {}
    for n, va, raw, vsz, rsz in p.secs:
        if n not in (".rdata", ".data"):
            continue
        for o in range(raw, raw + rsz - 16, 8):
            ptr, ln = struct.unpack_from("<QQ", p.d, o)
            if BASE <= ptr < BASE + 0x2000000 and ln < 0x8000:
                pairs[va + o - raw] = (ptr - BASE, ln)

    for table, (stride, body_off, is_sv, title_off) in TABLES.items():
        items = doc.get(table, [])
        votes = Counter()
        per_item = []
        for it in items:
            i = it["index"]
            cands = find_str(it["orig"])
            if len(cands) != 1:
                per_item.append((i, len(cands), None))
                continue
            rva = cands[0]
            hits = [
                slot
                for slot, (ptr, ln) in pairs.items()
                if ptr == rva and (not is_sv or ln == len(it["orig"]))
            ]
            # slots in the entries are aligned to the stride
            base_votes = set()
            for slot in hits:
                base = slot - body_off - i * stride
                base_votes.add(base)
            if len(base_votes) == 1:
                votes.update(base_votes)
            per_item.append((i, len(hits), sorted(base_votes)))
        print(f"--- {table}: {len(items)} items, stride {stride:#x}")
        print("   votes:", [(hex(b), c) for b, c in votes.most_common(5)])
        bad = [x for x in per_item if x[1] != 1 or (x[2] and len(x[2]) != 1)]
        print(f"   items with ambiguity: {len(bad)}")
        for x in bad[:8]:
            print("     ", x)


if __name__ == "__main__":
    main()
