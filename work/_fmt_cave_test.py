"""Emulate the value cave (L-0051) before flashing it into the game.

The cave replaces a formatter call; it calls the formatter and then rewrites the
substituted number's ASCII bytes into menu-font glyph indices.  This harness
fakes the formatter (it reproduces the tiny `{}` substitution in Python) and
checks the bytes the cave leaves in the result.

It models the *real* entry: the cave is reachable through a `call`, so its rsp
is 8 bytes below the caller's frame (`S-8`), and the formatter must see
`rsp % 16 == 8` when entered -- the first version of the cave shifted rsp by 8
and killed the game in `movaps [rsp+0x40]` at 0x22EF1.

Both known frames are covered: 0xB6C70 (float rows, "{:g} Gr./s") and 0xC1030
(percent option lists of the deadzone rows, "{}%").

    python work/_fmt_cave_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))

import apply_ru_093 as A  # noqa: E402
import _fmt_cave  # noqa: E402
import unicorn  # noqa: E402
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_PROT_ALL  # noqa: E402
from unicorn.x86_const import UC_X86_REG_RIP, UC_X86_REG_RSP  # noqa: E402

BASE = 0x180000000
CAVE_RVA = 0xC56340
FMT_RVA = 0x22DF0
HEAP = 0x180200000  # result buffer for the heap std::string branch
S_OFF = 0x8000  # caller rsp S inside the mapped stack

# Frame slot offsets relative to the caller's rsp (S).  Keep in sync with
# _fmt_cave.FRAMES: there the offsets are cave-relative, i.e. these + 8.
FRAMES = {
    0x00: {
        "fmt_ptr": 0x50,
        "fmt_len": 0x58,
        "buf": 0x60,
        "size": 0x70,
        "cap": 0x78,
        "back": 0xB6D33,  # or esi, 2 in 0xB6C70
    },
    0x10: {
        "fmt_ptr": 0x60,
        "fmt_len": 0x68,
        "buf": 0x70,
        "size": 0x80,
        "cap": 0x88,
        "back": 0xC1104,  # or esi, 2 in 0xC1030
    },
}


def encode(s: str) -> bytes:
    A.ENCODING = "fontidx"
    return A.encode_text(s)


def vformat(fmt: bytes, value: bytes) -> bytes:
    """The mod's formatter: literal bytes, the first {..} field replaced."""
    i = fmt.find(b"{")
    if i < 0:
        return fmt
    j = fmt.find(b"}", i)
    return fmt[:i] + value + fmt[j + 1 :]


def run(fmt: bytes, value: bytes, shift: int = 0x00) -> tuple[bytes, bool, bool, bool]:
    """Return (result bytes, heap branch, formatter aligned, stack balanced)."""
    fr = FRAMES[shift]
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(BASE, 0x3000000, UC_PROT_ALL)
    uc.mem_write(BASE + CAVE_RVA, A.build_value_cave(CAVE_RVA, second=shift != 0))
    fmt_va = BASE + 0xC56400
    uc.mem_write(fmt_va, fmt)

    s = BASE + S_OFF  # caller rsp at the original call site
    uc.mem_write(s - 8, (BASE + fr["back"]).to_bytes(8, "little"))
    uc.mem_write(s + fr["fmt_ptr"], fmt_va.to_bytes(8, "little"))
    uc.mem_write(s + fr["fmt_len"], len(fmt).to_bytes(8, "little"))

    result = vformat(fmt, value)
    on_heap = len(result) > 0xF
    seen = {"aligned": None}

    def hook(uc_, address, _size, _data):
        if address != BASE + FMT_RVA:
            return
        rsp = uc_.reg_read(UC_X86_REG_RSP)
        seen["aligned"] = rsp % 16 == 8
        buf = HEAP if on_heap else s + fr["buf"]
        if on_heap:
            uc_.mem_write(HEAP, result + b"\0")
            uc_.mem_write(s + fr["buf"], buf.to_bytes(8, "little"))
        else:
            uc_.mem_write(s + fr["buf"], result + b"\0")
        uc_.mem_write(s + fr["size"], len(result).to_bytes(8, "little"))
        uc_.mem_write(s + fr["cap"], (0x1F if on_heap else 0xF).to_bytes(8, "little"))
        ret = int.from_bytes(uc_.mem_read(rsp, 8), "little")
        uc_.reg_write(UC_X86_REG_RIP, ret)
        uc_.reg_write(UC_X86_REG_RSP, rsp + 8)

    uc.hook_add(unicorn.UC_HOOK_CODE, hook)
    uc.reg_write(UC_X86_REG_RSP, s - 8)
    try:
        uc.emu_start(BASE + CAVE_RVA, BASE + fr["back"], count=400)
    except unicorn.UcError as exc:  # pragma: no cover
        raise SystemExit(f"emulation failed for {fmt!r}/{value!r}: {exc}")

    ptr = HEAP if on_heap else s + fr["buf"]
    size = int.from_bytes(uc.mem_read(s + fr["size"], 8), "little")
    # The cave must hand the continuation exactly the rsp the original `call`
    # would have left: the return address it pushed has to be gone.  A `jmp`
    # back instead of `ret` left it 8 bytes low and the caller's cookie check
    # read the wrong slot (0xC0000409, fast fail 2).
    balanced = uc.reg_read(UC_X86_REG_RSP) == s
    return bytes(uc.mem_read(ptr, size)), on_heap, bool(seen["aligned"]), balanced


def show(encoded: bytes) -> str:
    return "".join(
        chr(A.FONT_GLYPHS[b]) if b < len(A.FONT_GLYPHS) else "?" for b in encoded
    )


CASES = [
    # frame 0x00 -- 0xB6C70, "{:g} Gr./s" and friends
    ("{:g} Гр./с", b"240", 0x00),
    ("{} СМ", b"12", 0x00),
    ("{}% (РЕКОМЕНД.)", b"100", 0x00),
    ("+{} СМ", b"7", 0x00),
    ("{} Гр.", b"3", 0x00),
    ("{:.2f} М", b"1.25", 0x00),
    ("{:g} Гр.", b"45", 0x00),
    ("{:+.0f} Гр.", b"-8", 0x00),
    ("{:.1f} М", b"0.4", 0x00),
    # frame 0x10 -- 0xC1030, the "{}%" option lists of the deadzone rows
    ("{}%", b"0", 0x10),
    ("{}%", b"5", 0x10),
    ("{}%", b"10", 0x10),
    ("{}%", b"30", 0x10),
    ("{}%", b"100", 0x10),
]

EMPTY_CASES = [
    ("ПЛАВНО", b"", 0x00),
    ("{:g} Гр./с", b"", 0x00),
    ("{}%", b"", 0x10),
]


def main() -> int:
    ok = True
    for ru, value, shift in CASES:
        fmt = encode(ru)
        out, heap, aligned, balanced = run(fmt, value, shift)
        want = vformat(fmt, bytes(A.value_glyph_table()[c - 0x2B] for c in value))
        good = out == want and aligned and balanced
        ok &= good
        print(
            f"{'ok ' if good else 'BAD'} [{shift:#04x}] {ru!r} value={value!r} "
            f"heap={heap} aligned={aligned} balanced={balanced} -> {out.hex()}  "
            f"{show(out)!r}"
        )
        if not good:
            print(f"    want {want.hex()} {show(want)!r}")

    for ru, value, shift in EMPTY_CASES:
        fmt = encode(ru)
        out, _heap, aligned, balanced = run(fmt, value, shift)
        good = out == vformat(fmt, value) and aligned and balanced
        ok &= good
        print(
            f"{'ok ' if good else 'BAD'} [{shift:#04x}] {ru!r} value={value!r} "
            f"balanced={balanced} -> {show(out)!r}"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
