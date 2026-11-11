#!/usr/bin/env python3
"""EXPERIMENTAL v0.9.1 patcher for MetroExodusVR.dll.

This version-specific port redirects mod UI strings to a new PE section and
updates known inline string-copy sites.  The patch structure passes static
verification, but the CP1251 encoding of the mod's custom UI has NOT been
validated in the game.  Do not treat the result as a release patch until a
Windows/VR test confirms the glyph mapping and layout.

Usage (CP1251 is an explicit, experimental test hypothesis only):
    python tools/apply_ru.py --src ORIGINAL_0.9.1.dll --check --no-fonts --experimental-cp1251
    python tools/apply_ru.py --src ORIGINAL_0.9.1.dll --out TEST.dll --verify --experimental-cp1251

Do not install a CP1251 build in the main game directory. Existing analysis notes
report that the custom UI renderer does not display this encoding correctly.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import (
    X86_OP_IMM,
    X86_OP_MEM,
    X86_OP_REG,
    X86_REG_RBP,
    X86_REG_RAX,
    X86_REG_RDX,
    X86_REG_RIP,
    X86_REG_RSP,
    X86_REG_R11,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "work" / "0.9.1" / "versions" / "0.9.1" / "MetroExodusVR.dll"
DEFAULT_OUT = ROOT / "build" / "MetroExodusVR.dll"
STRINGS_TSV = ROOT / "ru" / "strings-0.9.1.tsv"
EXPECTED_SOURCE_SHA256 = "fbbf2812bc7c3304a22829249aba334c812a326baf75fc5c2a75e559202c40b4"
UI2_JSON = ROOT / "ru" / "ui2-0.9.1.json"

# Embedded font resources that have to carry Cyrillic before the strings can be
# displayed.  The files are produced by tools/merge_cyrillic.py.
FONT_DIR = ROOT / "build" / "fonts"
FONT_RESOURCES = (
    "INFO_BARLOW_CONDENSED_SEMIBOLD",
    "INFO_INTER_MEDIUM",
    "INFO_INTER_REGULAR",
    "INFO_INTER_SEMIBOLD",
)

IMAGE_BASE = 0x180000000

SECT_ALIGN = 0x1000
FILE_ALIGN = 0x200

# Second UI layer: tables of (ptr, len) pairs in .rdata.  Each tuple is
# (table base RVA, entry stride, body slot offset, body has an explicit length,
# title slot offset or None).
UI2_TABLES = {
    "popups": (0x4BABC0, 0x70, 0x10, True, None),
    "options": (0x4C06A0, 0x20, 0x10, True, None),
    "hints": (0x4B6768, 0x28, 0x10, False, None),
    "hintpages": (0x4B85E0, 0x20, 0x10, True, 0x00),
}

# Literals that are neither captions nor table entries but still show up in the
# UI.  They are built inline, so they get the same copy-stub treatment.
EXTRA_STRINGS = (
    dict(
        orig="VR HINTS",
        ru="СОВЕТЫ VR",
        lit=0x4B85C0,
        site=0x843FC,
        lit_len=8,
        cap=0xF,
        allow_heap=False,
    ),
    dict(
        orig="VR GAMEPAD LAYOUT",
        ru="ГЕЙМПАД VR",
        lit=0x4B5860,
        site=0x7C20C,
        lit_len=0x11,
        cap=None,
        allow_heap=True,
    ),
)

# Only the mod's own menu/page-building code is redirected.
MENU_LO = 0xB0000
MENU_HI = 0xC0000

# offset of the immediate byte in a printable-ASCII check:
#   cmp al, 0x5e  (after `sub al, 0x20`)  ->  cmp al, 0xff  (any byte)
#   cmp cl, 0x5e  (after `sub cl, 0x20`)  ->  cmp cl, 0xff  (any byte)
# 0xA4728 page builder, 0xA4C76 option-list builder, 0xA6556 vector-of-captions
# validator (runs before a menu page is applied, rejects non-ASCII).
VALIDATORS = (0xA4728, 0xA4C76, 0xA6556)

# std::string SSO capacity used by all inline constructions in the menu code
SSO_CAP = 0xF
MAX_LEN = 0x7E  # caption length limit enforced by the page builder

BASE_NAMES = {
    X86_REG_RSP: "rsp",
    X86_REG_RBP: "rbp",
    X86_REG_RDX: "rdx",
    X86_REG_R11: "r11",
}

HEAP_BASES = {
    X86_REG_RAX: "rax",
}


def encode_text(s):
    """Encode the current experimental candidate as CP1251.

    IMPORTANT: repository research says the custom UI2 renderer may use a
    US-charmap instead.  This encoder is a test hypothesis, not an established
    runtime fact.  Keep the original DLL and verify rendered text on Windows.
    """
    try:
        enc = s.encode("cp1251")
    except UnicodeEncodeError as exc:
        raise ValueError(
            f"{s!r}: character {s[exc.start]!r} (U+{ord(s[exc.start]):04X}) "
            "cannot be encoded as CP1251"
        ) from None
    if 0 in enc:
        raise ValueError(f"encoded {s!r} contains a NUL byte")
    return enc


class PE:
    def __init__(self, data):
        self.data = bytearray(data)
        self.e_lfanew = struct.unpack_from("<I", self.data, 0x3C)[0]
        self.nsec = struct.unpack_from("<H", self.data, self.e_lfanew + 6)[0]
        self.size_opt = struct.unpack_from("<H", self.data, self.e_lfanew + 20)[0]
        self.opt = self.e_lfanew + 24
        if struct.unpack_from("<H", self.data, self.opt)[0] != 0x20B:
            raise RuntimeError("expected PE32+")
        self.size_image = struct.unpack_from("<I", self.data, self.opt + 56)[0]
        self.size_headers = struct.unpack_from("<I", self.data, self.opt + 60)[0]
        self.sect_table = self.opt + self.size_opt
        self.sections = []
        for i in range(self.nsec):
            off = self.sect_table + 40 * i
            name = bytes(self.data[off : off + 8]).rstrip(b"\0").decode("latin-1")
            vsize, va, rawsize, raw = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append(
                dict(name=name, vsize=vsize, va=va, rawsize=rawsize, raw=raw, hdr=off)
            )

    def rva_to_off(self, rva):
        for s in self.sections:
            if s["va"] <= rva < s["va"] + max(s["vsize"], s["rawsize"]):
                d = rva - s["va"]
                return None if d >= s["rawsize"] else s["raw"] + d
        return None

    def read_cstr(self, rva, maxlen=400):
        o = self.rva_to_off(rva)
        if o is None:
            return None
        e = self.data.find(b"\0", o, o + maxlen)
        if e < 0:
            return None
        return bytes(self.data[o:e]).decode("latin-1")


def resource_leaves(pe, data):
    """Yield the PE resource leaves as (path, data-entry offset, rva, size)."""
    # PE32+: data directories start after the 112-byte optional header
    rsrc_rva = struct.unpack_from("<I", data, pe.opt + 112 + 8 * 2)[0]
    if not rsrc_rva:
        return
    base = pe.rva_to_off(rsrc_rva)
    if base is None:
        raise RuntimeError("resource directory is not mapped")

    def name_at(off):
        ln = struct.unpack_from("<H", data, base + off)[0]
        raw = data[base + off + 2 : base + off + 2 + ln * 2]
        return raw.decode("utf-16-le")

    def walk(dir_off, path):
        n_named, n_id = struct.unpack_from("<HH", data, base + dir_off + 12)
        for i in range(n_named + n_id):
            e = base + dir_off + 16 + i * 8
            name_field, data_field = struct.unpack_from("<II", data, e)
            nm = (
                name_at(name_field & 0x7FFFFFFF)
                if name_field & 0x80000000
                else f"#{name_field}"
            )
            if data_field & 0x80000000:
                yield from walk(data_field & 0x7FFFFFFF, path + [nm])
            else:
                de = base + data_field
                rva, size = struct.unpack_from("<II", data, de)
                yield path + [nm], de, rva, size

    yield from walk(0, [])


def collect_fonts(pe, data, errors):
    """Load the patched fonts and match them with their RCDATA entries."""
    leaves = list(resource_leaves(pe, data))
    out = []
    for name in FONT_RESOURCES:
        path = FONT_DIR / f"{name}.ttf"
        if not path.exists():
            errors.append(
                f"font {name}: {path} is missing (run tools/merge_cyrillic.py first)"
            )
            continue
        found = [leaf for leaf in leaves if name in leaf[0]]
        if len(found) != 1:
            errors.append(
                f"font {name}: expected one resource entry, found {len(found)}"
            )
            continue
        blob = path.read_bytes()
        if blob[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
            errors.append(f"font {name}: {path} is not a TrueType/OpenType file")
            continue
        out.append(dict(name=name, blob=blob, entry=found[0][1]))
    return out


def parse_tsv(path):
    rows = []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise RuntimeError(f"{path}:{ln}: expected 3 tab separated columns")
        rows.append((int(parts[0], 16), parts[1], parts[2]))
    return rows


def is_mov_imm64(x):
    return (
        x.mnemonic == "mov"
        and len(x.operands) == 2
        and x.operands[0].type == X86_OP_MEM
        and x.operands[0].size == 8
        and x.operands[1].type == X86_OP_IMM
    )


def find_capacity_pairs(ins_list, idx, lit_len, cap_value=SSO_CAP):
    """Find the (size, capacity) store pair emitted just before the data copy.

    MSVC emits ``mov qword [obj+0x10], len`` followed by
    ``mov qword [obj+0x18], 0xf`` immediately before filling the SSO buffer.
    A heap-allocated string gets an arbitrary capacity instead, so ``cap_value``
    can be set to ``None`` to accept any capacity that fits ``lit_len``.
    """
    for j in range(idx - 1, 0, -1):
        cap = ins_list[j]
        if not is_mov_imm64(cap):
            continue
        if cap_value is not None:
            if cap.operands[1].imm != cap_value:
                continue
        elif cap.operands[1].imm < lit_len:
            continue
        size = ins_list[j - 1]
        if not is_mov_imm64(size) or size.operands[1].imm != lit_len:
            continue
        if size.operands[0].mem.base != cap.operands[0].mem.base:
            continue
        if cap.operands[0].mem.disp - size.operands[0].mem.disp != 8:
            continue
        return size, cap
    return None, None


def lea_rdi(base, disp):
    if base == "rsp":
        return b"\x48\x8d\xbc\x24" + struct.pack("<i", disp)
    if base == "rbp":
        return b"\x48\x8d\xbd" + struct.pack("<i", disp)
    if base == "rdx":
        return b"\x48\x8d\xba" + struct.pack("<i", disp)
    if base == "r11":
        return b"\x49\x8d\xbb" + struct.pack("<i", disp)
    raise ValueError(f"unsupported dst base {base}")


def rdi_from_dst(base, disp):
    if base == "rax":
        return b"\x48\x89\xc7"  # mov rdi, rax
    return lea_rdi(base, disp)


def func_start(funcs, rva):
    for a, b, _ in funcs:
        if a <= rva < b:
            return a
    return rva


def disasm_func(md, data, pe, funcs, site, extra=0x200):
    """Disassemble from the enclosing function start up to site + extra."""
    lo = func_start(funcs, site)
    o = pe.rva_to_off(lo)
    end = pe.rva_to_off(site + extra)
    if o is None or end is None:
        raise RuntimeError(f"cannot map {lo:#x}..{site + extra:#x}")
    return list(md.disasm(bytes(data[o:end]), lo))


def same_mem_location(m1, m2):
    return (
        m1.base == m2.base
        and m1.index == m2.index
        and m1.segment == m2.segment
        and m1.disp + 8 == m2.disp
    )


def find_len_store(ins, idx, lit_len):
    """Find ``mov qword [ptr+8], lit_len`` emitted right after ``mov [ptr], reg``.

    Some captions are stored as a ``string_view`` (pointer + explicit length)
    rather than as a C string; the length immediate then has to be updated.
    """
    seq = ins[idx : idx + 9]
    dstreg = seq[0].operands[0].reg
    for j, x in enumerate(seq[1:], 1):
        if not (x.mnemonic == "mov" and len(x.operands) == 2):
            continue
        if x.operands[0].type != X86_OP_MEM or x.operands[1].type != X86_OP_REG:
            continue
        if x.operands[1].reg != dstreg:
            continue
        if j + 1 >= len(seq):
            continue
        nxt = seq[j + 1]
        if (
            nxt.mnemonic == "mov"
            and len(nxt.operands) == 2
            and nxt.operands[0].type == X86_OP_MEM
            and nxt.operands[0].size == 8
            and nxt.operands[1].type == X86_OP_IMM
            and same_mem_location(x.operands[0].mem, nxt.operands[0].mem)
            and nxt.operands[1].imm == lit_len
        ):
            return nxt
    return None


def analyze_inline(
    md, data, pe, funcs, site, lit_addr, lit_len, allow_heap=False, cap_value=SSO_CAP
):
    """Parse the inline std::string construction starting at ``site``."""
    bases = dict(BASE_NAMES)
    if allow_heap:
        bases.update(HEAP_BASES)
    ins = disasm_func(md, data, pe, funcs, site)
    idx = next((i for i, x in enumerate(ins) if x.address == site), None)
    if idx is None:
        raise RuntimeError(f"{site:#x}: not an instruction boundary")

    dst = None
    region = []
    for x in ins[idx:]:
        if x.id == 0:
            break
        copy = False
        for op in x.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                tgt = x.address + x.size + op.mem.disp
                if lit_addr <= tgt < lit_addr + lit_len:
                    copy = True
        if (
            x.mnemonic.startswith("mov")
            and len(x.operands) == 2
            and x.operands[0].type == X86_OP_MEM
            and x.operands[0].mem.base in bases
        ):
            m = x.operands[0].mem
            if dst is None:
                dst = (bases[m.base], m.disp)
                copy = True
            elif bases[m.base] == dst[0] and 0 <= m.disp - dst[1] <= lit_len:
                copy = True
        if not copy:
            break
        region.append(x)

    if dst is None or not region:
        raise RuntimeError(f"{site:#x}: cannot find inline construction buffer")

    size_insn, cap_insn = find_capacity_pairs(ins, idx, lit_len, cap_value)
    if size_insn is None:
        raise RuntimeError(f"{site:#x}: cannot find size/capacity pair")

    return dict(
        site=site,
        region=region,
        dst=dst,
        back=region[-1].address + region[-1].size,
        size_insn=size_insn,
        cap_insn=cap_insn,
    )


def build_stub(base, disp, enc, string_rva, stub_rva, back_rva):
    b = bytearray()
    b += b"\x57"  # push rdi
    b += rdi_from_dst(base, disp + (8 if base == "rsp" else 0))
    b += b"\x9c\x50\x56\x51"  # pushfq; push rax; push rsi; push rcx
    lea_rsi_pos = len(b)
    b += b"\x48\x8d\x35\0\0\0\0"  # lea rsi, [rip+string]
    b += b"\xfc"  # cld
    b += b"\xb9" + struct.pack("<I", len(enc))  # mov ecx, len
    b += b"\xf3\xa4"  # rep movsb
    b += b"\xc6\x07\x00"  # mov byte ptr [rdi], 0
    b += b"\x59\x5e\x58\x9d\x5f"  # pop rcx/rsi/rax/rflags/rdi
    jmp_pos = len(b)
    b += b"\xe9\0\0\0\0"  # jmp back

    str_disp = string_rva - (stub_rva + lea_rsi_pos + 7)
    back_disp = back_rva - (stub_rva + jmp_pos + 5)
    struct.pack_into("<i", b, lea_rsi_pos + 3, str_disp)
    struct.pack_into("<i", b, jmp_pos + 1, back_disp)
    return bytes(b)


def load_ui2(data, pe, errors):
    """Validate ru/ui2.json against the (ptr,len) tables in .rdata."""
    if not UI2_JSON.exists():
        return []
    doc = json.loads(UI2_JSON.read_text(encoding="utf-8"))
    out = []
    seen = set()

    def read_pair(slot, label, what):
        off = pe.rva_to_off(slot)
        if off is None:
            errors.append(f"{label}: {what} slot {slot:#x} not mapped")
            return None
        ptr, ln = struct.unpack_from("<QQ", data, off)
        if not (IMAGE_BASE <= ptr < IMAGE_BASE + 0x2000000):
            errors.append(f"{label}: bad {what} pointer {ptr:#x}")
            return None
        return ptr - IMAGE_BASE, ln

    for table, (base, stride, body_off, is_sv, title_off) in UI2_TABLES.items():
        for item in doc.get(table, []):
            i = item["index"]
            key = (table, i)
            if key in seen:
                errors.append(f"{table}[{i}]: duplicate index in {UI2_JSON.name}")
                continue
            seen.add(key)
            label = f"{table}[{i}]"
            slot = base + i * stride
            parts = []
            ok = True

            if title_off is not None:
                got = read_pair(slot + title_off, label, "title")
                if got is None:
                    ok = False
                else:
                    tptr, tlen = got
                    actual = pe.read_cstr(tptr, tlen + 1)
                    if actual != item["orig_title"]:
                        errors.append(
                            f"{label}: title mismatch\n"
                            f"  expect={item['orig_title']!r}\n  actual={actual!r}"
                        )
                        ok = False
                    else:
                        parts.append(
                            dict(
                                slot=slot + title_off,
                                enc=encode_text(item["ru_title"]),
                                has_len=True,
                            )
                        )

            got = read_pair(slot + body_off, label, "body")
            if got is None:
                ok = False
            else:
                bptr, blen = got
                actual = pe.read_cstr(bptr, (blen + 1) if is_sv else 20000)
                if actual != item["orig"]:
                    errors.append(
                        f"{label}: orig mismatch\n  expect={item['orig']!r}\n  actual={actual!r}"
                    )
                    ok = False
                else:
                    parts.append(
                        dict(
                            slot=slot + body_off,
                            enc=encode_text(item["ru"]),
                            has_len=is_sv,
                        )
                    )

            if ok:
                out.append(
                    dict(
                        table=table,
                        index=i,
                        parts=parts,
                        orig=item["orig"],
                        ru=item["ru"],
                    )
                )
    return out


def resolve_extras(md, data, pe, funcs, errors):
    """Prepare stubs for display literals outside the caption/table ranges."""
    out = []
    for spec in EXTRA_STRINGS:
        actual = pe.read_cstr(spec["lit"], spec["lit_len"] + 1)
        if actual != spec["orig"]:
            errors.append(
                f"extra {spec['site']:#x}: expected {spec['orig']!r}, found {actual!r}"
            )
            continue
        enc = encode_text(spec["ru"])
        try:
            info = analyze_inline(
                md,
                data,
                pe,
                funcs,
                spec["site"],
                spec["lit"],
                spec["lit_len"],
                allow_heap=spec["allow_heap"],
                cap_value=spec["cap"],
            )
        except RuntimeError as ex:
            errors.append(str(ex))
            continue
        cap = info["cap_insn"].operands[1].imm
        if len(enc) > cap:
            errors.append(
                f"extra {spec['site']:#x}: {spec['ru']!r} needs {len(enc)} bytes (capacity {cap})"
            )
            continue
        out.append(dict(orig=spec["orig"], ru=spec["ru"], enc=enc, info=info))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--allow-unknown-source", action="store_true",
                    help="expert only: permit patching a DLL whose SHA-256 differs from tested v0.9.1")
    ap.add_argument("--experimental-cp1251", action="store_true",
                    help="required opt-in: encode with CP1251 for an isolated test only; not runtime-validated")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verify", action="store_true", help="verify the patched output")
    ap.add_argument(
        "--no-fonts",
        action="store_true",
        help="keep the original Latin-only fonts (Cyrillic shows as boxes)",
    )
    args = ap.parse_args()
    if not args.experimental_cp1251:
        ap.error(
            "no encoding path is runtime-confirmed; refusing to build implicitly. "
            "Use --experimental-cp1251 only for an isolated diagnostic test."
        )
    data = Path(args.src).read_bytes()
    source_sha256 = hashlib.sha256(data).hexdigest()
    if source_sha256 != EXPECTED_SOURCE_SHA256 and not args.allow_unknown_source:
        ap.error(
            f"source SHA-256 mismatch: {source_sha256}; expected the tested v0.9.1 DLL "
            f"{EXPECTED_SOURCE_SHA256}. Refusing to patch."
        )
    print(f"source SHA-256: {source_sha256}")
    print("WARNING: CP1251 is an experimental hypothesis; existing notes report incorrect rendering.")
    pe = PE(data)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    plan = json.loads((ROOT / "work" / "plan-0.9.1.json").read_text(encoding="utf-8"))
    funcs = json.loads((ROOT / "work" / "funcs-0.9.1.json").read_text(encoding="utf-8"))[
        "funcs"
    ]
    plan_by_addr = {e["addr"]: e for e in plan}

    rows = parse_tsv(STRINGS_TSV)
    errors = []

    # ---- validate the translation table --------------------------------------
    entries = []
    seen_addr = set()
    for addr, orig, ru in rows:
        if addr in seen_addr:
            errors.append(f"{addr:#x}: duplicate row in {STRINGS_TSV.name}")
            continue
        seen_addr.add(addr)
        p = plan_by_addr.get(addr)
        if p is None:
            errors.append(f"{addr:#x}: not a known caption address")
            continue
        actual = pe.read_cstr(addr)
        if actual != orig:
            errors.append(f"{addr:#x}: expected {orig!r}, found {actual!r}")
            continue
        enc = encode_text(ru)
        if len(enc) > MAX_LEN:
            errors.append(
                f"{addr:#x}: {ru!r} encodes to {len(enc)} bytes (> {MAX_LEN})"
            )
        e = dict(
            addr=addr,
            orig=orig,
            ru=ru,
            enc=enc,
            skip=(ru == orig),
            lea_sites=[],
            inline=[],
            outside=[],
        )
        for site, kind in p["sites"]:
            if not (MENU_LO <= site < MENU_HI):
                e["outside"].append((site, kind))
            elif kind == "lea":
                e["lea_sites"].append(site)
            else:
                e["inline"].append(site)
        entries.append(e)

    missing = sorted(set(plan_by_addr) - seen_addr)
    for addr in missing:
        errors.append(
            f"{addr:#x}: {plan_by_addr[addr]['text']!r} has no translation row"
        )

    if errors:
        for x in errors:
            print("ERROR", x)
        return 1

    # ---- resolve every display site ------------------------------------------
    for e in entries:
        if e["skip"]:
            continue
        e["lea_patches"] = []
        e["lea_len"] = []
        for site in e["lea_sites"]:
            ins = disasm_func(md, data, pe, funcs, site, 0x10)
            idx = next((i for i, x in enumerate(ins) if x.address == site), None)
            if idx is None:
                errors.append(f"{site:#x}: lea site not on an instruction boundary")
                continue
            insn = ins[idx]
            ok = False
            if insn.mnemonic == "lea":
                for op in insn.operands:
                    if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                        if insn.address + insn.size + op.mem.disp == e["addr"]:
                            ok = True
                            e["lea_patches"].append(
                                (site + insn.size - 4, site + insn.size)
                            )
            if not ok:
                errors.append(
                    f"{site:#x}: not a lea to {e['addr']:#x} ({insn.mnemonic} {insn.op_str})"
                )
                continue
            # string_view style (ptr,len) pair
            wide = disasm_func(md, data, pe, funcs, site, 0x60)
            widx = next((i for i, x in enumerate(wide) if x.address == site), None)
            store = (
                find_len_store(wide, widx, len(e["orig"])) if widx is not None else None
            )
            if store is not None:
                e["lea_len"].append((store.address + store.size - 4, store.address))

        e["inline"] = []
        for site, kind in [
            (s, k) for s, k in plan_by_addr[e["addr"]]["sites"] if k != "lea"
        ]:
            if not (MENU_LO <= site < MENU_HI):
                continue
            try:
                info = analyze_inline(
                    md, data, pe, funcs, site, e["addr"], len(e["orig"])
                )
            except RuntimeError as ex:
                errors.append(str(ex))
                continue
            info["kind"] = kind
            e["inline"].append(info)

        for info in e["inline"]:
            if len(e["enc"]) > SSO_CAP:
                errors.append(
                    f"{info['site']:#x}: {e['ru']!r} needs {len(e['enc'])} bytes (SSO cap {SSO_CAP})"
                )

    ui2 = load_ui2(data, pe, errors)
    extras = resolve_extras(md, data, pe, funcs, errors)
    fonts = [] if args.no_fonts else collect_fonts(pe, data, errors)

    if errors:
        for x in errors:
            print("ERROR", x)
        print(f"{len(errors)} error(s)")
        return 1

    # ---- layout the new section ----------------------------------------------
    strings_blob = bytearray()
    str_off = {}
    for e in entries:
        if e["skip"]:
            continue
        str_off[e["addr"]] = len(strings_blob)
        strings_blob += e["enc"] + b"\0"
        while len(strings_blob) % 8:
            strings_blob.append(0)

    ui2_off = {}
    for it in ui2:
        for part in it["parts"]:
            ui2_off[(it["table"], it["index"], part["slot"])] = len(strings_blob)
            strings_blob += part["enc"] + b"\0"
            while len(strings_blob) % 8:
                strings_blob.append(0)

    extra_off = {}
    for ex in extras:
        extra_off[ex["info"]["site"]] = len(strings_blob)
        strings_blob += ex["enc"] + b"\0"
        while len(strings_blob) % 8:
            strings_blob.append(0)

    last = max(pe.sections, key=lambda s: s["va"])
    new_va = max(
        (last["va"] + last["vsize"] + SECT_ALIGN - 1) & ~(SECT_ALIGN - 1),
        pe.size_image,
    )
    while len(strings_blob) % 16:
        strings_blob.append(0)

    # ---- build stubs ----------------------------------------------------------
    inline_plans = []
    for e in entries:
        if e["skip"]:
            continue
        for info in e["inline"]:
            inline_plans.append(
                dict(enc=e["enc"], key=("cap", e["addr"]), info=info, text=e)
            )
    for ex in extras:
        inline_plans.append(
            dict(
                enc=ex["enc"],
                key=("extra", ex["info"]["site"]),
                info=ex["info"],
                text=ex,
            )
        )

    stubs = bytearray()
    stub_plans = []
    for ip in inline_plans:
        while len(stubs) % 16:
            stubs.append(0xCC)
        stub_plans.append(dict(ip, off=len(stubs)))
        # placeholder, displacements fixed after the base RVA is known
        stubs += b"\0" * 64
    stub_base_off = len(strings_blob)
    stub_base_rva = new_va + stub_base_off
    for sp in stub_plans:
        stub_rva = stub_base_rva + sp["off"]
        kind, val = sp["key"]
        if kind == "cap":
            str_rva = new_va + str_off[val]
        else:
            str_rva = new_va + extra_off[val]
        blob = build_stub(
            sp["info"]["dst"][0],
            sp["info"]["dst"][1],
            sp["enc"],
            str_rva,
            stub_rva,
            sp["info"]["back"],
        )
        stubs[sp["off"] : sp["off"] + len(blob)] = blob
        sp["size"] = len(blob)
    # trim unused placeholder space
    used = max((sp["off"] + sp["size"] for sp in stub_plans), default=0)
    stubs = stubs[:used]
    while len(stubs) % 16:
        stubs.append(0xCC)

    # ---- append the Cyrillic fonts --------------------------------------------
    font_blob = bytearray()
    font_off = {}
    font_base = len(strings_blob) + len(stubs)
    for f in fonts:
        while len(font_blob) % 16:
            font_blob.append(0)
        font_off[f["name"]] = font_base + len(font_blob)
        font_blob += f["blob"]
    while len(font_blob) % 16:
        font_blob.append(0)

    payload = bytes(strings_blob) + bytes(stubs) + bytes(font_blob)

    # ---- collect byte patches -------------------------------------------------
    patches = []
    for e in entries:
        if e["skip"]:
            continue
        target = new_va + str_off[e["addr"]]
        for disp_off, end in e["lea_patches"]:
            foff = pe.rva_to_off(disp_off)
            if foff is None:
                errors.append(f"{disp_off:#x}: cannot map lea displacement")
                continue
            patches.append((foff, struct.pack("<i", target - end)))
        for imm_off, ins_end in e["lea_len"]:
            foff = pe.rva_to_off(imm_off)
            if foff is None:
                errors.append(f"{imm_off:#x}: cannot map lea length constant")
                continue
            patches.append((foff, struct.pack("<I", len(e["enc"]))))
        for info in e["inline"]:
            # explicit std::string length constant
            si = info["size_insn"]
            foff = pe.rva_to_off(si.address + si.size - 4)
            if foff is None:
                errors.append(f"{si.address:#x}: cannot map length constant")
                continue
            patches.append((foff, struct.pack("<I", len(e["enc"]))))

    for it in ui2:
        label = f"{it['table']}[{it['index']}]"
        for part in it["parts"]:
            target = new_va + ui2_off[(it["table"], it["index"], part["slot"])]
            ptr_off = pe.rva_to_off(part["slot"])
            if ptr_off is None:
                errors.append(f"{label}: cannot map slot {part['slot']:#x}")
                continue
            patches.append((ptr_off, struct.pack("<Q", IMAGE_BASE + target)))
            if part["has_len"]:
                len_off = pe.rva_to_off(part["slot"] + 8)
                if len_off is None:
                    errors.append(f"{label}: cannot map length slot")
                    continue
                patches.append((len_off, struct.pack("<Q", len(part["enc"]))))

    for ex in extras:
        # explicit std::string length constant of the extra display literal
        si = ex["info"]["size_insn"]
        foff = pe.rva_to_off(si.address + si.size - 4)
        if foff is None:
            errors.append(f"{si.address:#x}: cannot map extra length constant")
            continue
        patches.append((foff, struct.pack("<I", len(ex["enc"]))))

    for sp in stub_plans:
        start = sp["info"]["site"]
        foff = pe.rva_to_off(start)
        if foff is None:
            errors.append(f"{start:#x}: cannot map inline site")
            continue
        rel = stub_base_rva + sp["off"] - (start + 5)
        fill = sp["info"]["back"] - start
        if fill < 5:
            errors.append(f"{start:#x}: inline region too small ({fill} bytes)")
            continue
        patches.append((foff, b"\xe9" + struct.pack("<i", rel) + b"\x90" * (fill - 5)))

    for v in VALIDATORS:
        foff = pe.rva_to_off(v)
        if foff is None:
            errors.append(f"validator {v:#x}: not mapped")
            continue
        if bytes(pe.data[foff : foff + 1]) != b"\x5e":
            errors.append(
                f"validator {v:#x}: unexpected byte {pe.data[foff : foff + 1].hex()}"
            )
            continue
        patches.append((foff, b"\xff"))

    for f in fonts:
        rva = new_va + font_off[f["name"]]
        patches.append((f["entry"], struct.pack("<II", rva, len(f["blob"]))))

    if errors:
        for x in errors:
            print("ERROR", x)
        return 1

    # no two patches may overlap
    for a, b in zip(sorted(patches), sorted(patches)[1:]):
        if a[0] + len(a[1]) > b[0]:
            errors.append(f"overlapping patches at {a[0]:#x} and {b[0]:#x}")
    if errors:
        for x in errors:
            print("ERROR", x)
        return 1

    total_strings = sum(1 for e in entries if not e["skip"])
    total_lea = sum(len(e["lea_patches"]) for e in entries if not e["skip"])
    total_lea_len = sum(len(e["lea_len"]) for e in entries if not e["skip"])
    if args.check:
        print("check ok")
        print(
            f"rows: {len(entries)}  translated: {total_strings}  kept: {len(entries) - total_strings}"
        )
        print(f"lea patches: {total_lea}  lea length immediates: {total_lea_len}")
        print(
            f"ui2: popups {sum(1 for x in ui2 if x['table'] == 'popups')}"
            f"  options {sum(1 for x in ui2 if x['table'] == 'options')}"
            f"  hints {sum(1 for x in ui2 if x['table'] == 'hints')}"
            f"  hintpages {sum(1 for x in ui2 if x['table'] == 'hintpages')}"
            f"  extras {len(extras)}"
        )
        print(f"inline stubs: {len(stub_plans)}")
        print(f"validator patches: {len(VALIDATORS)}")
        print(f"new section .ru @ RVA {new_va:#x}, payload {len(payload)} bytes")
        print(f"strings {len(strings_blob)} bytes, stubs {len(stubs)} bytes")
        if fonts:
            print(
                f"fonts: {len(fonts)} patched, "
                f"{sum(len(f['blob']) for f in fonts)} bytes"
            )
            for f in fonts:
                print(
                    f"  font {f['name']} {len(f['blob'])}B -> RVA "
                    f"{new_va + font_off[f['name']]:#x}"
                )
        else:
            print("fonts: kept as shipped (--no-fonts)")
        for sp in stub_plans:
            e = sp["text"]
            print(
                f"  inline {sp['info']['site']:#07x} {e['orig']!r} -> {e['ru']!r} "
                f"({len(e['enc'])}B, region {sp['info']['back'] - sp['info']['site']}B)"
            )
        return 0

    # ---- write the patched image ---------------------------------------------
    out = bytearray(data)
    for foff, blob in patches:
        out[foff : foff + len(blob)] = blob

    raw_ptr = (len(out) + FILE_ALIGN - 1) & ~(FILE_ALIGN - 1)
    out += b"\0" * (raw_ptr - len(out))
    out += payload
    raw_size = (len(payload) + FILE_ALIGN - 1) & ~(FILE_ALIGN - 1)
    out += b"\0" * (raw_size - len(payload))

    hdr = pe.sect_table + 40 * pe.nsec
    if hdr + 40 > pe.size_headers:
        errors.append("no room for another section header")
    if errors:
        for x in errors:
            print("ERROR", x)
        return 1

    struct.pack_into(
        "<8sIIIIIIHHI",
        out,
        hdr,
        b".ru\0\0\0\0\0",
        len(payload),
        new_va,
        raw_size,
        raw_ptr,
        0,
        0,
        0,
        0,
        0x60000040,  # CNT_INITIALIZED_DATA | MEM_EXECUTE | MEM_READ
    )
    struct.pack_into("<H", out, pe.e_lfanew + 6, pe.nsec + 1)
    new_size_image = (new_va + len(payload) + SECT_ALIGN - 1) & ~(SECT_ALIGN - 1)
    struct.pack_into("<I", out, pe.opt + 56, new_size_image)
    size_init = struct.unpack_from("<I", out, pe.opt + 8)[0]
    struct.pack_into("<I", out, pe.opt + 8, size_init + raw_size)
    struct.pack_into("<I", out, pe.opt + 64, 0)  # clear checksum

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(out)

    print(f"wrote {out_path} ({len(out)} bytes)")
    print(
        f"translated {total_strings} strings ({total_lea} lea sites, {len(stub_plans)} stubs)"
    )
    print(f".ru section: RVA {new_va:#x}, raw {raw_ptr:#x}, {len(payload)} bytes")

    if args.verify:
        return verify(
            out_path,
            entries,
            ui2,
            extras,
            stub_plans,
            str_off,
            ui2_off,
            extra_off,
            new_va,
            patches,
            md,
            fonts,
            font_off,
        )
    return 0


def verify(
    path,
    entries,
    ui2,
    extras,
    stub_plans,
    str_off,
    ui2_off,
    extra_off,
    new_va,
    patches,
    md,
    fonts=(),
    font_off=None,
):
    data = Path(path).read_bytes()
    pe = PE(data)
    errors = []
    font_off = font_off or {}

    for e in entries:
        if e["skip"]:
            continue
        o = pe.rva_to_off(new_va + str_off[e["addr"]])
        got = bytes(pe.data[o : o + len(e["enc"])])
        if got != e["enc"]:
            errors.append(f"{e['addr']:#x}: string bytes mismatch")
        elif pe.data[o + len(e["enc"])] != 0:
            errors.append(f"{e['addr']:#x}: missing terminator")

    for it in ui2:
        label = f"{it['table']}[{it['index']}]"
        for part in it["parts"]:
            o = pe.rva_to_off(
                new_va + ui2_off[(it["table"], it["index"], part["slot"])]
            )
            enc = part["enc"]
            got = bytes(pe.data[o : o + len(enc)])
            if got != enc:
                errors.append(f"{label} @{part['slot']:#x}: string bytes mismatch")
            elif pe.data[o + len(enc)] != 0:
                errors.append(f"{label} @{part['slot']:#x}: missing terminator")

    for ex in extras:
        label = f"extra {ex['info']['site']:#x}"
        o = pe.rva_to_off(new_va + extra_off[ex["info"]["site"]])
        got = bytes(pe.data[o : o + len(ex["enc"])])
        if got != ex["enc"]:
            errors.append(f"{label}: string bytes mismatch")
        elif pe.data[o + len(ex["enc"])] != 0:
            errors.append(f"{label}: missing terminator")

    for foff, blob in patches:
        if bytes(pe.data[foff : foff + len(blob)]) != blob:
            errors.append(f"patch at file offset {foff:#x} not applied")

    # disassemble every patched lea and every replaced inline region
    for e in entries:
        if e["skip"]:
            continue
        for disp_off, end in e.get("lea_patches", []):
            site = disp_off - 3
            # the instruction may start further back; just decode the target
            o = pe.rva_to_off(disp_off)
            disp = struct.unpack_from("<i", pe.data, o)[0]
            if end + disp != new_va + str_off[e["addr"]]:
                errors.append(f"{disp_off:#x}: lea target wrong")
        for imm_off, ins_end in e.get("lea_len", []):
            o = pe.rva_to_off(imm_off)
            if struct.unpack_from("<I", pe.data, o)[0] != len(e["enc"]):
                errors.append(f"{imm_off:#x}: lea length constant not updated")

    for sp in stub_plans:
        site = sp["info"]["site"]
        o = pe.rva_to_off(site)
        if pe.data[o] != 0xE9:
            errors.append(f"{site:#x}: inline site is not a jmp")
            continue
        rel = struct.unpack_from("<i", pe.data, o + 1)[0]
        stub_rva = site + 5 + rel
        so = pe.rva_to_off(stub_rva)
        ins = list(md.disasm(bytes(pe.data[so : so + 0x60]), stub_rva))
        if not ins or ins[0].mnemonic != "push":
            errors.append(f"{site:#x}: stub does not start with push")
            continue
        last = None
        for x in ins:
            if x.mnemonic == "jmp" and x.address > stub_rva + 5:
                last = x
                break
        if last is None:
            errors.append(f"{site:#x}: stub has no closing jmp")
            continue
        if last.operands[0].imm != sp["info"]["back"]:
            errors.append(f"{site:#x}: stub jumps to the wrong place")
        # length constant
        si = sp["info"]["size_insn"]
        lo = pe.rva_to_off(si.address + si.size - 4)
        if struct.unpack_from("<I", pe.data, lo)[0] != len(sp["enc"]):
            errors.append(f"{si.address:#x}: length constant not updated")

    for f in fonts:
        o = pe.rva_to_off(new_va + font_off[f["name"]])
        if o is None:
            errors.append(f"font {f['name']}: payload is not mapped")
            continue
        if bytes(pe.data[o : o + len(f["blob"])]) != f["blob"]:
            errors.append(f"font {f['name']}: bytes mismatch in .ru")
        rva, size = struct.unpack_from("<II", pe.data, f["entry"])
        if (rva, size) != (new_va + font_off[f["name"]], len(f["blob"])):
            errors.append(f"font {f['name']}: resource data entry not repointed")

    if errors:
        for x in errors:
            print("VERIFY ERROR", x)
        return 1
    print(f"verify ok: {len(stub_plans)} stubs, {len(patches)} byte patches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
