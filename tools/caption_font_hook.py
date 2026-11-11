#!/usr/bin/env python3
"""Caption-font code cave for the MetroExodusVR control-property setter.

The mod sets the ``caption`` property of a control but never sets a font, so
the engine draws every caption with its default ``arial``, which has ASCII
glyphs only (A-0029 section 4.3).  This module builds the code cave that is
installed over the first bytes of the generic property setter

    bool set(control* rcx, string_view* rdx /* name */, string_view* r8 /* value */)

and, on every caption that belongs to our translation (positive FNV-1a filter,
``ru/caption_filter.json``), additionally writes the font property.

It is version-parameterised: 0.9.0 and 0.9.1 differ only in the setter RVA and
in how many bytes of its prologue the 5-byte ``jmp`` displaces.

    version   setter RVA   displaced prologue                bytes
    0.9.0     0x9BC70      push rbx, rbp, rdi, r14           6
    0.9.1     0x9F0D0      push rbx, rbp, rdi, r14, r15      8   (L-0034)

Which property to write -- the whole point of L-0034 -- is settled by two runs:

  * L-0026 (0.9.0, bag7, ``font_name``):  the record exists on **206 of 209**
    matched controls and the setter returned success for all of them;
  * L-0029 (0.9.0, bag9, ``override_font_name``): **no** such record exists on
    any matched control, ``found_any=0``, ``set_ok_any=0``.  The setter only
    writes into a record it finds in the bag, it never creates one, so that arm
    cannot work on these controls.

``font_name`` is therefore the default.  ``override_font_name`` stays available
through ``--caption-prop`` for a control class that does carry the record.

Marker fields added by the write arm (the marker is MARKER_SIZE bytes, so these are
far past the last field of bag15 at +0x1C6C):

    +0x1C70  set_calls   how many times we called the setter
    +0x1C74  set_ok      how many times it returned non-zero
    +0x1C78  set_fail    how many times it returned zero
    +0x1C7C  set_last    the raw ``al`` of the last call

``set_ok`` is counted independently of the old ``found`` flag on purpose:
L-0029 section 2 showed that aggregating ``set_ok`` inside the ``found`` branch
hides exactly the case we need to see.

Standalone use (no DLL needed):

    python tools/caption_font_hook.py --self-test
    python tools/caption_font_hook.py --dump-asm work/cave_091.asm
"""

import argparse
import json
import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_RIP

ROOT = Path(__file__).resolve().parent.parent

SETPROP_RVA_090 = 0x9BC70
SETPROP_RVA_091 = 0x9F0D0

# What the 5-byte `jmp rel32` overwrites at the setter entry.  0.9.1 has one
# more callee-saved register than 0.9.0 (L-0034: `push rbx/rbp/rdi/r14/r15`),
# so the displacement is 8 bytes there and 6 bytes in 0.9.0.  Verified against
# the real DLL by ``check_displaced``/``derive_displaced`` before a build.
DEFAULT_DISPLACED_090 = b"\x40\x53\x55\x57\x41\x56"
DEFAULT_DISPLACED_091 = b"\x40\x53\x55\x57\x41\x56\x41\x57"

MARKER_SIZE = 0x2400

# --- L-0035: where a font ref becomes an object, and what to dump ------------
# Offsets below 0x1D00 are taken by the existing marker fields (see the map at
# the top of this file); the dumps live above them.  The marker grew from
# 0x2000 to 0x2400 bytes for them.
EXE_FONTS_INLINE = 0x1733240  # L-0035: the `Fonts` array quoted in the runlog
EXE_FONTS_PTR = 0x1733260  # what the swap block writes through
EXE_BANKS = 0x175F140  # 32 qword bank bases (work/resolve_fonts.py)

CTL_CAP_DUMP = 0x1D00  # 0x100 bytes of the matched caption control
CTL_VAL_DUMP = 0x1E00  # 0x100 bytes of the first local_text control
FONTS_INLINE = 0x1F00  # 0x20 bytes: [exe+0x1733240]
FONTS_DEREF = 0x1F20  # 0x20 bytes: *[exe+0x1733260]
FONTS_PTR = 0x1F40  # qword: the pointer [exe+0x1733260] itself
BANKS = 0x1F80  # 0x100 bytes: the 32 bank bases
NODE_REC = 0x2080  # 4 x 0x40: {node@0, refcount@8, nlen@0xc, name[32]@0x10}
SUBST_CTLS = 0x2180  # controls that reached the substitution block
SUBST_FOUND = 0x2184  # dwords equal to the arial ref
SUBST_FIRST = 0x2188  # lowest offset that matched (-1 = none)
SUBST_LAST = 0x218C  # highest offset that matched
SUBST_WRITES = 0x2190  # dwords actually stored
SUBST_NOREF = 0x2194  # passes where the arial or menu ref was still empty
SWAP_FIXES = 0x2198  # sticky swap: passes that really changed the slot
STATIC_DONE = 0x219C  # the one-off registry dump has run
CTL_FLAGS = 0x21A0  # bit0 caption control dumped, bit1 local_text dumped
WRITE_CALLS = 0x1C70
WRITE_OK = 0x1C74
WRITE_FAIL = 0x1C78
WRITE_LAST = 0x1C7C

CAPTION_FILTER = ROOT / "ru" / "caption_filter.json"

# pop opcode for rax..rdi; r8..r15 need a 0x41 REX.B prefix
_POP64 = {
    "rax": 0x58,
    "rcx": 0x59,
    "rdx": 0x5A,
    "rbx": 0x5B,
    "rsp": 0x5C,
    "rbp": 0x5D,
    "rsi": 0x5E,
    "rdi": 0x5F,
}


def _disasm(b, addr=0):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    return list(md.disasm(bytes(b), addr))


def check_displaced(b):
    """Refuse a displaced prologue we cannot safely replay.

    The bytes are executed twice: once by us (epilogue, before ``jmp
    site+dlen``) and once by our write arm (before calling the setter body).
    Anything other than plain register pushes -- a RIP-relative operand, a
    branch, a ``rsp``-touching instruction -- would break one of the two.
    """
    ins = _disasm(b)
    if not (5 <= len(b) <= 8):
        raise SystemExit(
            f"caption_font_hook: displaced prologue is {len(b)} bytes, "
            "expected 5..8 (a jmp rel32 plus padding)"
        )
    if sum(i.size for i in ins) != len(b) or not ins:
        raise SystemExit(
            "caption_font_hook: displaced prologue does not disassemble "
            f"cleanly: {b.hex()}"
        )
    for i in ins:
        if i.mnemonic != "push":
            raise SystemExit(
                "caption_font_hook: displaced byte is "
                f"{i.mnemonic} {i.op_str}, only `push reg` can be replayed"
            )
        ops = i.operands
        if len(ops) != 1 or ops[0].type != X86_OP_REG:
            raise SystemExit(
                f"caption_font_hook: `{i.mnemonic} {i.op_str}` is not a register push"
            )
        if i.reg_name(ops[0].reg) == "rsp":
            raise SystemExit("caption_font_hook: cannot replay `push rsp`")
    return ins


def pops_for(b):
    """The pops that undo ``b``, in reverse order (``pop r15..rbx``)."""
    ins = check_displaced(b)
    out = bytearray()
    for i in reversed(ins):
        name = i.reg_name(i.operands[0].reg)
        if name in _POP64:
            out.append(_POP64[name])
        elif name.startswith("r") and name[1:].isdigit() and 8 <= int(name[1:]) <= 15:
            out += b"\x41" + bytes([0x58 + int(name[1:]) - 8])
        else:
            raise SystemExit(f"caption_font_hook: no pop encoding for {name}")
    return bytes(out)


def derive_displaced(data, file_off, max_len=8):
    """Read the displaced prologue straight out of the DLL.

    Preferred over a hardcoded constant: disassemble the setter entry and take
    the whole run of leading ``push reg`` instructions, up to ``max_len``.
    The run has to cover the *complete* prologue: the write arm replays it and
    calls the body behind it, so cutting it in the middle (0.9.1: 6 of 8 bytes
    = 4 of 5 pushes) left the body 8 bytes off its 16-byte stack alignment and
    crashed inside the setter on the first caption write (bag15 never called
    the setter, so this path was new in L-0034).  A caller that passes
    ``--site-head`` bypasses this.
    """
    ins = _disasm(data[file_off : file_off + max_len + 16], 0)
    total = 0
    for i in ins:
        if i.mnemonic != "push" or total + i.size > max_len:
            break
        total += i.size
    if total < 5:
        raise SystemExit(
            f"caption_font_hook: cannot displace {total} bytes at the setter "
            f"(need 5..{max_len}); pass --site-head with the real bytes"
        )
    b = bytes(data[file_off : file_off + total])
    check_displaced(b)
    return b


def sib_byte(scale, index, base):
    """Encode a SIB byte; refuse a scale that would silently break a stride.

    A-0028 §6: bag13 wrote ``mov [rcx+r9+0x1a34], r10d`` (scale 1) for a
    dword array and the dump still looked plausible.  Keep the check here so
    the same typo cannot cost another run.
    """
    if scale not in (1, 2, 4, 8):
        raise SystemExit(f"apply_ru: bad SIB scale {scale}, expected 1/2/4/8")
    if (index & 7) == 4:
        raise SystemExit("apply_ru: SIB index rsp/r12 (field 4) is not encodable")
    if base == 5:
        raise SystemExit("apply_ru: SIB base rbp/r13 (field 5) is not encodable")
    return ((scale.bit_length() - 1) << 6) | ((index & 7) << 3) | (base & 7)


def _patch32(b, pos, target):
    """Patch the rel32 of a ``0f 8x`` near jump at ``pos``."""
    struct.pack_into("<i", b, pos + 2, target - (pos + 6))


def _patchjmp32(b, pos, target):
    """Patch the rel32 of an ``e9`` near jump at ``pos``."""
    struct.pack_into("<i", b, pos + 1, target - (pos + 5))


def emit_font_scan(out_len, out_bytes, base, fixups):
    """Read-only scan of the control's bag for the ``font_name`` record.

    ``rbx`` = control, ``rcx`` = marker on entry/exit.  Writes ``0xFFFFFFFF``
    to ``out_len`` when no record exists, otherwise the record's value length
    and its first 16 value bytes at ``out_bytes``.  Never writes to the game
    object (A-0028 wants this probe to be safe to run before any change).

    ``base`` is the current ``len(code)``; RIP fixups are appended with it.
    """
    b = bytearray()

    def mark():
        fixups.append((base + len(b) - 4, b"marker"))

    def lit():
        fixups.append((base + len(b) - 4, b"font_name_lit"))

    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    b += b"\xc7\x81" + struct.pack("<I", out_len) + b"\xff\xff\xff\xff"
    # `mov qword [reg+disp32], imm32` is 11 bytes: opcode + disp32 + imm32.
    # Eight zero bytes here made the CPU execute `00 00` (`add [rax], al`)
    # right after it; that is the VR crash "write to 0000000000000065".
    b += b"\x48\xc7\x81" + struct.pack("<I", out_bytes) + b"\0" * 4
    b += b"\x48\xc7\x81" + struct.pack("<I", out_bytes + 8) + b"\0" * 4
    b += b"\x4c\x8d\x15\0\0\0\0"  # lea r10, [rip+font_name_lit]
    lit()
    b += b"\x48\x8b\x53\x38"  # mov rdx, [rbx+0x38] (bag begin)
    b += b"\x4c\x8b\x4b\x40"  # mov r9, [rbx+0x40]  (bag end)
    loop = len(b)
    b += b"\x4c\x39\xca"  # cmp rdx, r9
    j_done = len(b)
    b += b"\x0f\x83\0\0\0\0"
    b += b"\x48\x83\x7a\x18\x09"  # cmp qword [rdx+0x18], 9
    j_next1 = len(b)
    b += b"\x0f\x85\0\0\0\0"
    b += b"\x48\x83\x7a\x20\x0f"  # cmp qword [rdx+0x20], 0xf
    j_inline = len(b)
    b += b"\x0f\x86\0\0\0\0"
    b += b"\x4c\x8b\x42\x08"  # mov r8, [rdx+8] (heap name)
    j_cmp = len(b)
    b += b"\xe9\0\0\0\0"
    inline = len(b)
    b += b"\x4c\x8d\x42\x08"  # lea r8, [rdx+8] (SSO name)
    cmpstart = len(b)
    b += b"\x45\x33\xdb"  # xor r11d, r11d
    cloop = len(b)
    b += b"\x49\x83\xfb\x09"  # cmp r11, 9
    j_match = len(b)
    b += b"\x0f\x83\0\0\0\0"
    b += b"\x43\x8a\x04\x18"  # mov al, [r8+r11]
    b += b"\x43\x3a\x04\x1a"  # cmp al, [r10+r11]
    j_next2 = len(b)
    b += b"\x0f\x85\0\0\0\0"
    b += b"\x49\xff\xc3"  # inc r11
    j_cloop = len(b)
    b += b"\xe9\0\0\0\0"
    match = len(b)
    b += b"\x8b\x42\x70"  # mov eax, [rdx+0x70] (value len)
    b += b"\x89\x81" + struct.pack("<I", out_len)  # mov [rcx+out_len], eax
    b += b"\x41\xb8\x10\0\0\0"  # mov r8d, 16
    b += b"\x44\x39\xc0"  # cmp eax, r8d
    j_keep = len(b)
    b += b"\x0f\x86\0\0\0\0"
    b += b"\x44\x89\xc0"  # mov eax, r8d (clamp 16)
    keep = len(b)
    b += b"\x48\x83\x7a\x78\x0f"  # cmp qword [rdx+0x78], 0xf
    j_vinline = len(b)
    b += b"\x0f\x86\0\0\0\0"
    b += b"\x4c\x8b\x42\x60"  # mov r8, [rdx+0x60]
    j_vcopy = len(b)
    b += b"\xe9\0\0\0\0"
    vinline = len(b)
    b += b"\x4c\x8d\x42\x60"  # lea r8, [rdx+0x60]
    vcopy = len(b)
    b += b"\x45\x33\xdb"  # xor r11d, r11d
    vloop = len(b)
    b += b"\x41\x39\xc3"  # cmp r11d, eax
    j_vdone = len(b)
    b += b"\x0f\x83\0\0\0\0"
    b += b"\x46\x0f\xb6\x0c\x18"  # movzx r9d, byte [r8+r11]
    b += b"\x46\x88\x8c\x19" + struct.pack("<I", out_bytes)
    b += b"\x49\xff\xc3"  # inc r11
    j_vloop = len(b)
    b += b"\xe9\0\0\0\0"
    next_ = len(b)
    b += b"\x48\x81\xc2\x98\0\0\0"  # add rdx, 0x98
    j_loop = len(b)
    b += b"\xe9\0\0\0\0"
    done = len(b)

    _patch32(b, j_done, done)
    _patch32(b, j_next1, next_)
    _patch32(b, j_inline, inline)
    _patchjmp32(b, j_cmp, cmpstart)
    _patch32(b, j_match, match)
    _patch32(b, j_next2, next_)
    _patchjmp32(b, j_cloop, cloop)
    _patch32(b, j_keep, keep)
    _patch32(b, j_vinline, vinline)
    _patchjmp32(b, j_vcopy, vcopy)
    _patch32(b, j_vdone, done)
    _patchjmp32(b, j_vloop, vloop)
    _patchjmp32(b, j_loop, loop)
    return bytes(b)


def emit_ctrl_scan(out_off, out_slot, base, fixups):
    """Read-only scan of ``[control+0x00 .. +0xA4]`` for the four live handles.

    A-0028 §2.2: ``rbx`` = control, handles are read from the marker copy at
    ``+0x1a38..+0x1a44`` (regular/arial/menu/console).  Writes the first
    matching dword offset (``0xFFFFFFFF`` = none) and the slot number 1..4.
    Stops at ``+0xA8`` -- the object is at least ``0xAD`` bytes (gate ``+0xac``
    is read), but bag12 proved that going further is not worth a crash.
    """
    b = bytearray()

    def mark():
        fixups.append((base + len(b) - 4, b"marker"))

    def slot_store(n):
        return b"\xc7\x81" + struct.pack("<I", out_slot) + struct.pack("<I", n)

    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    b += b"\xc7\x81" + struct.pack("<I", out_off) + b"\xff\xff\xff\xff"
    b += b"\xc7\x81" + struct.pack("<I", out_slot) + b"\0\0\0\0"
    b += b"\x44\x8b\x81" + struct.pack("<I", 0x1A38)  # mov r8d, [rcx+0x1a38]
    b += b"\x44\x8b\x89" + struct.pack("<I", 0x1A3C)  # mov r9d, [rcx+0x1a3c]
    b += b"\x44\x8b\x91" + struct.pack("<I", 0x1A40)  # mov r10d, [rcx+0x1a40]
    b += b"\x44\x8b\x99" + struct.pack("<I", 0x1A44)  # mov r11d, [rcx+0x1a44]
    b += b"\x33\xd2"  # xor edx, edx
    loop = len(b)
    b += b"\x81\xfa\xa8\0\0\0"  # cmp edx, 0xa8
    j_done = len(b)
    b += b"\x0f\x83\0\0\0\0"
    b += b"\x8b\x04\x13"  # mov eax, [rbx+rdx]
    b += b"\x85\xc0"  # test eax, eax
    j_zero = len(b)
    b += b"\x0f\x84\0\0\0\0"
    b += b"\x44\x39\xc0"  # cmp eax, r8d
    j_s1 = len(b)
    b += b"\x0f\x84\0\0\0\0"
    b += b"\x44\x39\xc8"  # cmp eax, r9d
    j_s2 = len(b)
    b += b"\x0f\x84\0\0\0\0"
    b += b"\x44\x39\xd0"  # cmp eax, r10d
    j_s3 = len(b)
    b += b"\x0f\x84\0\0\0\0"
    b += b"\x44\x39\xd8"  # cmp eax, r11d
    j_s4 = len(b)
    b += b"\x0f\x84\0\0\0\0"
    next_ = len(b)
    b += b"\x83\xc2\x04"  # add edx, 4
    j_loop = len(b)
    b += b"\xe9\0\0\0\0"
    s1 = len(b)
    b += slot_store(1)
    j_f1 = len(b)
    b += b"\xe9\0\0\0\0"
    s2 = len(b)
    b += slot_store(2)
    j_f2 = len(b)
    b += b"\xe9\0\0\0\0"
    s3 = len(b)
    b += slot_store(3)
    j_f3 = len(b)
    b += b"\xe9\0\0\0\0"
    s4 = len(b)
    b += slot_store(4)
    found = len(b)
    b += b"\x89\x91" + struct.pack("<I", out_off)  # mov [rcx+out_off], edx
    done = len(b)

    _patch32(b, j_done, done)
    _patch32(b, j_zero, next_)
    _patch32(b, j_s1, s1)
    _patch32(b, j_s2, s2)
    _patch32(b, j_s3, s3)
    _patch32(b, j_s4, s4)
    _patchjmp32(b, j_loop, loop)
    _patchjmp32(b, j_f1, found)
    _patchjmp32(b, j_f2, found)
    _patchjmp32(b, j_f3, found)
    return bytes(b)


def _check_swap_encoding(code, slot=0x08):
    """Assert the slot swap block really moves r11d, not r10d.

    The first version had ModRM 0x91/0x50 with REX.R set, i.e. both stores
    used r10d (the *old* arial ref): the swap silently wrote the old handle
    back into the arial slot and only the marker showed the new value.
    Encoding is not reviewable by eye, so the block is disassembled at build
    time and the three memory operations are pinned here.  ``slot`` is the
    offset inside ``Fonts``: 0x04 regular, 0x08 arial, 0x0c menu, 0x10 console.
    """
    a = str(slot) if slot < 10 else hex(slot)  # match capstone's rendering
    want = [
        f"mov r10d, dword ptr [rax + {a}]",
        "mov r11d, dword ptr [rax + 0xc]",
        "mov dword ptr [rcx + 0x1c84], r10d",
        "mov dword ptr [rcx + 0x1c88], r11d",
        f"mov dword ptr [rax + {a}], r11d",
    ]
    got = [f"{i.mnemonic} {i.op_str}" for i in _disasm(code)]
    missing = [w for w in want if w not in got]
    if missing:
        raise AssertionError(
            "swap block encoding wrong, expected "
            + "; ".join(missing)
            + " in "
            + " | ".join(got)
        )


def emit_mem_dump(src, out_off, size, base, fixups):
    """Copy ``size`` bytes from ``[rsi]`` (set by ``src``) to marker+out_off.

    ``src`` is a byte string that loads ``rsi`` and must not touch ``rcx``.
    rdi/rsi are saved, the marker is parked in the caller's shadow space for
    the duration of ``rep movsb`` (which clobbers rcx).
    """
    b = bytearray()

    def mark():
        fixups.append((base + len(b) - 4, b"marker"))

    b += src  # rsi = source
    b += b"\x57"  # push rdi
    b += b"\x56"  # push rsi
    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    b += b"\x48\x89\x4c\x24\x10"  # mov [rsp+0x10], rcx  (park marker)
    b += b"\x48\x8d\xb9" + struct.pack("<i", out_off)  # lea rdi, [rcx+out]
    b += b"\xb9" + struct.pack("<I", size)  # mov ecx, size
    b += b"\xfc"  # cld
    b += b"\xf3\xa4"  # rep movsb
    b += b"\x48\x8b\x4c\x24\x10"  # mov rcx, [rsp+0x10]  (restore marker)
    b += b"\x5e"  # pop rsi
    b += b"\x5f"  # pop rdi
    return bytes(b)


def emit_fonts_refresh(base, fixups):
    """Refresh the two views of the ``Fonts`` registry on every call.

    Cheap (two 0x20-byte copies) and done every time on purpose: L-0035 shows
    ``Fonts::Fonts`` rebuilds the slots, so the arial and menu refs the
    substitution compares against must be current, not a snapshot taken on
    the first call.
    """
    b = bytearray()

    def mark():
        fixups.append((base + len(b) - 4, b"marker"))

    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    b += b"\x48\x8b\x81\x1c\x1a\0\0"  # mov rax, [rcx+0x1a1c] (exe base)
    b += b"\x48\x85\xc0"  # test rax, rax
    j = len(b)
    b += b"\x0f\x84\0\0\0\0"  # je fr_done
    b += emit_mem_dump(
        b"\x48\x8d\xb0" + struct.pack("<i", EXE_FONTS_INLINE),
        FONTS_INLINE,
        0x20,
        base + len(b),
        fixups,
    )  # lea rsi, [rax+0x1733240]
    b += emit_mem_dump(
        b"\x48\x8b\xb0" + struct.pack("<i", EXE_FONTS_PTR),
        FONTS_DEREF,
        0x20,
        base + len(b),
        fixups,
    )  # mov rsi, [rax+0x1733260]
    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    b += b"\x48\x8b\x81\x1c\x1a\0\0"  # mov rax, [rcx+0x1a1c] (exe base)
    b += b"\x48\x8b\x80" + struct.pack("<i", EXE_FONTS_PTR)
    b += b"\x48\x89\x81" + struct.pack("<I", FONTS_PTR)  # [rcx+fptr] = rax
    fr_done = len(b)
    struct.pack_into("<i", b, j + 2, fr_done - (j + 6))
    return bytes(b)


def emit_static_dump(base, fixups):
    """One-off dump of the ref->node path: banks and the four resolved nodes.

    Retries on every call until both the arial and the menu slot are
    non-zero, so the dump never freezes an empty registry.  If the four names
    come out ``regular/arial/menu/console`` the resolver from
    ``work/resolve_fonts.py`` is confirmed inside the game.
    """
    b = bytearray()

    def mark():
        fixups.append((base + len(b) - 4, b"marker"))

    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    b += b"\x83\xb9" + struct.pack("<I", STATIC_DONE) + b"\x00"
    j1 = len(b)
    b += b"\x0f\x85\0\0\0\0"  # jne sd_done (once per run)
    b += b"\x48\x8b\x81\x1c\x1a\0\0"  # mov rax, [rcx+0x1a1c] (exe base)
    b += b"\x48\x85\xc0"  # test rax, rax
    j2 = len(b)
    b += b"\x0f\x84\0\0\0\0"  # je sd_done
    b += b"\x83\xb9" + struct.pack("<I", FONTS_INLINE + 0x08) + b"\x00"
    j3 = len(b)
    b += b"\x0f\x84\0\0\0\0"  # je sd_done (arial slot still empty)
    b += b"\x83\xb9" + struct.pack("<I", FONTS_INLINE + 0x0C) + b"\x00"
    j4 = len(b)
    b += b"\x0f\x84\0\0\0\0"  # je sd_done (menu slot still empty)
    b += emit_mem_dump(
        b"\x48\x8d\xb0" + struct.pack("<i", EXE_BANKS),
        BANKS,
        0x100,
        base + len(b),
        fixups,
    )  # lea rsi, [rax+0x175f140]
    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    # ---- resolve the four refs: node = banks[ref>>24] + (ref & 0xffffff) ----
    for slot in (1, 2, 3, 4):  # regular, arial, menu, console
        rec = NODE_REC + (slot - 1) * 0x40
        b += b"\x44\x8b\x91" + struct.pack("<I", FONTS_INLINE + slot * 4)
        b += b"\x45\x85\xd2"  # test r10d, r10d
        jz = len(b)
        b += b"\x0f\x84\0\0\0\0"  # je next (empty ref, near)
        b += b"\x44\x89\xd0"  # mov eax, r10d   (REX.R selects r10)
        b += b"\xc1\xe8\x18"  # shr eax, 0x18      (bank)
        b += b"\x41\x81\xe2\xff\xff\xff\x00"  # and r10d, 0xffffff  (off)
        b += b"\x4c\x8b\x9c\xc1" + struct.pack("<I", BANKS)
        # mov r11, [rcx + rax*8 + banks]
        b += b"\x4d\x01\xd3"  # add r11, r10        (node; REX.W|R|B)
        b += b"\x4c\x89\x99" + struct.pack("<I", rec)  # mov [rcx+rec], r11
        b += b"\x43\x8b\x43\x08"  # mov eax, [r11+8] (refcount)
        b += b"\x89\x81" + struct.pack("<I", rec + 8)
        b += b"\x41\x0f\xb7\x43\x10"  # movzx eax, word [r11+0x10] (nlen)
        b += b"\x89\x81" + struct.pack("<I", rec + 0x0C)
        b += emit_mem_dump(
            b"\x49\x8d\x73\x14",  # lea rsi, [r11+0x14]
            rec + 0x10,
            0x20,
            base + len(b),
            fixups,
        )
        b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
        mark()
        struct.pack_into("<i", b, jz + 2, len(b) - (jz + 6))
    b += b"\xc7\x81" + struct.pack("<I", SUBST_FIRST) + b"\xff\xff\xff\xff"
    b += b"\xc7\x81" + struct.pack("<I", STATIC_DONE) + b"\x01\x00\x00\x00"
    sd_done = len(b)
    for pos in (j1, j2, j3, j4):
        struct.pack_into("<i", b, pos + 2, sd_done - (pos + 6))
    return bytes(b)


def emit_ctl_dump(out_off, flag_off, flag_bit, base, fixups):
    """Dump the first 0x100 bytes of the control in ``rbx``, once."""
    b = bytearray()

    def mark():
        fixups.append((base + len(b) - 4, b"marker"))

    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    b += b"\xf6\x81" + struct.pack("<I", flag_off) + bytes([flag_bit])
    # test byte [rcx+flag_off], flag_bit
    j = len(b)
    b += b"\x75\0"  # jne cd_done
    b += b"\x80\x89" + struct.pack("<I", flag_off) + bytes([flag_bit])
    # or byte [rcx+flag_off], flag_bit
    b += emit_mem_dump(b"\x48\x89\xde", out_off, 0x100, base + len(b), fixups)
    # mov rsi, rbx
    cd_done = len(b)
    struct.pack_into("<b", b, j + 1, cd_done - (j + 2))
    return bytes(b)


def emit_ref_subst(write, base, fixups, force_off=None):
    """Replace the `arial` ref by the `menu` ref inside the live control.

    No offset is assumed: every dword in ``[rbx, rbx+0x100)`` equal to the
    current ``arial`` ref becomes the ``menu`` ref.  Idempotent by
    construction -- after the write the slot no longer matches -- and it
    needs no knowledge of which field the draw code reads.  The menu node's
    refcount is bumped with a ``lock inc``, the same way the exe's own
    setters do it; the arial node is left alone (it is a singleton).

    ``force_off`` additionally stores the menu ref at ``[rbx+force_off]`` on
    every pass.  That is the probe for the case where the control carries an
    *empty* ref and the arial substitution happens at draw time: pick the
    offset from the control dump and see whether the glyphs change.
    """
    b = bytearray()

    def mark():
        fixups.append((base + len(b) - 4, b"marker"))

    b += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    mark()
    b += b"\xff\x81" + struct.pack("<I", SUBST_CTLS)  # inc controls seen
    b += b"\x8b\x91" + struct.pack("<I", FONTS_INLINE + 0x08)  # arial ref
    b += b"\x85\xd2"  # test edx, edx
    j1 = len(b)
    b += b"\x0f\x84\0\0\0\0"  # je rs_noref
    b += b"\x44\x8b\x81" + struct.pack("<I", FONTS_INLINE + 0x0C)  # menu ref
    b += b"\x45\x85\xc0"  # test r8d, r8d
    j2 = len(b)
    b += b"\x0f\x84\0\0\0\0"  # je rs_noref
    b += b"\x45\x33\xc9"  # xor r9d, r9d          (offset)
    rs_loop = len(b)
    b += b"\x41\x81\xf9\x00\x01\x00\x00"  # cmp r9d, 0x100
    j3 = len(b)
    b += b"\x0f\x83\0\0\0\0"  # jae rs_scan_done
    b += b"\x42\x8b\x04\x0b"  # mov eax, [rbx+r9*1]  (dword at offset r9)
    b += b"\x39\xd0"  # cmp eax, edx
    j4 = len(b)
    b += b"\x75\0"  # jne rs_next
    b += b"\xff\x81" + struct.pack("<I", SUBST_FOUND)  # inc found
    b += b"\x83\xb9" + struct.pack("<I", SUBST_FIRST) + b"\xff"
    # cmp dword [rcx+first], -1
    j5 = len(b)
    b += b"\x75\0"  # jne rs_have_first
    b += b"\x44\x89\x89" + struct.pack("<I", SUBST_FIRST)  # mov [rcx+first], r9d
    rs_have_first = len(b)
    struct.pack_into("<b", b, j5 + 1, rs_have_first - (j5 + 2))
    b += b"\x44\x89\x89" + struct.pack("<I", SUBST_LAST)  # mov [rcx+last], r9d
    if write:
        b += b"\x46\x89\x04\x0b"  # mov [rbx+r9*1], r8d  (the substitution)
        b += b"\x48\x8b\x91" + struct.pack("<I", NODE_REC + 2 * 0x40)  # menu
        b += b"\x48\x85\xd2"  # test rdx, rdx
        j6 = len(b)
        b += b"\x74\0"  # je rs_next (no node -> do not touch a refcount)
        b += b"\xf0\xff\x42\x08"  # lock inc dword [rdx+8]
        b += b"\xff\x81" + struct.pack("<I", SUBST_WRITES)  # inc writes
        struct.pack_into("<b", b, j6 + 1, len(b) - (j6 + 2))
    rs_next = len(b)
    b += b"\x41\x83\xc1\x04"  # add r9d, 4
    j7 = len(b)
    b += b"\xe9\0\0\0\0"  # jmp rs_loop
    rs_noref = len(b)
    b += b"\xff\x81" + struct.pack("<I", SUBST_NOREF)  # inc [rcx+noref]
    rs_scan_done = len(b)
    for pos in (j1, j2, j3):
        struct.pack_into("<i", b, pos + 2, rs_scan_done - (pos + 6))
    struct.pack_into("<i", b, j7 + 1, rs_loop - (j7 + 5))
    struct.pack_into("<b", b, j4 + 1, rs_next - (j4 + 2))
    if force_off is None:
        return bytes(b)
    # --- force: store the menu ref at a fixed offset of the control ---------
    b += b"\x44\x8b\x81" + struct.pack("<I", FONTS_INLINE + 0x0C)  # menu ref
    b += b"\x45\x85\xc0"  # test r8d, r8d
    jf = len(b)
    b += b"\x0f\x84\0\0\0\0"  # je rs_done
    b += b"\x44\x89\x83" + struct.pack("<i", force_off)  # mov [rbx+off], r8d
    b += b"\x48\x8b\x91" + struct.pack("<I", NODE_REC + 2 * 0x40)  # menu node
    b += b"\x48\x85\xd2"  # test rdx, rdx
    jg = len(b)
    b += b"\x74\0"  # je rs_done
    b += b"\xf0\xff\x42\x08"  # lock inc dword [rdx+8]
    b += b"\xff\x81" + struct.pack("<I", SUBST_WRITES)  # inc writes
    struct.pack_into("<b", b, jg + 1, len(b) - (jg + 2))
    rs_done = len(b)
    struct.pack_into("<i", b, jf + 2, rs_done - (jf + 6))
    return bytes(b)


def build_caption_font_hook(
    blob_rva,
    site_rva,
    font_name,
    prop_name="font_name",
    write=True,
    displaced=None,
    accept_all=False,
    swap_arial=False,
    swap_sticky=False,  # False | slot offset into Fonts (0x04/0x08/0x0c/0x10)
    ctl_dump=False,
    font_subst="off",
    subst_offset=None,
):
    """Code cave for the property setter ``site_rva``.

    The mod sets the ``caption`` property of a control but never touches the
    font, so the engine draws the caption with its default ``arial`` (ASCII
    only).  Through bag14 this hook wrote ``prop_name`` on the same control;
    A-0028 turned bag15 into a **read-only** probe: it records the original
    ``font_name`` record of our controls and of the working ``local_text``
    element (plus a dword scan for cached font handles) and never writes to
    the game object.

    The cave starts at ``blob_rva``; the caller maps the first six bytes of
    ``site_rva`` to it.  Returns ``(blob, site_patch, marker_off)``.
    """
    code = bytearray()
    fixups = []

    # --- the bytes our 5-byte jmp overwrites at the setter's entry -----------
    # 0.9.0: 4 pushes (6 bytes).  0.9.1 (L-0034): 5 pushes (8 bytes) --
    # `push rbx/rbp/rdi/r14/r15`.  They are replayed in our epilogue, so the
    # length decides both the size of the site patch and where we jump back.
    # Never hardcode it: a wrong guess here reproduces as a stack imbalance
    # three frames later, which is exactly the kind of crash that costs a run.
    if displaced is None:
        displaced = DEFAULT_DISPLACED_091
    displaced = bytes(displaced)
    check_displaced(displaced)
    dlen = len(displaced)

    # --- positive caption filter (ru/caption_filter.json, A-0020 §7.1) -------
    # ``accept_all`` (L-0035 experiment) skips the hash test and writes the font
    # on every ``caption`` property: the menu labels go through the same
    # property but only ~half of them are in the table, so this answers whether
    # the same write can also fix the menu without a UI2 table.
    prop = prop_name.encode("ascii")
    hashes = []
    cf = Path(__file__).resolve().parent.parent / "ru" / "caption_filter.json"
    if cf.exists():
        doc = json.loads(cf.read_text(encoding="utf-8"))
        hashes = sorted({int(e["hash32"]) & 0xFFFFFFFF for e in doc.get("entries", [])})
    if not hashes:
        hashes = [0xFFFFFFFF]
    filter_count = len(hashes)
    # labels of the branches that only exist in the filtered build
    hash_loop = hash_done = search_loop = jmiss = h1 = h2 = s1 = s2 = None
    accept_j = None

    # --- save every register we clobber (5 callee-saved + 8 volatile) --------
    code += b"\x53\x55\x57\x41\x56\x41\x57"  # push rbx, rbp, rdi, r14, r15
    code += b"\x50\x51\x52\x56\x41\x50\x41\x51\x41\x52\x41\x53"  # rax..r11
    code += b"\x48\x83\xec\x20"  # sub rsp, 0x20 (shadow space, keeps 16B align)

    code += b"\x48\x8b\xd9"  # mov rbx, rcx  (control)
    code += b"\x48\x8b\xea"  # mov rbp, rdx  (name string_view)
    code += b"\x49\x8b\xf8"  # mov rdi, r8   (value string_view)

    # --- exe image base + live Fonts registry (bag11, L-0030) ----------------
    # PEB -> Ldr -> InLoadOrderModuleList (offset 0x10 in PEB_LDR_DATA) ->
    # first entry. InLoadOrderLinks is the FIRST field of LDR_DATA_TABLE_ENTRY,
    # so Flink *is* the entry base and DllBase sits at +0x30 (not +0x20:
    # +0x20 is InInitializationOrderLinks, live-verified 0x0).
    # exe+0x1733260 holds the lazy ``Fonts*`` singleton (0x39b720 accessor,
    # 0x39b5f0 ctor).  Its dwords are the pre-resolved handles:
    #   +0x00 pad, +0x04 "regular", +0x08 "arial", +0x0c "menu",
    #   +0x10 "console", +0x14 0.
    # bag10 copied exe+0x1733240, which is a CRT allocator buffer
    # (A-0027 §4 was wrong) - never read it again.
    code += b"\x65\x48\x8b\x04\x25\x60\0\0\0"  # mov rax, gs:[0x60] (PEB)
    code += b"\x48\x8b\x40\x18"  # mov rax, [rax+0x18]  (Ldr)
    code += b"\x48\x8b\x40\x10"  # mov rax, [rax+0x10]  (InLoadOrder list)
    code += b"\x48\x8b\x40\x30"  # mov rax, [rax+0x30]  (DllBase of entry)
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\x48\x89\x81\x1c\x1a\0\0"  # mov [rcx+0x1a1c], rax (exe base)
    code += b"\x48\x85\xc0"  # test rax, rax
    fz1 = len(code)
    code += b"\x74\0"  # je fonts_done (no exe base -> never deref low memory)
    code += b"\x48\x8b\x90\x60\x32\x73\x01"  # mov rdx, [rax+0x1733260] Fonts*
    code += b"\x48\x89\x91\x2c\x1a\0\0"  # mov [rcx+0x1a2c], rdx (fonts ptr)
    code += b"\x48\x85\xd2"  # test rdx, rdx
    fz2 = len(code)
    code += b"\x74\0"  # je fonts_done (not constructed yet)
    code += b"\x45\x33\xc9"  # xor r9d, r9d
    floop = len(code)
    code += b"\x46\x8b\x14\x8a"  # mov r10d, [rdx+r9*4]
    code += b"\x45\x85\xd2"  # test r10d, r10d
    fz4 = len(code)
    code += b"\x74\0"  # je floop_next (keep the last non-zero handle)
    # SIB must be 0x89 (scale=4, index=r9, base=rcx): the old 0x09 wrote the
    # handles at a 1-byte stride, so each dword overlapped its neighbour and
    # the dump showed garbage (bag13: "regular=0x00cd6190, arial=0x00008000").
    code += bytes([0x46, 0x89, 0x94, sib_byte(4, 9, 1)]) + struct.pack(
        "<I", 0x1A34
    )  # mov [rcx+r9*4+0x1a34], r10d (SIB asserted by sib_byte)
    floop_next = len(code)
    code += b"\x41\xff\xc1"  # inc r9d
    code += b"\x41\x83\xf9\x08"  # cmp r9d, 8
    fz3 = len(code)
    code += b"\x72\0"  # jb floop
    fonts_done = len(code)

    # --- L-0035: one-off dump of the font registry and of the ref->node path
    if ctl_dump or font_subst != "off":
        code += emit_fonts_refresh(len(code), fixups)
        code += emit_static_dump(len(code), fixups)

    # --- L-0035: one-time arial -> menu slot swap ----------------------------
    # A-0027 §5 / A-0030 §4.4 / A-0031 §3: the only remaining binary test for
    # "our captions are drawn with `arial`".  The mod never sets a font, the
    # exe falls back to the `arial` slot of the live `Fonts` object; the menu
    # labels go through the same caption property.  If the captions turn
    # Cyrillic after this write, the font is taken from the slot and the fix
    # is one dword.  If nothing changes, the font is pinned per class.
    #
    # `Fonts` is a heap object (lazy singleton at exe+0x1733260), so the slot
    # write needs no VirtualProtect.  Slot layout (L-0030 §2.1):
    #   +0x04 regular, +0x08 arial, +0x0c menu, +0x10 console
    # Do it once per process, only when the `menu` handle is already resolved;
    # otherwise retry on the next setter call.  Never write a zero handle.
    swap_done = None
    swap_start = len(code)
    if swap_arial:
        code += b"\x48\x8b\x81\x2c\x1a\0\0"  # mov rax, [rcx+0x1a2c] (Fonts*)
        code += b"\x48\x85\xc0"  # test rax, rax
        sw1 = len(code)
        code += b"\x0f\x84\0\0\0\0"  # je swap_done
        code += b"\x83\xb9\x80\x1c\0\0\x00"  # cmp dword [rcx+0x1c80], 0
        sw2 = len(code)
        code += b"\x0f\x85\0\0\0\0"  # jne swap_done (already swapped)
        code += b"\x44\x8b\x50\x08"  # mov r10d, [rax+0x08] (old arial ref)
        code += b"\x44\x8b\x58\x0c"  # mov r11d, [rax+0x0c] (menu ref)
        code += b"\x45\x85\xdb"  # test r11d, r11d
        sw3 = len(code)
        code += b"\x75\0"  # jne swap_have (slot already resolved)
        code += b"\x44\x8b\x99\xe4\x1b\0\0"  # mov r11d, [rcx+0x1be4] probe
        swap_have = len(code)
        code += b"\x45\x85\xdb"  # test r11d, r11d
        sw4 = len(code)
        code += b"\x0f\x84\0\0\0\0"  # je swap_done (no menu handle yet)
        code += b"\x44\x89\x91\x84\x1c\0\0"  # mov [rcx+0x1c84], r10d (old)
        code += b"\x44\x89\x99\x88\x1c\0\0"  # mov [rcx+0x1c88], r11d (new)
        code += b"\x44\x89\x58\x08"  # mov [rax+0x08], r11d (arial <- menu)
        code += b"\xc7\x81\x80\x1c\0\0\x01\0\0\0"  # mov dword [rcx+0x1c80], 1
        swap_done = len(code)
        struct.pack_into("<i", code, sw1 + 2, swap_done - (sw1 + 6))
        struct.pack_into("<i", code, sw2 + 2, swap_done - (sw2 + 6))
        struct.pack_into("<i", code, sw4 + 2, swap_done - (sw4 + 6))
        struct.pack_into("<b", code, sw3 + 1, swap_have - (sw3 + 2))
        _check_swap_encoding(bytes(code[swap_start:swap_done]))
    if swap_sticky is not False:
        # Same store, but (a) the registry pointer is re-read from the exe
        # every call, so a rebuilt registry is found, (b) there is no
        # once-guard, so the slot is corrected after every rebuild, and (c)
        # the target slot is a parameter: L-0035's live dump has
        # [Fonts+0x04] regular = 0 while the page draws arial, so the slot
        # worth overwriting may be `regular`, not `arial`.
        slot = 0x08 if swap_sticky is True else int(swap_sticky)
        st_start = len(code)
        code += b"\x48\x8b\x81\x1c\x1a\0\0"  # mov rax,[rcx+0x1a1c]
        code += b"\x48\x85\xc0"  # test rax, rax
        st1 = len(code)
        code += b"\x0f\x84\0\0\0\0"  # je st_done
        code += b"\x48\x8b\x80" + struct.pack("<i", EXE_FONTS_PTR)
        # mov rax, [rax+0x1733260]
        code += b"\x48\x85\xc0"  # test rax, rax
        st2 = len(code)
        code += b"\x0f\x84\0\0\0\0"  # je st_done
        code += b"\x48\x89\x81" + struct.pack("<I", FONTS_PTR)
        # mov [rcx+FONTS_PTR], rax  (what we are about to patch)
        code += b"\x44\x8b\x50" + bytes([slot])  # mov r10d, [rax+slot]
        code += b"\x44\x8b\x58\x0c"  # mov r11d, [rax+0x0c] (menu ref)
        code += b"\x45\x85\xdb"  # test r11d, r11d
        st3 = len(code)
        code += b"\x75\0"  # jne st_have (slot already resolved)
        code += b"\x44\x8b\x99\xe4\x1b\0\0"  # mov r11d, [rcx+0x1be4]
        st_have = len(code)
        code += b"\x45\x85\xdb"  # test r11d, r11d
        st4 = len(code)
        code += b"\x0f\x84\0\0\0\0"  # je st_done (no menu handle yet)
        code += b"\x45\x39\xda"  # cmp r10d, r11d
        st5 = len(code)
        code += b"\x74\0"  # je st_store (slot already holds the menu ref)
        code += b"\xff\x81" + struct.pack("<I", SWAP_FIXES)  # inc fixes
        st_store = len(code)
        struct.pack_into("<b", code, st5 + 1, st_store - (st5 + 2))
        code += b"\x44\x89\x91\x84\x1c\0\0"  # mov [rcx+0x1c84], r10d
        code += b"\x44\x89\x99\x88\x1c\0\0"  # mov [rcx+0x1c88], r11d
        code += b"\x44\x89\x58" + bytes([slot])  # mov [rax+slot], r11d
        code += b"\xc7\x81\x80\x1c\0\0\x01\0\0\0"  # [rcx+0x1c80] = 1
        st_done = len(code)
        for pos in (st1, st2, st4):
            struct.pack_into("<i", code, pos + 2, st_done - (pos + 6))
        struct.pack_into("<b", code, st3 + 1, st_have - (st3 + 2))
        _check_swap_encoding(bytes(code[st_start:st_done]), slot)

    # --- bag12: probe the exe font manager -----------------------------------
    # Fonts::Fonts (exe 0x39b5f0) resolves regular/arial/menu/console once at
    # startup through 0xab20d0(manager=[exe+0x175f138], name, len, 0).  Live
    # dumps show regular != 0 but menu == 0, so the setter may be writing a
    # name the manager cannot resolve.  Ask the manager directly, but only
    # when the registry already has a non-zero "regular" handle (font system
    # is up).  Keeps the last non-zero handle in the marker.
    code += b"\x48\x89\xce"  # mov rsi, rcx (marker)
    code += b"\x48\x8b\x81\x2c\x1a\0\0"  # mov rax, [rsi+0x1a2c] (Fonts*)
    code += b"\x48\x85\xc0"  # test rax, rax
    rp0 = len(code)
    code += b"\x0f\x84\0\0\0\0"  # je probe_done
    code += b"\x83\x78\x04\x00"  # cmp dword [rax+4], 0 (regular handle)
    rp1 = len(code)
    code += b"\x0f\x84\0\0\0\0"  # je probe_done (font system not ready)
    code += b"\x48\x8b\x86\x1c\x1a\0\0"  # mov rax, [rsi+0x1a1c] (exe base)
    code += b"\x48\x8b\x88\x38\xf1\x75\x01"  # mov rcx, [rax+0x175f138]
    code += b"\x48\x89\x8e\xf0\x1b\0\0"  # mov [rsi+0x1bf0], rcx
    code += b"\x48\x85\xc9"  # test rcx, rcx
    rp2 = len(code)
    code += b"\x0f\x84\0\0\0\0"  # je probe_done
    code += b"\x83\xbe\xf8\x1b\0\0\x00"  # cmp dword [rsi+0x1bf8], 0
    rp3 = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne probe_done (probe exactly once per run)
    # ABI trap (bag12 crash, L-0031): 0xab20d0 homes its arguments in the
    # caller's 32-byte shadow space - live disasm at 0xab20d0/0xab20d5/0xab20db
    # writes rcx to [rsp+8], r9w to [rsp+0x20] and rbx to [rsp+0x18] of the
    # caller frame.  Parking the marker in the shadow area (bag12 did
    # `push rsi; push rsi`) means the first call overwrites it, so the second
    # iteration read [garbage+0x1a1c] and called a non-canonical r11.
    # Allocate our own scratch block and keep the marker at +0x20, which is
    # above every stack slot the resolver touches (max seen: caller +0x1f).
    code += b"\x48\x83\xec\x30"  # sub rsp, 0x30
    code += b"\x48\x89\x74\x24\x20"  # mov [rsp+0x20], rsi (marker)
    for lit, ln, slot in (
        (b"res_menu", 4, 0x1BE4),
        (b"res_arial", 5, 0x1BE8),
        (b"res_regular", 7, 0x1BEC),
    ):
        code += b"\x48\x8b\x74\x24\x20"  # mov rsi, [rsp+0x20] (marker)
        code += b"\x48\x8b\x8e\xf0\x1b\0\0"  # mov rcx, [rsi+0x1bf0]
        code += b"\x48\x8b\x86\x1c\x1a\0\0"  # mov rax, [rsi+0x1a1c]
        code += b"\x4c\x8d\x98\xd0\x20\xab\x00"  # lea r11, [rax+0xab20d0]
        code += b"\x48\x8d\x15\0\0\0\0"  # lea rdx, [rip+lit]
        fixups.append((len(code) - 4, lit))
        code += b"\x41\xb8" + struct.pack("<I", ln)  # mov r8d, len
        code += b"\x45\x33\xc9"  # xor r9d, r9d
        code += b"\x41\xff\xd3"  # call r11
        code += b"\x48\x8b\x74\x24\x20"  # mov rsi, [rsp+0x20] (marker)
        code += b"\x85\xc0"  # test eax, eax
        rpn = len(code)
        code += b"\x74\0"  # je probe_next (keep the last non-zero handle)
        code += b"\x89\x86" + struct.pack("<I", slot)  # mov [rsi+slot], eax
        probe_next = len(code)
        struct.pack_into("<b", code, rpn + 1, probe_next - (rpn + 2))
    code += b"\x48\x8b\x74\x24\x20"  # mov rsi, [rsp+0x20] (marker)
    code += b"\xff\x86\xf8\x1b\0\0"  # inc dword [rsi+0x1bf8] (probes)
    code += b"\x48\x83\xc4\x30"  # add rsp, 0x30
    probe_done = len(code)
    code += b"\x48\x89\xf1"  # mov rcx, rsi (marker for the code below)

    # --- reentrancy guard (A-0027 §7.4): depth counter -----------------------
    code += b"\xff\x81\x14\x1a\0\0"  # inc dword [rcx+0x1a14] (depth)
    code += b"\x83\xb9\x14\x1a\0\0\x01"  # cmp dword [rcx+0x1a14], 1
    g1 = len(code)
    code += b"\x74\0"  # je not_reentry
    code += b"\xff\x81\x18\x1a\0\0"  # inc dword [rcx+0x1a18] (reentries)
    g2 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp done (near; patched below)
    not_reentry = len(code)

    # --- debug marker: [+0x00] calls dword, [+0x04] caption dword -------------
    code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+marker]
    mfx1 = len(code) - 4
    code += b"\xff\x40\x00"  # inc dword ptr [rax]      (calls seen)

    # --- bag15 §2.1: the WORKING element (name == "local_text") --------------
    # The right-hand values are drawn with the correct Cyrillic glyphs because
    # the game sets `local_text` on them.  Record the first such call
    # read-only: its control, its (original!) font_name record and its value.
    # No write to the game object happens anywhere in bag15.
    code += b"\x48\x83\x7d\x08\x0a"  # cmp qword [rbp+8], 10
    lt_a = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne lt_done (near)
    code += b"\x48\x8b\x45\x00"  # mov rax, [rbp]
    code += b"\x81\x38" + b"loca"  # cmp dword [rax], 'loca'
    lt_b = len(code)
    code += b"\x0f\x85\0\0\0\0"
    code += b"\x81\x78\x04" + b"l_te"  # cmp dword [rax+4], 'l_te'
    lt_c = len(code)
    code += b"\x0f\x85\0\0\0\0"
    code += b"\x66\x81\x78\x08" + b"xt"  # cmp word [rax+8], 'xt'
    lt_d = len(code)
    code += b"\x0f\x85\0\0\0\0"
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\xff\x81" + struct.pack("<I", 0x1C00)  # inc [rcx+0x1c00]
    code += b"\x83\xb9" + struct.pack("<I", 0x1C00) + b"\x01"  # cmp .., 1
    lt_e = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne lt_done (only the first call)
    code += b"\x48\x89\x99" + struct.pack("<I", 0x1C08)  # val_ctl = control
    if ctl_dump:
        code += emit_ctl_dump(CTL_VAL_DUMP, CTL_FLAGS, 0x02, len(code), fixups)
    code += b"\x48\x8b\x57\x08"  # mov rdx, [rdi+8] (local_text len)
    code += b"\x89\x91" + struct.pack("<I", 0x1C60)  # val_text_len
    code += b"\x48\xc7\x81" + struct.pack("<I", 0x1C64) + b"\0" * 4
    code += b"\x48\xc7\x81" + struct.pack("<I", 0x1C6C) + b"\0" * 4
    code += b"\x4c\x8b\x0f"  # mov r9, [rdi]
    code += b"\x41\xba\x10\0\0\0"  # mov r10d, 16
    code += b"\x4c\x39\xd2"  # cmp rdx, r10
    lt_f = len(code)
    code += b"\x76\0"  # jbe lt_keep
    code += b"\x44\x89\xd2"  # mov edx, r10d
    lt_keep = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    lt_vloop = len(code)
    code += b"\x4c\x39\xda"  # cmp rdx, r11
    lt_g = len(code)
    code += b"\x74\0"  # je lt_scan
    code += b"\x47\x0f\xb6\x04\x19"  # movzx r8d, byte [r9+r11]
    code += b"\x46\x88\x84\x19" + struct.pack("<I", 0x1C64)
    code += b"\x49\xff\xc3"  # inc r11
    lt_h = len(code)
    code += b"\xeb\0"  # jmp lt_vloop
    lt_scan = len(code)
    code += emit_font_scan(0x1C10, 0x1C14, len(code), fixups)
    code += emit_ctrl_scan(0x1C40, 0x1C44, len(code), fixups)
    lt_done = len(code)
    for pos in (lt_a, lt_b, lt_c, lt_d, lt_e):
        struct.pack_into("<i", code, pos + 2, lt_done - (pos + 6))
    for pos, target in (
        (lt_f, lt_keep),
        (lt_g, lt_scan),
        (lt_h, lt_vloop),
    ):
        struct.pack_into("<b", code, pos + 1, target - (pos + 2))

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
    if accept_all:
        # Every caption is ours: jump straight to the hit arm.  The filter
        # table stays in the data section (harmless, keeps offsets stable).
        accept_j = len(code)
        code += b"\xe9\0\0\0\0"  # jmp hit (patched once hit is known)
    else:
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
    if accept_j is not None:
        struct.pack_into("<i", code, accept_j + 1, hit - (accept_j + 5))
    code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\xff\x40\x2c"  # inc dword ptr [rax+0x2c] (matched counter)
    # bag15 §2.1: cap_fn_* = the font_name record of OUR control, read-only.
    # First matched caption primes the "absent" sentinel; fn_reader below
    # overwrites it whenever the record exists (a later control may have one).
    code += b"\x83\xb8" + struct.pack("<I", 0x1C48) + b"\x00"  # cmp [rax+0x1c48], 0
    j_cap = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne cap_ready
    code += b"\xc7\x80" + struct.pack("<I", 0x1C24) + b"\xff\xff\xff\xff"
    code += b"\x48\xc7\x80" + struct.pack("<I", 0x1C28) + b"\0" * 4
    code += b"\x48\xc7\x80" + struct.pack("<I", 0x1C30) + b"\0" * 4
    code += b"\xc7\x80" + struct.pack("<I", 0x1C48) + b"\x01\0\0\0"
    cap_ready = len(code)
    struct.pack_into("<i", code, j_cap + 2, cap_ready - (j_cap + 6))
    if ctl_dump:
        code += emit_ctl_dump(CTL_CAP_DUMP, CTL_FLAGS, 0x01, len(code), fixups)
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
    # bag15 §2.2: scan [control..+0xA8] for a cached live font handle.
    code += emit_ctrl_scan(0x1C38, 0x1C3C, len(code), fixups)

    # --- read the EXISTING font_name value before any write (A-0026 §3) ------
    # Scan the same bag for name "font_name" (9 bytes), capture value len+8B.
    # Preserves rbx/rbp/rdi; clobbers rax,rcx,rdx,r8-r11,rsi.
    # Uses near (rel32) branches: fn_reader is long, rel8 would overflow.
    code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
    fixups.append((len(code) - 4, b"marker"))
    code += b"\x4c\x8d\x15\0\0\0\0"  # lea r10, [rip+font_name_lit]
    fixups.append((len(code) - 4, b"font_name_lit"))
    code += b"\x48\x8b\x53\x38"  # mov rdx, [rbx+0x38]
    code += b"\x4c\x8b\x4b\x40"  # mov r9, [rbx+0x40]
    fn_loop = len(code)
    code += b"\x4c\x39\xca"  # cmp rdx, r9
    fn1 = len(code)
    code += b"\x0f\x83\0\0\0\0"  # jae fn_done (near)
    code += b"\x48\x83\x7a\x18\x09"  # cmp qword [rdx+0x18], 9
    fn2 = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne fn_next (near)
    code += b"\x48\x83\x7a\x20\x0f"  # cmp qword [rdx+0x20], 0xf
    fn3 = len(code)
    code += b"\x0f\x86\0\0\0\0"  # jbe fn_inline (near)
    code += b"\x4c\x8b\x42\x08"  # mov r8, [rdx+8]
    fn4 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp fn_cmp (near)
    fn_inline = len(code)
    code += b"\x4c\x8d\x42\x08"  # lea r8, [rdx+8]
    fn_cmp = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    fn_cloop = len(code)
    code += b"\x49\x83\xfb\x09"  # cmp r11, 9
    fn5 = len(code)
    code += b"\x0f\x83\0\0\0\0"  # jae fn_match (near)
    code += b"\x43\x8a\x04\x18"  # mov al, [r8+r11]
    code += b"\x43\x3a\x04\x1a"  # cmp al, [r10+r11]
    fn6 = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne fn_next (near)
    code += b"\x49\xff\xc3"
    fn7 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp fn_cloop (near)
    fn_match = len(code)
    # rdx = matching record, rcx = marker
    code += b"\x4c\x8b\x42\x70"  # mov r8, [rdx+0x70] (value len)
    code += b"\x44\x89\x81\x88\x19\0\0"  # mov [rcx+0x1988], r8d
    # bag15 §2.1: the same record is cap_fn_* (our control's original value).
    # Keep the FIRST record that exists; later matched controls must not
    # overwrite it (their values are expected to be identical anyway).
    code += b"\x83\xb9" + struct.pack("<I", 0x1C4C) + b"\x00"  # cmp [rcx+0x1c4c], 0
    j_capfn = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne cap_fn_done
    code += b"\x44\x89\x81" + struct.pack("<I", 0x1C24)  # cap_fn_len
    code += b"\x48\xc7\x81" + struct.pack("<I", 0x1C28) + b"\0" * 4
    code += b"\x48\xc7\x81" + struct.pack("<I", 0x1C30) + b"\0" * 4
    code += b"\xc7\x81" + struct.pack("<I", 0x1C4C) + b"\x01\0\0\0"
    cap_fn_done = len(code)
    struct.pack_into("<i", code, j_capfn + 2, cap_fn_done - (j_capfn + 6))

    # --- A-0027 §3: first control that HAS a font_name record ----------------
    code += b"\xff\x81\xe8\x19\0\0"  # inc dword [rcx+0x19e8] (records found)
    code += b"\x83\xb9\x0c\x1a\0\0\x00"  # cmp dword [rcx+0x1a0c], 0
    fnn1 = len(code)
    code += b"\x0f\x85\0\0\0\0"  # jne fn_first_done (near)
    code += b"\xc7\x81\x0c\x1a\0\0\x01\0\0\0"  # mov dword [rcx+0x1a0c], 1
    # bag11: keep the raw record of the FIRST font_name match, plus the bag
    # bounds and the record pointer, so the dump after the nested set can be
    # compared byte-for-byte (A-0027 §3 left this open).
    code += b"\x48\x89\x91\x54\x1a\0\0"  # mov [rcx+0x1a54], rdx (rec ptr)
    code += b"\xc6\x81\x5c\x1a\0\0\x01"  # mov byte [rcx+0x1a5c], 1 (pending)
    code += b"\x48\x8b\x43\x38"  # mov rax, [rbx+0x38] (bag begin)
    code += b"\x48\x89\x81\xc8\x1b\0\0"  # mov [rcx+0x1bc8], rax
    code += b"\x48\x8b\x43\x40"  # mov rax, [rbx+0x40] (bag end)
    code += b"\x48\x89\x81\xd0\x1b\0\0"  # mov [rcx+0x1bd0], rax
    code += b"\x48\x8b\xf2"  # mov rsi, rdx
    code += b"\x48\x8d\xb9\x60\x1a\0\0"  # lea rdi, [rcx+0x1a60]
    code += b"\x49\x89\xc9"  # mov r9, rcx (park marker)
    code += b"\xfc"  # cld
    code += b"\xb9\x98\0\0\0"  # mov ecx, 0x98
    code += b"\xf3\xa4"  # rep movsb
    code += b"\x4c\x89\xc9"  # mov rcx, r9 (restore marker)
    code += b"\x48\x8b\x91\x54\x1a\0\0"  # mov rdx, [rcx+0x1a54] (record)
    code += b"\x48\x8b\x03"  # mov rax, [rbx] (control tag / first qword)
    code += b"\x89\x81\xe0\x19\0\0"  # mov [rcx+0x19e0], eax (low dword)
    code += b"\x48\x89\x81\x24\x1a\0\0"  # mov [rcx+0x1a24], rax (full qword)
    code += b"\x48\x8b\x43\x60"  # mov rax, [rbx+0x60]
    code += b"\x89\x81\xe4\x19\0\0"  # mov [rcx+0x19e4], eax
    # tail of the record: [rec+0x80 .. +0x97], six dwords (A-0027 §3)
    for _t in range(6):
        code += b"\x8b\x82" + struct.pack("<I", 0x80 + 4 * _t)  # mov eax, [rdx+0x80+4t]
        code += b"\x89\x81" + struct.pack("<I", 0x19EC + 4 * _t)  # mov [rcx+..], eax
    code += b"\xc7\x81\x04\x1a\0\0\xff\xff\xff\xff"  # mov [rcx+0x1a04], -1
    fn_first_done = len(code)

    code += b"\x48\x83\x7a\x78\x0f"  # cmp qword [rdx+0x78], 0xf (val cap)
    fn8 = len(code)
    code += b"\x0f\x86\0\0\0\0"  # jbe fn_vsso (near)
    code += b"\x48\x8b\x42\x60"  # mov rax, [rdx+0x60] (heap ptr)
    fn9 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp fn_vcopy (near)
    fn_vsso = len(code)
    code += b"\x48\x8d\x42\x60"  # lea rax, [rdx+0x60] (inline)
    fn_vcopy = len(code)
    # rax = value bytes ptr, r8 = value len, rcx = marker
    code += b"\x41\xba\x08\0\0\0"  # mov r10d, 8
    code += b"\x4d\x39\xc2"  # cmp r10, r8  (cap count at 8)
    fn10 = len(code)
    code += b"\x0f\x86\0\0\0\0"  # jbe fn_vcnt (near)
    code += b"\x44\x89\xc2"  # mov edx, r8d (count = len)
    fn11 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp fn_vgo (near)
    fn_vcnt = len(code)
    code += b"\x41\xba\x08\0\0\0"  # mov r10d, 8
    code += b"\x44\x89\xd2"  # mov edx, r10d (count = 8)
    fn_vgo = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    fn_vloop = len(code)
    code += b"\x41\x39\xd3"  # cmp r11d, edx
    fn12 = len(code)
    code += b"\x0f\x83\0\0\0\0"  # jae fn_cap (near)
    code += b"\x46\x0f\xb6\x04\x18"  # movzx r8d, byte [rax+r11]
    code += b"\x46\x88\x84\x19\x8c\x19\0\0"  # mov [rcx+r11+0x198c], r8b
    code += b"\x49\xff\xc3"
    fn13 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp fn_vloop (near)
    # bag15 §2.1: up to 16 value bytes into cap_fn_16 (0x198c only had 8).
    fn_cap = len(code)
    code += b"\x8b\x91" + struct.pack("<I", 0x1C24)  # mov edx, [rcx+0x1c24]
    code += b"\x41\xba\x10\0\0\0"  # mov r10d, 16
    code += b"\x44\x39\xd0"  # cmp edx, r10d
    cap_j1 = len(code)
    code += b"\x0f\x86\0\0\0\0"  # jbe cap_keep
    code += b"\x44\x89\xd2"  # mov edx, r10d
    cap_keep = len(code)
    code += b"\x45\x33\xdb"  # xor r11d, r11d
    cap_loop = len(code)
    code += b"\x41\x39\xd3"  # cmp r11d, edx
    cap_j2 = len(code)
    code += b"\x0f\x83\0\0\0\0"  # jae fn_done (patched below)
    code += b"\x46\x0f\xb6\x04\x18"  # movzx r8d, byte [rax+r11]
    code += b"\x46\x88\x84\x19" + struct.pack("<I", 0x1C28)
    code += b"\x49\xff\xc3"  # inc r11
    cap_j3 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp cap_loop
    struct.pack_into("<i", code, cap_j1 + 2, cap_keep - (cap_j1 + 6))
    struct.pack_into("<i", code, cap_j3 + 1, cap_loop - (cap_j3 + 5))
    fn_next = len(code)
    code += b"\x48\x81\xc2\x98\0\0\0"  # add rdx, 0x98
    fn14 = len(code)
    code += b"\xe9\0\0\0\0"  # jmp fn_loop (near)
    fn_done = len(code)

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
    # fn_reader branches (near, rel32) - block is too long for rel8
    for pos, target, jmp in (
        (fn1, fn_done, False),
        (fn2, fn_next, False),
        (fn3, fn_inline, False),
        (fn4, fn_cmp, True),
        (fn5, fn_match, False),
        (fn6, fn_next, False),
        (fn7, fn_cloop, True),
        (fn8, fn_vsso, False),
        (fn9, fn_vcopy, True),
        (fn10, fn_vcnt, False),
        (fn11, fn_vgo, True),
        (fn12, fn_cap, False),
        (fn13, fn_vloop, True),
        (fn14, fn_loop, True),
        (fnn1, fn_first_done, False),
        # bag15 cap_fn_16 copy (near, rel32)
        (cap_j2, fn_done, False),
        # bag12 resolver probe (near, rel32 - block is too long for rel8)
        (rp0, probe_done, False),
        (rp1, probe_done, False),
        (rp2, probe_done, False),
        (rp3, probe_done, False),
    ):
        if jmp:
            struct.pack_into("<i", code, pos + 1, target - (pos + 5))
        else:
            struct.pack_into("<i", code, pos + 2, target - (pos + 6))
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
        (fz1, fonts_done),
        (fz2, fonts_done),
        (fz3, floop),
        (fz4, floop_next),
        (g1, not_reentry),
    ):
        if pos is None:
            continue  # branch does not exist in --caption-all builds
        disp = target - (pos + 2)
        if not -128 <= disp <= 127:
            raise SystemExit(
                f"apply_ru: rel8 branch at +{pos:#x} -> +{target:#x} is "
                f"{disp:+d} bytes; use a near jump instead (A-0027 §6)"
            )
        code[pos + 1] = disp & 0xFF

    # --- L-0035: arial ref -> menu ref inside the live control ---------------
    if font_subst != "off":
        code += emit_ref_subst(
            font_subst == "write", len(code), fixups, subst_offset
        )

    # --- write arm: set(control, &name_sv, &value_sv) -------------------------
    # L-0034 asks for the write; these are the two facts that pick the arm:
    #   * L-0026 (0.9.0, bag7): with ``font_name`` the record exists on 206 of
    #     209 matched controls and the setter returned success for all 206;
    #   * L-0029 (0.9.0, bag9): with ``override_font_name`` there is no record
    #     at all, ``found_any=0`` and ``set_ok_any=0`` -- the setter only
    #     writes into an existing record, so that arm is a guaranteed no-op.
    # Hence ``font_name`` is the default and ``--caption-prop`` keeps the other
    # arm available for a control that does have the record.
    #
    # Two ABI details, each of which cost a run before:
    # Two more ABI details, each of which cost a run:
    #   * the callee spills into its caller's 32-byte shadow space (bag12,
    #     L-0031), so the two string_views live in our own 32-byte slot;
    #   * we never call ``site_rva`` itself -- that is our hook entry, and
    #     bag6..bag9 re-entered the hook on every nested write (L-0029 §3).
    if write:
        prop_len = len(prop)
        font_len = len(font_name.encode("ascii"))
        # ``site+dlen`` (the setter body) is NOT a function: the five pushes at
        # ``site`` are its prologue and its epilogue pops them right before
        # ``ret``.  So the body must see the original frame:
        #     [ret] [saved r15] [saved r14] [saved rdi] [saved rbp] [saved rbx]
        # A ``call`` would push the return address BELOW the replayed saves,
        # the body's first ``pop r15`` would eat it and ``ret`` would land in
        # our data (0xC0000096 at cave+code_len, L-0034b).  Hence: replay the
        # prologue, push a return address, ``jmp`` -- and the body's ``ret``
        # pops it with the five saves still on top.  Stack alignment matches
        # the original exactly (rsp % 16 == 0 at the body entry).
        code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+marker]
        fixups.append((len(code) - 4, b"marker"))
        code += b"\xff\x80" + struct.pack("<I", 0x1C70)  # inc [rax+0x1c70] calls
        # string_views: {ptr,len} at [rsp] and [rsp+0x10].  That is the cave's
        # own 32-byte slot, above everything the body touches (its frame sits
        # below the return address pushed further down).
        code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+prop_name]
        fixups.append((len(code) - 4, b"prop_name"))
        code += b"\x48\x89\x04\x24"  # mov [rsp], rax        (name ptr)
        code += b"\x48\xc7\x44\x24\x08" + struct.pack(
            "<I", prop_len
        )  # mov qword [rsp+8], len
        code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+font_value]
        fixups.append((len(code) - 4, b"font_value"))
        code += b"\x48\x89\x44\x24\x10"  # mov [rsp+0x10], rax   (value ptr)
        code += b"\x48\xc7\x44\x24\x18" + struct.pack(
            "<I", font_len
        )  # mov qword [rsp+0x18], len
        code += b"\x48\x8b\xcb"  # mov rcx, rbx          (control)
        code += b"\x48\x8d\x14\x24"  # lea rdx, [rsp]        (&name_sv)
        code += b"\x4c\x8d\x44\x24\x10"  # lea r8, [rsp+0x10]   (&value_sv)
        # rsp is Q here and the two views sit at [Q, Q+0x20).  Reserve 8 bytes
        # below them first: the replayed prologue then lands at Q-0x40..Q-8
        # with the return address in the last slot above it, i.e. the original
        # frame `[ret][saved rbx]..[saved r15]`.  Body entry rsp == Q-0x40 is
        # 16-aligned, as it was after the real prologue.
        code += b"\x48\x83\xec\x08"  # sub rsp, 8
        code += displaced  # replay the entry prologue (saved regs)
        code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+cont]
        cont_fix = len(code) - 4
        code += b"\x48\x89\x44\x24\x28"  # mov [rsp+0x28], rax (return address)
        code += b"\x4c\x8d\x1d\0\0\0\0"  # lea r11, [rip+site_body]
        fixups.append((len(code) - 4, b"site_body"))
        code += b"\x41\xff\xe3"  # jmp r11
        struct.pack_into("<i", code, cont_fix, len(code) - (cont_fix + 4))
        # cont: the body's epilogue popped the five saves and its `ret` popped
        # our address, so rsp is Q again -- exactly where the read path leaves
        # it, ready for the marker counters and the shared epilogue.
        code += b"\x48\x8d\x0d\0\0\0\0"  # lea rcx, [rip+marker]
        fixups.append((len(code) - 4, b"marker"))
        code += b"\x88\x81" + struct.pack("<I", 0x1C7C)  # mov [rcx+0x1c7c], al
        code += b"\x84\xc0"  # test al, al
        code += b"\x74\x06"  # je +6 (al == 0 -> fail)
        code += b"\xff\x81" + struct.pack("<I", 0x1C74)  # inc [rcx+0x1c74] ok
        code += b"\xeb\x06"  # jmp +6
        code += b"\xff\x81" + struct.pack("<I", 0x1C78)  # inc [rcx+0x1c78] fail

    # --- epilogue ------------------------------------------------------------
    done = len(code)
    # leave the reentrancy guard (A-0027 §7.4)
    code += b"\x48\x8d\x05\0\0\0\0"  # lea rax, [rip+marker]
    mfx4 = len(code) - 4
    code += b"\xff\x88\x14\x1a\0\0"  # dec dword [rax+0x1a14]
    for p in (jne1, jne2, jne3, jne4):
        struct.pack_into("<i", code, p + 2, done - (p + 6))
    if jmiss is not None:
        struct.pack_into("<i", code, jmiss + 1, done - (jmiss + 5))
    struct.pack_into("<i", code, g2 + 1, done - (g2 + 5))
    code += b"\x48\x83\xc4\x20"  # add rsp, 0x20
    code += b"\x41\x5b\x41\x5a\x41\x59\x41\x58\x5e\x5a\x59\x58"
    code += b"\x41\x5f\x41\x5e\x5f\x5d\x5b"  # pop r11..rbx
    code += displaced  # displaced prologue of the setter, verbatim
    jmp_pos = len(code)
    code += b"\xe9\0\0\0\0"  # jmp site+dlen

    # --- data ---------------------------------------------------------------
    while len(code) % 16:
        code.append(0xCC)
    code_len = len(code)
    data_off = {}
    for name, raw in (
        (b"prop_name", prop + b"\0"),
        (b"font_name_lit", b"font_name\0"),
        (b"font_value", font_name.encode("ascii") + b"\0"),
        (b"res_menu", b"menu\0"),
        (b"res_arial", b"arial\0"),
        (b"res_regular", b"regular\0"),
        (b"filter_table", struct.pack(f"<{len(hashes)}I", *hashes)),
        (b"marker", b"\0" * MARKER_SIZE),
    ):
        data_off[name] = (len(code), len(raw) - 1)
        code += raw
    for fx in (mfx1, mfx2, mfx4):
        fixups.append((fx, b"marker"))
    blob = bytes(code)

    for disp_pos, name in fixups:
        if name == b"site_body":
            # the setter body, i.e. the first byte after the displaced pushes
            disp = (site_rva + dlen) - (blob_rva + disp_pos + 4)
        else:
            off, ln = data_off[name]
            disp = (blob_rva + off) - (blob_rva + disp_pos + 4)
        code = bytearray(blob)
        struct.pack_into("<i", code, disp_pos, disp)
        blob = bytes(code)

    blob = bytearray(blob)
    struct.pack_into(
        "<i", blob, jmp_pos + 1, (site_rva + dlen) - (blob_rva + jmp_pos + 5)
    )
    site_patch = (
        b"\xe9" + struct.pack("<i", blob_rva - (site_rva + 5)) + b"\x90" * (dlen - 5)
    )
    return (bytes(blob), site_patch, data_off[b"marker"][0], dlen, code_len)


# ---------------------------------------------------------------------------
# self-test: everything that can be checked without the game or the DLL
# ---------------------------------------------------------------------------


def audit(blob, code_len, site_rva, dlen, blob_rva):
    """Disassemble the cave and return a list of problems (empty == clean)."""
    problems = []
    ins = _disasm(blob[:code_len], blob_rva)
    got = sum(i.size for i in ins)
    if got != code_len:
        problems.append(
            f"code region: {got} of {code_len} bytes disassemble; "
            f"first undecoded byte at +{got:#x}"
        )
    lo, hi = blob_rva, blob_rva + code_len
    tail_rva = site_rva + dlen
    for i in ins:
        if bytes(blob[i.address - blob_rva : i.address - blob_rva + 2]) == b"\x00\x00":
            problems.append(
                f"+{i.address - blob_rva:#x}: {i.mnemonic} {i.op_str} -- orphan "
                "`00 00` (an imm32 written as 8 bytes; L-0034/4ac6565)"
            )
        for op in i.operands:
            if op.type == X86_OP_IMM and i.mnemonic[0] in "jl":
                # capstone reports x86 branch immediates as absolute targets
                tgt = op.imm
                if not (lo <= tgt < hi or tgt == tail_rva):
                    problems.append(
                        f"+{i.address - blob_rva:#x}: {i.mnemonic} -> {tgt:#x} "
                        "leaves the cave"
                    )
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                tgt = i.address + i.size + op.mem.disp
                if not (blob_rva <= tgt < blob_rva + len(blob)) and tgt != tail_rva:
                    problems.append(
                        f"+{i.address - blob_rva:#x}: rip-relative -> {tgt:#x} "
                        "outside the blob"
                    )
    return problems


def self_test(verbose=True):
    ok = True
    for label, site, disp in (
        ("0.9.1", SETPROP_RVA_091, DEFAULT_DISPLACED_091),
        ("0.9.0", SETPROP_RVA_090, DEFAULT_DISPLACED_090),
    ):
        blob_rva = 0xBF3000
        for prop in ("font_name", "override_font_name"):
            for write, accept, swap, stick, dump, subst, off in (
                (True, False, False, False, False, "off", None),
                (True, True, False, False, False, "off", None),
                (False, False, False, False, False, "off", None),
                (False, True, False, False, False, "off", None),
                (False, False, True, False, False, "off", None),
                (True, False, True, False, False, "off", None),
                (False, False, False, True, False, "off", None),
                (False, True, False, True, False, "off", None),
                (False, True, False, 0x04, False, "off", None),
                (False, True, False, 0x10, False, "off", None),
                (False, True, False, False, True, "off", None),
                (False, True, False, False, True, "dry", None),
                (False, True, False, False, True, "write", None),
                (False, True, False, False, True, "write", 0x60),
            ):
                blob, patch, marker_off, dlen, code_len = build_caption_font_hook(
                    blob_rva,
                    site,
                    "menu",
                    prop,
                    write=write,
                    displaced=disp,
                    accept_all=accept,
                    swap_arial=swap,
                    swap_sticky=stick,
                    ctl_dump=dump,
                    font_subst=subst,
                    subst_offset=off,
                )
                tag = (
                    f"{label} {prop} write={int(write)} all={int(accept)} "
                    f"swap={int(swap)} sticky={int(stick)} dump={int(dump)} "
                    f"subst={subst} off={off}"
                )
                problems = audit(blob, code_len, site, dlen, blob_rva)
                if len(patch) != len(disp):
                    problems.append(
                        f"site patch is {len(patch)} bytes, displaced {len(disp)}"
                    )
                if patch[0] != 0xE9:
                    problems.append("site patch does not start with jmp rel32")
                jmp_tgt = site + 5 + struct.unpack_from("<i", patch, 1)[0]
                if jmp_tgt != blob_rva:
                    problems.append(f"site patch jumps to {jmp_tgt:#x}, not the cave")
                if not (0 <= marker_off < len(blob)):
                    problems.append("marker offset outside the blob")
                for field in (
                    WRITE_CALLS,
                    WRITE_OK,
                    WRITE_FAIL,
                    WRITE_LAST,
                    SUBST_WRITES,
                    SWAP_FIXES,
                    STATIC_DONE,
                    CTL_FLAGS,
                    NODE_REC + 4 * 0x40 - 1,
                    BANKS + 0x100 - 1,
                    CTL_VAL_DUMP + 0x100 - 1,
                ):
                    if field >= MARKER_SIZE:
                        problems.append(f"marker field {field:#x} outside the marker")
                if b"\0" * MARKER_SIZE not in blob:
                    problems.append("marker is not MARKER_SIZE zero bytes")
                if b"menu\0" not in blob:
                    problems.append("font value literal missing from the blob")
                if prop.encode("ascii") + b"\0" not in blob:
                    problems.append("prop name literal missing from the blob")
                if problems:
                    ok = False
                    for p in problems:
                        print(f"FAIL {tag}: {p}")
                elif verbose:
                    print(
                        f"ok   {tag}: cave {len(blob)} B "
                        f"(code {code_len} B), site patch {len(patch)} B, "
                        f"marker +{marker_off:#x}"
                    )
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--dump-asm", metavar="PATH", default=None)
    ap.add_argument("--setter-rva", default=hex(SETPROP_RVA_091))
    ap.add_argument("--blob-rva", default="0xbf3000")
    ap.add_argument("--font", default="menu")
    ap.add_argument(
        "--prop",
        default="font_name",
        choices=("font_name", "override_font_name"),
    )
    ap.add_argument("--no-write", action="store_true", help="read-only probe (bag15)")
    ap.add_argument(
        "--swap-arial-slot",
        action="store_true",
        help="L-0035: one-time [Fonts+0x08] = [Fonts+0x0c] (arial <- menu)",
    )
    ap.add_argument(
        "--ctl-dump",
        action="store_true",
        help=(
            "L-0035: dump the font registry (Fonts inline and dereferenced, "
            "the 32 bank bases, the four resolved nodes with their names) "
            "and the first 0x100 bytes of the matched caption control and of "
            "the first local_text control into the marker"
        ),
    )
    ap.add_argument(
        "--font-subst",
        choices=("off", "dry", "write"),
        default="off",
        help=(
            "L-0035: in every control that passes the caption filter, "
            "replace each dword in [control, control+0x100) equal to the "
            "current `arial` ref by the `menu` ref. 'dry' only counts "
            "matches and records their offsets; 'write' also substitutes "
            "and bumps the menu node refcount"
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
        "--swap-arial-sticky",
        action="store_true",
        help=(
            "L-0035: like --swap-arial-slot, but the registry pointer is "
            "re-read from exe+0x1733260 and the store is re-applied on "
            "every setter call, because Fonts::Fonts rebuilds the slots "
            "after a one-shot write"
        ),
    )
    ap.add_argument(
        "--swap-sticky-slot",
        default=None,
        metavar="HEX",
        help=(
            "L-0035: sticky swap of a chosen Fonts slot instead of arial: "
            "0x04 regular, 0x08 arial (default), 0x0c menu, 0x10 console. "
            "The live dump in the L-0035 runlog has regular = 0, so the slot "
            "the UI actually falls back from may be regular"
        ),
    )
    ap.add_argument(
        "--site-head",
        default=None,
        metavar="HEX",
        help="the bytes the site jmp overwrites, e.g. 4053555741564157",
    )
    args = ap.parse_args()

    site = int(args.setter_rva, 16)
    blob_rva = int(args.blob_rva, 16)
    disp = bytes.fromhex(args.site_head) if args.site_head else DEFAULT_DISPLACED_091
    s_off = int(args.subst_offset, 16) if args.subst_offset else None
    sticky_slot = False
    if args.swap_arial_sticky:
        sticky_slot = 0x08
    if args.swap_sticky_slot:
        sticky_slot = int(args.swap_sticky_slot, 16)
    blob, patch, marker_off, dlen, code_len = build_caption_font_hook(
        blob_rva,
        site,
        args.font,
        args.prop,
        write=not args.no_write,
        displaced=disp,
        swap_arial=args.swap_arial_slot,
        swap_sticky=sticky_slot,
        ctl_dump=args.ctl_dump,
        font_subst=args.font_subst,
        subst_offset=s_off,
    )
    if args.dump_asm:
        lines = [
            f"; setter {site:#x} -> cave {blob_rva:#x}, displaced {dlen} B, "
            f"prop {args.prop!r} = {args.font!r}, write={not args.no_write}, "
            f"swap={args.swap_arial_slot}, sticky={sticky_slot}, "
            f"dump={args.ctl_dump}, subst={args.font_subst}, "
            f"off={args.subst_offset}",
            f"; site patch: {patch.hex()}",
            "",
        ]
        for i in _disasm(blob[:code_len], blob_rva):
            raw = blob[i.address - blob_rva : i.address - blob_rva + i.size]
            lines.append(f"{i.address:08x}  {raw.hex():<24}  {i.mnemonic} {i.op_str}")
        Path(args.dump_asm).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {args.dump_asm} ({code_len} bytes of code, {len(blob)} total)")
    if args.self_test or not args.dump_asm:
        print(
            f"cave {len(blob)} B (code {code_len} B), site patch {len(patch)} B, "
            f"setter {site:#x} + {dlen} -> body {site + dlen:#x}, "
            f"marker +{marker_off:#x}"
        )
        ok = self_test()
        print("self-test:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
