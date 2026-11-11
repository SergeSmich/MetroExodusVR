#!/usr/bin/env python3
"""Apply Russian translations to MetroExodusVR.dll 0.9.1 (native menu captions).

A port of ``tools/apply_ru.py`` to the 0.9.1 release.  Two things differ from
the 0.9.0 path, and both are why this is a separate file:

1. **The encoding is UTF-8, and that was settled live (L-0036).**  A-0029
   assumed a caption's bytes are *indices into the drawing font's glyph
   table* (the localization charmap of ``stable_ru.lng``), and L-0032 seemed to
   confirm it because CP1251 captions came out blank.  Live runs on 0.9.1 show
   the opposite: charmap indices below 0xE0 are valid ASCII, and the VR page
   rendered them as Latin letters -- ``TURN MODE`` came out as
   ``HIcDG <?7?H?:5``, exactly ``ru/charmap.txt`` bytes read as latin-1.  The
   US charmap decodes those same bytes to a different sequence, so the control
   text path does not use a charmap at all: it decodes the bytes as UTF-8.
   Rebuilding with ``--encoding utf8`` put the whole main menu and the VR page
   in Cyrillic.  ``utf8`` is therefore the default here; ``charmap`` and
   ``--experimental-cp1251`` are kept for diagnostics only.

2. **The captions do not need a font swap.**  The mod never sets a font
   property, and once the bytes are UTF-8 the default font draws Cyrillic
   fine.  ``--caption-font menu`` (the code cave over the generic property
   setter 0x9F0D0, see ``tools/caption_font_hook.py``) is now only a probe:
   the live font-slot experiments changed nothing.

Everything version specific is in ``ADDRS`` below.  The source DLL is pinned by
SHA-256; passing a different file needs ``--allow-unknown-source``.

Usage:
    python tools/apply_ru_091.py --self-test
    python tools/apply_ru_091.py --src <0.9.1 orig> --out X --no-fonts --check
    python tools/apply_ru_091.py --src <0.9.1 orig> --out X --caption-font menu --verify
    python tools/apply_ru_091.py --src <0.9.1 orig> --out X --hook-only --caption-font menu
"""

import argparse
import json
import re
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402
import hashlib  # noqa: E402

# ---------------------------------------------------------------------------
# 0.9.1 addresses -- everything version specific lives here
# ---------------------------------------------------------------------------

# MetroExodusVR.dll from versions/0.9.1 of the mod (handoff note).
SRC_SHA256 = "fbbf2812bc7c3304a22829249aba334c812a326baf75fc5c2a75e559202c40b4"

ADDRS = dict(
    # Generic control-property setter `bool set(control, name_sv*, value_sv*)`.
    # L-0034: 0.9.1 is 0x9F0D0 (0.9.0 was 0x9BC70); the first 0x700 bytes
    # disassemble to the same 591 instructions, and its prologue has one push
    # more (r15), so 8 bytes are displaced instead of 6.  The bytes are read
    # back out of the DLL at build time and checked, never assumed.
    setter=0x9F0D0,
    # `cmp .., 0x5e` immediates of the printable-ASCII checks (kit handoff).
    # L-0033: they run on the .rdata literals, not on our payload, so they do
    # not have to be patched; --no-validators keeps the build clean.
    validators=(0xA4728, 0xA4C76, 0xA6556),
    # Only the mod's own menu code is redirected.  UNVERIFIED for 0.9.1: the
    # range is only used to warn about display sites that fall outside it,
    # every site comes from --plan anyway.
    menu_lo=0xA0000,
    menu_hi=0xC0000,
    # Second-layer table bases (popups/options/hints/hintpages), 0.9.1 counts
    # are 15/79/52/14.  UNKNOWN: fill from the kit's tables before building.
    ui2_tables=None,
    # Inline-built extras such as "VR HINTS".  UNKNOWN for 0.9.1.
    extra_strings=(),
)
DEFAULT_SRC = re_paths.DLL
DEFAULT_OUT = ROOT / "build" / "MetroExodusVR.dll"
STRINGS_TSV = ROOT / "ru" / "strings.tsv"
UI2_JSON = ROOT / "ru" / "ui2.json"

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
    "popups": (0x49BF40, 0x70, 0x10, True, None),
    "options": (0x4A1820, 0x20, 0x10, True, None),
    "hints": (0x497E00, 0x20, 0x10, False, None),
    "hintpages": (0x499A00, 0x20, 0x10, True, 0x00),
}

# Literals that are neither captions nor table entries but still show up in the
# UI.  They are built inline, so they get the same copy-stub treatment.
#
# 0.9.1: empty.  The two literals from 0.9.0 ("VR HINTS" @0x4999E0 and
# "VR GAMEPAD LAYOUT" @0x497100) have neither a rip-relative `lea` nor an
# absolute pointer in the 0.9.1 .text: at the kit's sites 0x8181C / 0x79A1C
# the bytes are unrelated, and the address check fails before any write.
# opencode verified this on the release DLL; Arena has to confirm or refute
# in A-0034.  Leaving the tuple empty keeps the build from writing stubs at
# sites that do not hold those literals in this build.
EXTRA_STRINGS = ()

# Only the mod's own menu/page-building code is redirected.
MENU_LO = 0xB0000
MENU_HI = 0xC0000

# offset of the immediate byte in a printable-ASCII check:
#   cmp al, 0x5e  (after `sub al, 0x20`)  ->  cmp al, 0xff  (any byte)
#   cmp cl, 0x5e  (after `sub cl, 0x20`)  ->  cmp cl, 0xff  (any byte)
# 0xA1816 page builder, 0xA30F6 option-list builder, 0xA12C8 vector-of-captions
# validator (runs before a menu page is applied, rejects non-ASCII).
VALIDATORS = (0xA1816, 0xA30F6, 0xA12C8)

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


CHARMAP_TXT = ROOT / "ru" / "charmap.txt"

# The 4A engine's *control caption* path is plain UTF-8: the setter stores the
# bytes unchanged and the UI decode step turns them into codepoints, then the
# font draws them.  ``.lng`` strings are a different path (charmap indices) and
# are not written by this driver.  Live proof in L-0036: charmap bytes for
# "TURN MODE" (48 49 63 44 47 01 ...) showed up on the VR page as
# "HIcDG <?7?H?:5", i.e. exactly those bytes under latin-1, while a UTF-8
# rebuild renders Cyrillic.  ``charmap`` and ``cp1251`` remain for comparison.
ENCODING = "utf8"


def load_charmap(path=None):
    """Return the localization charmap: index -> Unicode codepoint."""
    p = Path(path) if path else CHARMAP_TXT
    cps = [
        int(line.strip()[2:], 16)
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("U+")
    ]
    if not cps:
        raise ValueError(f"{p}: no charmap entries")
    return cps


_CHARMAP = None


def charmap():
    global _CHARMAP
    if _CHARMAP is None:
        _CHARMAP = load_charmap()
    return _CHARMAP


def encode_text(s):
    """Encode a display string as localization charmap indices.

    Indices below 0xE0 are one byte.  Larger indices use the two byte form of
    the ``.lng`` format: ``value = index + 0xDE41``, bytes ``value // 255`` and
    ``value % 255`` -- the same rule ``tools/lng_dump.py`` decodes with.
    """
    if ENCODING == "utf8":
        enc = s.encode("utf-8")
        if 0 in enc:
            raise ValueError(f"encoded {s!r} contains a NUL byte")
        return enc

    if ENCODING == "cp1251":
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

    rev = {}
    for i, cp in enumerate(charmap()):
        rev.setdefault(cp, i)
    out = bytearray()
    for ch in s:
        i = rev.get(ord(ch))
        if i is None:
            raise ValueError(
                f"{s!r}: character {ch!r} (U+{ord(ch):04X}) is not in the "
                "localization charmap (see ru/charmap.txt)"
            )
        if i < 0xE0:
            out.append(i)
        else:
            v = i + 0xDE41
            out += bytes((v // 255, v % 255))
    if 0 in out:
        raise ValueError(f"encoded {s!r} contains a NUL byte")
    return bytes(out)


def decode_text(enc):
    """Inverse of encode_text (used by the self-check)."""
    if ENCODING == "utf8":
        return enc.decode("utf-8")
    if ENCODING == "cp1251":
        return enc.decode("cp1251")
    cps = charmap()
    out = []
    i = 0
    while i < len(enc):
        ci = enc[i]
        if ci < 0xE0:
            out.append(chr(cps[ci]))
            i += 1
        else:
            idx = ci * 255 + enc[i + 1] - 0xDE41
            out.append(chr(cps[idx]))
            i += 2
    return "".join(out)


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
                                text=item["ru_title"],
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
                            text=item["ru"],
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


def check_encodings(entries, ui2, extras):
    """Round-trip every payload through the engine's glyph lookup.

    ``encode_text`` maps text to charmap indices; the engine maps those indices
    back to glyphs through the font of the menu.  A mismatch here means the
    caption would render as other characters (or as .notdef).
    """
    errors = []

    def check(label, text, enc):
        try:
            back = decode_text(enc)
        except (IndexError, ValueError) as exc:
            errors.append(
                f"{label}: encoded bytes are not valid charmap indices ({exc})"
            )
            return
        if back != text:
            errors.append(f"{label}: {text!r} would render as {back!r}")
        if 0 in enc:
            errors.append(f"{label}: encoded text contains a NUL")

    for e in entries:
        if not e["skip"]:
            check(f"{e['addr']:#x}", e["ru"], e["enc"])
    for it in ui2:
        for part in it["parts"]:
            check(
                f"{it['table']}[{it['index']}] @{part['slot']:#x}",
                part.get("text", ""),
                part["enc"],
            )
    for ex in extras:
        check(f"extra {ex['info']['site']:#x}", ex["ru"], ex["enc"])
    if len(charmap()) <= 0xE0:
        errors.append(
            f"charmap has {len(charmap())} entries; the two-byte form starts at 0xE0"
        )
    return errors


def report_limits(entries, ui2, extras):
    """Print how close the encoded payloads come to the engine's limits."""
    groups = (
        (
            f"captions (string_view, {MAX_LEN:#x})",
            [e for e in entries if not e["skip"]],
        ),
        ("table entries", [p for it in ui2 for p in it["parts"]]),
        ("extras", extras),
    )
    print(f"encoding: {ENCODING}")
    for label, items in groups:
        if not items:
            continue
        longest = max(len(it["enc"]) for it in items)
        over = sum(1 for it in items if len(it["enc"]) > MAX_LEN)
        print(
            f"  {label}: {len(items)} payloads, longest {longest} bytes, "
            f"{over} over {MAX_LEN:#x}"
        )
    inline = [e for e in entries if not e["skip"] and e["inline"]]
    if inline:
        tight = sum(1 for e in inline if len(e["enc"]) <= SSO_CAP)
        print(
            f"  inline std::string sites: {len(inline)} entries, "
            f"{tight} fit the {SSO_CAP:#x} byte SSO buffer"
        )


def disasm_window(md, pe, site, extra=0x200, back=0x200):
    """Disassemble around ``site`` when no function map is available.

    ``find_capacity_pairs`` walks *backwards* from the site, so the window has
    to start before it.  x86 instructions are variable length, so an arbitrary
    start decodes garbage for the first few instructions; try every byte offset
    in the window and keep the one that both puts an instruction boundary on
    ``site`` and decodes the most instructions before it.
    """
    lo = max(0, site - back)
    o0 = pe.rva_to_off(lo)
    o1 = pe.rva_to_off(site + extra)
    if o0 is None or o1 is None:
        raise RuntimeError(f"cannot map {lo:#x}..{site + extra:#x}")
    buf = bytes(pe.data[o0:o1])
    best = None
    best_n = -1
    for skip in range(24):
        ins = list(md.disasm(buf[skip:], lo + skip))
        n = sum(1 for i in ins if i.address < site)
        if any(i.address == site for i in ins) and n > best_n:
            best, best_n = ins, n
    if best is None:
        raise RuntimeError(
            f"{site:#x}: no instruction boundary inside a {back:#x} byte window"
        )
    return best


def disasm_func(md, data, pe, funcs, site, extra=0x200):
    """Disassemble around ``site``; uses the function map when there is one."""
    if funcs:
        lo = func_start(funcs, site)
        o = pe.rva_to_off(lo)
        end = pe.rva_to_off(site + extra)
        if o is None or end is None:
            raise RuntimeError(f"cannot map {lo:#x}..{site + extra:#x}")
        return list(md.disasm(bytes(data[o:end]), lo))
    return disasm_window(md, pe, site, extra)


def load_plan(path):
    """Caption plan: ``addr -> {text, sites:[[site, kind], ...]}``.

    Accepts the 0.9.0 JSON shape (a list of dicts with ``addr``, ``text`` and
    ``sites``) or the flat table opencode offers for 0.9.1::

        RVA<TAB>original text<TAB>site RVA<TAB>lea|inline

    one row per display site, several rows per string.
    """
    p = Path(path)
    if not p.is_file():
        raise SystemExit(
            f"ERROR caption plan not found: {p}\n"
            "      the 0.9.1 kit ships work/plan-0.9.1.json; or dump\n"
            "      RVA<TAB>text<TAB>site<TAB>kind and pass --plan that.tsv"
        )
    if p.suffix.lower() == ".json":
        return {e["addr"]: e for e in json.loads(p.read_text(encoding="utf-8"))}
    plan = {}
    for ln, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            raise SystemExit(f"{p}:{ln}: expected at least 3 tab separated columns")
        addr = int(parts[0], 16)
        text = parts[1]
        site = int(parts[2], 16)
        kind = parts[3] if len(parts) > 3 and parts[3] else "lea"
        e = plan.setdefault(addr, dict(addr=addr, text=text, sites=[]))
        e["sites"].append([site, kind])
    return plan


def load_funcs(path):
    """Function boundaries, optional: without them sites are window-decoded."""
    if path is None:
        return []
    p = Path(path)
    if not p.is_file():
        print(f"WARN function map not found ({p}); decoding sites from a window")
        return []
    return json.loads(p.read_text(encoding="utf-8"))["funcs"]


FILTER_JSON = ROOT / "ru" / "caption_filter.json"


def fnv1a32(b):
    """FNV-1a 32, the hash the cave's positive filter compares against."""
    h = 0x811C9DC5
    for x in b:
        h ^= x
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def filter_hashes(path=None):
    p = Path(path) if path else FILTER_JSON
    if not p.is_file():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {int(e["hash32"]) & 0xFFFFFFFF for e in doc.get("entries", [])}


def build_filter(strings_path, out_path):
    """Regenerate the positive filter from the translation table in use.

    The cave filters captions by FNV-1a of the *payload bytes*, so the filter
    has to be rebuilt whenever the translations or the encoding change --
    otherwise the captions the filter does not know simply never get a font.
    """
    rows = parse_tsv(Path(strings_path))
    entries = []
    for addr, orig, ru in rows:
        if ru == orig:
            continue
        enc = encode_text(ru)
        entries.append(
            dict(
                rva=hex(addr),
                original=orig,
                ru=ru,
                len=len(enc),
                hash32=fnv1a32(enc),
                hash16=fnv1a32(enc) & 0xFFFF,
                bytes_hex=" ".join(f"{b:02X}" for b in enc),
            )
        )
    doc = dict(
        purpose=(
            "positive filter for the caption-font cave: FNV-1a 32 of the "
            "payload bytes the patcher writes"
        ),
        encoded_with="tools/apply_ru_091.py encode_text (encoding: %s)" % ENCODING,
        applies_to="MetroExodusVR.dll 0.9.1",
        counts=dict(entries=len(entries), source=Path(strings_path).name),
        match_rule="fnv1a32(caption value) must be in this table",
        entries=sorted(entries, key=lambda e: e["hash32"]),
    )
    Path(out_path).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {out_path}: {len(entries)} entries (encoding {ENCODING})")
    return 0


def filter_encoding(path=None):
    """The encoding the filter file was generated with (None if unknown)."""
    p = Path(path) if path else FILTER_JSON
    if not p.is_file():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    m = re.search(r"encoding:\s*([a-z0-9]+)", doc.get("encoded_with", ""))
    return m.group(1) if m else None


def check_filter(strings_path, label="filter"):
    """Warn when translated captions would not be recognised by the cave."""
    built_with = filter_encoding()
    if built_with is not None and built_with != ENCODING:
        print(
            f"WARN {label}: {FILTER_JSON.name} was built with encoding "
            f"{built_with!r}, the current one is {ENCODING!r}; the table only "
            f"matters for builds without --caption-all, rebuild it with "
            f"--build-filter if you need that path"
        )
        return 0
    want = set()
    for addr, orig, ru in parse_tsv(Path(strings_path)):
        if ru != orig:
            want.add(fnv1a32(encode_text(ru)))
    have = filter_hashes()
    if have is None:
        print(f"WARN {FILTER_JSON.name} not found: the cave would match nothing")
        return 1
    miss = sorted(want - have)
    if miss:
        print(
            f"WARN {label}: {len(miss)} of {len(want)} translated captions are "
            f"not in {FILTER_JSON.name} and would get no font; rebuild it with "
            f"--build-filter ({', '.join(hex(x) for x in miss[:4])}...)"
        )
        return 1
    print(f"ok   {label}: all {len(want)} translated captions are covered")
    return 0


def self_test():
    """Everything that can be checked without the DLL: the cave and the encoder."""
    ok = True
    import caption_font_hook as cfh

    ok = cfh.self_test() and ok

    cm = load_charmap()
    rows = parse_tsv(STRINGS_TSV)
    bad = 0
    for addr, orig, ru in rows:
        enc = encode_text(ru)
        if decode_text(enc) != ru:
            print(f"FAIL {addr:#x}: {ru!r} does not survive the {ENCODING} round trip")
            bad += 1
    extra = f"{len(cm)} charmap entries" if ENCODING == "charmap" else "no charmap"
    print(
        f"{'ok  ' if not bad else 'FAIL'} {ENCODING} round trip: {len(rows)} rows "
        f"from {STRINGS_TSV.name}, {bad} mismatch(es), {extra}"
    )
    ok = ok and not bad
    ok = check_filter(STRINGS_TSV, "self-test filter") == 0 and ok
    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verify", action="store_true", help="verify the patched output")
    ap.add_argument(
        "--strings",
        default=str(ROOT / "ru" / "strings-0.9.1.tsv"),
        help="translation table: RVA<TAB>english<TAB>russian (0.9.1 RVAs)",
    )
    ap.add_argument(
        "--ui2",
        default=str(ROOT / "ru" / "ui2-0.9.1.json"),
        help="second-layer UI table for 0.9.1 (popups/options/hints/hintpages)",
    )
    ap.add_argument(
        "--plan",
        default=str(ROOT / "work" / "plan-0.9.1.json"),
        help="caption display sites: JSON (0.9.0 shape) or RVA/text/site/kind TSV",
    )
    ap.add_argument(
        "--funcs",
        default=str(ROOT / "work" / "funcs-0.9.1.json"),
        help="function boundaries; optional, sites are window-decoded without it",
    )
    ap.add_argument(
        "--caption-font",
        default=None,
        metavar="NAME",
        help=(
            "font to write on the translated captions, e.g. 'menu' or "
            "'regular'; without it the engine keeps drawing them with "
            "'arial', whose glyph table is ASCII only"
        ),
    )
    ap.add_argument(
        "--caption-prop",
        default="font_name",
        choices=(
            "font_name",
            "override_font_name",
            "text_font",
            "alt_font_name",
        ),
        help=(
            "property that receives --caption-font. 'font_name' (default) is "
            "the only one L-0026 saw succeed: the record exists on 206/209 "
            "matched controls and the setter returned success; L-0029 showed "
            "override_font_name has no record at all, so the setter fails. "
            "'text_font'/'alt_font_name' are the other font properties the "
            "0.9.1 image carries (opencode, L-0035: font_name did not change "
            "the menu)"
        ),
    )
    ap.add_argument(
        "--hook-only",
        action="store_true",
        help="install the caption-font cave only; leave every string as shipped",
    )
    ap.add_argument(
        "--caption-all",
        action="store_true",
        help=(
            "L-0035: skip the ru/caption_filter.json table and run the cave "
            "on EVERY 'caption' property. Menu labels go through the same "
            "setter but are mostly not in the table, so the VR Options page "
            "is only reachable with this flag (opencode, L-0035 runlog)"
        ),
    )
    ap.add_argument(
        "--swap-arial-slot",
        action="store_true",
        help=(
            "L-0035 binary test: the cave writes [Fonts+0x08] = [Fonts+0x0c] "
            "(arial <- menu) once per process, keeping old/new in the marker "
            "(+0x1C80 swapped, +0x1C84 old, +0x1C88 new)"
        ),
    )
    ap.add_argument(
        "--swap-arial-sticky",
        action="store_true",
        help=(
            "L-0035: like --swap-arial-slot, but the registry pointer is "
            "re-read from exe+0x1733260 and the store is re-applied on EVERY "
            "setter call, because Fonts::Fonts rebuilds the slots after a "
            "one-shot write (runlog L-0035: arial came back as 0x17056E28). "
            "Counts the passes that really changed the slot at marker "
            "+0x2198"
        ),
    )
    ap.add_argument(
        "--swap-sticky-slot",
        default=None,
        metavar="HEX",
        help=(
            "L-0035: sticky swap of a chosen Fonts slot instead of arial: "
            "0x04 regular, 0x08 arial (default), 0x0c menu, 0x10 console. "
            "The live dump in the runlog has regular = 0 while the page "
            "draws arial, so regular is the slot worth trying next"
        ),
    )
    ap.add_argument(
        "--ctl-dump",
        action="store_true",
        help=(
            "L-0035: dump the font registry (Fonts inline + dereferenced, the "
            "32 bank bases, the four resolved nodes with names) and the first "
            "0x100 bytes of the matched caption control and of the first "
            "local_text control into the marker"
        ),
    )
    ap.add_argument(
        "--font-subst",
        choices=("off", "dry", "write"),
        default="off",
        help=(
            "L-0035: in every control that reaches the cave, replace each "
            "dword in [control, control+0x100) equal to the current `arial` "
            "ref by the `menu` ref. 'dry' only counts matches and records "
            "offsets (+0x2184 found, +0x2188 first, +0x218C last); 'write' "
            "also substitutes and bumps the menu node refcount"
        ),
    )
    ap.add_argument(
        "--subst-offset",
        default=None,
        metavar="HEX",
        help=(
            "L-0035: with --font-subst, also store the `menu` ref at "
            "[control+HEX] on every pass. Probe for the case where the "
            "control carries an empty ref and arial is substituted at draw "
            "time; pick HEX from the control dump"
        ),
    )
    ap.add_argument(
        "--encoding",
        choices=("utf8", "charmap", "cp1251"),
        default="utf8",
        help=(
            "'utf8' (default) matches the live VR control text path (L-0036); "
            "'charmap' writes localization charmap indices, which the control "
            "path renders as Latin letters because every index below 0xE0 is "
            "ASCII; 'cp1251' rebuilds the diagnostic build of the 0.9.1 kit"
        ),
    )
    ap.add_argument(
        "--experimental-cp1251",
        action="store_true",
        help="alias for --encoding cp1251, kept for the kit's command lines",
    )
    ap.add_argument(
        "--no-validators",
        dest="validators",
        action="store_false",
        default=True,
        help=(
            "do not relax the 0x5e ASCII checks. L-0033 proved they never see "
            "our bytes (they run on the .rdata literals), so this is the "
            "default for a clean build; the tested 0.9.1 candidate had them "
            "patched, hence the flag rather than a silent change"
        ),
    )
    ap.add_argument(
        "--site-head",
        default=None,
        metavar="HEX",
        help=(
            "the bytes the site jmp overwrites at the setter, e.g. "
            "4053555741564157 for 0.9.1's five pushes; by default they are "
            "read out of the DLL and checked"
        ),
    )
    ap.add_argument(
        "--allow-unknown-source",
        action="store_true",
        help="build from a DLL whose SHA-256 is not the pinned 0.9.1 release",
    )
    ap.add_argument(
        "--build-filter",
        default=None,
        metavar="PATH",
        help=(
            "regenerate the positive caption filter from --strings and the "
            "selected encoding, then exit"
        ),
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="check the code cave and the charmap encoder; needs no DLL",
    )
    ap.add_argument("--fonts", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--no-fonts", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.experimental_cp1251:
        args.encoding = "cp1251"

    global ENCODING, MENU_LO, MENU_HI, UI2_TABLES, EXTRA_STRINGS, UI2_JSON
    global VALIDATORS, STRINGS_TSV
    ENCODING = args.encoding
    STRINGS_TSV = Path(args.strings)
    if args.build_filter:
        if not STRINGS_TSV.is_file():
            print(f"ERROR translation table not found: {STRINGS_TSV}")
            return 1
        return build_filter(STRINGS_TSV, args.build_filter)

    MENU_LO = ADDRS["menu_lo"]
    MENU_HI = ADDRS["menu_hi"]
    VALIDATORS = () if not args.validators else ADDRS["validators"]
    UI2_JSON = Path(args.ui2)
    STRINGS_TSV = Path(args.strings)
    if "ui2_tables" in ADDRS and ADDRS["ui2_tables"]:
        UI2_TABLES = {k: tuple(v) for k, v in ADDRS["ui2_tables"].items()}
    if ADDRS["extra_strings"]:
        EXTRA_STRINGS = [dict(x) for x in ADDRS["extra_strings"]]

    src = Path(args.src)
    if not src.is_file():
        print(f"ERROR source DLL not found: {src}")
        print("      unpack the mod release there, or pass --src/--out")
        return 1
    data = src.read_bytes()
    got_sha = hashlib.sha256(data).hexdigest()
    if got_sha != SRC_SHA256 and not args.allow_unknown_source:
        print(f"ERROR unexpected source DLL: sha256 {got_sha}")
        print(f"      expected the 0.9.1 release   {SRC_SHA256}")
        print("      pass --allow-unknown-source only if you know why")
        return 1
    if got_sha != SRC_SHA256:
        print(f"WARN source sha256 {got_sha} is not the pinned 0.9.1 release")

    if data[:2] != b"MZ":
        print(f"ERROR {src} is not a PE image (no MZ signature)")
        return 1
    try:
        pe = PE(data)
    except (struct.error, IndexError, ValueError) as ex:
        print(f"ERROR {src}: cannot parse the PE headers ({ex})")
        return 1
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    funcs = [] if args.hook_only else load_funcs(args.funcs)
    errors = []

    if args.hook_only:
        entries, ui2, extras = [], [], []
        plan_by_addr = {}
    else:
        plan_by_addr = load_plan(args.plan)
        rows = parse_tsv(STRINGS_TSV)
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
                    f"{site:#x}: not a lea to {e['addr']:#x} "
                    f"({insn.mnemonic} {insn.op_str})"
                )
                continue
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
                    f"{info['site']:#x}: {e['ru']!r} needs {len(e['enc'])} "
                    f"bytes (SSO cap {SSO_CAP})"
                )

    if not args.hook_only and UI2_JSON.is_file() and not ADDRS.get("ui2_tables"):
        errors.append(
            f"{UI2_JSON.name} exists but ADDRS['ui2_tables'] is not filled for "
            "0.9.1; the 0.9.0 bases would patch the wrong slots"
        )
    ui2 = [] if args.hook_only else load_ui2(data, pe, errors)
    extras = [] if args.hook_only else resolve_extras(md, data, pe, funcs, errors)
    if not args.hook_only and not ui2:
        print(f"WARN no second-layer table loaded from {UI2_JSON.name}")

    if not errors:
        errors.extend(check_encodings(entries, ui2, extras))
        report_limits(entries, ui2, extras)

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
        stubs += b"\0" * 64
    stub_base_off = len(strings_blob)
    stub_base_rva = new_va + stub_base_off
    for sp in stub_plans:
        stub_rva = stub_base_rva + sp["off"]
        kind, val = sp["key"]
        str_rva = new_va + (str_off[val] if kind == "cap" else extra_off[val])
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
    used = max((sp["off"] + sp["size"] for sp in stub_plans), default=0)
    stubs = stubs[:used]
    while len(stubs) % 16:
        stubs.append(0xCC)

    payload = bytes(strings_blob) + bytes(stubs)

    # ---- the caption-font cave ------------------------------------------------
    import caption_font_hook as cfh

    if args.caption_font and not args.hook_only:
        check_filter(STRINGS_TSV, "caption filter")

    hook_blob = b""
    hook_rva = None
    marker_rva = None
    site_patch = None
    hook_dlen = 0
    probe_only = bool(
        args.ctl_dump
        or args.font_subst != "off"
        or args.swap_arial_slot
        or args.swap_arial_sticky
        or args.swap_sticky_slot
    )
    if args.caption_font or probe_only:
        setter = ADDRS["setter"]
        foff = pe.rva_to_off(setter)
        if foff is None:
            errors.append(f"caption font: setter {setter:#x} not mapped")
        else:
            if args.site_head:
                disp = bytes.fromhex(args.site_head)
                cfh.check_displaced(disp)
            else:
                disp = cfh.derive_displaced(pe.data, foff)
                if disp != cfh.DEFAULT_DISPLACED_091:
                    print(
                        f"WARN setter prologue is {disp.hex()}, not the expected "
                        f"{cfh.DEFAULT_DISPLACED_091.hex()}; using what is there"
                    )
            pre = len(payload)
            pad = (-pre) % 16
            hook_rva = new_va + pre + pad
            sticky_slot = False
            if args.swap_arial_sticky:
                sticky_slot = 0x08
            if args.swap_sticky_slot:
                sticky_slot = int(args.swap_sticky_slot, 16)
            subst_off = int(args.subst_offset, 16) if args.subst_offset else None
            hook_blob, site_patch, marker_off, hook_dlen, _ = (
                cfh.build_caption_font_hook(
                    hook_rva,
                    setter,
                    args.caption_font or "menu",
                    args.caption_prop,
                    write=bool(args.caption_font),
                    displaced=disp,
                    accept_all=args.caption_all,
                    swap_arial=args.swap_arial_slot,
                    swap_sticky=sticky_slot,
                    ctl_dump=args.ctl_dump,
                    font_subst=args.font_subst,
                    subst_offset=subst_off,
                )
            )
            marker_rva = hook_rva + marker_off
            hook_blob = b"\0" * pad + hook_blob
            payload = payload + hook_blob

    # ---- collect byte patches -------------------------------------------------
    patches = []
    if site_patch is not None:
        patches.append((pe.rva_to_off(ADDRS["setter"]), site_patch))
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

    if errors:
        for x in errors:
            print("ERROR", x)
        return 1

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
            f"rows: {len(entries)}  translated: {total_strings}  "
            f"kept: {len(entries) - total_strings}"
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
        if hook_rva is not None:
            print(
                f"caption font hook: RVA {hook_rva:#x}, "
                f"setter {ADDRS['setter']:#x} redirected, prop "
                f"{args.caption_prop!r} = {args.caption_font!r}, "
                f"{len(hook_blob)} bytes, marker RVA {marker_rva:#x}"
            )
        else:
            print("caption font hook: off")
        for sp in stub_plans:
            e = sp["text"]
            print(
                f"  inline {sp['info']['site']:#07x} {e['orig']!r} -> "
                f"{e['ru']!r} ({len(e['enc'])}B, region "
                f"{sp['info']['back'] - sp['info']['site']}B)"
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
        0xE0000040,  # MEM_WRITE | MEM_EXECUTE | MEM_READ | CNT_INITIALIZED_DATA
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
        f"translated {total_strings} strings ({total_lea} lea sites, "
        f"{len(stub_plans)} stubs), encoding {ENCODING}"
    )
    print(f".ru section: RVA {new_va:#x}, raw {raw_ptr:#x}, {len(payload)} bytes")
    if hook_rva is not None:
        print(
            f"caption font hook: RVA {hook_rva:#x} -> prop "
            f"{args.caption_prop!r} = {args.caption_font!r} "
            f"(setter {ADDRS['setter']:#x} redirected, marker {marker_rva:#x})"
        )

    rc = 0
    if args.verify:
        rc = verify(
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
        )
        if rc == 0 and hook_rva is not None:
            rc = verify_hook(out_path, hook_rva, ADDRS["setter"], hook_dlen, md)
    return rc


def verify_hook(path, hook_rva, setter_rva, dlen, md):
    """Re-read the cave out of the patched DLL and disassemble it."""
    data = Path(path).read_bytes()
    pe = PE(data)
    o = pe.rva_to_off(setter_rva)
    if o is None or pe.data[o] != 0xE9:
        print("VERIFY ERROR hook: setter site is not a jmp")
        return 1
    tgt = setter_rva + 5 + struct.unpack_from("<i", pe.data, o + 1)[0]
    if tgt != hook_rva:
        print(f"VERIFY ERROR hook: site jumps to {tgt:#x}, cave is {hook_rva:#x}")
        return 1
    for i in range(5, dlen):
        if pe.data[o + i] != 0x90:
            print(f"VERIFY ERROR hook: site pad byte {i} is not 0x90")
            return 1
    body = pe.rva_to_off(setter_rva + dlen)
    if body is None:
        print("VERIFY ERROR hook: setter body not mapped")
        return 1
    # disassemble until the final `jmp` back to the setter body
    start = pe.rva_to_off(hook_rva)
    ins = list(md.disasm(bytes(pe.data[start : start + 0x4000]), hook_rva))
    total = 0
    orphans = 0
    tail = setter_rva + dlen
    for i in ins:
        # the cave has internal `jmp rel32` too; only the one that lands on
        # the displaced setter body is the tail
        if i.mnemonic == "jmp" and i.operands and i.operands[0].type == X86_OP_IMM:
            if i.operands[0].imm == tail:
                print(
                    f"hook ok: {total} bytes of code, {orphans} orphan "
                    f"`00 00`, tail jmp -> {i.operands[0].imm:#x}"
                )
                return 0 if orphans == 0 else 1
            continue
        total += i.size
        if bytes(pe.data[start + i.address - hook_rva :][:2]) == b"\x00\x00":
            orphans += 1
    print("VERIFY ERROR hook: cave does not end with a jmp back to the setter")
    return 1


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
