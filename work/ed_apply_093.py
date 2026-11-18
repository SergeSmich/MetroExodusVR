# -*- coding: utf-8 -*-
"""To4e4nye pravki perevoda 0.9.3 (chast A) v strings-0.9.3.tsv i ui2-0.9.3.json.

Kazdaja pravka proverjaetsja: staryj tekst dolzhen najtis' rovno odin raz.
Log -> work/ed_apply.log (utf-8).
"""

import json
import sys

TSV = "kit093/ru/strings-0.9.3.tsv"
UI2 = "kit093/ru/ui2-0.9.3.json"
LOG = "work/ed_apply.log"

# --- TSV: (RVA, bylo, stalo) ---
TSV_EDITS = [
    ("0x4f31a0", "МАСШТАБ", "ПО КОМНАТЕ"),  # A1 ROOM-SCALE
    ("0x4f3390", "ОСНОВНАЯ РУКА", "ВЕДУЩАЯ РУКА"),  # A2 DOMINANT HAND
    ("0x4f3090", "УДЕРЖ.", "УДЕРЖАНИЕ"),  # A5 HOLD
    ("0x4f3098", "ПЕРЕКЛ.", "ПЕРЕКЛЮЧЕНИЕ"),  # A5 TOGGLE
    ("0x4f3728", "ВИДИМО", "ВИДНО"),  # A5 VISIBLE
    ("0x4f3738", "ЧЕРНЫЙ", "ЧЕРНО"),  # A5 BLACK
    ("0x4f376c", "УРОВЕНЬ", "ПО ГОРИЗОНТУ"),  # A5 LEVEL
    ("0x4f3778", "ФИКСИРОВАНО", "К ОБЗОРУ"),  # A5 FIXED TO VIEW
    ("0x4f3240", "СЛЕДОВАТЬ ЗА ГОЛОВОЙ", "ПО ГОЛОВЕ"),  # A5 FOLLOW HEAD
    ("0x4f3a98", "НАПРАВЛЕНИЕ УДАРА", "НАПРАВЛЕНИЕ ПОПАДАНИЯ"),  # A6 HIT DIRECTION
    ("0x4f3b18", "ПОЛ КИНО", "ПОЛ В VR ОКРУЖЕНИИ"),  # A3 CINEMA FLOOR
    ("0x4f3b40", "КОНТРОЛЛЕРЫ КИНО", "КОНТРОЛЛЕРЫ"),  # A3 CINEMA CONTROLLERS
    ("0x4f3b70", "ИНФО КИНО", "ИНФО В VR ОКРУЖЕНИИ"),  # A3 CINEMA INFO
    ("0x4f3b98", "ССЫЛКИ КИНО", "ССЫЛКИ В VR ОКРУЖЕНИИ"),  # A3 CINEMA LINKS
    ("0x4f3c58", "РАССТОЯНИЕ ЭКРАНА КИНО", "РАССТОЯНИЕ ЭКРАНА VR"),  # A3
    ("0x4f3c88", "РАЗМЕР ЭКРАНА КИНО", "РАЗМЕР ЭКРАНА VR"),  # A3
]

# --- ui2: (kategorija, index, pole, tip, bylo, stalo) ---
U = [
    # A8 startovoe okno 3
    (
        "popups",
        3,
        "ru",
        "sub",
        "Настроить это можно позже в Настройки / VR / Оружие.",
        "Настроить это можно позже в разделе Настройки / VR / Оружие.",
    ),
    # A2 popups 7
    (
        "popups",
        7,
        "ru",
        "sub",
        "Потянитесь к рюкзаку второй рукой над вторым плечом",
        "Потянитесь к рюкзаку противоположной рукой над противоположным плечом",
    ),
    # A2 popups 11 - protivogaz
    (
        "popups",
        11,
        "ru",
        "sub",
        "ПРОТИВОГАЗ\n\nНадеть: <grip_nondominant> у второго бедра",
        "ПРОТИВОГАЗ\n\nНадеть: <grip_nondominant> у противоположного бедра",
    ),
    (
        "popups",
        11,
        "ru",
        "sub",
        "Фильтр: (когда маска надета) <grip_nondominant> у второго бедра",
        "Фильтр: (когда маска надета) <grip_nondominant> у противоположного бедра",
    ),
    (
        "popups",
        11,
        "ru",
        "sub",
        "скотч со второго бедра",
        "скотч с противоположного бедра",
    ),
    (
        "popups",
        11,
        "ru",
        "sub",
        "схватите <grip_nondominant> над вторым плечом",
        "схватите <grip_nondominant> над противоположным плечом",
    ),
    # A2 popups 12 - rjukzak
    (
        "popups",
        12,
        "ru",
        "sub",
        "Схватите <grip_nondominant> над вторым плечом",
        "Схватите <grip_nondominant> над противоположным плечом",
    ),
    # A8 podskazka 4 - upscaling mode
    (
        "options",
        4,
        "ru",
        "sub",
        "Насколько низко рендерит апскейлер.",
        "С какого разрешения работает апскейлер.",
    ),
    # A7 podskazka 18 - crouch button
    (
        "options",
        18,
        "ru",
        "full",
        "УДЕРЖ. приседает, пока кнопка удерживается. ПЕРЕКЛ. приседает одним нажатием и встает следующим.",
        "УДЕРЖАНИЕ приседает, пока кнопка удерживается. ПЕРЕКЛЮЧЕНИЕ приседает одним нажатием и встает следующим.",
    ),
    # A1 podskazka 23 - play mode
    (
        "options",
        23,
        "ru",
        "full",
        "МАСШТАБ позволяет ходить по комнате. СТОЯ удерживает вас на одном месте. СИДЯ предназначен для игры сидя.",
        "ПО КОМНАТЕ: можно свободно ходить по комнате. СТОЯ удерживает вас на одном месте. СИДЯ – для игры сидя.",
    ),
    # A4 podskazka 26 - physical crouch
    (
        "options",
        26,
        "ru",
        "full",
        "Приседание в реальной жизни приседает в игре. Требуется РОСТ ИГРОКА.",
        "Реальное приседание. Требуется РОСТ ИГРОКА.",
    ),
    # A7 podskazka 29 - body turning
    (
        "options",
        29,
        "ru",
        "full",
        "СЛЕДОВАТЬ ЗА ГОЛОВОЙ поворачивает тело за головой, когда вы достаточно далеко посмотрите в сторону. ЗАБЛОКИРОВАНО поворачивает его только стиком поворота.",
        "ПО ГОЛОВЕ поворачивает тело вслед за головой, когда вы достаточно далеко посмотрите в сторону. ЗАБЛОКИРОВАНО поворачивает его только стиком поворота.",
    ),
    # A7 podskazka 34 - grip
    (
        "options",
        34,
        "ru",
        "full",
        "УДЕРЖ. держит взятое, пока удерживается хват. ПЕРЕКЛ. берет одним хватом и возвращает хватом туда, откуда взяли.",
        "УДЕРЖАНИЕ держит взятое, пока удерживается хват. ПЕРЕКЛЮЧЕНИЕ берет предмет одним хватом и возвращает таким же хватом на место.",
    ),
    # A2 podskazka 35 - backpack in hand
    (
        "options",
        35,
        "ru",
        "sub",
        "Хват над вторым плечом берет",
        "Хват над противоположным плечом берет",
    ),
    # A7 podskazka 62 - hit direction
    (
        "options",
        62,
        "ru",
        "full",
        "Показывает дугу в сторону того, кто вас только что ударил.",
        "Показывает дугу в сторону того, кто в вас только что попал.",
    ),
    # A2 kontekstnye podskazki: rjukzak
    ("hints", 4, "ru", "sub", "над вторым плечом", "над противоположным плечом"),
    ("hints", 5, "ru", "sub", "над вторым плечом", "над противоположным плечом"),
    # A2 pompa
    ("hints", 7, "ru", "sub", "второй рукой", "противоположной рукой"),
    ("hints", 9, "ru", "sub", "второй рукой", "противоположной рукой"),
    # A2 binokl'
    (
        "hints",
        25,
        "ru",
        "sub",
        "со второй стороны поясницы",
        "с противоположной стороны поясницы",
    ),
    (
        "hints",
        26,
        "ru",
        "sub",
        "со второй стороны поясницы",
        "с противоположной стороны поясницы",
    ),
    # A2 zazhigalka
    (
        "hints",
        33,
        "ru",
        "sub",
        "со второй стороны груди",
        "с противоположной стороны груди",
    ),
    (
        "hints",
        34,
        "ru",
        "sub",
        "со второй стороны груди",
        "с противоположной стороны груди",
    ),
    (
        "hints",
        35,
        "ru",
        "sub",
        "со второй стороны груди",
        "с противоположной стороны груди",
    ),
    (
        "hints",
        36,
        "ru",
        "sub",
        "со второй стороны груди",
        "с противоположной стороны груди",
    ),
    # A2 protivogaz / fil'tr / skotch
    ("hints", 41, "ru", "sub", "у второго бедра", "у противоположного бедра"),
    ("hints", 42, "ru", "sub", "у второго бедра", "у противоположного бедра"),
    ("hints", 43, "ru", "sub", "у второго бедра", "у противоположного бедра"),
    ("hints", 46, "ru", "sub", "со второго бедра", "с противоположного бедра"),
    ("hints", 47, "ru", "sub", "со второго бедра", "с противоположного бедра"),
    # A2 stranicy sovetov VR
    # 3 - oruzhie: spisok
    (
        "hintpages",
        3,
        "ru",
        "sub",
        "* особое оружие – из-за второго плеча",
        "* особое оружие – из-за противоположного плеча",
    ),
    # 3 - ekipirovka
    (
        "hintpages",
        3,
        "ru",
        "sub",
        "Взяв его, можно взяться второй рукой за основную рукоять или цевье",
        "Взяв его, можно взяться противоположной рукой за рукоять или цевье",
    ),
    # 4 - ruchnaja perezarjadka: podsumok
    (
        "hintpages",
        4,
        "ru",
        "sub",
        "(второе бедро или вторая сторона груди)",
        "(противоположное бедро или противоположная сторона груди)",
    ),
    # 4 - pnevmatika
    (
        "hintpages",
        4,
        "ru",
        "sub",
        "Качайте вручную второй рукой",
        "Качайте вручную противоположной рукой",
    ),
    # 5 - rjukzak
    (
        "hintpages",
        5,
        "ru",
        "sub",
        "Просто схватите (<grip_nondominant>) над вторым плечом",
        "Просто схватите (<grip_nondominant>) над противоположным плечом",
    ),
    # 5 - zony snarjazhenija
    (
        "hintpages",
        5,
        "ru",
        "sub",
        "  * вторая – зажигалка",
        "  * противоположная – зажигалка",
    ),
    (
        "hintpages",
        5,
        "ru",
        "sub",
        "  * из-за второго – особое оружие",
        "  * из-за противоположного – особое оружие",
    ),
    (
        "hintpages",
        5,
        "ru",
        "sub",
        "  * второе – маска*, фильтр*, скотч*",
        "  * противоположное – маска*, фильтр*, скотч*",
    ),
    (
        "hintpages",
        5,
        "ru",
        "sub",
        "  * вторая – бинокль*",
        "  * противоположная – бинокль*",
    ),
    # 6 - protivogaz
    (
        "hintpages",
        6,
        "ru",
        "sub",
        "Противогаз обычно висит на втором бедре",
        "Противогаз обычно висит на противоположном бедре",
    ),
    (
        "hintpages",
        6,
        "ru",
        "sub",
        "новый фильтр появится на втором бедре",
        "новый фильтр появится на противоположном бедре",
    ),
    (
        "hintpages",
        6,
        "ru",
        "sub",
        "на втором бедре или в рюкзаке (<grip_dominant>) появляется кусок скотча",
        "на противоположном бедре или в рюкзаке (<grip_dominant>) появляется кусок скотча",
    ),
    # 10 - otkrytie rjukzaka
    (
        "hintpages",
        10,
        "ru",
        "sub",
        "схватите (<grip_nondominant>) над вторым плечом",
        "схватите (<grip_nondominant>) над противоположным плечом",
    ),
    # 11 - binokl'
    (
        "hintpages",
        11,
        "ru",
        "sub",
        "его со второй стороны поясницы",
        "его с противоположной стороны поясницы",
    ),
]

LIMITS = {"caption": 22, "value": 18, "hint": 150}


def fail(msg):
    print("FAIL: " + msg, file=sys.stderr)
    sys.exit(1)


def main():
    log = []
    # ---------- TSV ----------
    raw = open(TSV, encoding="utf-8", newline="").read()
    lines = raw.split("\r\n")
    if lines[-1] != "":
        fail("tsv: net perevoda stroki v konce fajla")
    body = lines[:-1]
    idx_by_rva = {}
    for i, l in enumerate(body):
        if l.startswith("#") or not l:
            continue
        parts = l.split("\t")
        if len(parts) != 3:
            fail("tsv stroka %d: ozhidal 3 kolonki" % (i + 1))
        idx_by_rva.setdefault(parts[0], []).append(i)
    for rva, old, new in TSV_EDITS:
        if rva not in idx_by_rva:
            fail("tsv: net RVA %s" % rva)
        if len(idx_by_rva[rva]) != 1:
            fail("tsv: RVA %s vstrechaetsja %d raz" % (rva, len(idx_by_rva[rva])))
        i = idx_by_rva[rva][0]
        p = body[i].split("\t")
        if p[2] != old:
            fail("tsv %s: bylo %r, ozhidalos %r" % (rva, p[2], old))
        p[2] = new
        body[i] = "\t".join(p)
        log.append(
            "tsv|%s|%s|%s|%s|%d/%d" % (rva, p[1], old, new, len(new), LIMITS["caption"])
        )
    out = "\r\n".join(body) + "\r\n"
    if out.count("\t") != raw.count("\t"):
        fail("tsv: izmenilos kolichestvo tabuljacij")

    # ---------- UI2 ----------
    raw2 = open(UI2, encoding="utf-8", newline="").read()
    d = json.loads(raw2)
    # format-fiksacija: pereserializacija bez pravok dolzhna dat' ishodnyj fajl
    if json.dumps(d, ensure_ascii=False, indent=2).replace("\n", "\r\n") != raw2:
        fail("ui2: pereserializacija menjaet format fajla")
    by = {}
    for cat in ("popups", "options", "hints", "hintpages"):
        for rec in d[cat]:
            by[(cat, rec["index"])] = rec
    for cat, idx, field, kind, old, new in U:
        rec = by.get((cat, idx))
        if rec is None:
            fail("ui2: net %s#%s" % (cat, idx))
        cur = rec.get(field)
        if cur is None:
            fail("ui2: net polja %s u %s#%s" % (field, cat, idx))
        if kind == "full":
            if cur != old:
                fail(
                    "ui2 %s#%s %s: znachenie ne sovpadaet\n  est: %r\n  zhda: %r"
                    % (cat, idx, field, cur, old)
                )
            rec[field] = new
        else:
            n = cur.count(old)
            if n != 1:
                fail(
                    "ui2 %s#%s %s: podstroka najdena %d raz: %r"
                    % (cat, idx, field, n, old)
                )
            rec[field] = cur.replace(old, new)
        log.append(
            "ui2|%s#%s.%s|%s|%s|%d/%s"
            % (
                cat,
                idx,
                field,
                old,
                new,
                len(rec[field]),
                "hint" if cat == "options" else "text",
            )
        )

    # proverka formata posle pravok
    cand = json.dumps(d, ensure_ascii=False, indent=2)
    # zapis' tol'ko kogda oba fajla uspeshno obrabotany
    open(TSV, "w", encoding="utf-8", newline="").write(out)
    open(UI2, "w", encoding="utf-8", newline="").write(cand.replace("\n", "\r\n"))

    open(LOG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    print("ok: %d pravok v tsv, %d v ui2" % (len(TSV_EDITS), len(U)))
    print("log: " + LOG)


main()
