"""Build the 0.9.3 caption kit from the 0.9.2 plan.

Input : kit092/work/plan-0.9.2.json  (267 literals + display sites)
        kit092/ru/strings-0.9.2.tsv   (RVA / English / Russian)
Output: kit093/ru/plan-0.9.3.json    (same literals, new RVA + sites)
        kit093/ru/strings-0.9.3.tsv   (same rows, new RVA)

A literal is located by exact C-string match in .rdata/.data; its display
sites are the RIP-relative references found in .text, kind = mnemonic.
"""

import json
import struct
import sys
from collections import Counter
from pathlib import Path

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

ROOT = Path(__file__).resolve().parent.parent
DLL = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else r"F:\SteamLibrary\steamapps\common\Metro Exodus\versions\0.9.3\MetroExodusVR.dll"
)
KIT092 = ROOT / "kit092"
KIT093 = ROOT / "kit093"
PLAN092 = KIT092 / "work" / "plan-0.9.2.json"
TSV092 = KIT092 / "ru" / "strings-0.9.2.tsv"
OUT_PLAN = KIT093 / "ru" / "plan-0.9.3.json"
OUT_TSV = KIT093 / "ru" / "strings-0.9.3.tsv"


class Img:
    def __init__(self, path):
        self.path = Path(path)
        self.d = self.path.read_bytes()
        pe = pefile.PE(data=self.d, fast_load=True)
        self.secs = [
            (
                s.Name.rstrip(b"\0").decode(),
                s.VirtualAddress,
                s.PointerToRawData,
                s.Misc_VirtualSize,
                s.SizeOfRawData,
            )
            for s in pe.sections
        ]
        self.text = next(x for x in self.secs if x[0] == ".text")
        self.pdata = next(x for x in self.secs if x[0] == ".pdata")
        self.funcs = self._pdata()

    def _pdata(self):
        n, va, raw, vsz, rsz = self.pdata
        out = []
        for k in range(vsz // 12):
            b, e, _u = struct.unpack_from("<III", self.d, raw + k * 12)
            if b and e > b:
                out.append((b, e))
        out.sort()
        return out

    def sec_of(self, rva):
        for n, va, raw, vsz, rsz in self.secs:
            if va <= rva < va + max(vsz, rsz):
                return n
        return None

    def cstr(self, rva, limit=0x400):
        n, va, raw, vsz, rsz = next(
            x for x in self.secs if x[1] <= rva < x[1] + max(x[3], x[4])
        )
        o = raw + rva - va
        e = self.d.find(b"\0", o, o + limit)
        return self.d[o : e if e >= 0 else o + limit]


def rip_refs(img):
    """target rva -> [(site rva, mnemonic)] for every RIP-relative operand."""
    n, va, raw, vsz, rsz = img.text
    code = img.d[raw : raw + vsz]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    refs = {}
    off = 0
    step = 0x2000
    while off < len(code):
        got = list(md.disasm(code[off : off + step], va + off))
        if not got:
            off += 1
            continue
        for i in got:
            for op in i.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    tgt = i.address + i.size + op.mem.disp
                    refs.setdefault(tgt, []).append((i.address, i.mnemonic))
                    break
        off = got[-1].address + got[-1].size - va
    return refs


def occurrences(img, text, refs):
    nb = text.encode("latin-1", "replace") + b"\0"
    out = []
    i = 0
    while True:
        k = img.d.find(nb, i)
        if k < 0:
            break
        for n, va, raw, vsz, rsz in img.secs:
            if n in (".rdata", ".data") and raw <= k < raw + rsz:
                rva = va + k - raw
                if rva + len(nb) <= va + vsz:
                    out.append((n, rva))
                break
        i = k + 1
    for n, rva in out:
        yield n, rva, refs.get(rva, [])


def pick(cands, want):
    """Choose the occurrence whose reference multiset matches the 0.9.2 sites."""
    best = None
    for n, rva, rs in cands:
        kinds = Counter(m for _s, m in rs)
        score = (
            1 if len(rs) == want else 0,
            1 if len(rs) else 0,
            -abs(len(rs) - want),
            len(rs),
        )
        if best is None or score > best[0]:
            best = (score, n, rva, rs)
    return best


def main():
    img = Img(DLL)
    print(f"image {img.path}")
    print(f"funcs {len(img.funcs)}")
    refs = rip_refs(img)
    print(f"rip refs {sum(len(v) for v in refs.values())} distinct targets {len(refs)}")

    doc = json.loads(PLAN092.read_text(encoding="utf-8"))
    plan092 = doc["plan"]
    out = []
    problems = []
    for e in plan092:
        cands = list(occurrences(img, e["text"], refs))
        if not cands:
            problems.append(f"{e['addr']:#x}: literal not found: {e['text'][:60]!r}")
            continue
        want = len(e["sites"])
        best = pick(cands, want)
        score, n, rva, rs = best
        if not rs:
            problems.append(
                f"{e['addr']:#x}: {e['text'][:50]!r} found at {rva:#x} "
                f"({n}) but no RIP refs"
            )
        elif len(rs) != want:
            problems.append(
                f"{e['addr']:#x}: {e['text'][:50]!r} -> {rva:#x} has "
                f"{len(rs)} refs, 0.9.2 had {want}"
            )
        out.append(
            dict(
                addr=rva,
                text=e["text"],
                orig_len=e["orig_len"],
                sites=[[s, m] for s, m in rs],
            )
        )

    OUT_PLAN.parent.mkdir(parents=True, exist_ok=True)
    OUT_PLAN.write_text(
        json.dumps(
            {"plan": out, "funcs": [list(x) for x in img.funcs]}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT_PLAN} ({len(out)} entries)")

    by_addr = {}
    for e, p in zip(plan092, out):
        by_addr[e["addr"]] = p

    rows = []
    for line in TSV092.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        addr, en, ru = line.split("\t")
        a = int(addr, 16)
        p = by_addr.get(a)
        if p is None:
            problems.append(f"tsv {addr}: not in the plan")
            continue
        got = img.cstr(p["addr"]).decode("latin-1")
        if got != en:
            problems.append(f"tsv {addr}: {en!r} != {got!r} at {p['addr']:#x}")
            continue
        rows.append(f"0x{p['addr']:x}\t{en}\t{ru}")
    header = (
        "# Metro Exodus VR 0.9.3 -- mod UI captions\n"
        "# columns: RVA <TAB> English <TAB> Russian\n"
    )
    OUT_TSV.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {OUT_TSV} ({len(rows)} rows)")
    print(f"problems {len(problems)}")
    for x in problems:
        print("  ", x)


if __name__ == "__main__":
    main()
