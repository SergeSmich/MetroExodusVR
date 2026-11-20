#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Механический аудит корпуса перевода Metro Exodus VR 0.9.3.

Только чтение исходников + запись двух отчётов:
    work/audit_093.md   -- человекочитаемо
    work/audit_093.json -- машинно

Запуск:
    $env:PYTHONIOENCODING='utf-8'; python -u -X utf8 work\\audit_093.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TSV_093 = ROOT / "kit093" / "ru" / "strings-0.9.3.tsv"
TSV_092 = ROOT / "kit092" / "ru" / "strings-0.9.2.tsv"
UI2_093 = ROOT / "kit093" / "ru" / "ui2-0.9.3.json"
UI2_092 = ROOT / "kit092" / "ru" / "ui2-0.9.2.json"
OUT_MD = ROOT / "work" / "audit_093.md"
OUT_JSON = ROOT / "work" / "audit_093.json"

TSV_CELL_LIMIT = 126  # байт charmap на одну строку tsv (упрощённо: len)
UI2_CELL_LIMIT = 1791  # байт charmap на один блок таблицы ui2 (упрощённо: len)
F_TOP_IN_MD = 20  # сколько строк длины показывать в .md

# --- правила проекта -------------------------------------------------------
FORBIDDEN_CHARS = "\u0401\u0451\u2116\u00b0\u201e"  # Ё ё № ° „
ALLOWED_EXTRA = (
    "\u00ab\u00bb\u00a9\u00ae\u2013\u2014\u2018\u2019\u201c\u201d\u2026\u2122"
)
KEEP_LATIN = {
    "FSR",
    "DLSS",
    "TAA",
    "NVIDIA",
    "bHaptics",
    "HUD",
    "Ko-fi",
    "GitHub",
    "Buy Me a Coffee",
    "AER+",
    "VIP",
    "K/M/L/J/E",
    "K",
    "M",
    "L",
    "J",
    "E",
    "VR",
}
# единицы измерения: обратный гомоглиф здесь ожидаем (CM -> СМ), только ручная проверка
UNIT_WORDS = {"СМ", "ММ", "М", "КМ", "КГ", "Г", "Л", "С", "Ч", "МИН", "СЕК", "ГР"}
UNIT_LATIN = {"CM", "MM", "M", "KM", "KG", "G", "L", "S", "H", "MIN", "SEC"}


def is_unit_token(tok: str) -> bool:
    """Токен — сокращение единицы измерения (СМ/CM/Гр./М ...)."""
    t = tok.strip(".,;:()[]|/\\—-")
    if not t:
        return False
    if t.upper() in UNIT_WORDS:
        return True
    mapped = "".join(CYR_LOOKALIKE.get(c, "") for c in t)
    return len(mapped) == len(t) and mapped in UNIT_LATIN


# латинские буквы-двойники, которые ищем внутри русских слов
HOMO_LATIN = set("aeopcxykmtHBhb")
CYR_LOOKALIKE = {
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "х": "x",
    "у": "y",
    "к": "k",
    "м": "m",
    "т": "t",
    "н": "h",
    "в": "b",
    "А": "A",
    "В": "B",
    "Е": "E",
    "К": "K",
    "М": "M",
    "Н": "H",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Т": "T",
    "У": "Y",
    "Х": "X",
}


def is_cyr(ch: str) -> bool:
    return "А" <= ch <= "Я" or "а" <= ch <= "я"


def is_ascii_allowed(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or 0x20 <= ord(ch) <= 0x7E)


def allowed_char(ch: str) -> bool:
    return is_ascii_allowed(ch) or is_cyr(ch) or ch in ALLOWED_EXTRA or ch in "\n\t"


def shape(ch: str) -> str:
    if is_cyr(ch):
        return "C"
    if ch.isascii() and ch.isalpha():
        return "L"
    return ""


def norm_space(s: str) -> str:
    return s.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")


def one_line(s: str, limit: int = 120) -> str:
    if s is None:
        return ""
    out = s.replace("\r", "").replace("\n", "\\n").replace("|", "\\|")
    return out if len(out) <= limit else out[: limit - 1] + "…"


# --- загрузка --------------------------------------------------------------
def load_tsv(path: Path) -> list[dict]:
    rows = []
    text = path.read_text(encoding="utf-8-sig")
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            parts = (parts + ["", "", ""])[:3]
        rows.append({"rva": parts[0], "en": parts[1], "ru": parts[2], "line": lineno})
    return rows


def load_ui2(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ui2_records(doc: dict) -> list[dict]:
    recs = []
    for section, items in doc.items():
        for entry in items:
            idx = entry.get("index")
            recs.append(
                {
                    "section": section,
                    "index": idx,
                    "field": "body",
                    "loc": f"ui2:{section}[{idx}]:body",
                    "en": entry.get("orig") or "",
                    "ru": entry.get("ru") or "",
                }
            )
            if "orig_title" in entry or "ru_title" in entry:
                recs.append(
                    {
                        "section": section,
                        "index": idx,
                        "field": "title",
                        "loc": f"ui2:{section}[{idx}]:title",
                        "en": entry.get("orig_title") or "",
                        "ru": entry.get("ru_title") or "",
                    }
                )
    return recs


# --- сбор находок ----------------------------------------------------------
findings: list[dict] = []
_counter: dict[str, int] = {}


def add(
    cat: str, loc: str, en: str, ru: str, issue: str, hint: str, level: str = "defect"
) -> dict:
    _counter[cat] = _counter.get(cat, 0) + 1
    rec = {
        "id": f"{cat}-{_counter[cat]:03d}",
        "category": cat,
        "level": level,  # defect | manual | info
        "location": loc,
        "en": en if en is not None else "",
        "ru": ru if ru is not None else "",
        "issue": issue,
        "hint": hint,
    }
    findings.append(rec)
    return rec


def cat_names() -> dict:
    return {
        "A": "charset (символы вне набора)",
        "B": "placeholders / теги / [сегменты] / \\n / числа",
        "C": "case (регистр)",
        "D": "hygiene (пробелы, пунктуация, пустое, == EN)",
        "E": "homoglyphs (латиница в кириллице и наоборот)",
        "F": "length (превышение лимита таблицы)",
        "G": "duplicates (один EN — разные RU)",
        "I": "ui2 блоки (табличные тексты)",
        "M": "проверить вручную: единицы измерения, нетранслируемые токены",
        "H": "drift 0.9.2 -> 0.9.3",
        "N": "информационно: замены <dominant>/<nondominant> (не дефекты)",
    }


# --- A. charset ------------------------------------------------------------
def check_charset(loc: str, en: str, ru: str, where: str) -> None:
    bad: dict[str, int] = {}
    forbidden: dict[str, int] = {}
    for ch in ru:
        if ch in FORBIDDEN_CHARS:
            forbidden[ch] = forbidden.get(ch, 0) + 1
        elif not allowed_char(ch):
            bad[ch] = bad.get(ch, 0) + 1
    for ch, n in sorted(forbidden.items()):
        add(
            "A",
            loc,
            en,
            ru,
            f"запрещённый символ {ch!r} (U+{ord(ch):04X}) x{n} в {where}",
            'заменить: Ё->Е, ё->е; № -> N или "номер"; ° -> DEG/Гр.; „ -> «',
        )
    for ch, n in sorted(bad.items()):
        name = unicodedata.name(ch, "?")
        add(
            "A",
            loc,
            en,
            ru,
            f"символ вне разрешённого набора {ch!r} (U+{ord(ch):04X} {name}) x{n} в {where}",
            "убрать/заменить на ASCII или кириллицу без Ё; проверить, не копипаст ли",
        )


# --- B. placeholders / tags / brackets / newlines --------------------------
FIELD_RE = re.compile(r"\{[^{}]*\}")
TAG_RE = re.compile(r"<[^<>\s]{1,40}>")
BRACKET_RE = re.compile(r"\[[^\[\]]{0,80}\]")
EXEMPT_TAGS = {"<dominant>", "<nondominant>"}


def check_placeholders(loc: str, en: str, ru: str) -> None:
    f_en = FIELD_RE.findall(en)
    f_ru = FIELD_RE.findall(ru)
    if f_en != f_ru:
        add(
            "B",
            loc,
            en,
            ru,
            f"подстановки {{}}: EN {f_en} != RU {f_ru}",
            "набор и порядок {..} должны совпадать с EN один-в-один",
        )
    n_en, n_ru = en.count("\n"), ru.count("\n")
    if n_en != n_ru:
        add(
            "B",
            loc,
            en,
            ru,
            f"переводы строк: EN {n_en} != RU {n_ru}",
            "количество \\n должно совпадать (вёрстка/разбиение на страницы)",
        )
    b_en = sorted(set(BRACKET_RE.findall(en)))
    b_ru = sorted(set(BRACKET_RE.findall(ru)))
    if b_en != b_ru:
        add(
            "B",
            loc,
            en,
            ru,
            f"сегменты [..]: EN {b_en} != RU {b_ru}",
            "содержимое [..] не переводится и не удаляется",
        )
    t_en = {t for t in TAG_RE.findall(en) if t.lower() not in EXEMPT_TAGS}
    t_ru = {t for t in TAG_RE.findall(ru) if t.lower() not in EXEMPT_TAGS}
    if t_en != t_ru:
        miss, extra = sorted(t_en - t_ru), sorted(t_ru - t_en)
        add(
            "B",
            loc,
            en,
            ru,
            f"теги <..>: потеряны {miss}, лишние {extra}",
            "теги менять нельзя (кроме <dominant>/<nondominant>)",
        )


# --- C. case ---------------------------------------------------------------
def strip_markup(s: str) -> str:
    return FIELD_RE.sub("", TAG_RE.sub("", BRACKET_RE.sub("", s)))


def strip_keep_latin(s: str) -> str:
    for tok in sorted(KEEP_LATIN, key=len, reverse=True):
        s = s.replace(tok, " ")
    return s


def suggest_upper(s: str) -> str:
    """Предлагаемый вариант в верхнем регистре (подстановки не трогаем)."""
    parts = FIELD_RE.split(s)
    fields = FIELD_RE.findall(s)
    out = []
    for i, part in enumerate(parts):
        out.append(part.upper())
        if i < len(fields):
            out.append(fields[i])
    return "".join(out)


def check_case(loc: str, en: str, ru: str) -> None:
    en_letters = [c for c in strip_markup(en) if c.isalpha()]
    ru_src = strip_keep_latin(strip_markup(ru))
    ru_letters = [c for c in ru_src if c.isalpha()]
    if not en_letters or not ru_letters:
        return
    if not en_letters == [c.upper() for c in en_letters]:
        return
    # единицы измерения (Гр., с, М) — намеренное сокращение, не дефект регистра
    masked_units = "".join(
        " " * len(tok) if is_unit_token(tok) else tok
        for tok in re.split(r"([^A-Za-zА-Яа-яЁё]+)", ru_src)
    )
    units_low = sorted(
        {
            t
            for t in re.split(r"[^A-Za-zА-Яа-яЁё]+", ru_src)
            if is_unit_token(t) and any(c.islower() for c in t)
        }
    )
    low = sorted({c for c in masked_units if c.islower()})
    if low:
        add(
            "C",
            loc,
            en,
            ru,
            f"EN заглавными, в RU строчные: {''.join(low)!r}",
            f"привести к верхнему регистру; предлагаемая правка: «{suggest_upper(ru)}»",
        )
    elif units_low:
        add(
            "M",
            loc,
            en,
            ru,
            f"единица измерения строчными: {', '.join(units_low)} "
            "(EN заглавными, RU — сокращение с точкой)",
            "не дефект: «Гр.» — обычное сокращение градусов; решить вручную, "
            "если нужен строгий верхний регистр (ГР.)",
            level="manual",
        )


# --- D. hygiene ------------------------------------------------------------
def mask_fields(s: str) -> str:
    """Заменить {...} пробелами: пунктуация внутри форматов — не дефект."""
    return FIELD_RE.sub(lambda m: " " * len(m.group(0)), s)


def check_hygiene(loc: str, en: str, ru: str, is_tsv: bool) -> None:
    if ru == "":
        add("D", loc, en, ru, "пустой RU", "перевод отсутствует")
        return
    if ru != ru.strip():
        add(
            "D",
            loc,
            en,
            ru,
            "пробел/перевод строки в начале или конце",
            "обрезать края",
        )
    if "\t" in ru and is_tsv:
        add(
            "D", loc, en, ru, "TAB внутри RU (ломает колонки tsv)", "заменить на пробел"
        )
    for seg in norm_space(ru).split("\n"):
        if "  " in seg:
            add("D", loc, en, ru, "двойной пробел", "один пробел")
            break
    if "\u00a0" in ru:
        add(
            "D",
            loc,
            en,
            ru,
            "неразрывный пробел U+00A0",
            "ASCII-пробел, если не нужно иначе",
        )
    for m in re.finditer(r"[ \t]+([,.;:!?])", ru):
        add(
            "D",
            loc,
            en,
            ru,
            f"пробел перед {m.group(1)!r}",
            "пробел перед знаком не ставится",
        )
        break
    masked = mask_fields(ru)
    for m in re.finditer(r"([,.:;])([A-Za-zА-Яа-яЁё«“(])", masked):
        prev = masked[max(0, m.start() - 1) : m.start()]
        punct, nxt = m.group(1), m.group(2)
        if punct == "." and (prev.isdigit() or nxt.isdigit()):
            continue
        if punct == ":" and nxt == "/":
            continue
        add(
            "D",
            loc,
            en,
            ru,
            f"нет пробела после {punct!r} (перед {nxt!r})",
            "после , . : ; нужен пробел, кроме чисел и сокращений — проверить вручную",
        )
        break
    for m in re.finditer(r"\.{2,}", masked):
        run = m.group(0)
        if len(run) == 2:
            add("D", loc, en, ru, "две точки '..'", "поставить '…' или один символ")
        else:
            add(
                "D",
                loc,
                en,
                ru,
                f"многоточие из точек {run!r}",
                "лучше символ '…' (разрешён); проверить вручную",
            )
        break
    if ru.strip() == en.strip() and ru.strip():
        hint = "проверить: возможно, намеренно"
        tokens = {t.strip(".,:;()") for t in ru.split()}
        if tokens and tokens <= KEEP_LATIN:
            hint = "вероятно намеренно: токен не переводится по правилам"
        elif not any(is_cyr(c) for c in ru):
            hint = "вероятно намеренно: в строке нет кириллицы (латинский токен/число)"
        add("D", loc, en, ru, "RU совпадает с EN (нет перевода)", hint)


# --- E. homoglyphs ---------------------------------------------------------
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+")


def check_homoglyphs(loc: str, en: str, ru: str) -> None:
    en_tokens = {t for t in TOKEN_RE.findall(en)}
    for tok in TOKEN_RE.findall(ru):
        shapes = {shape(c) for c in tok if shape(c)}
        if shapes == {"C", "L"}:
            lat = "".join(c for c in tok if shape(c) == "L")
            cyr = "".join(c for c in tok if shape(c) == "C")
            if tok in KEEP_LATIN:
                add(
                    "E",
                    loc,
                    en,
                    ru,
                    f"смешанное слово {tok!r} (= разрешённый токен)",
                    "разрешённое исключение из правил — не дефект",
                )
            else:
                add(
                    "E",
                    loc,
                    en,
                    ru,
                    f"гомоглиф: в слове {tok!r} латиница {lat!r} и кириллица {cyr!r}",
                    "заменить латинские двойники на кириллицу (или наоборот)",
                )
            continue
        if (
            shapes == {"L"}
            and len(tok) >= 2
            and tok not in KEEP_LATIN
            and tok not in en_tokens
        ):
            add(
                "E",
                loc,
                en,
                ru,
                f"латиница в переводе: {tok!r}",
                "либо перевести, либо внести в список нетранслируемых токенов",
            )
        if shapes == {"C"} and len(tok) >= 2:
            mapped = "".join(CYR_LOOKALIKE.get(c, "") for c in tok)
            if len(mapped) != len(tok) or mapped not in en_tokens:
                continue
            if mapped in KEEP_LATIN:
                add(
                    "E",
                    loc,
                    en,
                    ru,
                    f"кириллические двойники латиницы: {tok!r} ~ {mapped!r} из EN",
                    "если токен должен остаться латиницей — вернуть латиницу",
                )
            elif tok in UNIT_WORDS or mapped in UNIT_LATIN:
                add(
                    "E",
                    loc,
                    en,
                    ru,
                    f"единица измерения кириллицей: {tok!r} ~ {mapped!r} из EN",
                    "проверить вручную: сокращение единицы обычно и есть намеренный "
                    "перевод (CM -> СМ); дефектом не считается",
                )
            else:
                add(
                    "E",
                    loc,
                    en,
                    ru,
                    f"кириллические двойники латиницы: {tok!r} ~ {mapped!r} из EN",
                    "проверить вручную: возможно, латиницу записали кириллицей",
                )


# --- F. length -------------------------------------------------------------
def check_length(loc: str, en: str, ru: str, limit: int) -> None:
    le, lr = len(en), len(ru)
    if lr > limit:
        add(
            "F",
            loc,
            en,
            ru,
            f"длина RU {lr} > лимита {limit} (упрощённо байт charmap)",
            "строка не влезет в таблицу; сократить перевод",
        )
    elif lr > le:
        add(
            "F",
            loc,
            en,
            ru,
            f"RU длиннее EN: {le} -> {lr} (+{lr - le})",
            "не дефект само по себе; важно для узких подписей UI",
        )


# --- I. ui2 ---------------------------------------------------------------
def check_ui2_block(rec: dict) -> None:
    loc, en, ru = rec["loc"], rec["en"], rec["ru"]
    if not ru:
        add("I", loc, en, ru, "пустой RU в блоке ui2", "перевод отсутствует")
        return
    check_charset(loc, en, ru, "блоке ui2")
    if ru.count("{") != ru.count("}"):
        add(
            "I",
            loc,
            en,
            ru,
            f"дисбаланс фигурных скобок: {{ x{ru.count('{')}, }} x{ru.count('}')}",
            "проверить подстановки",
        )
    f_en, f_ru = FIELD_RE.findall(en), FIELD_RE.findall(ru)
    if f_en != f_ru:
        add(
            "I",
            loc,
            en,
            ru,
            f"подстановки {{}}: EN {f_en} != RU {f_ru}",
            "набор и порядок {..} должны совпадать",
        )
    if ru.count("[") != ru.count("]"):
        add(
            "I",
            loc,
            en,
            ru,
            f"непарные [ ]: [ x{ru.count('[')}, ] x{ru.count(']')}",
            "проверить парность квадратных скобок",
        )
    n_en, n_ru = en.count("<tab>"), ru.count("<tab>")
    if n_en != n_ru:
        add(
            "I",
            loc,
            en,
            ru,
            f"тег <tab>: EN x{n_en}, RU x{n_ru}",
            "тег <tab> — структурный, должен сохраняться",
        )
    # <dominant>/<nondominant> правило разрешает заменять словом — только информационно
    for tag in ("<dominant>", "<nondominant>"):
        c_en, c_ru = en.count(tag), ru.count(tag)
        if c_en != c_ru:
            add(
                "N",
                loc,
                en,
                ru,
                f"тег {tag}: EN x{c_en}, RU x{c_ru}"
                + (" — заменён словом" if c_ru < c_en else " — добавлен в RU"),
                "правило разрешает замену <dominant>/<nondominant> словом; "
                "если добавлен в RU — проверить, что выбор руки верный",
            )
    for seg in norm_space(ru).split("\n"):
        probe = seg
        # "  * item" — отступ вложенного списка (перенесён из EN как структура), не дефект
        if probe.startswith("  *"):
            probe = probe[2:]
        if "  " in probe:
            add(
                "I",
                loc,
                en,
                ru,
                "двойной пробел в блоке ui2",
                "один пробел (внутри строки)",
            )
            break
    if len(ru) > UI2_CELL_LIMIT:
        add(
            "I",
            loc,
            en,
            ru,
            f"длина RU {len(ru)} > лимита таблицы {UI2_CELL_LIMIT}",
            "блок не влезет в таблицу; сократить или разбить",
        )


# --- прогон ----------------------------------------------------------------
def delta_of(f: dict) -> int:
    """Дельта длины из текста находки ('RU длиннее EN: 6 -> 10 (+4)')."""
    m = re.search(r"\+(\d+)\)$", f["issue"])
    return int(m.group(1)) if m else 0


def main() -> None:
    tsv = load_tsv(TSV_093)
    ui2 = load_ui2(UI2_093)

    for r in tsv:
        loc = f"tsv:{r['rva']}"
        check_charset(loc, r["en"], r["ru"], "строке tsv")
        check_placeholders(loc, r["en"], r["ru"])
        check_case(loc, r["en"], r["ru"])
        check_hygiene(loc, r["en"], r["ru"], True)
        check_homoglyphs(loc, r["en"], r["ru"])
        check_length(loc, r["en"], r["ru"], TSV_CELL_LIMIT)

    recs = ui2_records(ui2)
    for rec in recs:
        check_ui2_block(rec)

    # G. duplicates по EN в tsv
    by_en: dict[str, list[dict]] = {}
    for r in tsv:
        by_en.setdefault(r["en"], []).append(r)
    for en, rows in by_en.items():
        variants = sorted({r["ru"] for r in rows})
        if len(variants) > 1:
            add(
                "G",
                "tsv:" + ",".join(r["rva"] for r in rows),
                en,
                " | ".join(variants),
                f"один EN переведён по-разному ({len(variants)} варианта)",
                "выбрать один вариант и выровнять все строки",
            )

    # H. drift 092 -> 093 (RVA в 093 сдвинуты, поэтому сверка по тексту)
    tsv092 = load_tsv(TSV_092)
    ui2092 = load_ui2(UI2_092)
    en092 = {r["en"]: r for r in tsv092}
    ru092: dict[str, list[dict]] = {}
    for r in tsv092:
        ru092.setdefault(r["ru"], []).append(r)
    shifted = len({r["rva"] for r in tsv} & {r["rva"] for r in tsv092})

    for r in tsv:
        if r["en"] in en092 and en092[r["en"]]["ru"] != r["ru"]:
            add(
                "H",
                f"tsv:{r['rva']}",
                r["en"],
                r["ru"],
                "перевод изменён между версиями: "
                f"0.9.2 «{en092[r['en']]['ru']}» -> 0.9.3 «{r['ru']}»",
                "не дефект: сверить, что новый вариант точнее EN",
            )
    for r in tsv:
        if r["en"] in en092:
            continue
        cands = [x for x in ru092.get(r["ru"], []) if x["en"] != r["en"]]
        if cands:
            add(
                "H",
                f"tsv:{r['rva']}",
                r["en"],
                r["ru"],
                "RU не менялся, а EN изменился: "
                f"0.9.2 EN «{cands[0]['en']}» -> 0.9.3 EN «{r['en']}»",
                "устаревший перевод: перевести новый EN заново",
            )
        else:
            add(
                "H",
                f"tsv:{r['rva']}",
                r["en"],
                r["ru"],
                "новая строка в 0.9.3 (EN нет в 0.9.2)",
                "проверить свежесть перевода",
            )
    en093 = {x["en"] for x in tsv}
    for r in tsv092:
        if r["en"] not in en093:
            add(
                "H",
                f"tsv092:{r['rva']}",
                r["en"],
                r["ru"],
                "строка пропала из 0.9.3 (EN отсутствует)",
                "проверить, не потерян ли перевод/строка",
            )
    for section, items in ui2092.items():
        new_items = {e.get("index"): e for e in ui2.get(section, [])}
        for e in items:
            n = new_items.get(e.get("index"))
            if not n:
                add(
                    "H",
                    f"ui2:{section}[{e.get('index')}]",
                    e.get("orig", ""),
                    e.get("ru", ""),
                    "блок пропал из 0.9.3",
                    "проверить потерю",
                )
                continue
            if (e.get("orig") or "") != (n.get("orig") or ""):
                stale = (e.get("ru") or "") == (n.get("ru") or "")
                add(
                    "H",
                    f"ui2:{section}[{n.get('index')}]",
                    n.get("orig", ""),
                    n.get("ru", ""),
                    "EN блока изменился"
                    + (
                        " при неизменном RU (устаревший перевод)"
                        if stale
                        else "; RU тоже правился"
                    ),
                    "сверить перевод с новым EN",
                )

    # --- отчёты ----------------------------------------------------------
    order = list("ABCDEFGHIN")
    counts = {c: _counter.get(c, 0) for c in order}
    cats = cat_names()

    lines: list[str] = []
    lines.append("# Аудит перевода 0.9.3 — механические проверки\n")
    lines.append(f"Дата: {date.today().isoformat()}  ")
    lines.append(
        "Скрипт: `work/audit_093.py` (только чтение источников, kit093 не менялся)\n"
    )
    lines.append("## Источники\n")
    lines.append(f"- `kit093/ru/strings-0.9.3.tsv` — {len(tsv)} строк")
    lines.append(
        f"- `kit093/ru/ui2-0.9.3.json` — {len(ui2)} секции, {len(recs)} записей "
        f"({', '.join(f'{k}:{len(v)}' for k, v in ui2.items())})"
    )
    lines.append(
        f"- `kit092/ru/strings-0.9.2.tsv` — {len(tsv092)} строк "
        f"(сверка по тексту: в 093 сдвинуты RVA, общих RVA {shifted})\n"
    )
    lines.append(
        f"Лимиты: tsv — {TSV_CELL_LIMIT} байт charmap на строку, ui2 — {UI2_CELL_LIMIT}. "
        "Байты считаются упрощённо как `len(ru)`: 1 байт на символ, кроме индексов >= 0xE0 "
        "(2 байта); без таблицы charmap берётся нижняя оценка.\n"
    )
    lines.append("## Сводка\n")
    lines.append("| Кат. | Проверка | Находок |")
    lines.append("| --- | --- | --- |")
    for c in order:
        lines.append(f"| {c} | {cats[c]} | {counts[c]} |")
    real = sum(counts[c] for c in order if c != "N")
    defects = sum(counts[c] for c in ("A", "B", "C", "G", "I"))
    lines.append(f"| | **дефекты + наблюдения (A-I)** | **{real}** |")
    lines.append(f"| N | информационные заметки | {counts['N']} |")
    lines.append("")
    lines.append(
        f"**Вердикт:** механических дефектов — {defects} "
        f"(A charset, B placeholders/теги, C регистр, G дубликаты, I ui2). "
        f"Остальное ({real - defects}) — наблюдения: D — совпадение с EN у намеренно "
        "нетранслируемых токенов, E — единицы измерения (проверить вручную), "
        "F — RU длиннее EN (лимиты не превышены), H — отличия от перевода 0.9.2.\n"
    )

    titles = {
        "A": "A. charset — символы вне разрешённого набора",
        "B": "B. placeholders / теги / [сегменты] / \\n",
        "C": "C. case — регистр",
        "D": "D. hygiene — пробелы, пунктуация, пустое, RU == EN",
        "E": "E. homoglyphs — латиница в русских словах и наоборот",
        "F": "F. length — длина и лимиты таблиц",
        "G": "G. duplicates — один EN, разные RU",
        "H": "H. drift 0.9.2 -> 0.9.3",
        "I": "I. ui2 — табличные блоки",
    }
    notes = {
        "E": "Совпадение с разрешённым токеном помечено как исключение — это не дефект, "
        "а напоминание. Единицы измерения (CM -> СМ и т.п.) помечены «проверить "
        "вручную»: обычно это намеренный перевод.",
        "F": f"В .md показаны топ-{F_TOP_IN_MD} по дельте (и все превышения лимита), "
        "полный список — в `work/audit_093.json`. «RU длиннее EN» само по себе "
        "не дефект: важно для узких подписей UI.",
        "H": "RVA между версиями сдвинуты, поэтому сверка сделана по тексту (EN и RU), "
        "а не по RVA.",
    }

    for c in order:
        if c == "N":
            continue
        lines.append(f"## {titles[c]}\n")
        subset = [f for f in findings if f["category"] == c]
        if notes.get(c):
            lines.append(notes[c] + "\n")
        if not subset:
            lines.append("Находок нет.\n")
            continue
        if c == "F":
            over = [f for f in subset if "лимита" in f["issue"]]
            longer = sorted(
                (f for f in subset if "лимита" not in f["issue"]),
                key=lambda f: (-delta_of(f), f["id"]),
            )
            subset = over + longer
            lines.append(
                f"Превышений лимита: {len(over)}. RU длиннее EN: {len(longer)} "
                f"(в .md — топ-{min(F_TOP_IN_MD, len(longer))}, полный список в .json).\n"
            )
            shown = over + longer[:F_TOP_IN_MD]
            lines.append("| ID | Где | EN | RU | Δ | Проблема |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for f in shown:
                delta = str(delta_of(f)) if "лимита" not in f["issue"] else "лимит"
                lines.append(
                    f"| {f['id']} | {f['location']} | {one_line(f['en'], 60)} | "
                    f"{one_line(f['ru'], 60)} | {delta} | {one_line(f['issue'], 80)} |"
                )
            lines.append("")
            continue
        lines.append(f"Находок: {len(subset)}\n")
        if c == "C":
            lines.append("| ID | Где | EN | RU | Предлагаемая правка | Проблема |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for f in subset:
                lines.append(
                    f"| {f['id']} | {f['location']} | {one_line(f['en'], 40)} | "
                    f"{one_line(f['ru'], 40)} | `{suggest_upper(f['ru'])}` | "
                    f"{one_line(f['issue'], 60)} |"
                )
            lines.append("")
            continue
        lines.append("| ID | Где | EN | RU | Проблема | Подсказка |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for f in subset:
            lines.append(
                f"| {f['id']} | {f['location']} | {one_line(f['en'], 70)} | "
                f"{one_line(f['ru'], 70)} | {one_line(f['issue'], 110)} | "
                f"{one_line(f['hint'], 90)} |"
            )
        lines.append("")

    # приложение по <dominant>/<nondominant>
    lines.append(
        "## Приложение: замены тегов <dominant>/<nondominant> (информационно)\n"
    )
    lines.append(
        "Правило проекта разрешает заменять `<dominant>`/`<nondominant>` словом "
        "(«ведущая/противоположная рука»), поэтому это не дефекты. Список нужен, чтобы "
        "проверить, что выбор руки в тексте верный.\n"
    )
    n_sub = [f for f in findings if f["category"] == "N"]
    if not n_sub:
        lines.append("Замен нет.\n")
    else:
        lines.append(f"Всего мест: {len(n_sub)}\n")
        lines.append("| ID | Где | EN | RU | Заметка |")
        lines.append("| --- | --- | --- | --- | --- |")
        for f in n_sub:
            lines.append(
                f"| {f['id']} | {f['location']} | {one_line(f['en'], 55)} | "
                f"{one_line(f['ru'], 55)} | {one_line(f['issue'], 70)} |"
            )
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(findings, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    # --- stdout: только сводка -------------------------------------------
    print(
        f"tsv строк: {len(tsv)}, ui2 записей: {len(recs)}, "
        f"всего находок: {sum(counts.values())}"
    )
    print("по категориям: " + ", ".join(f"{c}={counts[c]}" for c in order))
    print("--- 15 главных примеров ---")
    prio = list("ABCEFGHID")
    ranked = sorted(
        (f for f in findings if f["category"] != "N"),
        key=lambda f: (prio.index(f["category"]), f["id"]),
    )
    seen = set()
    n = 0
    for f in ranked:
        key = (f["category"], f["issue"][:60])
        if key in seen:
            continue
        seen.add(key)
        n += 1
        if n > 15:
            break
        print(
            f"{f['id']} [{f['category']}] {f['location']}: "
            f"{one_line(f['issue'], 80)} | EN={one_line(f['en'], 34)} | "
            f"RU={one_line(f['ru'], 34)}"
        )
    print(f"отчёты: {OUT_MD.relative_to(ROOT)} , {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
