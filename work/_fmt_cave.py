"""Assemble the value-field digit cave (L-0051).

The mod builds every numeric row with a std::vformat-like helper at 0xB6C70:
it copies the format string and calls 0x22DF0, which returns a **plain ASCII**
string.  The menu font is addressed by glyph index (see work/font093.json), so
ASCII digits come out as random Cyrillic letters -- "240" drew as "gКш".

This cave is entered instead of a formatter ``call``.  It calls the formatter
itself and then rewrites the substituted number (and only the text between the
format field's braces) into glyph indices, using the 15-entry table for
``+ , - . / 0..9`` (0x2B..0x39).

Two call sites use it so far, each with its own frame layout (``S`` is rsp at
the original call site):

    0xB6D2E in 0xB6C70  -- float rows ("{:g} Gr./s")
        [S+0x50] format string pointer, [S+0x58] length
        [S+0x60] result std::string (size at +0x70, cap at +0x78)
    0xC10FF in 0xC1030  -- percent option lists ("{}%", the deadzone rows)
        [S+0x60] format string pointer, [S+0x68] length
        [S+0x70] result std::string (size at +0x80, cap at +0x88)

0xC1030 is called only from 0xBB05A and 0xBB0A2 (MOVE/TURN STICK DEADZONE),
and it hard-codes the ``{}%`` format at 0xC1092, so one instance covers both
rows; its three float entries per row are the option list itself.

The cave is entered through a ``call``, so its own rsp is ``S-8``; every slot
below is read with the +8 shift.  It also has to keep the ABI: the nested
``call`` must not hand the formatter a rsp that is 16-aligned (the formatter
does ``movaps [rsp+0x40]`` and dies with 0xC0000005 if it is), hence the
``sub rsp, 8`` / ``add rsp, 8`` pair around it.

The cave leaves through ``ret``, not ``jmp``: the ``call`` that used to reach
the formatter pushed the return address to 0xB6D33, so ``ret`` both continues
there and drops it.  A ``jmp`` would leave rsp 8 bytes low, the rest of
0xB6C70 would then run shifted, and its epilogue would compare the stack
cookie from the wrong slot -- the game dies with 0xC0000409 (fast fail 2,
stack cookie check).  That was the third crash of this task.

    python work/_fmt_cave.py            # print + check the blob
"""

from __future__ import annotations

import keystone
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

CALL_FMT_RVA = 0xB6D2E  # call 0x180022DF0 inside 0xB6C70
CALL_FMT_END = 0xB6D33  # right after the call: orig esi, 2
FORMATTER_RVA = 0x22DF0

# Slot offsets are relative to the cave's own rsp, which is ``S - 8`` because the
# patched ``call`` pushed a return address.  The same logic serves every builder
# that formats a single field, but each builder keeps the format string_view and
# the result std::string at its own frame offsets (see the module docstring).
# Values below already include the +8 shift, i.e. they are (frame offset + 8).
FRAMES = {
    0x00: {"fmt_ptr": 0x58, "fmt_len": 0x60, "buf": 0x68, "cap": 0x80, "size": 0x78},
    0x10: {"fmt_ptr": 0x68, "fmt_len": 0x70, "buf": 0x78, "cap": 0x90, "size": 0x88},
}

ASM_TEMPLATE = r"""
    sub   rsp, 8
    .byte 0xe8, 0, 0, 0, 0
    add   rsp, 8
    mov   r8,  qword ptr [rsp + {fmt_ptr:#x}]
    mov   r9,  qword ptr [rsp + {fmt_len:#x}]
    mov   r10d, 0
find_open:
    cmp   r10, r9
    jae   done
    cmp   byte ptr [r8 + r10], 0x7b
    je    found
    inc   r10
    jmp   find_open
found:
    mov   r11, r10
find_close:
    inc   r11
    cmp   r11, r9
    jae   done
    cmp   byte ptr [r8 + r11], 0x7d
    jne   find_close
    sub   r9,  r11
    dec   r9
    lea   rdx, [rsp + {buf:#x}]
    cmp   qword ptr [rsp + {cap:#x}], 0x10
    jb    have_ptr
    mov   rdx, qword ptr [rsp + {buf:#x}]
have_ptr:
    mov   rax, qword ptr [rsp + {size:#x}]
    sub   rax, r9
    cmp   rax, r10
    jbe   done
    lea   r11, [rip + tbl]
loop:
    movzx ecx, byte ptr [rdx + r10]
    sub   ecx, 0x2b
    cmp   ecx, 0x0e
    ja    next
    movzx ecx, byte ptr [r11 + rcx]
    mov   byte ptr [rdx + r10], cl
next:
    inc   r10
    cmp   r10, rax
    jb    loop
done:
    ret
tbl:
    .byte 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
"""


def asm_text(slot_shift: int = 0) -> str:
    """The cave source with the frame slots for ``slot_shift``."""
    return ASM_TEMPLATE.format(**FRAMES[slot_shift])


TABLE_FIRST = 0x2B  # '+'
TABLE_LAST = 0x39  # '9'


def assemble(cave_rva: int, table: bytes, slot_shift: int = 0) -> bytes:
    """Return the cave blob for ``cave_rva``; ``table`` is the glyph indices."""
    assert len(table) == TABLE_LAST - TABLE_FIRST + 1, len(table)
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_64)
    enc, _ = ks.asm(asm_text(slot_shift), 0x180000000 + cave_rva)
    blob = bytearray(enc)

    disp = FORMATTER_RVA - (cave_rva + 9)
    assert blob[4] == 0xE8, blob[:8].hex()
    blob[5:9] = disp.to_bytes(4, "little", signed=True)

    assert blob[-len(table) - 1] == 0xC3, "value cave: ret missing"
    blob[-len(table) :] = table
    return bytes(blob)


def template(
    table_size: int = TABLE_LAST - TABLE_FIRST + 1, slot_shift: int = 0
) -> tuple[bytes, int, int]:
    """Cave with the call displacement zeroed: (blob, call_at, ret_at)."""
    blob = bytearray(
        assemble(0xC57000, bytes(range(table_size)), slot_shift)
    )  # relative only
    assert blob[-table_size - 1] == 0xC3
    out = bytearray(blob)
    out[5:9] = b"\0" * 4
    return bytes(out), 5, len(out) - table_size - 1


def check(blob: bytes, cave_rva: int, slot_shift: int = 0) -> None:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    base = 0x180000000 + cave_rva
    for i in md.disasm(blob, base):
        note = ""
        if i.mnemonic == "call":
            note = "  -> fmt %#x" % (0x180000000 + FORMATTER_RVA)
        elif i.mnemonic == "ret":
            note = "  -> back to caller (frame %#x)" % slot_shift
        elif i.mnemonic == "lea" and "rip" in i.op_str:
            note = "  -> glyph table"
        print("  %#x  %-8s %-40s%s" % (i.address, i.mnemonic, i.op_str, note))


if __name__ == "__main__":
    CAVE = 0xC57000
    glyphs = [
        0x9A,
        0x0E,
        0x3A,
        0x08,
        0x8A,
        0x5C,
        0x57,
        0x42,
        0x6C,
        0x72,
        0x7C,
        0x76,
        0x7F,
        0x78,
        0x81,
    ]
    for shift in (0x00, 0x10):
        b = assemble(CAVE, bytes(glyphs), shift)
        print("== frame %#x: blob %d bytes" % (shift, len(b)))
        check(b, CAVE, shift)
        tb = bytearray(b)
        tb[5:9] = b"\0" * 4
        print("TEMPLATE[%#x] = %s" % (shift, tb.hex()))
        print(
            "call_disp_at=%d ret_at=%d table_at=%d"
            % (5, len(tb) - 15 - 1, len(tb) - 15)
        )
