"""Emulate the third value cave (L-0052), the frame-independent one.

Cave 3 is entered instead of a formatter ``call`` but reads the result string
from ``rcx`` and the format string_view from ``rdx`` (the mod's usual call
shape), so it needs no per-frame offsets.  This harness fakes the formatter,
writes an MSVC ``std::string`` (inline buffer at +0, size +0x10, capacity
+0x18) through ``rcx``, and checks what the cave leaves behind.

    python work/_fmt_cave3_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))

import apply_ru_093 as A  # noqa: E402
import unicorn  # noqa: E402
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_PROT_ALL  # noqa: E402
from unicorn.x86_const import (
    UC_X86_REG_RCX,
    UC_X86_REG_RDX,
    UC_X86_REG_RIP,
    UC_X86_REG_RSP,
)  # noqa: E402

BASE = 0x180000000
CAVE_RVA = 0xC56480
FMT_RVA = 0x22DF0
HEAP = 0x180200000
STOP = BASE + 0x4000
S_OFF = 0x8000  # caller rsp at the original call site
OUT_OFF = 0x400  # result std::string inside the stack
SV_OFF = 0x500  # format std::string_view inside the stack


def encode(s: str) -> bytes:
    A.ENCODING = "fontidx"
    return A.encode_text(s)


def vformat(fmt: bytes, value: bytes) -> bytes:
    i = fmt.find(b"{")
    if i < 0:
        return fmt
    j = fmt.find(b"}", i)
    return fmt[:i] + value + fmt[j + 1 :]


def run(fmt: bytes, value: bytes) -> tuple[bytes, bool, bool, int]:
    """Return (result bytes, heap branch, formatter aligned, stack delta)."""
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(BASE, 0x3000000, UC_PROT_ALL)
    uc.mem_write(BASE + CAVE_RVA, A.build_value_cave3(CAVE_RVA))

    fmt_va = BASE + 0xC56800
    uc.mem_write(fmt_va, fmt)

    s = BASE + S_OFF
    out = s + OUT_OFF
    sv = s + SV_OFF
    uc.mem_write(s - 8, STOP.to_bytes(8, "little"))
    uc.mem_write(sv, fmt_va.to_bytes(8, "little"))
    uc.mem_write(sv + 8, len(fmt).to_bytes(8, "little"))

    result = vformat(fmt, value)
    on_heap = len(result) > 0xF
    seen = {"aligned": None}

    def hook(uc_, address, _size, _data):
        if address != BASE + FMT_RVA:
            return
        rsp = uc_.reg_read(UC_X86_REG_RSP)
        seen["aligned"] = rsp % 16 == 8
        dst = uc_.reg_read(UC_X86_REG_RCX)
        if on_heap:
            uc_.mem_write(HEAP, result + b"\0")
            uc_.mem_write(dst, HEAP.to_bytes(8, "little"))
        else:
            uc_.mem_write(dst, result + b"\0" * (0x10 - len(result)))
        uc_.mem_write(dst + 0x10, len(result).to_bytes(8, "little"))
        uc_.mem_write(dst + 0x18, (0x1F if on_heap else 0xF).to_bytes(8, "little"))
        ret = int.from_bytes(uc_.mem_read(rsp, 8), "little")
        uc_.reg_write(UC_X86_REG_RIP, ret)
        uc_.reg_write(UC_X86_REG_RSP, rsp + 8)

    uc.hook_add(unicorn.UC_HOOK_CODE, hook)
    uc.reg_write(UC_X86_REG_RSP, s - 8)
    uc.reg_write(UC_X86_REG_RCX, out)
    uc.reg_write(UC_X86_REG_RDX, sv)
    try:
        uc.emu_start(BASE + CAVE_RVA, STOP, count=600)
    except unicorn.UcError as exc:  # pragma: no cover
        raise SystemExit(f"emulation failed for {fmt!r}/{value!r}: {exc}")

    size = int.from_bytes(uc.mem_read(out + 0x10, 8), "little")
    ptr = HEAP if on_heap else out
    delta = uc.reg_read(UC_X86_REG_RSP) - s
    return bytes(uc.mem_read(ptr, size)), on_heap, bool(seen["aligned"]), delta


def show(encoded: bytes) -> str:
    return "".join(
        chr(A.FONT_GLYPHS[b]) if b < len(A.FONT_GLYPHS) else "?" for b in encoded
    )


CASES = [
    ("{}%", b"0"),
    ("{}%", b"5"),
    ("{}%", b"10"),
    ("{}%", b"30"),
    ("{}%", b"70"),
    ("{}%", b"100"),
    ("{}%", b"100000"),  # heap branch
    ("{} СМ", b"12"),
    ("{:g} Гр./с", b"240"),
    ("{:+.0f} Гр.", b"-8"),
    ("{:.2f} М", b"1.25"),
]

# Formats the cave must leave alone: more than one field, or a substituted value
# that is not a plain number (already glyph-encoded text).  The heuristic has a
# blind spot: one glyph whose index happens to be 0x2b..0x39 ('С' = 0x37) looks
# exactly like an ASCII number and would be converted again -- that is why the
# cave is only aimed at the numeric option lists.
UNTOUCHED = [
    ("{}: {}", b"70"),
    ("{} / {}", b"70"),
    (
        "{}",
        encode("ДА"),
    ),
]


def main() -> int:
    ok = True
    for ru, value in CASES:
        fmt = encode(ru)
        out, heap, aligned, delta = run(fmt, value)
        want = vformat(fmt, bytes(A.value_glyph_table()[c - 0x2B] for c in value))
        good = out == want and aligned and delta == 0
        ok &= good
        print(
            f"{'ok ' if good else 'BAD'} {ru!r} value={value!r} heap={heap} "
            f"aligned={aligned} delta={delta} -> {show(out)!r}"
        )
        if not good:
            print(f"    want {show(want)!r}")

    for ru, value in UNTOUCHED:
        fmt = encode(ru)
        out, _heap, aligned, delta = run(fmt, value)
        want = vformat(fmt, value)
        good = out == want and aligned and delta == 0
        ok &= good
        print(f"{'ok ' if good else 'BAD'} untouched {ru!r} -> {show(out)!r}")
        if not good:
            print(f"    want {show(want)!r}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
