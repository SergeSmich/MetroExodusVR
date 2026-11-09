#!/usr/bin/env python3
"""Apply Russian translations to MetroExodusVR.dll (mod UI strings).

The original English literals are left untouched: some of them are shared with
engine / graphics code (FSR, DLSS, TAA, OFF, NORMAL, VISIBLE, LEFT/RIGHT HAND).
Instead a new PE section ``.ru`` is appended that holds

  * the translated strings in the encoding selected by ``--encoding`` (see
    below), and
  * small copy stubs for strings that the mod builds inline on the stack.

Which encoding the native menu reads is still an open question between two
models (``ru/ENCODING_NOTES.md`` sections 6-7, ``collab/arena/A-0003``):
localization charmap indices (verified on the ``.lng`` files) versus UTF-8
(the mod also ships ImGui 1.92.8, but that path is confirmed only for the
links plaque).  ``--encoding`` therefore keeps all three builds available:

  * ``charmap`` (default) -- charmap indices, one byte below ``0xE0``;
  * ``utf8`` -- plain UTF-8, the ImGui experiment;
  * ``cp1251`` -- the oldest comparison build.

The four TTF files embedded in the DLL as RCDATA resources (``INFO_INTER_*``
and ``INFO_BARLOW_CONDENSED_SEMIBOLD``) are Latin-only as shipped, so
``--fonts`` (on by default) replaces them with the Cyrillic builds from
``build/fonts/`` made by ``tools/merge_cyrillic.py``; ``--no-fonts`` keeps the
shipped files.

Per display site inside the mod's menu code (0xB0000-0xBFFFF):

  * ``lea reg, [rip+literal]``  ->  the 32-bit RIP displacement is repointed at
    the new string;
  * inline ``std::string`` constructions (mov/movsd/movzx chunks copied into a
    stack buffer) -> a 5-byte ``jmp`` replaces the copy region, the stub copies
    the whole translated string, patches the explicit length constant and jumps
    back after the replaced region.

Finally the "captions are printable ASCII" validators are relaxed
(``cmp al,0x5e`` -> ``cmp al,0xff``) so that UTF-8 bytes and high charmap
indices both pass.

Before anything is written, every payload is encoded and decoded back and
compared with the source text, so a wrong encoding fails the build instead of
producing silent mojibake.

Usage:
    python tools/apply_ru.py --check
    python tools/apply_ru.py [--src DLL] [--out DLL]
"""

import argparse
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_paths  # noqa: E402

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
EXTRA_STRINGS = (
    dict(
        orig="VR HINTS",
        ru="СОВЕТЫ VR",
        lit=0x4999E0,
        site=0x8181C,
        lit_len=8,
        cap=0xF,
        allow_heap=False,
    ),
    dict(
        orig="VR GAMEPAD LAYOUT",
        ru="ГЕЙМПАД VR",
        lit=0x497100,
        site=0x79A1C,
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
# 0xA1816 page builder, 0xA30F6 option-list builder, 0xA12C8 vector-of-captions
# validator (runs before a menu page is applied, rejects non-ASCII).
VALIDATORS = (0xA1816, 0xA30F6, 0xA12C8)

# Generic control-property setter ``bool set(control, name_sv, value_sv)``.
# Every caption goes through it, so it is the cheapest place to also assign a
# font to the control (the mod itself never sets ``font_name``).
SETPROP_RVA = 0x9BC70
SETPROP_HEAD = b"\x40\x53\x55\x57\x41\x56"  # push rbx, rbp, rdi, r14

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

# Three encodings are kept on purpose, because the model is still open:
#   ``charmap`` (default) -- localization charmap indices, the model that
#       ``ru/ENCODING_NOTES.md`` verified byte-for-byte on the .lng files;
#   ``utf8``  -- the ImGui hypothesis (bytes decoded as UTF-8 codepoints);
#   ``cp1251`` -- the oldest experiment, kept for comparison.
# ``charmap`` stays the default until the A-0003 section 5 experiment says
# otherwise (A-0005: ENCODING stays ``charmap`` by default).
ENCODING = "charmap"


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
    """Encode a display string for the mod's UI.

    ``charmap`` (default): localization charmap indices.  Indices below 0xE0
    are one byte.  Larger indices use the two byte form of the ``.lng``
    format: ``value = index + 0xDE41``, bytes ``value // 255`` and
    ``value % 255`` -- the same rule ``tools/lng_dump.py`` decodes with.

    ``utf8``: plain UTF-8, the ImGui experiment build.

    ``cp1251``: the oldest experiment.
    """
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

    if ENCODING == "utf-8":
        enc = s.encode("utf-8")
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
    if ENCODING in ("cp1251", "utf-8"):
        codec = "cp1251" if ENCODING == "cp1251" else "utf-8"
        return enc.decode(codec)
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


def build_caption_font_hook(blob_rva, site_rva, font_name, prop_name="font_name"):
    """Code cave for the property setter ``site_rva``.

    The mod sets the ``caption`` property of a control but never touches the
    font, so the engine draws the caption with its default ``arial`` (ASCII
    only).  This hook watches the setter and, whenever the property being set
    is ``caption``, sets ``prop_name`` (a font property: ``font_name`` class
    level or ``override_font_name`` control level, A-0016 §7.2) on the same
    control first.  The nested call re-enters the site and the hook lets it
    through.

    The cave starts at ``blob_rva``; the caller maps the first six bytes of
    ``site_rva`` to it.  Returns ``(blob, site_patch)``.
    """
    code = bytearray()
    fixups = []

    # --- positive caption filter (ru/caption_filter.json, A-0020 §7.1) -------
    prop = prop_name.encode("ascii")
    hashes = []
    cf = Path(__file__).resolve().parent.parent / "ru" / "caption_filter.json"
    if cf.exists():
        doc = json.loads(cf.read_text(encoding="utf-8"))
        hashes = sorted({int(e["hash32"]) & 0xFFFFFFFF for e in doc.get("entries", [])})
    if not hashes:
        hashes = [0xFFFFFFFF]
    filter_count = len(hashes)

    # --- save every register we clobber (5 callee-saved + 8 volatile) --------
    code += b"\x53\x55\x57\x41\x56\x41\x57"  # push rbx, rbp, rdi, r14, r15
    code += b"\x50\x51\x52\x56\x41\x50\x41\x51\x41\x52\x41\x53"  # rax..r11
    code += b"\x48\x83\xec\x20"  # sub rsp, 0x20 (shadow space, keeps 16B align)

    code += b"\x48\x8b\xd9"  # mov rbx, rcx  (control)
    code += b"\x48\x8b\xea"  # mov rbp, rdx  (name string_view)
    code += b"\x49\x8b\xf8"  # mov rdi, r8   (value string_view)

    # --- debug marker: [+0x00] calls dword, [+0x04] caption dword -------------
    code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+marker]
    mfx1 = len(code) - 4
    code += b"\xff\x40\x00"  # inc dword ptr [rax]      (calls seen)

    # --- recognizers (A-0025 §3): name=="on_draw_item" / name startswith "item"
    code += b"\x48\x83\x7d\x08\x0c"  # cmp qword [rbp+8], 12
    ra1 = len(code)
    code += b"\x75\0"  # jne rec_b
    code += b"\x48\x8b\x45\x00"  # mov rax, [rbp]
    code += b"\x81\x38" + b"on_d"
    ra2 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x04" + b"raw_"
    ra3 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x08" + b"item"
    ra4 = len(code)
    code += b"\x75\0"
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\x48\x89\x99\x28\x19\0\0"  # mov [rcx+0x1928], rbx (list control)
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rdi+8] (value len)
    code += b"\x89\x91\x30\x19\0\0"  # mov [rcx+0x1930], edx
    code += b"\xff\x81\x44\x19\0\0"  # inc dword [rcx+0x1944] (count a)
    code += b"\x4c\x8b\x0f"  # mov r9, [rdi]
    code += b"\x41\xba\x10\0\0\0"  # mov r10d, 16
    code += b"\x4c\x39\xd2"  # cmp rdx, r10
    code += b"\x76\x03"  # jbe keep
    code += b"\x44\x89\xd2"  # mov edx, r10d
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    ra_loop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    ra6 = len(code)
    code += b"\x74\0"  # je rec_b
    code += b"\x47\x0f\xb6\x04\x19"  # movzx r8d, byte [r9+r11]
    code += b"\x46\x88\x84\x19\x48\x19\0\0"  # mov [rcx+r11+0x1948], r8b
    code += b"\x49\xff\xc3"  # inc r11
    ra7 = len(code)
    code += b"\xeb\0"  # jmp ra_loop

    rec_b = len(code)
    code += b"\x48\x83\x7d\x08\x04"  # cmp qword [rbp+8], 4
    rb1 = len(code)
    code += b"\x72\0"  # jb not_b
    code += b"\x48\x8b\x45\x00"  # mov rax, [rbp]
    code += b"\x81\x38" + b"item"
    rb2 = len(code)
    code += b"\x75\0"  # jne not_b
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\x48\x89\x99\x38\x19\0\0"  # mov [rcx+0x1938], rbx
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rbp+8] (name len)
    code += b"\x89\x91\x40\x19\0\0"  # mov [rcx+0x1940], edx
    code += b"\xff\x81\x34\x19\0\0"  # inc dword [rcx+0x1934] (count b)
    code += b"\x4c\x8b\x0f"  # mov r9, [rbp]
    code += b"\x41\xba\x10\0\0\0"  # mov r10d, 16
    code += b"\x4c\x39\xd2"  # cmp rdx, r10
    code += b"\x76\x03"  # jbe keep
    code += b"\x44\x89\xd2"  # mov edx, r10d
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    rb_loop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    rb4 = len(code)
    code += b"\x74\0"  # je not_b
    code += b"\x47\x0f\xb6\x04\x19"  # movzx r8d, byte [r9+r11]
    code += b"\x46\x88\x84\x19\x58\x19\0\0"  # mov [rcx+r11+0x1958], r8b
    code += b"\x49\xff\xc3"
    rb5 = len(code)
    code += b"\xeb\0"  # jmp rb_loop
    not_b = len(code)

    # --- recognizer (c): name == "override_font_name" (A-0026 §4) ------------
    code += b"\x48\x83\x7d\x08\x12"  # cmp qword [rbp+8], 18
    rc1 = len(code)
    code += b"\x75\0"  # jne not_c
    code += b"\x48\x8b\x45\x00"  # mov rax, [rbp]
    code += b"\x81\x38" + b"over"
    rc2 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x04" + b"ride"
    rc3 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x08" + b"_fon"
    rc4 = len(code)
    code += b"\x75\0"
    code += b"\x81\x78\x0c" + b"t_na"
    rc5 = len(code)
    code += b"\x75\0"
    code += b"\x66\x81\x78\x10" + b"me"  # cmp word [rax+0x10], 'me'
    rc6 = len(code)
    code += b"\x75\0"
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\xff\x81\x68\x19\0\0"  # inc dword [rcx+0x1968] (count c)
    code += b"\x48\x89\x99\x70\x19\0\0"  # mov [rcx+0x1970], rbx
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rdi+8]
    code += b"\x89\x91\x6c\x19\0\0"  # mov [rcx+0x196c], edx
    code += b"\x4c\x8b\x0f"  # mov r9, [rdi]
    code += b"\x41\xba\x10\0\0\0"  # mov r10d, 16
    code += b"\x4c\x39\xd2"  # cmp rdx, r10
    code += b"\x76\x03"  # jbe keep
    code += b"\x44\x89\xd2"  # mov edx, r10d
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    rc_loop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    rc7 = len(code)
    code += b"\x74\0"  # je not_c
    code += b"\x47\x0f\xb6\x04\x19"  # movzx r8d, byte [r9+r11]
    code += b"\x46\x88\x84\x19\x78\x19\0\0"  # mov [rcx+r11+0x1978], r8b
    code += b"\x49\xff\xc3"
    rc8 = len(code)
    code += b"\xeb\0"  # jmp rc_loop
    not_c = len(code)

    # --- name == "caption"? --------------------------------------------------
    code += b"\x48\x83\x7d\x08\x07"  # cmp qword ptr [rbp+8], 7
    jne1 = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne done
    code += b"\x48\x8b\x45\x00"  # mov rax, [rbp]
    code += b"\x81\x38" + b"capt"  # cmp dword ptr [rax], 'capt'
    jne2 = len(code)
    code += b"\x0f\x85\0\0\0\0"
    code += b"\x66\x81\x78\x04" + b"io"  # cmp word ptr [rax+4], 'io'
    jne3 = len(code)
    code += b"\x0f\x85\0\0\0\0"
    code += b"\x80\x78\x06" + b"n"  # cmp byte ptr [rax+6], 'n'
    jne4 = len(code)
    code += b"\x0f\x85\0\0\0\0"

    # --- caption matched: counter, len (+0x38), first 8 bytes (+0x30) --------
    code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+marker]
    mfx2 = len(code) - 4
    code += b"\xff\x40\x04"  # inc dword ptr [rax+4]    (caption matches)

    # --- positive filter: fnv1a32(caption value) must be in our table --------
    code += b"\x4c\x8b\x0f"  # mov r9, [rdi]        (value bytes)
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rdi+8] (value len)
    code += b"\xb8\xc5\x9d\x1c\x81"  # mov eax, 0x811c9dc5
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    hash_loop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    h1 = len(code)
    code += b"\x76\0"  # jbe hash_done (r11 >= len)
    code += b"\x47\x0f\xb6\x14\x19"  # movzx r10d, byte [r9+r11]
    code += b"\x44\x31\xd0"  # xor eax, r10d
    code += b"\x69\xc0\x93\x01\x00\x01"  # imul eax, eax, 0x01000193
    code += b"\x49\xff\xc3"  # inc r11
    h2 = len(code)
    code += b"\xeb\0"  # jmp hash_loop
    hash_done = len(code)
    code += b"\x4c\x8d\x0d\0\0\0\0"  # lea r9, [rip+filter_table]
    fixups.append((len(code) - 4, b"filter_table"))
    code += b"\xb9" + struct.pack("<I", filter_count)  # mov ecx, count
    search_loop = len(code)
    code += b"\x41\x39\x01"  # cmp dword [r9], eax
    s1 = len(code)
    code += b"\x74\0"  # je hit
    code += b"\x49\x83\xc1\x04"  # add r9, 4
    code += b"\xff\xc9"  # dec ecx
    s2 = len(code)
    code += b"\x75\0"  # jnz search_loop
    jmiss = len(code)
    code += b"\xe9\0\0\0\0"  # jmp done (miss: not our caption)

    # --- hit: record kind/found in the marker --------------------------------
    hit = len(code)
    code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\xff\x40\x2c"  # inc dword ptr [rax+0x2c] (matched counter)
    # len + sample describe THIS matched call (A-0024 §1)
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rdi+8]     (caption len)
    code += b"\x89\x50\x28"  # mov [rax+0x28], edx  (caption len)
    code += b"\x4c\x8b\x0f"  # mov r9, [rdi]        (caption bytes)
    code += b"\x41\xba\x08\0\0\0"  # mov r10d, 8
    code += b"\x4c\x39\xd2"  # cmp rdx, r10
    ncclamp = len(code)
    code += b"\x76\x03"  # jbe keep (count stays rdx)
    code += b"\x44\x89\xd2"  # mov edx, r10d (count = 8)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    nsloop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    nb1 = len(code)
    code += b"\x74\0"  # je sample done
    code += b"\x47\x0f\xb6\x04\x19"  # movzx r8d, byte [r9+r11]
    code += b"\x46\x88\x44\x18\x30"  # mov [rax+r11+0x30], r8b (sample)
    code += b"\x49\xff\xc3"  # inc r11
    nb2 = len(code)
    code += b"\xeb\0"  # jmp nsloop
    nsdone = len(code)
    code += b"\xc6\x40\x27\x00"  # mov byte [rax+0x27], 0 (found = 0)
    code += b"\xc6\x40\x26\x00"  # mov byte [rax+0x26], 0 (body kind = 0)
    code += b"\xc6\x40\x23\x00"  # mov byte [rax+0x23], 0 (has kind-2 = 0)
    code += b"\x48\x8b\x53\x38"  # mov rdx, [rbx+0x38] (bag begin/cursor)
    code += b"\x4c\x8b\x4b\x40"  # mov r9, [rbx+0x40]  (bag end)
    code += b"\x4c\x8d\x15\0\0\0\0"  # lea r10, [rip+prop_name]
    fixups.append((len(code) - 4, b"prop_name"))
    scan_loop = len(code)
    code += b"\x4c\x39\xca"  # cmp rdx, r9
    sc1 = len(code)
    code += b"\x73\0"  # jae scan_done
    code += b"\x48\x83\x7a\x18" + struct.pack(
        "<B", len(prop)
    )  # cmp [rdx+0x18], len(prop)
    sc2 = len(code)
    code += b"\x75\0"  # jne scan_next
    code += b"\x48\x83\x7a\x20\x0f"  # cmp qword [rdx+0x20], 0xf
    sc3 = len(code)
    code += b"\x76\0"  # jbe scan_inline
    code += b"\x4c\x8b\x42\x08"  # mov r8, [rdx+8] (heap name)
    sc4 = len(code)
    code += b"\xeb\0"  # jmp cmp_start
    scan_inline = len(code)
    code += b"\x4c\x8d\x42\x08"  # lea r8, [rdx+8] (SSO name)
    cmp_start = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    cmploop = len(code)
    code += b"\x49\x83\xfb" + struct.pack("<B", len(prop))  # cmp r11, len(prop)
    sc6 = len(code)
    code += b"\x73\0"  # jae match
    code += b"\x43\x8a\x34\x18"  # mov sil, byte [r8+r11]
    code += b"\x43\x3a\x34\x1a"  # cmp sil, byte [r10+r11]
    sc7 = len(code)
    code += b"\x75\0"  # jne scan_next
    code += b"\x49\xff\xc3"  # inc r11
    sc8 = len(code)
    code += b"\xeb\0"  # jmp cmploop
    smatch = len(code)
    code += b"\x44\x0f\xb6\x02"  # movzx r8d, byte [rdx] (kind)
    code += b"\x41\x80\xf8\x01"  # cmp r8b, 1
    sk_body = len(code)
    code += b"\x74\0"  # je body
    code += b"\x41\x80\xf8\x02"  # cmp r8b, 2
    sk_skip = len(code)
    code += b"\x75\0"  # jne scan_next (kinds 0/3/4 ignored, like setter)
    code += b"\xc6\x40\x23\x01"  # mov byte [rax+0x23], 1 (kind-2 header seen)
    sk_h2 = len(code)
    code += b"\xeb\0"  # jmp scan_next
    sbody = len(code)
    code += b"\xc6\x40\x26\x01"  # mov byte [rax+0x26], 1 (body kind = 1)
    code += b"\xc6\x40\x27\x01"  # mov byte [rax+0x27], 1 (found)
    sc9 = len(code)
    code += b"\xeb\0"  # jmp scan_done
    scan_next = len(code)
    code += b"\x48\x81\xc2\x98\0\0\0"  # add rdx, 0x98
    sc10 = len(code)
    code += b"\xeb\0"  # jmp scan_loop
    scan_done = len(code)

    # --- read the EXISTING font_name value before any write (A-0026 §3) ------
    # Scan the same bag for name "font_name" (9 bytes), capture value len+8B.
    # Preserves rbx/rbp/rdi; clobbers rax,rcx,rdx,r8-r11,rsi.
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fn_mfx = len(code) - 4
    fixups.append((fn_mfx, b"marker"))
    code += b"\x4c\x8d\x15\0\0\0\0"  # lea r10, [rip+font_name_lit]
    fixups.append((len(code) - 4, b"font_name_lit"))
    code += b"\x48\x8b\x53\x38"  # mov rdx, [rbx+0x38]
    code += b"\x4c\x8b\x4b\x40"  # mov r9, [rbx+0x40]
    fn_loop = len(code)
    code += b"\x4c\x39\xca"  # cmp rdx, r9
    fn1 = len(code)
    code += b"\x73\0"  # jae fn_done
    code += b"\x48\x83\x7a\x18\x09"  # cmp qword [rdx+0x18], 9
    fn2 = len(code)
    code += b"\x75\0"  # jne fn_next
    code += b"\x48\x83\x7a\x20\x0f"  # cmp qword [rdx+0x20], 0xf
    fn3 = len(code)
    code += b"\x76\0"  # jbe fn_inline
    code += b"\x4c\x8b\x42\x08"  # mov r8, [rdx+8]
    fn4 = len(code)
    code += b"\xeb\0"  # jmp fn_cmp
    fn_inline = len(code)
    code += b"\x4c\x8d\x42\x08"  # lea r8, [rdx+8]
    fn_cmp = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    fn_cloop = len(code)
    code += b"\x49\x83\xfb\x09"  # cmp r11, 9
    fn5 = len(code)
    code += b"\x73\0"  # jae fn_match
    code += b"\x43\x8a\x04\x18"  # mov al, [r8+r11]
    code += b"\x43\x3a\x04\x1a"  # cmp al, [r10+r11]
    fn6 = len(code)
    code += b"\x75\0"  # jne fn_next
    code += b"\x49\xff\xc3"
    fn7 = len(code)
    code += b"\xeb\0"  # jmp fn_cloop
    fn_match = len(code)
    # rdx = matching record, rcx = marker
    code += b"\x4c\x8b\x42\x70"  # mov r8, [rdx+0x70] (value len)
    code += b"\x44\x89\x81\x88\x19\0\0"  # mov [rcx+0x1988], r8d
    code += b"\x48\x83\x7a\x78\x0f"  # cmp qword [rdx+0x78], 0xf (val cap)
    fn8 = len(code)
    code += b"\x76\0"  # jbe fn_vsso
    code += b"\x48\x8b\x42\x60"  # mov rax, [rdx+0x60] (heap ptr)
    fn9 = len(code)
    code += b"\xeb\0"  # jmp fn_vcopy
    fn_vsso = len(code)
    code += b"\x48\x8d\x42\x60"  # lea rax, [rdx+0x60] (inline)
    fn_vcopy = len(code)
    # rax = value bytes ptr, r8 = value len, rcx = marker
    code += b"\x41\xba\x08\0\0\0"  # mov r10d, 8
    code += b"\x4d\x39\xc2"  # cmp r10, r8  (cap count at 8)
    fn10 = len(code)
    code += b"\x76\0"  # jbe fn_vcnt (8 <= len => copy 8)
    code += b"\x44\x89\xc2"  # mov edx, r8d (count = len)
    fn11 = len(code)
    code += b"\xeb\0"  # jmp fn_vgo
    fn_vcnt = len(code)
    code += b"\x41\xba\x08\0\0\0"  # mov r10d, 8
    code += b"\x44\x89\xd2"  # mov edx, r10d (count = 8)
    fn_vgo = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    fn_vloop = len(code)
    code += b"\x41\x39\xd3"  # cmp r11d, edx
    fn12 = len(code)
    code += b"\x73\0"  # jae fn_done
    code += b"\x46\x0f\xb6\x04\x18"  # movzx r8d, byte [rax+r11]
    code += b"\x46\x88\x84\x19\x8c\x19\0\0"  # mov [rcx+r11+0x198c], r8b
    code += b"\x49\xff\xc3"
    fn13 = len(code)
    code += b"\xeb\0"  # jmp fn_vloop
    fn_next = len(code)
    code += b"\x48\x81\xc2\x98\0\0\0"  # add rdx, 0x98
    fn14 = len(code)
    code += b"\xeb\0"  # jmp fn_loop
    fn_done = len(code)

    # --- set the font property on the same control ---------------------------
    code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+prop_name]
    fixups.append((len(code) - 4, b"prop_name"))
    code += b"\x48\x89\x04\x24"  # mov [rsp], rax
    code += b"\x48\xc7\x44\x24\x08" + struct.pack("<I", len(prop))  # name len
    code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+font_value]
    fixups.append((len(code) - 4, b"font_value"))
    code += b"\x48\x89\x44\x24\x10"  # mov [rsp+0x10], rax
    code += b"\x48\xc7\x44\x24\x18" + struct.pack("<I", len(font_name))
    code += b"\x48\x8b\xcb"  # mov rcx, rbx
    code += b"\x48\x8d\x14\x24"  # lea rdx, [rsp]
    code += b"\x4c\x8d\x44\x24\x10"  # lea r8, [rsp+0x10]
    call_pos = len(code)
    code += b"\xe8\0\0\0\0"  # call site (the setter itself)
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mfx3 = len(code) - 4
    code += b"\x88\x41\x24"  # mov byte ptr [rcx+0x24], al (set result)
    # probe fields the resolver cares about (A-0018 §1/§2/§6)
    code += b"\x48\x8b\x43\x60"  # mov rax, [rbx+0x60]  (override member)
    code += b"\x48\x89\x41\x40"  # mov [rcx+0x40], rax
    code += b"\x0f\xb6\x83\xac\0\0\0"  # movzx eax, byte [rbx+0xac] (disp32!)
    code += b"\x24\x01"  # and al, 1
    code += b"\x88\x41\x25"  # mov [rcx+0x25], al     (gate bit)
    code += b"\x48\x89\x59\x08"  # mov qword ptr [rcx+8], rbx (matched control)
    # record bag bounds, read the same way the setter does
    code += b"\x48\x8b\x43\x38"  # mov rax, [rbx+0x38]
    code += b"\x48\x89\x41\x10"  # mov [rcx+0x10], rax
    code += b"\x48\x8b\x43\x40"  # mov rax, [rbx+0x40]
    code += b"\x48\x89\x41\x18"  # mov [rcx+0x18], rax
    # return address of whoever set the property (13 pushes + 0x20 shadow)
    code += b"\x48\x8b\x84\x24\x88\0\0\0"  # mov rax, [rsp+0x88]
    code += b"\x48\x89\x41\x38"  # mov [rcx+0x38], rax (caller)
    # class identity (A-0024 §5): vtable qword + bag byte size
    code += b"\x48\x8b\x03"  # mov rax, [rbx] (vtable ptr)
    code += b"\x48\x89\x81\x18\x19\0\0"  # mov [rcx+0x1918], rax
    code += b"\x48\x8b\x41\x18"  # mov rax, [rcx+0x18] (bag end)
    code += b"\x48\x2b\x41\x10"  # sub rax, [rcx+0x10] (begin)
    code += b"\x89\x81\x20\x19\0\0"  # mov [rcx+0x1920], eax (bag bytes)

    # --- aggregate counters across matched controls (tail of the marker) --
    code += b"\x80\x79\x27\x00"  # cmp byte [rcx+0x27], 0 (found?)
    agg1 = len(code)
    code += b"\x74\0"  # je agg_done
    code += b"\xff\x81\x00\x19\0\0"  # inc dword [rcx+0x1900] (found_any)
    code += b"\x80\x79\x24\x00"  # cmp byte [rcx+0x24], 0 (set ok?)
    agg2 = len(code)
    code += b"\x74\0"  # je agg_done
    code += b"\xff\x81\x04\x19\0\0"  # inc dword [rcx+0x1904] (set_ok_any)
    code += b"\x48\x83\xb9\x08\x19\0\0\x00"  # cmp qword [rcx+0x1908], 0
    agg3 = len(code)
    code += b"\x75\0"  # jne agg_done (keep first)
    code += b"\x48\x89\x99\x08\x19\0\0"  # mov [rcx+0x1908], rbx (first control)
    code += b"\x48\x8b\x03"  # mov rax, [rbx] (A-0026 §5)
    code += b"\x48\x89\x81\x98\x19\0\0"  # mov [rcx+0x1998], rax
    code += b"\x48\x8b\x43\x60"  # mov rax, [rbx+0x60]
    code += b"\x48\x89\x81\x10\x19\0\0"  # mov [rcx+0x1910], rax (its q60)
    agg_done = len(code)

    # --- copy the record list into the marker, RAW ----------------------------
    # Each record is 0x98 bytes: kind @0, name as std::string {ptr @+8,
    # len @+0x18, cap @+0x20} and value at +0x60 {ptr, len @+0x70, cap
    # @+0x78}.  We copy the records verbatim (40 max) at marker+0x40; the
    # offline parser (work/dump_bag.py) reads SSO content directly and heap
    # pointers only while they are still alive.  The stale 'glued names'
    # artefact (L-0015 §2) came from the old 15-byte compact entries.
    code += b"\x48\x8b\x41\x10"  # mov rax, [rcx+0x10]  (bag begin)
    code += b"\x48\x8b\x51\x18"  # mov rdx, [rcx+0x18]  (bag end)
    code += b"\x48\x8d\x79\x48"  # lea rdi, [rcx+0x48]  (out: raw records)
    code += b"\x45\x33\xc0"  # xor r8d, r8d          (records copied)
    loop_start = len(code)
    code += b"\x48\x3b\xc2"  # cmp rax, rdx
    jae1 = len(code)
    code += b"\x0f\x83\0\0\0\0"  # jae done (near)
    code += b"\x41\x83\xf8\x28"  # cmp r8d, 40
    jae2 = len(code)
    code += b"\x0f\x83\0\0\0\0"  # jae done (near)
    code += b"\x48\x8b\xf0"  # mov rsi, rax           (src record)
    code += b"\x48\x89\x4c\x24\x10"  # mov [rsp+0x10], rcx  (park marker)
    code += b"\xfc"  # cld (rep movsb needs DF=0)
    code += b"\xb9\x98\0\0\0"  # mov ecx, 0x98
    code += b"\xf3\xa4"  # rep movsb              (record -> marker, raw)
    code += b"\x48\x8b\x4c\x24\x10"  # mov rcx, [rsp+0x10]  (restore marker)
    code += b"\x48\x89\xf0"  # mov rax, rsi           (rsi advanced by 0x98)
    code += b"\x41\xff\xc0"  # inc r8d
    jb11 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp loop_start (near)
    copied_done = len(code)
    code += b"\x44\x89\x41\x20"  # mov [rcx+0x20], r8d  (records copied)

    # --- patch the record-loop branches -------------------------------------
    for pos, target in ((jae1, copied_done), (jae2, copied_done)):
        struct.pack_into("<i", code, pos + 2, target - (pos + 6))
    struct.pack_into("<i", code, jb11 + 1, loop_start - (jb11 + 5))
    # caption-sample / hash / search / scan branches (short, 8-bit)
    for pos, target in (
        (nb1, nsdone),
        (nb2, nsloop),
        (h1, hash_done),
        (h2, hash_loop),
        (s1, hit),
        (s2, search_loop),
        (sc1, scan_done),
        (sc2, scan_next),
        (sc3, scan_inline),
        (sc4, cmp_start),
        (sc6, smatch),
        (sc7, scan_next),
        (sc8, cmploop),
        (sc9, scan_done),
        (sc10, scan_loop),
        (fn1, fn_done),
        (fn2, fn_next),
        (fn3, fn_inline),
        (fn4, fn_cmp),
        (fn5, fn_match),
        (fn6, fn_next),
        (fn7, fn_cloop),
        (fn8, fn_vsso),
        (fn9, fn_vcopy),
        (fn10, fn_vcnt),
        (fn11, fn_vgo),
        (fn12, fn_done),
        (fn13, fn_vloop),
        (fn14, fn_loop),
        (sk_body, sbody),
        (sk_skip, scan_next),
        (sk_h2, scan_next),
        (agg1, agg_done),
        (agg2, agg_done),
        (agg3, agg_done),
        (ra1, rec_b),
        (ra2, rec_b),
        (ra3, rec_b),
        (ra4, rec_b),
        (ra6, rec_b),
        (ra7, ra_loop),
        (rb1, not_b),
        (rb2, not_b),
        (rb4, not_b),
        (rb5, rb_loop),
        (rc1, not_c),
        (rc2, not_c),
        (rc3, not_c),
        (rc4, not_c),
        (rc5, not_c),
        (rc6, not_c),
        (rc7, not_c),
        (rc8, rc_loop),
    ):
        code[pos + 1] = (target - (pos + 2)) & 0xFF

    # --- epilogue ------------------------------------------------------------
    done = len(code)
    for p in (jne1, jne2, jne3, jne4):
        struct.pack_into("<i", code, p + 2, done - (p + 6))
    struct.pack_into("<i", code, jmiss + 1, done - (jmiss + 5))
    code += b"\x48\x83\xc4\x20"  # add rsp, 0x20
    code += b"\x41\x5b\x41\x5a\x41\x59\x41\x58\x5e\x5a\x59\x58"
    code += b"\x41\x5f\x41\x5e\x5f\x5d\x5b"  # pop r11..rbx
    code += b"\x53\x55\x57\x41\x56"  # displaced prologue: rbx, rbp, rdi, r14
    jmp_pos = len(code)
    code += b"\xe9\0\0\0\0"  # jmp site+6

    # --- data ---------------------------------------------------------------
    while len(code) % 16:
        code.append(0xCC)
    data_off = {}
    for name, raw in (
        (b"prop_name", prop + b"\0"),
        (b"font_name_lit", b"font_name\0"),
        (b"font_value", font_name.encode("ascii") + b"\0"),
        (b"filter_table", struct.pack(f"<{len(hashes)}I", *hashes)),
        (b"marker", b"\0" * 0x1C00),
    ):
        data_off[name] = (len(code), len(raw) - 1)
        code += raw
    for fx in (mfx1, mfx2, mfx3):
        fixups.append((fx, b"marker"))
    blob = bytes(code)

    for disp_pos, name in fixups:
        off, ln = data_off[name]
        disp = (blob_rva + off) - (blob_rva + disp_pos + 4)
        code = bytearray(blob)
        struct.pack_into("<i", code, disp_pos, disp)
        blob = bytes(code)

    blob = bytearray(blob)
    struct.pack_into("<i", blob, call_pos + 1, site_rva - (blob_rva + call_pos + 5))
    struct.pack_into("<i", blob, jmp_pos + 1, (site_rva + 6) - (blob_rva + jmp_pos + 5))
    return (
        bytes(blob),
        b"\xe9" + struct.pack("<i", blob_rva - (site_rva + 5)) + b"\x90",
        data_off[b"marker"][0],
    )


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
    """Round-trip every payload through the same decoder the UI uses.

    For UTF-8 that is ImGui's own decoder; in the legacy charmap mode it is the
    engine's glyph lookup.  A mismatch here means the caption would render as
    other characters (or as .notdef).
    """
    errors = []

    def check(label, text, enc):
        try:
            back = decode_text(enc)
        except (IndexError, ValueError, UnicodeDecodeError) as exc:
            errors.append(f"{label}: encoded bytes are not valid ({exc})")
            return
        if back != text:
            errors.append(f"{label}: {text!r} would render as {back!r}")
        if 0 in enc:
            errors.append(f"{label}: encoded text contains a NUL")

    for e in entries:
        if e.get("probe"):
            # raw byte probe: the payload is not text, only the NUL rule applies
            if 0 in e["enc"]:
                errors.append(f"{e['addr']:#x}: probe payload contains a NUL")
        elif not e["skip"]:
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
    if ENCODING == "charmap" and len(charmap()) <= 0xE0:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verify", action="store_true", help="verify the patched output")
    ap.add_argument(
        "--fonts",
        dest="fonts",
        action="store_true",
        default=True,
        help=(
            "replace the embedded Inter/Barlow RCDATA fonts with the Cyrillic "
            "builds from build/fonts/; the links plaque's ImGui draws with them, "
            "so this is on by default"
        ),
    )
    ap.add_argument(
        "--no-fonts",
        dest="fonts",
        action="store_false",
        help="keep the fonts as shipped (Latin-only) - rollback for comparison",
    )
    ap.add_argument(
        "--encoding",
        choices=("charmap", "cp1251", "utf8"),
        default="charmap",
        help=(
            "how the translation is written into .ru: 'charmap' (default) emits "
            "the localization charmap indices the engine's glyph lookup expects; "
            "'cp1251' rebuilds the old Windows-1251 build; 'utf8' is the "
            "experiment build for the ImGui hypothesis"
        ),
    )
    ap.add_argument(
        "--probe-json",
        default=None,
        help=(
            "JSON object {caption RVA hex: hex payload} that replaces the encoded "
            "bytes of those captions with arbitrary raw bytes (diagnostic builds)"
        ),
    )
    ap.add_argument(
        "--caption-font",
        default=None,
        metavar="NAME",
        help=(
            "assign this font (e.g. 'main_menu') to every control whose caption "
            "the mod sets; without it captions fall back to the engine default "
            "'arial', which has ASCII glyphs only"
        ),
    )
    ap.add_argument(
        "--caption-prop",
        default="font_name",
        metavar="PROP",
        help=(
            "which property receives --caption-font: the class-level "
            "'font_name' (legacy) or the control-level 'override_font_name' "
            "(A-0016 §7.2, preferred)"
        ),
    )
    args = ap.parse_args()

    global ENCODING
    ENCODING = "utf-8" if args.encoding == "utf8" else args.encoding

    src = Path(args.src)
    if not src.is_file():
        print(f"ERROR source DLL not found: {src}")
        print("      unpack the mod release there, or pass --src/--out")
        print(
            "      (tables-only checks: tools/charmap_codec.py, tools/validate_ui2.py)"
        )
        return 1
    data = src.read_bytes()
    pe = PE(data)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    plan = json.loads(re_paths.PLAN.read_text(encoding="utf-8"))
    funcs = json.loads(re_paths.FUNCS.read_text(encoding="utf-8"))["funcs"]
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

    # ---- optional raw byte probe ---------------------------------------------
    # ``--probe-json {"0x49f694": "312e8081.."}`` replaces the encoded payload
    # of the given captions with arbitrary bytes, so a VR run can show what the
    # native renderer does with byte values (no text round-trip).
    if args.probe_json:
        probe = json.loads(Path(args.probe_json).read_text(encoding="utf-8"))
        by_addr = {e["addr"]: e for e in entries}
        for key, hexbytes in probe.items():
            addr = int(key, 16)
            e = by_addr.get(addr)
            if e is None:
                errors.append(f"probe {key}: not a caption address")
                continue
            enc = bytes.fromhex(hexbytes)
            if len(enc) > MAX_LEN:
                errors.append(f"probe {key}: {len(enc)} bytes > {MAX_LEN:#x}")
                continue
            if 0 in enc:
                errors.append(f"probe {key}: payload contains a NUL")
                continue
            e["enc"] = enc
            e["probe"] = True
            print(
                f"probe {addr:#x} ({e['orig']!r}): {' '.join(f'{b:02x}' for b in enc)}"
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
    # The embedded Inter/Barlow files are RCDATA resources that ImGui loads for
    # the mod's own page; the strings are UTF-8 and these fonts must carry the
    # Cyrillic glyphs, so replacing them is part of the normal build.
    fonts = []
    if args.fonts:
        fonts = collect_fonts(pe, data, errors)

    # ---- the bytes must mean the same thing to the engine ---------------------
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

    # ---- optional caption-font hook ------------------------------------------
    hook_blob = b""
    hook_rva = None
    marker_rva = None
    site_patch = None
    hook_site_foff = None
    if args.caption_font:
        foff = pe.rva_to_off(SETPROP_RVA)
        if foff is None:
            errors.append(f"caption font: setter {SETPROP_RVA:#x} not mapped")
        elif bytes(pe.data[foff : foff + 6]) != SETPROP_HEAD:
            errors.append(
                f"caption font: setter {SETPROP_RVA:#x} starts with "
                f"{bytes(pe.data[foff : foff + 6]).hex()}, expected {SETPROP_HEAD.hex()}"
            )
        else:
            pre = len(strings_blob) + len(stubs) + len(font_blob)
            pad = (-pre) % 16
            hook_rva = new_va + pre + pad
            hook_blob, site_patch, marker_off = build_caption_font_hook(
                hook_rva, SETPROP_RVA, args.caption_font, args.caption_prop
            )
            marker_rva = hook_rva + marker_off
            hook_blob = b"\0" * pad + hook_blob
            payload = payload + hook_blob
            hook_site_foff = foff

    # ---- collect byte patches -------------------------------------------------
    patches = []
    if site_patch is not None and hook_site_foff is not None:
        patches.append((hook_site_foff, site_patch))
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
        if hook_rva is not None:
            print(
                f"caption font hook: RVA {hook_rva:#x}, setter {SETPROP_RVA:#x}, "
                f"prop {args.caption_prop!r}, font {args.caption_font!r}, "
                f"{len(hook_blob)} bytes, marker RVA {marker_rva:#x}"
            )
        else:
            print("caption font hook: off")
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
        0xE0000040,  # CNT_INITIALIZED_DATA | EXECUTE | READ | WRITE
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
    if hook_rva is not None:
        print(
            f"caption font hook: RVA {hook_rva:#x} -> prop {args.caption_prop!r} "
            f"= font {args.caption_font!r} "
            f"(setter {SETPROP_RVA:#x} redirected, marker {marker_rva:#x})"
        )

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
