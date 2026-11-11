#!/usr/bin/env python3
"""Find every place in MetroExodus.exe that decodes a font ref.

L-0035 asks for "the RVA of the resolver".  A ref is ``(bank << 24) | off``
and the 32 bank bases live at ``exe+0x175F140``, so a decode is at most

    lea  rax, [rip + d]          ; -> exe+0x175F140
    mov  rax, [rax + r64*8]      ; bank base     (SIB, scale 8)
    add  rax, r64                ; + (ref & 0xffffff)

That is two or three instructions with no call, so there is probably **no
single resolver function to hook** -- the sequence is inlined at every use.
This tool settles it by listing the places that touch the tables.

Usage (needs the exe, which is not in this repository)::

    python tools/scan_ref_decode.py path/to/MetroExodus.exe

    --banks RVA    bank table (default 0x175F140)
    --fonts RVA    inline Fonts array (default 0x1733240)
    --json PATH    write the hits as JSON
"""
from __future__ import annotations

import argparse
import json
import struct
import sys

DEFAULT_BANKS = 0x175F140  # 32 qword bank bases
DEFAULT_FONTS = 0x1733240  # inline Fonts array
DEFAULT_FONTS_PTR = 0x1733260  # pointer to the live Fonts object
DEFAULT_MANAGER = 0x175F138  # intern manager used by Fonts::Fonts


def _cs():
    import capstone

    return capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)


def scan(data, text_rva, targets, detail=True):
    """Linear-sweep ``data`` (mapped at ``text_rva``) for rip-relative hits.

    Returns a list of ``{rva, bytes, text, target, insn_end}``.  Only
    instructions whose rip-relative operand points into ``targets`` are
    reported; both loads and stores are kept, because a store into the
    table matters as much as a load from it.
    """
    md = _cs()
    md.detail = bool(detail)
    hits = []
    for insn in md.disasm(bytes(data), text_rva):
        for op in insn.operands:
            if op.type != 3:  # X86_OP_MEM
                continue
            mem = op.mem
            if mem.base != 41:  # X86_REG_RIP
                continue
            tgt = insn.address + insn.size + mem.disp
            if tgt in targets:
                hits.append(
                    {
                        "rva": insn.address,
                        "insn_end": insn.address + insn.size,
                        "target": tgt,
                        "text": f"{insn.mnemonic} {insn.op_str}",
                        "bytes": bytes(
                            data[insn.address - text_rva : insn.address - text_rva + insn.size]
                        ).hex(),
                    }
                )
                break
    return hits


def scan_pe(path, targets):
    """Sweep the executable sections of a PE image."""
    import pefile

    pe = pefile.PE(path, fast_load=True)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    out = []
    for sect in pe.sections:
        if not (sect.Characteristics & 0x20000000):  # IMAGE_SCN_MEM_EXECUTE
            continue
        data = sect.get_data()
        rva = sect.VirtualAddress
        out.append((sect.Name.rstrip(b"\0").decode("ascii", "replace"), rva, len(data)))
        for h in scan(data, image_base + rva, {image_base + t for t in targets}):
            h["section"] = out[-1][0]
            yield h


# ---------------------------------------------------------------------------
# self-test: the sweep logic on hand-built code, no PE needed
# ---------------------------------------------------------------------------

# lea rax, [rip + d] -> the bank table, then mov rax, [rax + rbx*8]
_BANK_LOAD = bytes.fromhex("488d05") + struct.pack("<i", 0) + bytes.fromhex("488b04d8")
# mov ecx, [rip + d] -> the inline Fonts array
_FONTS_LOAD = bytes.fromhex("8b0d") + struct.pack("<i", 0)
# mov rax, [rip + d] -> the Fonts pointer slot
_PTR_LOAD = bytes.fromhex("488b05") + struct.pack("<i", 0)


def self_test(verbose=True):
    base = 0x180000000
    banks = DEFAULT_BANKS
    fonts = DEFAULT_FONTS
    ptr = DEFAULT_FONTS_PTR

    # every target is a VA in this test, an RVA in the real image
    v_bank, v_fonts, v_ptr = base + banks, base + fonts, base + ptr

    blob = bytearray(b"\x90" * 16)
    off_bank = len(blob)
    blob += _BANK_LOAD
    # rip after the 7-byte lea
    struct.pack_into("<i", blob, off_bank + 3, v_bank - (base + off_bank + 7))

    blob += b"\x90" * 8
    off_fonts = len(blob)
    blob += _FONTS_LOAD  # 6 bytes: disp32 is the last field
    struct.pack_into("<i", blob, off_fonts + 2, v_fonts - (base + off_fonts + 6))

    blob += b"\x90" * 8
    off_ptr = len(blob)
    blob += _PTR_LOAD  # 7 bytes
    struct.pack_into("<i", blob, off_ptr + 3, v_ptr - (base + off_ptr + 7))

    blob += b"\x90" * 32
    hits = scan(bytes(blob), base, {v_bank, v_fonts, v_ptr})
    got = sorted(h["target"] - base for h in hits)
    want = sorted([banks, fonts, ptr])
    ok = got == want
    if verbose:
        print(
            f"{'ok  ' if ok else 'FAIL'} rip sweep: found "
            f"{[hex(t) for t in got]}, expected {[hex(t) for t in want]}"
        )
        for h in hits:
            print(f"     +{h['rva'] - base:#x}  {h['text']}")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("exe", nargs="?", help="path to MetroExodus.exe")
    ap.add_argument("--banks", default=hex(DEFAULT_BANKS))
    ap.add_argument("--fonts", default=hex(DEFAULT_FONTS))
    ap.add_argument("--fonts-ptr", default=hex(DEFAULT_FONTS_PTR))
    ap.add_argument("--manager", default=hex(DEFAULT_MANAGER))
    ap.add_argument("--json", default=None, metavar="PATH")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test or not args.exe:
        ok = self_test()
        print("self-test:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    targets = {
        int(args.banks, 16),
        int(args.fonts, 16),
        int(args.fonts_ptr, 16),
        int(args.manager, 16),
    }
    hits = list(scan_pe(args.exe, targets))
    hits.sort(key=lambda h: h["rva"])
    for h in hits:
        print(f"{h['rva']:#x}  {h['section']:<8} {h['text']}")
    print(f"{len(hits)} site(s) touching the font tables")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(hits, fh, indent=1)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
