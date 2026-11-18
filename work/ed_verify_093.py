# -*- coding: utf-8 -*-
"""Proverki 1-5 dlja pravok A (skriptom, ne na glaz). Log -> work/ed_verify.log"""

import json
import re
import subprocess
import sys

TSV = "kit093/ru/strings-0.9.3.tsv"
UI2 = "kit093/ru/ui2-0.9.3.json"
MODEL = "work/menu_model.json"
OUT = "work/ed_verify.log"
LOG = []


def w(s=""):
    LOG.append(s)


def head(data):
    return subprocess.run(
        ["git", "show", "HEAD:" + data],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")


def load_tsv(text):
    if text.endswith("\n"):
        text = text[:-1]
    lines = text.split("\n")
    rows = []
    for l in lines:
        rows.append(l.split("\t") if not l.startswith("#") else [l])
    return lines, rows


def num(s, limit_or_path):
    return s


CYR = "".join(chr(c) for c in range(0x410, 0x450) if c not in (0x401, 0x451))
EXTRA = set("«»©®–—‘’“”…™")
ALLOWED = set("".join(chr(c) for c in range(0x20, 0x7F)) + CYR + "\n") | EXTRA
BAD_RE = re.compile("[Ёё№°„]")
PH = re.compile(r"\{[^{}]*\}")
TAG = re.compile(r"<[^<>]*>")


def bad_chars(s):
    out = []
    for ch in s:
        if ch in " \t":
            continue
        if ch not in ALLOWED:
            out.append(ch)
    return out


def orig_mismatch(base, other):
    """Kategorii rashozhdenij perevoda s originalom (podstanovki/tegi/skobki).

    Tegi <dominant>/<nondominant> perevodjatsja (pravilo), pojetomu oni iskljucheny.
    """

    def tags(s):
        return sorted(
            t.lower()
            for t in TAG.findall(s)
            if t[1:-1].strip().lower() not in ("dominant", "nondominant")
        )

    out = set()
    if sorted(PH.findall(base)) != sorted(PH.findall(other)):
        out.add("podstanovki")
    if tags(base) != tags(other):
        out.add("tegi")
    if (base.count("["), base.count("]")) != (other.count("["), other.count("]")):
        out.add("skobki")
    return out


def esc(s):
    return s.replace("\r", "").replace("\n", "\\n").replace("|", "/")


def main():
    old_tsv, new_tsv = head(TSV), open(TSV, encoding="utf-8", newline="").read()
    old_u2, new_u2 = head(UI2), open(UI2, encoding="utf-8", newline="").read()
    w(
        "perevody strok: tsv CR %d (git: %d), ui2 CR %d (git: %d) -- sravnenie nizhe po LF"
        % (
            new_tsv.count("\r"),
            old_tsv.count("\r"),
            new_u2.count("\r"),
            old_u2.count("\r"),
        )
    )
    old_tsv, new_tsv = old_tsv.replace("\r\n", "\n"), new_tsv.replace("\r\n", "\n")
    old_u2, new_u2 = old_u2.replace("\r\n", "\n"), new_u2.replace("\r\n", "\n")

    w("=== 3. Stroenie fajlov ===")
    for name, o, n in (("tsv", old_tsv, new_tsv), ("ui2", old_u2, new_u2)):
        w(
            "%s: LF %d->%d, CR %d->%d, TAB %d->%d, len %d->%d"
            % (
                name,
                o.count("\n"),
                n.count("\n"),
                o.count("\r"),
                n.count("\r"),
                o.count("\t"),
                n.count("\t"),
                len(o),
                len(n),
            )
        )
    w(
        "tsv: strok s # : %d -> %d"
        % (
            sum(1 for l in old_tsv.split("\n") if l.startswith("#")),
            sum(1 for l in new_tsv.split("\n") if l.startswith("#")),
        )
    )

    o_lines, o_rows = load_tsv(old_tsv)
    n_lines, n_rows = load_tsv(new_tsv)
    w("tsv: strok dannih %d -> %d" % (len(o_rows), len(n_rows)))

    model = json.load(open(MODEL, encoding="utf-8"))
    cap_addr = {}
    val_addr = {}
    for e in model:
        cap_addr[e["caption"]] = e["addr"]
        for v in e.get("values", []):
            val_addr.setdefault(v["text"], e["addr"])

    w("")
    w("=== 1+2. Pravki v tsv ===")
    w("| RVA | original | bylo | stalo | dlina/limit | simvoly |")
    w("| --- | --- | --- | --- | --- | --- |")
    stat = {"cap": 0, "val": 0}
    for i, (o, n) in enumerate(zip(o_rows, n_rows)):
        if len(o) != 3 or o == n:
            continue
        rva, en, ru_old = o
        _, _, ru_new = n
        role = "cap" if en in cap_addr else ("val" if en in val_addr else "cap")
        lim = 22 if role == "cap" else 18
        stat[role] += 1
        b = bad_chars(ru_new)
        w(
            "| %s | %s | %s | %s | %d/%d | %s |"
            % (
                rva,
                en,
                ru_old,
                ru_new,
                len(ru_new),
                lim,
                ("NET: " + " ".join(b)) if b else "ok",
            )
        )
        if len(ru_new) > lim:
            w("  ! prevyshen limit: %s (%d > %d)" % (en, len(ru_new), lim))
        old_mm, new_mm = orig_mismatch(en, ru_old), orig_mismatch(en, ru_new)
        fresh = sorted(new_mm - old_mm)
        if fresh:
            w(
                "  ! %s: novoe rashozhdenie s originalom: %s (bylo: %s)"
                % (en, ", ".join(fresh), ",".join(sorted(old_mm)) or "ok")
            )

    w("")
    w("=== Pravki v ui2 ===")
    od = json.loads(old_u2)
    nd = json.loads(new_u2)
    by_o = {}
    by_n = {}
    for cat in ("popups", "options", "hints", "hintpages"):
        for r in od[cat]:
            by_o[(cat, r["index"])] = r
        for r in nd[cat]:
            by_n[(cat, r["index"])] = r

    ph = re.compile(r"\{[^{}]*\}")
    tag = re.compile(r"<[^<>]*>")

    ph = PH
    tag = TAG

    def mm(base, other):
        return orig_mismatch(base, other)

    changed = 0
    problems = []
    rows = []
    orig_notes = []
    for key in by_o:
        ro, rn = by_o[key], by_n[key]
        cat, idx = key
        for f in ("ru", "ru_title"):
            a, b = ro.get(f), rn.get(f)
            if a == b or b is None:
                continue
            changed += 1
            ph_o, ph_n = sorted(ph.findall(a)), sorted(ph.findall(b))
            tg_o = sorted(t.lower() for t in tag.findall(a))
            tg_n = sorted(t.lower() for t in tag.findall(b))
            br_o = [x.count("[") for x in (a,)]
            if ph_o != ph_n:
                problems.append(
                    "%s#%s.%s: podstanovki %s -> %s" % (cat, idx, f, ph_o, ph_n)
                )
            if tg_o != tg_n:
                problems.append("%s#%s.%s: tegi %s -> %s" % (cat, idx, f, tg_o, tg_n))
            if a.count("[") != b.count("[") or a.count("]") != b.count("]"):
                problems.append(
                    "%s#%s.%s: skobki [] %d/%d -> %d/%d"
                    % (
                        cat,
                        idx,
                        f,
                        a.count("["),
                        a.count("]"),
                        b.count("["),
                        b.count("]"),
                    )
                )
            orig = ro.get("orig") or ""
            if orig:
                old_mm, new_mm = mm(orig, a), mm(orig, b)
                fresh = sorted(new_mm - old_mm)
                if fresh:
                    problems.append(
                        "%s#%s.%s: novoe rashozhdenie s originalom: %s"
                        % (cat, idx, f, ", ".join(fresh))
                    )
                if new_mm:
                    orig_notes.append(
                        "sverka s orig %s#%s.%s: bylo %s, stalo %s"
                        % (
                            cat,
                            idx,
                            f,
                            ",".join(sorted(old_mm)) or "ok",
                            ",".join(sorted(new_mm)) or "ok",
                        )
                    )
            bc = bad_chars(b)
            if bc:
                problems.append(
                    "%s#%s.%s: zapreshchennye simvoly %r" % (cat, idx, f, bc)
                )
            if cat == "options" and len(b) > 150:
                problems.append("%s#%s.%s: dlina %d > 150" % (cat, idx, f, len(b)))
            if cat == "hints" and len(b) > 150:
                problems.append("%s#%s.%s: dlina %d > 150" % (cat, idx, f, len(b)))
            rows.append((cat, idx, f, a, b))

    w("izmeneno znachenij: %d" % changed)
    w("| gde | bylo | stalo | dlina |")
    w("| --- | --- | --- | --- |")
    for cat, idx, f, a, b in rows:
        w("| %s#%s.%s | %s | %s | %d |" % (cat, idx, f, esc(a), esc(b), len(b)))
    w("")
    if orig_notes:
        w("sverka novyh tekstov s originalom (tolko gde est rashozhdenie):")
        for s in orig_notes:
            w("  " + s)
    else:
        w("sverka s originalom: novyh rashozhdenij net")
    w("")
    if problems:
        w("PROBLEMY:")
        for p in problems:
            w("  ! " + p)
    else:
        w("problemy 1-2: net")

    w("")
    w("=== 4. Upominanija znachenij v podskazkah ===")
    joined = [
        (cat, r["index"], f, r[f])
        for cat in ("popups", "options", "hints", "hintpages")
        for r in nd[cat]
        for f in ("ru", "ru_title")
        if r.get(f)
    ]
    for word, where in (
        ("УДЕРЖАНИЕ", "znachenie HOLD"),
        ("ПЕРЕКЛЮЧЕНИЕ", "znachenie TOGGLE"),
        ("ПО ГОЛОВЕ", "znachenie FOLLOW HEAD"),
        ("ПО КОМНАТЕ", "znachenie ROOM-SCALE"),
        ("ВЕДУЩАЯ РУКА", "zagolovok DOMINANT HAND"),
        ("ПО ГОРИЗОНТУ", "LEVEL"),
        ("К ОБЗОРУ", "FIXED TO VIEW"),
        ("НАПРАВЛЕНИЕ ПОПАДАНИЯ", "HIT DIRECTION"),
    ):
        hits = [
            "%s#%s.%s" % (c, i, f) for c, i, f, t in joined if word.lower() in t.lower()
        ]
        w("%s (%s): %s" % (word, where, ", ".join(hits) if hits else "net upominanij"))
    for stale in ("УДЕРЖ.", "ПЕРЕКЛ.", "СЛЕДОВАТЬ ЗА ГОЛОВОЙ"):
        hits = ["%s#%s.%s" % (c, i, f) for c, i, f, t in joined if stale in t]
        w("ustarevshee '%s': %s" % (stale, ", ".join(hits) if hits else "net"))

    w("")
    w("=== 5. Ostavshiesja 'vtor...' v russkih tekstah ===")
    pat = re.compile(r"втор", re.I)
    for c, i, f, t in joined:
        for m in pat.finditer(t):
            a = max(0, m.start() - 30)
            b = min(len(t), m.end() + 30)
            w("%s#%s.%s: ...%s..." % (c, i, f, esc(t[a:b])))
    w("")
    for bad in (
        "второй рукой",
        "второго бедра",
        "вторым плечом",
        "второй стороны",
        "второго плеча",
        "вторую руку",
        "второй руке",
    ):
        hits = []
        for c, i, f, t in joined:
            if bad in t.lower():
                hits.append("%s#%s.%s" % (c, i, f))
        w("grep '%s': %s" % (bad, ", ".join(hits) if hits else "chisto"))
    tsv_bad = [r[0] for r in n_rows if len(r) == 3 and pat.search(r[2])]
    w("tsv 'vtor...': %s" % (", ".join(tsv_bad) if tsv_bad else "net"))

    open(OUT, "w", encoding="utf-8").write("\n".join(LOG) + "\n")
    print("log: " + OUT, "problems:", len(problems))


main()
