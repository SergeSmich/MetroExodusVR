#!/usr/bin/env python3
"""Apply the Russian translation to MetroExodusVR.dll 0.9.3 (mod UI text).

Fork of ``apply_ru_092.py`` for the 0.9.3 release (SHA-256
``2f9ed2d1..458b2c64``).  Only the version block below changed; the mechanics
are the 0.9.2 ones, so the long rationale lives in that file.  The 0.9.3
values were measured on the release DLL:

* captions: the 267 literals are located by exact C-string match, their
  display sites by the RIP-relative references in ``.text`` (325 lea + 30
  inline sites);
* ui2 tables moved by +0xE0 and kept their strides: popups ``0x4EF0F0``/0x70,
  options ``0x4F5170``/0x20, hints ``0x4EA618``/0x28 (bare body pointer),
  hintpages ``0x4EC570``/0x20 with the title at +0x00;
* the menu code ends at ``0xC581F``, so the window is ``0xA0000..0xC5820``;
* the printable-ASCII gates were not relocated yet, so they are left alone:
  a charmap build keeps every byte below 0x80 (L-0033 patched nothing here).

The encoding is the glyph table of the *menu* font, not UTF-8 and not the
localization charmap (A-0034, L-0048).  A caption's bytes are glyph indices,
so the builder writes the index of every character in the 269-entry table the
game holds at ``exe+0x1765A68`` (``work/font093.json``), and the init cave in
``.ru`` flips the EXE's kind-4 text handler to the byte-identity kind-6 one --
without that flip the engine reads kind-4 bytes as ANSI codepoints and looks
them up in a different table, which is why the charmap build rendered Latin
garbage.  All Cyrillic the kit uses is below index 0x100, i.e. one byte.
"""

import argparse
import json
import os
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
import hashlib  # noqa: E402

# ---------------------------------------------------------------------------
# 0.9.2 addresses -- everything version specific lives here
# ---------------------------------------------------------------------------

# MetroExodusVR.dll from versions/0.9.2 of the mod (E:\MetroExodusVR).
SRC_SHA256 = "2f9ed2d1206f7fc18f87ff554a10e9e6fae849ce8a7dc3074685aa14458b2c64"

ADDRS = dict(
    # Generic control-property setter `bool set(control, name_sv*, value_sv*)`.
    # 0.9.2: 0xA4C40 (0.9.1 0x9F0D0, 0.9.0 0x9BC70).  Found by normalizing the
    # immediates of the 0.9.1 body and comparing against every prologue match
    # in 0.9.2: 55/55 instructions identical, prologue bytes identical.
    setter=0x0,  # 0.9.3: not located; only --caption-font uses it
    # `sub .., 0x20; cmp .., 0x5e` printable-ASCII gates of the page builder.
    # 0.9.3 sites, located by decoding every `sub <r8>, 0x20` candidate:
    #   0xAA8B0  movzx ecx, [rax] / sub cl, 0x20 / cmp cl, 0x5e  (80 f9 5e)
    #   0xAAE00  movzx eax, [rcx] / sub al, 0x20 / cmp al, 0x5e  (3c 5e)
    #   0xAC6E0  movzx eax, [rcx] / sub al, 0x20 / cmp al, 0x5e  (3c 5e)
    # The address is the *entry* of the sequence, so the immediate is located
    # by decoding; widening it to 0xff accepts every byte.
    #
    # A charmap build keeps every byte below 0x80 and does not need it
    # (L-0033 patched nothing here).  A `fontidx` build maps Cyrillic to glyph
    # indices above 0x7f, and the mod then refuses the setting or the whole
    # page ("captions are printable ASCII (at most 127)"), which is exactly why
    # the category pages came up empty (L-0048).
    validators=(0xAA8B0, 0xAAE00, 0xAC6E0),
    # Only the mod's own menu code is redirected.  The range is used to warn
    # about display sites outside it; every site comes from --plan anyway.
    # 0.9.2 menu code ends at 0xC5508 (0.9.1 ended below 0xC0000).
    menu_lo=0xA0000,
    menu_hi=0xC5820,
    # Second-layer table bases (popups/options/hints/hintpages), 0.9.2 counts
    # are 16/82/52/14.  Strides are unchanged from 0.9.1.
    ui2_tables={
        "popups": (0x4EF0F0, 0x70, 0x10, True, None),
        "options": (0x4F5170, 0x20, 0x10, True, None),
        "hints": (0x4EA618, 0x28, 0x10, False, None),
        "hintpages": (0x4EC570, 0x20, 0x10, True, 0x00),
    },
    # Inline-built extras such as "VR HINTS".  None in 0.9.2 either.
    extra_strings=(),
)

# The 0.9.2 kit and the caption plan live in the analysis repository
# (MetroExodusVR-REA); this tools repository is frozen as the 0.9.1 source.
# Override with METRO_KIT093 when the checkout is somewhere else.
KIT093 = Path(os.environ.get("METRO_KIT093", str(ROOT / "kit093")))
PLAN_093 = Path(os.environ.get("METRO_PLAN093", str(KIT093 / "ru" / "plan-0.9.3.json")))
DEFAULT_SRC = Path(
    os.environ.get(
        "METRO_SRC093",
        r"F:\SteamLibrary\steamapps\common\Metro Exodus\versions\0.9.3\MetroExodusVR.dll",
    )
)
DEFAULT_OUT = ROOT / "build" / "MetroExodusVR-0.9.3.dll"
STRINGS_TSV = KIT093 / "ru" / "strings-0.9.3.tsv"
UI2_JSON = KIT093 / "ru" / "ui2-0.9.3.json"

# Embedded font resources that have to carry Cyrillic before the strings can be
# displayed.  The files are produced by tools/merge_cyrillic.py.  Not used on
# the 0.9.2 path: the readable build is Latin (see the docstring).
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
    "popups": (0x4EF0F0, 0x70, 0x10, True, None),
    "options": (0x4F5170, 0x20, 0x10, True, None),
    "hints": (0x4EA618, 0x28, 0x10, False, None),
    "hintpages": (0x4EC570, 0x20, 0x10, True, 0x00),
}
# 0.9.1 for reference: popups 0x4BABC0, options 0x4C06A0, hints 0x4B6768,
# hintpages 0x4B85E0; 0.9.0: 0x49BF40, 0x4A1820, 0x497E00, 0x499A00.

# Literals that are neither captions nor table entries but still show up in the
# UI.  They are built inline, so they get the same copy-stub treatment.
# 0.9.2: empty, as in 0.9.1 (the 0.9.0 "VR HINTS"/"VR GAMEPAD LAYOUT" literals
# have no reference in the newer .text and the address check would fail).
EXTRA_STRINGS = ()

# Only the mod's own menu/page-building code is redirected.
MENU_LO = 0xA0000
MENU_HI = 0xC5820

# offset of the immediate byte in a printable-ASCII check:
#   cmp al, 0x5e  (after `sub al, 0x20`)  ->  cmp al, 0xff  (any byte)
#   cmp cl, 0x5e  (after `sub cl, 0x20`)  ->  cmp cl, 0xff  (any byte)
# 0.9.1 page builder was 0xA1816; the 0.9.2 addresses are in ADDRS above.
VALIDATORS = ()  # 0.9.3: ASCII gates not relocated

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

# ---- the game EXE the DLL runs inside (0.9.3, ImageBase 0x140000000) ---------
# kind 4 = "the bytes are ANSI codepoints, look them up in the font table of
# 0xb56a60"; kind 6 = "the bytes are glyph indices, take them as they are".
# The descriptor table lives at [exe+0xB8DC60] and entry N is the dword at
# +4*N; the panel and the other mod captions are the only kind-4 texts the
# process builds (18 sidebar nodes + "VR" + "VR HINTS"), so the init cave
# rewrites that one slot to kind 6 and leaves kind 1 (the game UI, 369 nodes)
# alone.  Proven live: work/shots/v093_now.png.
EXE_KIND_TABLE = 0xB8DC60
EXE_KIND4_SLOT = 0xB8DC70
EXE_KIND_TABLE_CODE = 0xB8D629  # kind 0/3 handler, an identity check
EXE_KIND6_CODE = 0xB8DBE9
EXE_VIRTUALPROTECT_IAT = 0x4D7200  # DLL IAT: KERNEL32!VirtualProtect
DLL_CREATETHREAD_IAT = 0x4D71A0  # DLL IAT: KERNEL32!CreateThread
DLL_SLEEP_IAT = 0x4D71C0  # DLL IAT: KERNEL32!Sleep

# L-0053: the footer hints of the game's own pause menu are composed with a real
# ASCII space (0x20), and after the kind flip that byte is a glyph index: the
# font table's 0x20 holds U+0021, so "A PLAY" drew as "A !PLAY".  The table is
# built by the game long after DllMain, so the cave spawns a small poller that
# rewrites two entries once the manager exists: 0x20 -> space, 0xA1 -> '!'
# (0xA1 is 'é' in the stock table, a codepoint the Russian kit never emits; our
# own '!' moves there through FONTIDX_BYTE_OVERRIDES).
EXE_FONT_MGR = 0x1765A68  # EXE global: menu font manager ([+8] table, [+0x12] count)
FONT_TABLE_COUNT = 269
FONT_TABLE_SIZE = FONT_TABLE_COUNT * 2
FONT_TABLE_PATCHES = ((0x20, 0x21, 0x20), (0xA1, 0xE9, 0x21))  # index, old cp, new cp

# DllMain entry of the 0.9.3 DLL: two `mov [rsp+..], reg` we replay in the cave
# and then jump back to entry+len(ENTRY_DISPLACED).
ENTRY_RVA = 0x4641A0
ENTRY_DISPLACED = bytes.fromhex("48895c24084889742410")

# L-0051: the value rows ("{:g} Gr./s") are built by the std::vformat look-alike
# at 0xB6C70, which returns plain ASCII; the menu font wants glyph indices, so
# the substituted number drew as random Cyrillic letters ("240" -> "gКш").  The
# call to the formatter is retargeted into a cave that rewrites the field's
# value bytes with glyph indices.  See ``work/_fmt_cave.py``.
VALUE_SITE_RVA = 0xB6D2E  # call 0x180022DF0 inside 0xB6C70
VALUE_BACK_RVA = 0xB6D33  # or esi, 2 -- where the cave returns
FORMATTER_RVA = 0x22DF0
VALUE_TABLE_FIRST = 0x2B  # '+'
VALUE_TABLE_LAST = 0x39  # '9'
# Cave bytes: 157 total.  Layout: ``sub rsp,8``, ``call formatter`` (opcode at
# 4, displacement at 5), ``add rsp,8``, the scan/rewrite loop, ``ret`` back to
# 0xB6D33 (at 141) and the 15-byte glyph table at 142.  ``ret`` and not
# ``jmp``: it must drop the return address that the retargeted ``call`` pushed.
# A ``jmp`` left rsp 8 bytes low, the rest of 0xB6C70 ran shifted and its
# epilogue compared the stack cookie from the wrong slot -> 0xC0000409 with
# fast fail code 2 (stack cookie check); that was the third crash of L-0051.
VALUE_CAVE_TEMPLATE = bytes.fromhex(
    "4883ec08e8000000004883c4084c8b4424584c8b4c246041ba000000004d39ca736b43803c107b74"
    "0549ffc2ebef4d89d349ffc34d39cb735443803c187d75f14d29d949ffc9488d5424684883bc2480"
    "000000107205488b542468488b4424784c29c84c39d076254c8d1d1f000000420fb60c1283e92b83"
    "f90e7709410fb60c0b42880c1249ffc24939c272e2c39a0e3a088a5c57426c727c767f7881"
)
VALUE_CAVE_CALL_DISP_AT = 5
VALUE_CAVE_RET_AT = 141
VALUE_CAVE_TABLE_AT = 142

# The deadzone rows ("{}%" choice lists: 0%, 5% ... 30%) are built by a
# different helper, 0xC1030, which keeps the format string_view 0x10 bytes
# higher in its frame than 0xB6C70 does.  Same cave logic, shifted slots:
# [S+0x60] fmt ptr, [S+0x68] len, [S+0x70] result, size +0x80, cap +0x88.
# Left unpatched, those two rows kept ASCII digits and drew as Cyrillic
# garbage while every 0xB6C70 row ("240 Gr./s") was already correct.
VALUE_SITE2_RVA = 0xC10FF  # call 0x180022DF0 inside 0xC1030
VALUE_BACK2_RVA = 0xC1104  # or esi, 2 -- where the second cave returns
VALUE_CAVE2_TEMPLATE = bytes.fromhex(
    "4883ec08e8000000004883c4084c8b4424684c8b4c247041ba000000004d39ca736e43803c107b74"
    "0549ffc2ebef4d89d349ffc34d39cb735743803c187d75f14d29d949ffc9488d5424784883bc2490"
    "000000107205488b542478488b8424880000004c29c84c39d076254c8d1d1f000000420fb60c1283e9"
    "2b83f90e7709410fb60c0b42880c1249ffc24939c272e2c39a0e3a088a5c57426c727c767f7881"
)
VALUE_CAVE2_CALL_DISP_AT = 5
VALUE_CAVE2_RET_AT = 144
VALUE_CAVE2_TABLE_AT = 145

# Options-page rows, third builder family.  Every formatter call is the same
# shape: ``rcx`` = &result std::string (MSVC: inline buffer at +0, size at
# +0x10, capacity at +0x18), ``rdx`` = &format std::string_view (pointer at +0,
# length at +8), ``r8`` = &arguments.  So unlike the two caves above this one
# needs no frame offsets at all: it saves rcx/rdx across its own formatter call
# and rewrites the result through them.
#
# Covered here are the remaining ``{}%`` choice lists (0xC4814, 0xC5442,
# 0xC55F9 -- e.g. RENDER SCALE, which drew "70" as two Cyrillic letters and
# "100" as three).  The cave is deliberately conservative: it converts the
# substituted field only if the format has exactly one ``{...}`` pair and the
# field bytes are all in 0x2b..0x39 (``+ , - . / 0..9``), so a row that
# substitutes an already-translated glyph string is left alone.
#
# Every other menu-side formatter call lives in the same family and drew its
# number the same wrong way (``ВЫСОТА ПОЯСА`` showed "oРК СМ" for "+15 CM"):
# the ``{} CM`` / ``+{} CM`` range rows (0xC0E78, 0xC0ED8 in 0xC0DB0 --
# belt height; 0xC3C94, 0xC3E85, 0xC450A, 0xC46CD, 0xC4F15) and the
# ``{} DEG`` / ``{}`` rows (0xBBA8D weapon grip angle, 0xB6B8A int list,
# 0xC6BF3 float-to-string helper).  All of them pass the arguments the same
# way, so one cave serves them all.
VALUE_SITES3_RVA = (
    0xB6B8A,
    0xBBA8D,
    0xC0E78,
    0xC0ED8,
    0xC3C94,
    0xC3E85,
    0xC450A,
    0xC46CD,
    0xC4F15,
    0xC487F,
    0xC54AF,
    0xC566D,
    0xC56CD,
    0xC6BF3,
)
VALUE_CAVE3_TEMPLATE = bytes.fromhex(
    "4883ec2848894c24184889542420e800000000488b5424204c8b024c8b4a08488b4c24184883c428"
    "4531d24d39ca0f839100000043803c107b740549ffc2ebeb4d89d349ffc34d39cb737a43803c187d"
    "75f14c89d848ffc04c39c8730941803c007b7461ebef4d29d949ffc9488d0148837918107203488b"
    "01488b51104c29ca4c39d276404c89d14839d17314440fb60c084183e92b4183f90e772948ffc1eb"
    "e74c89d14c8d1d1b000000440fb60c084183e92b470fb60c0b44880c0848ffc14839d172e6c30000"
    "00000000000000000000000000"
)
VALUE_CAVE3_CALL_DISP_AT = 15
VALUE_CAVE3_RET_AT = 197
VALUE_CAVE3_TABLE_AT = 198

# The mod's own "{}%" literal (0x4f2ed4) never reaches the caption table: the
# plan generator classifies a brace-only string as a printf pattern, not a
# caption (tools/plan.py, FMT), so the row is not in plan-0.9.3.json.  Its '%'
# therefore stayed raw ASCII 0x25, which under fontidx is the glyph index of
# 'l' -- the deadzone rows read "30l" while the digits (rewritten by the cave
# above) were already right.  Four menu builders use this literal: 0xC1092 in
# 0xC1030, plus 0xC4814, 0xC5442, 0xC55F9.  Under fontidx '%' is 0x9b.
FMT_LITERAL_PATCHES = ((0x4F2ED4 + 2, 0x25, 0x9B),)

# Raw-ASCII literals that never reach the caption plan, yet are drawn as they
# are.  Two kinds: short labels the plan generator does not classify as captions
# ("16:9", "4:3", "1.00X" ...) and suffixes of printf patterns that are not
# translated at all ("{:.1f}X", "{:.2f}X", "{}P").  Because kind-6 reads each
# byte as a glyph index, their ASCII letters came out as whatever character sits
# at that index: HUD SHAPE read "РП-Н" (0x31 0x36 0x3a 0x39 = Р П - Н) and "К-И",
# the size rows ended in "R" ('X' = 0x58) and "720P" in the glyph 0x50.  Only the
# literal bytes are rewritten; a {format} part stays ASCII for the formatter.
# Under fontidx: '1'=0x57 '6'=0x76 ':'=0x0f '9'=0x81, '4'=0x72 '3'=0x6c,
# '.'=0x08 '0'=0x5c '2'=0x42 '5'=0x7c, 'X'=0x87, 'P'=0x6e.
GLYPH_LITERAL_PATCHES = (
    (0x4F3814, "16:9"),  # HUD SHAPE option labels (0xBC557 / 0xBC578)
    (0x4F381C, "4:3"),
    (0x4F395C, "1.00X"),  # HINT TIME multipliers (0xBC949 ... 0xBC9AC)
    (0x4F3964, "1.25X"),
    (0x4F396C, "1.50X"),
    (0x4F3974, "2.00X"),
    (0x4F393E, "X"),  # suffix of "{:.1f}X", HINT SIZE value (0xBC8CB)
    (0x4F39B6, "X"),  # suffix of "{:.2f}X", ACTION PROMPT SIZE (0xBCA3C)
    (0x4F4286, "P"),  # suffix of "{}P", HUD RESOLUTION (0xBDDFC)
)

# L-0053: the pause-menu caption of the mod's VR hints section is a plain ASCII
# literal, not a caption row, so it kept its Latin bytes and kind 6 drew them as
# glyph indices: "VR HINTS" read "ЕЯ!МЬЗХА" (V=0x56 -> 'E', R=0x52 -> 'Я',
# ' '=0x20 -> '!', H=0x4d -> 'М', I=0x49 -> 'b', N=0x4e -> 'З', T=0x54 -> 'Х',
# S=0x53 -> 'А').  The literal is loaded whole at 0x8A2CC, one ``mov rax,
# [rip+..]`` plus ``mov [rbp+0x210], rax``, and the std::string's size is then
# set to 8 -- so the field is exactly 8 bytes wide and the word has to fit.
# "СОВЕТЫ VR" is the name the kit uses in the popups but needs 9 bytes; the
# slot keeps "СОВЕТЫ" and two glyph spaces (0x01) as padding.
GLYPH_TEXT_PATCHES = ((0x4EC548, "VR HINTS", "СОВЕТЫ", 8),)

# A-0034: a caption's bytes are glyph-table indices, never codepoints.  The
# kind-4 handler reads them as ANSI codepoints and looks them up in a *second*
# table (``0xb56a60``), so a charmap build came out as Latin garbage; the
# kind-6 handler in the engine takes the bytes literally, so the payload has to
# be the indices of the glyph table the menu font really uses.
ENCODING = "fontidx"

# The 269 codepoints of the 0.9.3 menu font, in glyph order: index = position.
# Read live from ``[[exe+0x1765A68]+8]`` (u16 array, count at ``+0x12``); see
# ``work/font093.json`` and ``work/panel_idx.py``.  It is NOT ``ru/charmap.txt``
# ('Д' is index 0x4d here, 0x43 there).  Only indices <= 0xFF are usable,
# because kind 6 takes one byte per glyph; every character the kit uses fits
# (max is 0xB0 for the Cyrillic letters).
_FONT_GLYPHS_HEX = (
    "0000 0020 043E 0430 0435 0442 0438 043D 002E 0441 0440 043B 0066 0432 002C 003A 043A 0443"
    "043C 0072 0434 003C 003E 0069 043F 0074 044F 044C 0065 0073 044B 0078 0021 0431 0447 006E"
    "0412 006C 0064 0410 0433 0061 0437 006F 005F 0439 0445 0436 0448 0420 0067 0418 041A 041E"
    "041F 0421 0415 041D 002D 0075 0079 0070 0413 0422 0068 003F 0032 044E 006D 0077 0449 044D"
    "041C 0062 0427 041B 0446 0414 0417 0423 042D 0411 042F 0041 0425 0022 0045 0031 0052 0049"
    "0054 0053 0030 004F 004E 006B 0063 0444 0428 0044 0043 0416 0076 004D 004C 003D 0028 0029"
    "0033 2026 0050 0047 0429 042B 0034 042C 0056 0048 0036 004B 0038 0055 0042 0046 0035 0424"
    "0419 0037 0426 0039 0059 007A 044A 0057 004A 0058 201D 201C 002F 042E 006A 00A9 005A 0051"
    "005C 003B 00AE 00A0 0071 00AB 00BB 0023 0026 0027 002B 0025 2122 007C 2019 2013 005B 00E9"
    "00ED 005D 002A 00F6 00FC 00F1 00D3 00E1 00FA 00E4 00D6 00C1 007D 2018 042A 007B 2014 0001"
    "0002 0003 0004 0005 0006 0007 0008 0009 000A 000B 000C 000D 000E 000F 0010 0011 0012 0013"
    "0014 0015 0016 0017 0018 0019 001A 001B 001C 001D 001E 001F 0024 0040 005E 0060 007E 00C0"
    "00C2 00C3 00C4 00C5 00C6 00C7 00C8 00C9 00CA 00CB 00CC 00CD 00CE 00CF 00D0 00D1 00D2 00D4"
    "00D5 00D7 00D8 00D9 00DA 00DB 00DC 00DD 00DE 00DF 00E0 00E2 00E3 00E5 00E6 00E7 00E8 00EA"
    "00EB 00EC 00EE 00EF 00F0 00F2 00F3 00F4 00F5 00F7 00F8 00F9 00FB 00FD 00FE 00FF F8FF"
)
# The literals above are one implicitly concatenated string; the line breaks
# fell where they fell, so drop the whitespace and slice the codepoints back
# out four hex digits at a time.
_FONT_GLYPHS_HEX = "".join(_FONT_GLYPHS_HEX.split())
assert len(_FONT_GLYPHS_HEX) == 269 * 4, "font table is not 4 hex digits per glyph"
FONT_GLYPHS = tuple(
    int(_FONT_GLYPHS_HEX[i : i + 4], 16) for i in range(0, len(_FONT_GLYPHS_HEX), 4)
)

# L-0053: the engine composes some of its own text and keeps the ASCII space
# (0x20) in it; kind 6 reads every byte as a glyph index, so the footer read
# "A !PLAY" -- index 0x20 is '!' in this table.  The DllMain cave patches the
# live table (index 0x20 -> U+0020, index 0xA1 -> U+0021); until it runs, and
# for anything the patch does not cover, our own '!' therefore moves to the
# free Latin index 0xA1 (it maps to 'é' in the table, a codepoint the Russian
# kit never uses).
FONTIDX_BYTE_OVERRIDES = {0x21: 0xA1}
FONTIDX_INDEX_OVERRIDES = {0xA1: 0x21}


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


def _fontidx_pieces(s):
    """Split ``s`` into characters and raw-ASCII ``{...}`` fields.

    The mod builds value texts with a std::vformat look-alike that scans the
    bytes for ``{`` / ``}`` (0x7B / 0x7D).  A glyph index for ``{`` is 0xB1, so
    an encoded format field is invisible to it and ends up drawn literally
    ("{:g} Gr./s" instead of the number).  Replacement fields are therefore
    kept as plain ASCII, everything else is encoded.
    """
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "{":
            end = s.find("}", i)
            if end > i:
                field = s[i : end + 1]
                try:
                    raw = field.encode("ascii")
                except UnicodeEncodeError:
                    raw = None
                if raw is not None and "{" not in field[1:]:
                    out.append(raw)
                    i = end + 1
                    continue
        out.append(ch)
        i += 1
    return out


def encode_text(s):
    """Encode a display string as menu-font glyph indices (``fontidx``).

    The 0.9.3 kind-6 handler takes each byte as a glyph index, so that is what
    this writes; every character the kit uses is below 0x100.  The older
    ``charmap`` branch is kept: indices below 0xE0 are one byte, larger ones use
    the two byte form of the ``.lng`` format (``value = index + 0xDE41``).
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

    if ENCODING == "fontidx":
        rev = {}
        for i, cp in enumerate(FONT_GLYPHS):
            rev.setdefault(cp, i)
        out = bytearray()
        for ch in _fontidx_pieces(s):
            if isinstance(ch, bytes):
                # A ``{...}`` replacement field stays raw ASCII: the mod feeds the
                # string to a std::vformat-like routine that scans bytes for
                # ``{`` / ``}`` (0x7B / 0x7D) and would ignore glyph indices.
                out += ch
                continue
            i = FONTIDX_BYTE_OVERRIDES.get(ord(ch))
            if i is None:
                i = rev.get(ord(ch))
            if i is None:
                raise ValueError(
                    f"{s!r}: character {ch!r} (U+{ord(ch):04X}) has no glyph in "
                    "the 0.9.3 menu font (work/font093.json)"
                )
            if i > 0xFF:
                raise ValueError(
                    f"{s!r}: glyph index {i:#x} for {ch!r} does not fit one "
                    "byte; kind 6 takes one byte per glyph"
                )
            out.append(i)
        if 0 in out:
            raise ValueError(f"encoded {s!r} contains a NUL byte")
        return bytes(out)

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
    if ENCODING == "fontidx":
        out = []
        i = 0
        while i < len(enc):
            b = enc[i]
            if b == 0x7B:
                end = enc.find(b"\x7d", i)
                if end > i:
                    out.append(enc[i : end + 1].decode("ascii"))
                    i = end + 1
                    continue
            out.append(chr(FONTIDX_INDEX_OVERRIDES.get(b, FONT_GLYPHS[b])))
            i += 1
        return "".join(out)
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


def find_len_imm(ins, idx, lit_len):
    """Find ``mov r8d, lit_len`` feeding a ``std::string(ptr, len)`` ctor.

    Pages and switch values are sometimes built with an explicit length::

        mov  r8d, <len>
        lea  rdx, [rip + lit]
        lea  rcx, [dest]
        call 0x8e80

    Here the byte count is a call argument rather than a stored ``string_view``
    field, so it has to be rewritten too.  Leaving it alone truncates a longer
    translation and, worse, appends a NUL to a shorter one: 0.9.3 built
    ``"GRAPHICS"`` as 8 bytes and the translation is 7, so the page caption
    ended up holding ``"ГРАФИКА\\0"`` and the GRAPHICS page never opened.
    """
    for x in ins[idx + 1 : idx + 5]:
        if x.id == 0:
            return None
        if x.mnemonic == "call":
            if x.op_str.strip() != "0x8e80":
                return None
            return _near_len(ins, idx, lit_len)
        if x.mnemonic == "lea" and x.op_str.startswith("rdx,"):
            return None
    return None


def _near_len(ins, idx, lit_len):
    for b in range(1, 5):
        if idx - b < 0:
            return None
        prev = ins[idx - b]
        if prev.id == 0:
            return None
        if prev.mnemonic in ("call", "ret", "jmp") or prev.mnemonic.startswith("j"):
            return None
        if prev.mnemonic == "mov" and prev.op_str.startswith("r8d, "):
            try:
                imm = int(prev.op_str.split(",")[1].strip(), 0)
            except ValueError:
                return None
            return prev if imm == lit_len else None
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
    if ENCODING == "charmap" and len(charmap()) <= 0xE0:
        errors.append(
            f"charmap has {len(charmap())} entries; the two-byte form starts at 0xE0"
        )
    if ENCODING == "fontidx" and len(FONT_GLYPHS) != 269:
        errors.append(f"font glyph table has {len(FONT_GLYPHS)} entries, expected 269")
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

    Accepts three shapes: a list of dicts with ``addr``, ``text`` and ``sites``
    (the 0.9.0/0.9.1 plan); the ``{"plan": [...], "funcs": [...]}`` object
    ``work/raw/plan_from_dll.py`` writes for 0.9.2; or the flat table
    ``RVA<TAB>original text<TAB>site RVA<TAB>lea|inline``, one row per display
    site, several rows per string.
    """
    p = Path(path)
    if not p.is_file():
        raise SystemExit(
            f"ERROR caption plan not found: {p}\n"
            "      pass --plan with work/plan-0.9.2.json (built by\n"
            "      work/raw/plan_from_dll.py), or dump\n"
            "      RVA<TAB>text<TAB>site<TAB>kind and pass --plan that.tsv"
        )
    if p.suffix.lower() == ".json":
        doc = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            doc = doc["plan"]
        return {e["addr"]: e for e in doc}
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
    doc = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(doc, dict):
        return doc.get("funcs", [])
    return doc["funcs"]


# Positive filter for the caption-font cave, hashed over the *payload* bytes.
# It only matters for the charmap path; the readable 0.9.2 build is Latin and
# needs no cave, so the table lives with the rest of the kit data.
FILTER_JSON = Path(
    os.environ.get("METRO_FILTER093", str(KIT093 / "ru" / "caption_filter-0.9.3.json"))
)


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
        encoded_with="tools/apply_ru_092.py encode_text (encoding: %s)" % ENCODING,
        applies_to="MetroExodusVR.dll 0.9.2",
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


def check_encoding():
    """Fail loud on the one encoding that provably cannot work (A-0034)."""
    if ENCODING != "utf8":
        return
    print(
        "WARN --encoding utf8: a caption's bytes are glyph-table indices, and\n"
        "     every Cyrillic-capable font is charmap-baked (271 entries), so\n"
        "     UTF-8 indices select unrelated glyphs; in `arial` (identity, 95\n"
        "     inked cells) they select nothing at all.  Of the 193 kit rows,\n"
        "     utf-8 + arial renders 13 (the ASCII-only ones) and charmap +\n"
        "     menu renders 193 -- see tools/predict_captions.py --all.\n"
        "     Building anyway; use --encoding charmap for a readable DLL."
    )


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


def validator_immediate(md, data, pe, rva):
    """File offset of the ``0x5e`` immediate in a printable-ASCII gate.

    The recorded site is the first instruction of a short sequence::

        0f b6 01   movzx eax, byte [rcx]      (or 0f b6 08 for ecx)
        2c 20      sub   al, 0x20             (or 80 e9 20)
        3c 5e      cmp   al, 0x5e             (or 80 f9 5e)

    so the immediate has to be found by decoding, not assumed to be the first
    byte of the site.
    """
    off = pe.rva_to_off(rva)
    if off is None:
        return None
    for ins in md.disasm(data[off : off + 32], rva):
        if ins.mnemonic == "cmp" and len(ins.operands) == 2:
            op = ins.operands[1]
            if op.type == X86_OP_IMM and op.imm == 0x5E:
                return pe.rva_to_off(ins.address + ins.size - 1)
        if ins.address - rva > 0x18:
            break
    return None


def build_kind_flip_cave(cave_rva, back_rva, vp_slot_rva, displaced, font_aux=None):
    """Assemble the DllMain cave that points the EXE's kind-4 slot at kind 6.

    The cave runs at DLL load, before the mod builds any page, so every kind-4
    text object created afterwards is resolved by the byte-identity kind-6
    handler and the ``fontidx`` payloads render as Cyrillic.  It is idempotent
    (skips when the slot already holds kind 6), keeps DllBase in rbx because
    the VirtualProtect calls clobber every volatile register, and pushes
    rcx/rdx/r8 (DllMain's arguments) around the work.  The two displaced
    instructions are spliced verbatim at the cave entry and the cave jumps back
    to ``back_rva``.

    ``font_aux`` = (create_thread_slot, sleep_slot, font_mgr_rva) additionally
    spawns the L-0053 poller (see ``build_font_table_thread``) with the EXE base
    as its parameter; the poller body is appended after the jump back.
    """
    code = bytearray(displaced)
    labels = {}
    jmp_fix = []
    rip_fix = []
    thread_fix = []

    def emit(h):
        code.extend(bytes.fromhex(h))

    def label(name):
        labels[name] = len(code)

    def branch(op, name):
        emit(op)
        jmp_fix.append((len(code), name))
        code.extend(b"\0\0\0\0")

    def call_iat(rva):
        emit("ff15")
        rip_fix.append((len(code), rva))
        code.extend(b"\0\0\0\0")

    emit("53")  # push rbx (callee-saved: keeps DllBase across the VP calls)
    emit("51")  # push rcx (HINSTANCE)
    emit("52")  # push rdx (reason)
    emit("4150415141524153")  # push r8 r9 r10 r11
    # PEB -> Ldr -> InLoadOrderModuleList.Flink: the first module is the EXE
    emit("65488b042560000000")  # mov rax, gs:[0x60]
    emit("488b4018")  # mov rax, [rax+0x18]
    emit("488b4010")  # mov rax, [rax+0x10]
    emit("488b5830")  # mov rbx, [rax+0x30]  (DllBase; NOT r10: the calls clobber it)
    # The launcher (versions/<ver>/MetroExodusVR-launcher.exe) LoadLibrary's
    # this DLL too, and there the offsets below are unmapped: read
    # SizeOfImage out of the PE header and bail out unless the module is at
    # least as big as the game EXE, otherwise the cave faults in that process.
    emit("8b433c")  # mov eax, [rbx+0x3c]        (e_lfanew)
    emit("3d00040000")  # cmp eax, 0x400
    branch("0f87", "done")  # ja done
    emit("8b440350")  # mov eax, [rbx+rax+0x50]  (SizeOfImage)
    emit("3d78dcb800")  # cmp eax, 0xb8dc78
    branch("0f82", "done")  # jb done
    emit("0fb703")  # movzx eax, word [rbx]
    emit("3d4d5a0000")  # cmp eax, 'MZ'
    branch("0f85", "done")
    emit("81bb60dcb80029d6b800")  # cmp dword [rbx+0xb8dc60], 0xB8D629
    branch("0f85", "done")
    emit("81bb70dcb800e9dbb800")  # cmp dword [rbx+0xb8dc70], 0xB8DBE9
    branch("0f84", "done")
    emit("4883ec20")  # sub rsp, 0x20 (7 pushes + 0x20 keeps rsp 16-aligned)
    emit("488d8b70dcb800")  # lea rcx, [rbx+0xb8dc70]
    emit("ba04000000")  # mov edx, 4
    emit("41b840000000")  # mov r8d, PAGE_EXECUTE_READWRITE
    emit("4c8d0c24")  # lea r9, [rsp]
    call_iat(vp_slot_rva)
    emit("85c0")  # test eax, eax
    branch("0f84", "norestore")
    emit("c78370dcb800e9dbb800")  # mov dword [rbx+0xb8dc70], 0xB8DBE9
    emit("8b0424")  # mov eax, [rsp]     (old protect)
    emit("418bc0")  # mov r8d, eax
    emit("488d8b70dcb800")  # lea rcx, [rbx+0xb8dc70]
    emit("ba04000000")  # mov edx, 4
    emit("4c8d4c2408")  # lea r9, [rsp+8]
    call_iat(vp_slot_rva)
    label("norestore")
    emit("4883c420")  # add rsp, 0x20
    if font_aux:
        ct_slot, _sleep_slot, _mgr_rva = font_aux
        # CreateThread(0, 0, poller, exe_base, 0, 0): args 5/6 live at
        # [rsp+0x20]/[rsp+0x28], so the frame is 0x30 (7 pushes left rsp aligned).
        emit("4883ec30")  # sub rsp, 0x30
        emit("c744242000000000")  # mov dword [rsp+0x20], 0
        emit("c744242800000000")  # mov dword [rsp+0x28], 0
        emit("31c9")  # xor ecx, ecx
        emit("31d2")  # xor edx, edx
        emit("4c8d05")  # lea r8, [rip + poller]
        thread_fix.append(len(code))
        code.extend(b"\0\0\0\0")
        emit("4989d9")  # mov r9, rbx      (lpParameter = EXE base)
        call_iat(ct_slot)
        emit("4883c430")  # add rsp, 0x30
    label("done")
    emit("415b")  # pop r11
    emit("415a")  # pop r10
    emit("4159")  # pop r9
    emit("4158")  # pop r8
    emit("5a")  # pop rdx
    emit("59")  # pop rcx
    emit("5b")  # pop rbx
    off = len(code)
    code.append(0xE9)
    code += struct.pack("<i", back_rva - (cave_rva + off + 5))

    if font_aux:
        _ct_slot, sleep_slot, mgr_rva = font_aux
        thread_off = len(code)
        body = build_font_table_thread(
            cave_rva + thread_off, vp_slot_rva, sleep_slot, mgr_rva
        )
        code += body

    for at, name in jmp_fix:
        struct.pack_into("<i", code, at, cave_rva + labels[name] - (cave_rva + at + 4))
    for at, rva in rip_fix:
        struct.pack_into("<i", code, at, rva - (cave_rva + at + 4))
    for at in thread_fix:
        struct.pack_into("<i", code, at, (cave_rva + thread_off) - (cave_rva + at + 4))
    return bytes(code)


def build_font_table_thread(cave_rva, vp_slot_rva, sleep_slot_rva, mgr_rva):
    """Assemble the L-0053 poller body (a thread entry, rcx = EXE base).

    Waits up to ~60 s for the game to build the menu font table, then swaps two
    entries of it (``FONT_TABLE_PATCHES``) so a composed ASCII space stops
    drawing as '!' and the freed index 0xA1 renders '!'.  Every guard is checked
    before writing: the manager, the table pointer, ``count == 269`` and the
    stock codepoints at both indices, so a different build is left untouched.
    The thread exits on its own; it touches memory only (plus Sleep and
    VirtualProtect), so it is safe under the loader lock.
    """
    code = bytearray()
    labels = {}
    jmp_fix = []
    rip_fix = []

    def emit(h):
        code.extend(bytes.fromhex(h))

    def label(name):
        labels[name] = len(code)

    def branch(op, name):
        emit(op)
        jmp_fix.append((len(code), name))
        code.extend(b"\0\0\0\0")

    def call_iat(rva):
        emit("ff15")
        rip_fix.append((len(code), rva))
        code.extend(b"\0\0\0\0")

    emit("53")  # push rbx
    emit("56")  # push rsi
    emit("4154")  # push r12
    emit("4889cb")  # mov rbx, rcx        (EXE base)
    emit("be58020000")  # mov esi, 600   (600 * 100 ms = 60 s)
    label("tloop")
    emit("488b83")  # mov rax, [rbx + mgr_rva]
    code.extend(struct.pack("<i", mgr_rva))
    emit("4885c0")  # test rax, rax
    branch("0f84", "tsleep")
    emit("4c8b6008")  # mov r12, [rax+8]    (table)
    emit("4d85e4")  # test r12, r12
    branch("0f84", "tsleep")
    emit("0fb75012")  # movzx edx, word [rax+0x12]
    emit("81fa")  # cmp edx, FONT_TABLE_COUNT
    code.extend(struct.pack("<I", FONT_TABLE_COUNT))
    branch("0f85", "tsleep")
    for idx, old_cp, _new_cp in FONT_TABLE_PATCHES:
        emit("410fb78424")  # movzx eax, word [r12 + idx*2]
        code.extend(struct.pack("<I", idx * 2))
        emit("3d")  # cmp eax, old_cp
        code.extend(struct.pack("<I", old_cp))
        branch("0f85", "tsleep")
    emit("4883ec30")  # sub rsp, 0x30 (3 pushes: rsp was 8 mod 16, now aligned)
    emit("4c89e1")  # mov rcx, r12
    emit("ba")  # mov edx, FONT_TABLE_SIZE
    code.extend(struct.pack("<I", FONT_TABLE_SIZE))
    emit("41b804000000")  # mov r8d, PAGE_READWRITE
    emit("4c8d0c24")  # lea r9, [rsp]
    call_iat(vp_slot_rva)
    emit("85c0")  # test eax, eax
    branch("0f84", "tnopatch")
    for idx, _old_cp, new_cp in FONT_TABLE_PATCHES:
        emit("6641c78424")  # mov word [r12 + idx*2], new_cp
        code.extend(struct.pack("<I", idx * 2))
        code.extend(struct.pack("<H", new_cp))
    emit("448b0424")  # mov r8d, [rsp]     (old protect)
    emit("4c89e1")  # mov rcx, r12
    emit("ba")
    code.extend(struct.pack("<I", FONT_TABLE_SIZE))
    emit("4c8d4c2408")  # lea r9, [rsp+8]
    call_iat(vp_slot_rva)
    label("tnopatch")
    emit("4883c430")  # add rsp, 0x30
    branch("e9", "tout")
    label("tsleep")
    emit("b964000000")  # mov ecx, 100
    call_iat(sleep_slot_rva)
    emit("ffce")  # dec esi
    branch("0f85", "tloop")
    label("tout")
    emit("31c0")  # xor eax, eax
    emit("415c")  # pop r12
    emit("5e")  # pop rsi
    emit("5b")  # pop rbx
    emit("c3")  # ret

    for at, name in jmp_fix:
        struct.pack_into("<i", code, at, cave_rva + labels[name] - (cave_rva + at + 4))
    for at, rva in rip_fix:
        struct.pack_into("<i", code, at, rva - (cave_rva + at + 4))
    return bytes(code)


def value_glyph_table():
    """Glyph indices for the 15 characters a formatted number can contain."""
    table = bytearray()
    for cp in range(VALUE_TABLE_FIRST, VALUE_TABLE_LAST + 1):
        if cp not in FONT_GLYPHS:
            raise ValueError(f"value cave: U+{cp:04X} has no glyph in the menu font")
        table.append(FONT_GLYPHS.index(cp))
    return bytes(table)


def build_value_cave(cave_rva, second=False):
    """Assemble the ASCII -> glyph-index cave for the vformat numbers (L-0051).

    The cave is entered instead of a formatter ``call`` (``VALUE_SITE_RVA`` for
    the float rows of 0xB6C70, ``VALUE_SITE2_RVA`` for the percent lists of
    0xC1030).  It calls the formatter itself, then rewrites the bytes between
    the format string's first ``{`` and ``}`` in the result -- the substituted
    number, whose literal prefix and suffix keep their byte lengths -- through
    the glyph table.  Registers the caller keeps (rbx, rsi, rdi, rbp, r12,
    r14, r15) are untouched.
    """
    if second:
        template = VALUE_CAVE2_TEMPLATE
        disp_at = VALUE_CAVE2_CALL_DISP_AT
        ret_at = VALUE_CAVE2_RET_AT
        table_at = VALUE_CAVE2_TABLE_AT
    else:
        template = VALUE_CAVE_TEMPLATE
        disp_at = VALUE_CAVE_CALL_DISP_AT
        ret_at = VALUE_CAVE_RET_AT
        table_at = VALUE_CAVE_TABLE_AT
    blob = bytearray(template)
    assert blob[disp_at - 1] == 0xE8, "value cave: call opcode moved"
    assert blob[ret_at] == 0xC3, "value cave: ret moved"
    call_disp = FORMATTER_RVA - (cave_rva + disp_at + 4)
    struct.pack_into("<i", blob, disp_at, call_disp)
    table = value_glyph_table()
    blob[table_at : table_at + len(table)] = table
    return bytes(blob)


def build_value_cave3(cave_rva):
    """Assemble the frame-independent ASCII -> glyph cave (L-0052).

    Same glyph table and same "one replacement field" rule as the caves above,
    but the result string and the format string_view are taken from the ABI
    (rcx / rdx) instead of fixed frame offsets, so one blob serves every
    options-page builder.  See ``VALUE_SITES3_RVA``.
    """
    blob = bytearray(VALUE_CAVE3_TEMPLATE)
    assert blob[VALUE_CAVE3_CALL_DISP_AT - 1] == 0xE8, "value cave 3: call opcode moved"
    assert blob[VALUE_CAVE3_RET_AT] == 0xC3, "value cave 3: ret moved"
    call_disp = FORMATTER_RVA - (cave_rva + VALUE_CAVE3_CALL_DISP_AT + 4)
    struct.pack_into("<i", blob, VALUE_CAVE3_CALL_DISP_AT, call_disp)
    table = value_glyph_table()
    at = VALUE_CAVE3_TABLE_AT
    blob[at : at + len(table)] = table
    return bytes(blob)


def main():
    global ENCODING, MENU_LO, MENU_HI, UI2_TABLES, EXTRA_STRINGS, UI2_JSON
    global VALIDATORS, STRINGS_TSV
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verify", action="store_true", help="verify the patched output")
    ap.add_argument(
        "--strings",
        default=str(STRINGS_TSV),
        help="translation table: RVA<TAB>english<TAB>russian (0.9.2 RVAs)",
    )
    ap.add_argument(
        "--ui2",
        default=str(UI2_JSON),
        help="second-layer UI table for 0.9.2 (popups/options/hints/hintpages)",
    )
    ap.add_argument(
        "--plan",
        default=str(PLAN_093),
        help=(
            "caption display sites: JSON (a list, or the {plan, funcs} object "
            "plan_from_dll.py writes) or RVA/text/site/kind TSV"
        ),
    )
    ap.add_argument(
        "--funcs",
        default=str(PLAN_093),
        help="function boundaries; the plan JSON carries them, sites are window-decoded otherwise",
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
            "released image carries (opencode, L-0035: font_name did not change "
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
        choices=("fontidx", "charmap", "utf8", "cp1251"),
        default="fontidx",
        help=(
            "'fontidx' (default, L-0048) writes one byte per glyph -- the index "
            "of the character in the menu font's 269-entry table -- which the "
            "engine's kind-6 handler takes literally; the init cave in .ru "
            "flips the EXE's kind-4 slot to it.  'charmap' writes localization "
            "charmap indices and renders as Latin garbage on 0.9.3 (the kind-4 "
            "handler looks them up again); 'utf8' reproduces the L-0036 build, "
            "which came out empty; 'cp1251' rebuilds the 0.9.1 diagnostic"
        ),
    )
    ap.add_argument(
        "--no-kind-flip",
        dest="kind_flip",
        action="store_false",
        default=True,
        help=(
            "do not add the init cave that rewrites the game EXE's kind-4 text "
            "slot to kind 6.  Without it the fontidx payloads are read as ANSI "
            "codepoints and render as Latin garbage (L-0048)"
        ),
    )
    ap.add_argument(
        "--no-value-glyphs",
        dest="value_glyphs",
        action="store_false",
        default=True,
        help=(
            "do not add the L-0051 cave that rewrites the ASCII number the "
            "vformat look-alike returns into menu-font glyph indices; without "
            "it '{:g} Gr./s' shows 'gКш Gr./s' on 0.9.3"
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
            "4053555741564157 for the five-push prologue; by default they are "
            "read out of the DLL and checked"
        ),
    )
    ap.add_argument(
        "--allow-unknown-source",
        action="store_true",
        help="build from a DLL whose SHA-256 is not the pinned 0.9.2 release",
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
    ap.add_argument(
        "--fonts",
        action="store_true",
        help=(
            "replace the four embedded ImGui font resources (INFO_*) with the "
            "files in build/fonts, so the mod can draw Cyrillic; needed with "
            "--encoding utf8"
        ),
    )
    ap.add_argument("--no-fonts", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.experimental_cp1251:
        args.encoding = "cp1251"

    ENCODING = args.encoding
    check_encoding()
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
        print(f"      expected the 0.9.2 release   {SRC_SHA256}")
        print("      pass --allow-unknown-source only if you know why")
        return 1
    if got_sha != SRC_SHA256:
        print(f"WARN source sha256 {got_sha} is not the pinned 0.9.2 release")

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
                # Skip only when the encoded bytes equal the original ones.
                # With `fontidx` an unchanged Latin caption ("VR", "FSR",
                # "DLSS", "TAA", "1.00X") still needs rewriting: its ASCII
                # bytes are glyph indices after the kind flip, so "VR" (56 52)
                # came out as the glyphs 0x56/0x52, i.e. "ЕЯ" (L-0048).
                skip=(enc == orig.encode("latin-1", "replace")),
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
            imm = find_len_imm(wide, widx, len(e["orig"])) if widx is not None else None
            if imm is not None:
                e["lea_len"].append((imm.address + imm.size - 4, imm.address))

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
            "this release; the older bases would patch the wrong slots"
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

    # ---- the kind-4 -> kind-6 init cave --------------------------------------
    init_blob = b""
    init_rva = None
    init_site_off = None
    init_patch = None
    if args.kind_flip:
        entry = struct.unpack_from("<I", data, pe.opt + 16)[0]
        foff = pe.rva_to_off(entry)
        if entry != ENTRY_RVA:
            errors.append(f"DllMain is at {entry:#x}, the cave expects {ENTRY_RVA:#x}")
        if foff is None:
            errors.append(f"DllMain {entry:#x} is not mapped")
        else:
            have = bytes(data[foff : foff + len(ENTRY_DISPLACED)])
            if have != ENTRY_DISPLACED:
                errors.append(
                    f"DllMain prologue is {have.hex()}, the cave replays "
                    f"{ENTRY_DISPLACED.hex()}"
                )
        if pe.rva_to_off(EXE_VIRTUALPROTECT_IAT) is None:
            errors.append(
                f"VirtualProtect IAT slot {EXE_VIRTUALPROTECT_IAT:#x} is not mapped"
            )
        for name, slot in (
            ("CreateThread", DLL_CREATETHREAD_IAT),
            ("Sleep", DLL_SLEEP_IAT),
        ):
            if pe.rva_to_off(slot) is None:
                errors.append(f"{name} IAT slot {slot:#x} is not mapped")
        if not errors:
            pre = len(payload)
            pad = (-pre) % 16
            init_rva = new_va + pre + pad
            blob = build_kind_flip_cave(
                init_rva,
                entry + len(ENTRY_DISPLACED),
                EXE_VIRTUALPROTECT_IAT,
                ENTRY_DISPLACED,
                font_aux=(DLL_CREATETHREAD_IAT, DLL_SLEEP_IAT, EXE_FONT_MGR),
            )
            init_blob = b"\0" * pad + blob
            payload = payload + init_blob
            init_site_off = foff
            init_patch = (
                b"\xe9"
                + struct.pack("<i", init_rva - (entry + 5))
                + b"\x90" * (len(ENTRY_DISPLACED) - 5)
            )

    # ---- the ASCII -> glyph cave for formatted numbers (L-0051) --------------
    value_blob = b""
    value_cave_bytes = b""
    value_rva = None
    value_site_off = None
    value_patch = None
    if args.value_glyphs:
        foff = pe.rva_to_off(VALUE_SITE_RVA)
        want = b"\xe8" + struct.pack("<i", FORMATTER_RVA - (VALUE_SITE_RVA + 5))
        if foff is None:
            errors.append(f"value cave: call site {VALUE_SITE_RVA:#x} is not mapped")
        else:
            have = bytes(data[foff : foff + 5])
            if have != want:
                errors.append(
                    f"value cave: call at {VALUE_SITE_RVA:#x} is {have.hex()}, "
                    f"the cave expects {want.hex()}"
                )
        if pe.rva_to_off(VALUE_BACK_RVA) is None:
            errors.append(f"value cave: return site {VALUE_BACK_RVA:#x} is not mapped")
        for e in entries:
            if e["skip"]:
                continue
            n_open = e["ru"].count("{")
            n_close = e["ru"].count("}")
            if n_open > 1 or n_open != n_close:
                errors.append(
                    f"{e['addr']:#x}: {e['ru']!r} needs exactly one '{{...}}' "
                    "field for the value cave"
                )
        if not errors:
            try:
                value_glyph_table()
            except ValueError as exc:
                errors.append(str(exc))
        if not errors:
            pre = len(payload)
            pad = (-pre) % 16
            value_rva = new_va + pre + pad
            value_cave_bytes = build_value_cave(value_rva)
            value_blob = b"\0" * pad + value_cave_bytes
            payload = payload + value_blob
            value_site_off = foff
            value_patch = b"\xe8" + struct.pack("<i", value_rva - (VALUE_SITE_RVA + 5))

    # ---- second cave: the percent lists of 0xC1030 (deadzone rows) -----------
    value2_blob = b""
    value2_cave_bytes = b""
    value2_rva = None
    value2_site_off = None
    value2_patch = None
    if args.value_glyphs:
        foff2 = pe.rva_to_off(VALUE_SITE2_RVA)
        want2 = b"\xe8" + struct.pack("<i", FORMATTER_RVA - (VALUE_SITE2_RVA + 5))
        if foff2 is None:
            errors.append(f"value cave 2: call site {VALUE_SITE2_RVA:#x} is not mapped")
        else:
            have2 = bytes(data[foff2 : foff2 + 5])
            if have2 != want2:
                errors.append(
                    f"value cave 2: call at {VALUE_SITE2_RVA:#x} is {have2.hex()}, "
                    f"the cave expects {want2.hex()}"
                )
        if pe.rva_to_off(VALUE_BACK2_RVA) is None:
            errors.append(
                f"value cave 2: return site {VALUE_BACK2_RVA:#x} is not mapped"
            )
        if not errors:
            pre = len(payload)
            pad = (-pre) % 16
            value2_rva = new_va + pre + pad
            value2_cave_bytes = build_value_cave(value2_rva, second=True)
            value2_blob = b"\0" * pad + value2_cave_bytes
            payload = payload + value2_blob
            value2_site_off = foff2
            value2_patch = b"\xe8" + struct.pack(
                "<i", value2_rva - (VALUE_SITE2_RVA + 5)
            )

    # ---- third cave: remaining "{}%" choice lists (render scale) --------------
    value3_blob = b""
    value3_cave_bytes = b""
    value3_rva = None
    value3_site_patches = []
    if args.value_glyphs:
        for site in VALUE_SITES3_RVA:
            foff3 = pe.rva_to_off(site)
            want3 = b"\xe8" + struct.pack("<i", FORMATTER_RVA - (site + 5))
            if foff3 is None:
                errors.append(f"value cave 3: call site {site:#x} is not mapped")
            else:
                have3 = bytes(data[foff3 : foff3 + 5])
                if have3 != want3:
                    errors.append(
                        f"value cave 3: call at {site:#x} is {have3.hex()}, "
                        f"the cave expects {want3.hex()}"
                    )
        if not errors:
            pre = len(payload)
            pad = (-pre) % 16
            value3_rva = new_va + pre + pad
            value3_cave_bytes = build_value_cave3(value3_rva)
            value3_blob = b"\0" * pad + value3_cave_bytes
            payload = payload + value3_blob
            for site in VALUE_SITES3_RVA:
                value3_site_patches.append(
                    (
                        pe.rva_to_off(site),
                        b"\xe8" + struct.pack("<i", value3_rva - (site + 5)),
                    )
                )

    # ---- collect byte patches -------------------------------------------------
    patches = []
    if value_patch is not None:
        patches.append((value_site_off, value_patch))
    if value2_patch is not None:
        patches.append((value2_site_off, value2_patch))
    for off, p in value3_site_patches:
        patches.append((off, p))
    if init_patch is not None:
        patches.append((init_site_off, init_patch))
    if site_patch is not None:
        patches.append((pe.rva_to_off(ADDRS["setter"]), site_patch))
    for off, want, new in FMT_LITERAL_PATCHES:
        foff = pe.rva_to_off(off)
        if foff is None:
            errors.append(f"fmt literal {off:#x}: not mapped")
            continue
        if data[foff] != want:
            errors.append(
                f"fmt literal {off:#x}: expected {want:#04x}, found {data[foff]:#04x}"
            )
            continue
        patches.append((foff, bytes((new,))))
    for off, text in GLYPH_LITERAL_PATCHES:
        foff = pe.rva_to_off(off)
        if foff is None:
            errors.append(f"glyph literal {off:#x}: not mapped")
            continue
        have = bytes(data[foff : foff + len(text)])
        if have != text.encode("ascii"):
            errors.append(f"glyph literal {off:#x}: expected {text!r}, found {have!r}")
            continue
        patches.append((foff, bytes(FONT_GLYPHS.index(ord(c)) for c in text)))
    for off, want, ru, width in GLYPH_TEXT_PATCHES:
        foff = pe.rva_to_off(off)
        if foff is None:
            errors.append(f"glyph text {off:#x}: not mapped")
            continue
        have = bytes(data[foff : foff + len(want)])
        if have != want.encode("ascii"):
            errors.append(f"glyph text {off:#x}: expected {want!r}, found {have!r}")
            continue
        enc = encode_text(ru)
        if len(enc) > width:
            errors.append(
                f"glyph text {off:#x}: {ru!r} is {len(enc)} glyphs, "
                f"the field holds {width}"
            )
            continue
        patches.append((foff, enc + b"\x01" * (width - len(enc))))
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
        ioff = validator_immediate(md, data, pe, v)
        if ioff is None:
            errors.append(f"validator {v:#x}: no `cmp .., 0x5e` found")
            continue
        if bytes(data[ioff : ioff + 1]) != b"\x5e":
            errors.append(
                f"validator {v:#x}: unexpected byte {data[ioff : ioff + 1].hex()}"
            )
            continue
        patches.append((ioff, b"\xff"))

    # ---- embedded ImGui font resources ---------------------------------------
    # The mod draws its own UI with Dear ImGui and loads these four RCDATA fonts
    # by name (INFO_*).  The shipped blobs have no Cyrillic, so a UTF-8 caption
    # renders as empty space.  The replacement is written in place: it has to fit
    # the original resource size, the tail is zero padded and the data entry is
    # narrowed to the real font length, which is what SizeofResource hands to
    # AddFontFromMemoryTTF.
    fonts = []
    if args.fonts:
        fonts = collect_fonts(pe, data, errors)
        for f in fonts:
            rva, size = struct.unpack_from("<II", data, f["entry"])
            foff = pe.rva_to_off(rva)
            if foff is None:
                errors.append(f"font {f['name']}: resource RVA {rva:#x} not mapped")
                continue
            if len(f["blob"]) > size:
                errors.append(
                    f"font {f['name']}: {len(f['blob'])} bytes do not fit the "
                    f"{size} byte resource"
                )
                continue
            f["rva"] = rva
            f["orig_size"] = size
            patches.append((foff, f["blob"] + b"\0" * (size - len(f["blob"]))))
            patches.append((f["entry"] + 4, struct.pack("<I", len(f["blob"]))))

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
        for f in fonts:
            print(
                f"font {f['name']}: {len(f['blob'])} / {f['orig_size']} bytes, "
                f"RVA {f['rva']:#x}"
            )
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
        if init_rva is not None:
            print(
                f"kind flip cave: RVA {init_rva:#x}, DllMain {ENTRY_RVA:#x} "
                f"jump, {len(init_blob)} bytes, slot "
                f"exe+{EXE_KIND4_SLOT:#x} -> {EXE_KIND6_CODE:#x}"
            )
        else:
            print("kind flip cave: off")
        if value_rva is not None:
            print(
                f"value glyph cave: RVA {value_rva:#x}, call "
                f"{VALUE_SITE_RVA:#x} redirected, {len(value_blob)} bytes, "
                f"table {value_glyph_table().hex()}"
            )
        else:
            print("value glyph cave: off")
        if value2_rva is not None:
            print(
                f"value glyph cave 2: RVA {value2_rva:#x}, call "
                f"{VALUE_SITE2_RVA:#x} redirected, {len(value2_blob)} bytes "
                f"(percent lists of 0xC1030, deadzone rows)"
            )
        else:
            print("value glyph cave 2: off")
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
            fonts=fonts,
        )
        if rc == 0 and hook_rva is not None:
            rc = verify_hook(out_path, hook_rva, ADDRS["setter"], hook_dlen, md)
        if rc == 0 and init_rva is not None:
            rc = verify_kind_flip(out_path, init_rva, init_blob)
        caves = []
        if rc == 0 and value_rva is not None:
            caves.append(("value cave", value_rva, value_cave_bytes))
        if rc == 0 and value2_rva is not None:
            caves.append(("value cave 2", value2_rva, value2_cave_bytes))
        if rc == 0 and value3_rva is not None:
            caves.append(("value cave 3", value3_rva, value3_cave_bytes))
        if rc == 0 and caves:
            rc = verify_value_caves(out_path, caves)
    return rc


def verify_value_caves(path, caves):
    """Re-read the value caves out of the patched DLL (L-0051)."""
    data = Path(path).read_bytes()
    pe = PE(data)
    errors = []
    for label, rva, blob in caves:
        o = pe.rva_to_off(rva)
        if o is None:
            errors.append(f"{label}: cave {rva:#x} is not mapped")
            continue
        if bytes(pe.data[o : o + len(blob)]) != blob:
            errors.append(f"{label}: cave bytes differ from what was built")
            continue
        if pe.data[o + len(blob) - 16] != 0xC3:
            errors.append(f"{label}: cave does not end the loop with ret")
            continue
        print(f"{label} ok: cave {rva:#x}, {len(blob)} bytes, ret before table")
    for e in errors:
        print(f"VERIFY ERROR {e}")
    return 0 if not errors else 1


def verify_kind_flip(path, init_rva, init_blob):
    """Re-read the DllMain hook and the cave out of the patched DLL."""
    data = Path(path).read_bytes()
    pe = PE(data)
    errors = []
    o = pe.rva_to_off(ENTRY_RVA)
    if o is None or pe.data[o] != 0xE9:
        print("VERIFY ERROR kind flip: DllMain is not a jmp")
        return 1
    tgt = ENTRY_RVA + 5 + struct.unpack_from("<i", pe.data, o + 1)[0]
    if tgt != init_rva:
        errors.append(f"DllMain jumps to {tgt:#x}, the cave is {init_rva:#x}")
    if bytes(pe.data[o + 5 : o + len(ENTRY_DISPLACED)]) != b"\x90" * (
        len(ENTRY_DISPLACED) - 5
    ):
        errors.append("DllMain site is not padded with 0x90")
    o = pe.rva_to_off(init_rva)
    if o is None:
        errors.append(f"cave {init_rva:#x} is not mapped")
    elif bytes(pe.data[o : o + len(init_blob)]) != init_blob:
        errors.append("cave bytes differ from what was built")
    else:
        back = ENTRY_RVA + len(ENTRY_DISPLACED)
        # L-0053 appends the font-table poller after the jmp back, so the tail
        # jmp is no longer the last instruction: scan back for it instead.
        found = None
        for i in range(len(init_blob) - 5, -1, -1):
            if init_blob[i] != 0xE9:
                continue
            rel = struct.unpack_from("<i", init_blob, i + 1)[0]
            if init_rva + i + 5 + rel == back:
                found = i
                break
        if found is None:
            errors.append(f"cave has no jmp back to {back:#x}")
    for e in errors:
        print(f"VERIFY ERROR kind flip: {e}")
    if not errors:
        print(
            f"kind flip ok: DllMain {ENTRY_RVA:#x} -> cave {init_rva:#x} "
            f"({len(init_blob)} bytes) -> {ENTRY_RVA + len(ENTRY_DISPLACED):#x}"
        )
    return 0 if not errors else 1


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
):
    data = Path(path).read_bytes()
    pe = PE(data)
    errors = []

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
        o = pe.rva_to_off(f["rva"])
        if o is None:
            errors.append(f"font {f['name']}: resource data is not mapped")
            continue
        if bytes(pe.data[o : o + len(f["blob"])]) != f["blob"]:
            errors.append(f"font {f['name']}: bytes mismatch in .rsrc")
        if bytes(pe.data[o + len(f["blob"]) : o + f["orig_size"]]) != (
            b"\0" * (f["orig_size"] - len(f["blob"]))
        ):
            errors.append(f"font {f['name']}: padding after the font is not zero")
        rva, size = struct.unpack_from("<II", pe.data, f["entry"])
        if rva != f["rva"] or size != len(f["blob"]):
            errors.append(f"font {f['name']}: resource data entry not sized")

    if errors:
        for x in errors:
            print("VERIFY ERROR", x)
        return 1
    print(f"verify ok: {len(stub_plans)} stubs, {len(patches)} byte patches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
