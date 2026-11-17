"""Generate the human-readable review document for the 0.9.3 Russian UI.

Sources (read-only):
  kit093/ru/strings-0.9.3.tsv   -- mod captions, RVA <TAB> English <TAB> Russian
  kit093/ru/ui2-0.9.3.json      -- popups / options (hints) / hints / hintpages
  work/menu_model.json          -- settings (id, caption, registered values)
  work/font093.json             -- the mod's glyph table

Out:
  docs/UI-RU-REVIEW-093.md
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "UI-RU-REVIEW-093.md"

# Root tabs / pages in menu order.  ``pid`` is the page id string in the DLL.
PAGES = [
    (
        "VR",
        "mevr_vr",
        [
            "mevr_turn_mode",
            "mevr_snap_turn",
            "mevr_smooth_turn",
            "mevr_popups_again",
        ],
    ),
    (
        "ИГРА",
        "mevr_game",
        [
            "mevr_video_legal",
            "mevr_video_credits",
            "mevr_video_intro",
        ],
    ),
    (
        "ГРАФИКА",
        "mevr_graphics",
        [
            "mevr_alternate_eye",
            "mevr_render_scale",
            "mevr_upscaler",
            "mevr_upscaling_mode",
            "mevr_fsr_sharpness",
            "mevr_dlss_model",
            "mevr_upscaling_fovea",
            "mevr_upscaling_periphery",
            "mevr_mirror",
            "mevr_mirror_window",
            "mevr_mirror_ui",
            "mevr_foveation",
            "mevr_water_reflections",
            "mevr_disable_blur",
            "mevr_depth_of_field",
            "mevr_deep_blacks",
            "mevr_hud_resolution",
            "mevr_depth_reprojection",
        ],
    ),
    (
        "ДВИЖЕНИЕ",
        "mevr_movement",
        [
            "mevr_move_direction",
            "mevr_crouch",
            "mevr_auto_sprint",
            "mevr_move_deadzone",
            "mevr_turn_deadzone",
            "mevr_reduce_head_bob",
        ],
    ),
    (
        "ТЕЛО",
        "mevr_body",
        [
            "mevr_play_mode",
            "mevr_player_height",
            "mevr_world_scale",
            "mevr_physical_crouch",
            "mevr_belt_height",
            "mevr_belt_crouch",
            "mevr_body_turning",
            "mevr_body_position",
        ],
    ),
    (
        "РУКИ",
        "mevr_hands",
        [
            "mevr_bhaptics",
            "mevr_bhaptics_strength",
            "mevr_dominant_hand",
            "mevr_grip_angle",
            "mevr_finger_tracking",
            "mevr_grab",
            "mevr_backpack_in_hand",
            "mevr_use_reach",
            "mevr_use_by_looking",
        ],
    ),
    (
        "ВИБРАЦИЯ",
        "mevr_vibration_page",
        [
            "mevr_vibration",
            "mevr_vibration_cues",
            "mevr_vibration_weapons",
            "mevr_vibration_damage",
            "mevr_vibration_world",
            "mevr_vibration_scenes",
            "mevr_vibration_movement",
        ],
    ),
    (
        "ОРУЖИЕ",
        "mevr_weapons",
        [
            "mevr_weapon_weight",
            "mevr_manual_reload",
            "mevr_part_highlights",
            "mevr_part_highlights_reset",
            "mevr_revolver_flick",
            "mevr_reload_pouch",
        ],
    ),
    (
        "ПРИЦЕЛЫ",
        "mevr_scopes",
        [
            "mevr_sighting_eye",
            "mevr_other_eye",
            "mevr_reticle",
            "mevr_scope_steering",
            "mevr_night_vision_tube",
        ],
    ),
    (
        "ИНТЕРФЕЙС",
        "mevr_hud",
        [
            "mevr_hud_shape",
            "mevr_hud_position",
            "mevr_hud_distance",
            "mevr_hud_size",
            "mevr_hud_height",
            "mevr_hud_opacity",
            "mevr_hint_height",
            "mevr_hint_size",
            "mevr_hint_time",
            "mevr_prompt_size",
            "mevr_menu_distance",
            "mevr_menu_size",
            "mevr_damage_effects",
            "mevr_damage_size",
            "mevr_hit_direction",
            "mevr_health_pulse",
            "mevr_debug_overlay",
        ],
    ),
    (
        "КОМФОРТ",
        "mevr_comfort",
        [
            "mevr_camera_preset",
            "mevr_realign",
            "mevr_head_leash",
            "mevr_cinema_floor",
            "mevr_cinema_controllers",
            "mevr_cinema_info",
            "mevr_cinema_links",
            "mevr_cinema_distance",
            "mevr_cinema_size",
        ],
    ),
    (
        "ПЕРЕОПРЕДЕЛЕНИЯ КАМЕРЫ",
        "mevr_camera_overrides",
        [
            "mevr_camera_cinematic_track",
            "mevr_camera_attached",
            "mevr_camera_third_person",
            "mevr_camera_free_cam",
            "mevr_camera_station",
            "mevr_camera_animation_lock",
            "mevr_camera_scripted_lock",
            "mevr_camera_bone_angles",
            "mevr_camera_axis_locked",
            "mevr_camera_gameplay_ui",
        ],
    ),
]

PAGE_IDS = {pid for _, pid, _ in PAGES} | {"mevr_vr_hints_menu"}

# Page captions that own no settable row in menu_model (the root tabs).
PAGE_TITLES = {
    "mevr_vr": "VR",
    "mevr_game": "GAME",
    "mevr_graphics": "GRAPHICS",
    "mevr_movement": "MOVEMENT",
    "mevr_body": "BODY",
    "mevr_hands": "HANDS",
    "mevr_vibration_page": "VIBRATION",
    "mevr_weapons": "WEAPONS",
    "mevr_scopes": "SCOPES",
    "mevr_hud": "INTERFACE",
    "mevr_comfort": "COMFORT",
    "mevr_camera_overrides": "CAMERA OVERRIDES",
}

# Option hints (ui2 "options" index) -> setting id, in table order.
OPTION_MAP = [
    "mevr_popups_again",
    "mevr_alternate_eye",
    "mevr_render_scale",
    "mevr_upscaler",
    "mevr_upscaling_mode",
    "mevr_dlss_model",
    "mevr_upscaling_fovea",
    "mevr_upscaling_periphery",
    "mevr_mirror",
    "mevr_mirror_ui",
    "mevr_foveation",
    "mevr_water_reflections",
    "mevr_disable_blur",
    "mevr_depth_of_field",
    "mevr_deep_blacks",
    "mevr_hud_resolution",
    "mevr_depth_reprojection",
    "mevr_move_direction",
    "mevr_crouch",
    "mevr_auto_sprint",
    "mevr_move_deadzone",
    "mevr_turn_deadzone",
    "mevr_reduce_head_bob",
    "mevr_play_mode",
    "mevr_player_height",
    "mevr_world_scale",
    "mevr_physical_crouch",
    "mevr_belt_height",
    "mevr_belt_crouch",
    "mevr_body_turning",
    "mevr_body_position",
    "mevr_bhaptics",
    "mevr_grip_angle",
    "mevr_finger_tracking",
    "mevr_grab",
    "mevr_backpack_in_hand",
    "mevr_use_reach",
    "mevr_use_by_looking",
    "mevr_vibration",
    "mevr_vibration_cues",
    "mevr_vibration_weapons",
    "mevr_vibration_damage",
    "mevr_vibration_scenes",
    "mevr_vibration_movement",
    "mevr_weapon_weight",
    "mevr_manual_reload",
    "mevr_part_highlights",
    "mevr_part_highlights_reset",
    "mevr_revolver_flick",
    "mevr_sighting_eye",
    "mevr_other_eye",
    "mevr_reticle",
    "mevr_scope_steering",
    "mevr_night_vision_tube",
    "mevr_hud_shape",
    "mevr_hud_position",
    "mevr_hud_distance",
    "mevr_hint_height",
    "mevr_hint_time",
    "mevr_prompt_size",
    "mevr_damage_effects",
    "mevr_damage_size",
    "mevr_hit_direction",
    "mevr_health_pulse",
    "mevr_debug_overlay",
    "mevr_cinema_floor",
    "mevr_cinema_controllers",
    "mevr_cinema_info",
    "mevr_cinema_links",
    "mevr_camera_preset",
    "mevr_realign",
    "mevr_head_leash",
    "mevr_camera_cinematic_track",
    "mevr_camera_attached",
    "mevr_camera_third_person",
    "mevr_camera_free_cam",
    "mevr_camera_station",
    "mevr_camera_animation_lock",
    "mevr_camera_scripted_lock",
    "mevr_camera_bone_angles",
    "mevr_camera_axis_locked",
    "mevr_camera_gameplay_ui",
]

# Values the mod registers once and reuses on another setting's list.
EXTRA_VALUES = {
    "mevr_move_direction": ["BODY"],
    "mevr_camera_preset": ["COMFORT"],
}

# Values produced by the model but actually belonging to a later cluster.
DROP_VALUES = {
    "mevr_graphics": [
        "GAME",
        "VR",
        "OFF",
        "0 (LOCKED)",
        "{} CM",
    ],
    "mevr_video_intro": ["+{} CM", "{} CM"],
}

CAPTION_MAX = 22
VALUE_MAX = 18


def esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def load():
    strings = []
    for line in (
        (ROOT / "kit093/ru/strings-0.9.3.tsv").read_text(encoding="utf-8").splitlines()
    ):
        if not line or line.startswith("#"):
            continue
        rva, en, ru = line.split("\t")
        strings.append({"rva": rva, "en": en, "ru": ru})
    by_addr = {int(s["rva"], 16): s for s in strings}
    by_text = {s["en"]: s for s in strings}
    ui2 = json.loads((ROOT / "kit093/ru/ui2-0.9.3.json").read_text(encoding="utf-8"))
    model = {
        m["id"]: m
        for m in json.loads((ROOT / "work/menu_model.json").read_text(encoding="utf-8"))
    }
    font = json.loads((ROOT / "work/font093.json").read_text(encoding="utf-8"))
    return strings, by_addr, by_text, ui2, model, font


def value_pairs(model, by_text, sid):
    out, seen = [], set()
    for v in model[sid]["values"]:
        t = v["text"]
        if t in seen or t in DROP_VALUES.get(sid, []):
            continue
        seen.add(t)
        s = by_text[t]
        out.append((t, s["ru"], s["rva"]))
    for t in EXTRA_VALUES.get(sid, []):
        if t in seen:
            continue
        s = by_text[t]
        out.append((t, s["ru"], s["rva"]))
    return out


def main() -> None:
    strings, by_addr, by_text, ui2, model, font = load()

    assigned = [sid for _, _, ids in PAGES for sid in ids]
    problems = []
    for sid in assigned:
        if sid not in model:
            problems.append(f"page id `{sid}` is missing from menu_model")
    for sid in model:
        if sid not in assigned and sid not in PAGE_IDS:
            problems.append(f"model setting `{sid}` is not in PAGES")
    if len(OPTION_MAP) != len(ui2["options"]):
        problems.append(
            f"OPTION_MAP has {len(OPTION_MAP)} entries, ui2 options has {len(ui2['options'])}"
        )
    hint_by_setting = {sid: i for i, sid in enumerate(OPTION_MAP)}

    page_of, pos_in_page = {}, {}
    for ru_name, _, ids in PAGES:
        for n, sid in enumerate(ids, 1):
            page_of[sid] = ru_name
            pos_in_page[sid] = n

    L = []
    a = L.append
    a("# Metro Exodus VR 0.9.3 — перевод интерфейса: полный список строк")
    a("")
    a("Документ для редактора перевода. Версия мода: **0.9.3**. Составлен по исходным")
    a("данным сборки (`kit093/ru/*`) и по строковым таблицам самого мода в DLL.")
    a("")
    a("| Раздел | Строк |")
    a("| --- | --- |")
    a(
        f"| 1. Пункты меню (страницы + пункты + значения) | {len(PAGES)} страниц, "
        f"{len(assigned)} {plural(len(assigned), 'пункт', 'пункта', 'пунктов')}, "
        f"{sum(len(value_pairs(model, by_text, s)) for s in assigned)} значений |"
    )
    a(f"| 2. Подсказки к пунктам меню | {len(ui2['options'])} |")
    a(f"| 3.1 Стартовые окна (обучение) | {len(ui2['popups'])} |")
    a(f"| 3.2 Раздел «СОВЕТЫ VR» (меню паузы) | {len(ui2['hintpages'])} |")
    a(f"| 3.3 Контекстные подсказки в игре | {len(ui2['hints'])} |")
    a("")
    a("## Как править")
    a("")
    a("Правятся два файла, больше ничего трогать не нужно:")
    a("")
    a("- `kit093/ru/strings-0.9.3.tsv` — пункты меню, значения переключателей")
    a("  (колонки: `RVA`, `English`, `Russian`, разделитель — табуляция; строки")
    a("  с `#` — комментарии, их не трогать).")
    a("- `kit093/ru/ui2-0.9.3.json` — подсказки и обучающие тексты, поля `ru`")
    a("  и `ru_title` (индексы в документе совпадают с индексами в файле).")
    a("")
    a("Правила, которые нельзя нарушать:")
    a("")
    a("1. **Заголовки пунктов и значений — ЗАГЛАВНЫМИ.** Это captions мода,")
    a("   регистр не пересчитывается.")
    a("2. **Сохранять подстановки:** `{}`, `{:g}`, `{:.2f}`, `{:.1f}`, `{:+.0f}`.")
    a("   Число и порядок подстановок менять нельзя.")
    a("3. **Сохранять игровые теги:** `<stick_left>`, `<start>`, `<xpad_y>`, `<tab>`,")
    a("   `<Press:rui>`, `<wpn_fire>`, `<grip_dominant>`, `<dominant>` и т.п. —")
    a("   игра подставляет по ним кнопку или название. `<tab>` в начале строки —")
    a("   отступ, а не слово.")
    a("4. **Сохранять необязательные части** в квадратных скобках:")
    a("   `[, or <press:map>]`. Игра показывает их только при определённой раскладке.")
    a("5. **Переносы строк** в `ui2` — реальные `\\n` внутри текста. Не склеивать")
    a("   абзацы и не менять ширину строки без причины.")
    a("6. **Длина:** заголовок пункта — до 22 символов, значение — до 18,")
    a("   подсказка — до ~150, обучающий текст — как в оригинале по ширине.")
    a("   Строки длиннее в игре обрезаются или вылезают за панель.")
    a("7. **Не переводить:** `FSR`, `DLSS`, `TAA`, `NVIDIA`, `bHaptics`, `HUD`,")
    a(
        "   `Ko-fi`, `GitHub`, `Buy Me a Coffee`, `AER+`, названия моделей DLSS (`K`, `M`,"
    )
    a("   `L`, `J`, `E`), `VIP`.")
    a("8. **Только символы из таблицы глифов** (ниже). Любой другой символ")
    a("   отрисуется мусором или приведёт к отказу строки.")
    a("")
    a(
        "Разрешённые символы (таблица глифов шрифта мода, "
        f"{len(font['codepoints'])} кодпоинтов):"
    )
    a("")
    a("- латиница: `A-Z`, `a-z`, цифры `0-9`, вся ASCII-пунктуация;")
    a("- кириллица: `А-Я` и `а-я` полностью, **кроме `Ё` и `ё`** — вместо них")
    a("  пишите `Е` и `е`;")
    a("- дополнительно: `«` `»` `©` `®` `–` `—` `‘` `’` `“` `”` `…` `™`.")
    a("")
    a("Нет в шрифте (отрисуется мусором или строка будет отклонена):")
    a("`Ё` `ё` `№` `°` `„` — и вообще любой символ, которого нет в таблице глифов.")
    a("")
    a("Термины, которых стоит держаться (сейчас в переводе разнобой):")
    a("")
    a("| English | Рекомендуется | Не использовать |")
    a("| --- | --- | --- |")
    a("| HUD | HUD | ИНТЕРФЕЙС (для HUD) |")
    a("| GRIP | ЗАХВАТ | ХВАТ, СХВАТИТЬ |")
    a("| BELT | ПОЯС | РЕМЕНЬ |")
    a("| CROUCH | ПРИСЕДАНИЕ / ПРИСЕСТЬ | ПРИСЕД |")
    a("| RELOAD | ПЕРЕЗАРЯДКА | ПЕРЕЗАРЯД |")
    a("| SCOPE | ПРИЦЕЛ | ОПТИКА |")
    a("| HINT | ПОДСКАЗКА | СОВЕТ (кроме раздела «СОВЕТЫ VR») |")
    a("| FOLLOW | СЛЕДОВАТЬ / СЛЕЖЕНИЕ | ИДТИ ЗА |")
    a("| RENDER SCALE | МАСШТАБ РЕНДЕРА | РАЗРЕШЕНИЕ РЕНДЕРА |")
    a("")
    a("---")
    a("")
    a("## 1. Пункты меню")
    a("")
    a("### 1.1. Страницы (вкладки) меню")
    a("")
    a("| id страницы | Оригинал | Перевод |")
    a("| --- | --- | --- |")
    for ru_name, pid, _ in PAGES:
        en = PAGE_TITLES[pid]
        a(f"| `{pid}` | {en} | {by_text[en]['ru']} |")
    a("| `mevr_vr_hints_menu` | VR HINTS | СОВЕТЫ VR (см. дефект 4.3) |")
    a("")
    a("### 1.2. Пункты настроек по страницам")
    a("")
    a("Формат: `Оригинал` → `Перевод`; в скобках — значения переключателя.")
    a("Столбец RVA — адрес строки в DLL (для сверки со `strings-0.9.3.tsv`).")
    a("")
    num = 0
    for ru_name, pid, ids in PAGES:
        a(f"#### {ru_name}")
        a("")
        a("| # | id | RVA | Оригинал | Перевод | Значения |")
        a("| --- | --- | --- | --- | --- | --- |")
        for sid in ids:
            num += 1
            it = model[sid]
            cap = by_addr[it["addr"]]
            vals = value_pairs(model, by_text, sid)
            vtxt = "; ".join(f"{esc(e)} → {esc(r)}" for e, r, _ in vals) or "—"
            a(
                f"| {num} | `{sid}` | {it['addr']:#x} | {esc(it['caption'])} | "
                f"{esc(cap['ru'])} | {vtxt} |"
            )
        a("")

    a("---")
    a("")
    a("## 2. Подсказки к пунктам меню")
    a("")
    a("Показываются внизу экрана, когда курсор стоит на пункте. «Индекс» —")
    a("позиция в `ui2-0.9.3.json` → `options` (по ней искать строку в файле).")
    a("")
    for ru_name, _, ids in PAGES:
        rows = [sid for sid in ids if sid in hint_by_setting]
        if not rows:
            continue
        a(f"### {ru_name}")
        a("")
        for sid in rows:
            i = hint_by_setting[sid]
            item = ui2["options"][i]
            cap = by_addr[model[sid]["addr"]]
            a(f"**{i}. {model[sid]['caption']} — {cap['ru']}**")
            a("")
            a(f"- EN: {item['orig']}")
            a(f"- RU: {item['ru']}")
            a("")

    a("---")
    a("")
    a("## 3. Обучение в игре")
    a("")
    a("### 3.1. Стартовые окна (popups)")
    a("")
    a("Показываются при первом запуске и по кнопке «СНОВА ПОКАЗАТЬ СОВЕТЫ VR».")
    a("Индекс — `popups` в `ui2-0.9.3.json`.")
    a("")
    for i, item in enumerate(ui2["popups"]):
        title_en = item["orig"].split("\n")[0]
        title_ru = item["ru"].split("\n")[0]
        a(f"#### {i}. {title_en} → {title_ru}")
        a("")
        a("Оригинал:")
        a("```")
        a(item["orig"])
        a("```")
        a("Перевод:")
        a("```")
        a(item["ru"])
        a("```")
        a("")

    a("### 3.2. Раздел «СОВЕТЫ VR» (hintpages)")
    a("")
    a("Вкладка в меню паузы. Индекс — `hintpages` в `ui2-0.9.3.json`;")
    a("`orig_title`/`ru_title` — заголовок страницы, `orig`/`ru` — текст.")
    a("")
    for i, item in enumerate(ui2["hintpages"]):
        a(f"#### {i}. {item['orig_title']} → {item['ru_title']}")
        a("")
        a("Оригинал:")
        a("```")
        a(item["orig"])
        a("```")
        a("Перевод:")
        a("```")
        a(item["ru"])
        a("```")
        a("")

    a("### 3.3. Контекстные подсказки в игре (hints)")
    a("")
    a("Всплывают по ходу игры. Индекс — `hints` в `ui2-0.9.3.json`. В тексте")
    a("`[...]` — необязательная часть, `<...>` — кнопки.")
    a("")
    for i, item in enumerate(ui2["hints"]):
        a(f"**{i}.**")
        a("")
        a(f"- EN: {item['orig']}")
        a(f"- RU: {item['ru']}")
        a("")

    a("---")
    a("")
    a("## 4. Дефекты сборки (не перевод)")
    a("")
    a("Это не текст, а рендер/сборка. Правкой `strings`/`ui2` не лечится,")
    a("редактору перевода можно игнорировать:")
    a("")
    a("1. `МАСШТАБ МИРА` показывает литерал `{}% (РЕКОМЕНД.)` вместо числа —")
    a("   подстановка формата не срабатывает (дефект обработчика).")
    a("2. Перед `НАЗАД` в футере виден лишний символ — это игровой футер")
    a("   (`Esc … НАЗАД`), строки мода там нет.")
    a("3. Литерал `VR HINTS` (`0x4ec548`) пока лежит в ASCII-байтах и рисуется как")
    a("   `EЯ!МbЗХA` — строка ещё не перекодирована в глифы.")
    a("4. Две строки на странице `ОРУЖИЕ` и пункт `MAGAZINE POUCH` отклоняются")
    a("   проверками мода (`lists need 2-255 printable ASCII labels`) — строки")
    a("   в таблице есть, но в игре не появляются.")
    a("")
    a("## 5. Автоматически найденные проблемы перевода")
    a("")
    a("### 5.1. Слишком длинные строки (риск обрезки)")
    a("")
    a("| Где | Оригинал | Перевод | Длина | Лимит |")
    a("| --- | --- | --- | --- | --- |")
    for sid in assigned:
        it = model[sid]
        cap = by_addr[it["addr"]]
        if len(cap["ru"]) > CAPTION_MAX:
            a(
                f"| пункт `{sid}` | {esc(it['caption'])} | {esc(cap['ru'])} | "
                f"{len(cap['ru'])} | {CAPTION_MAX} |"
            )
        for en, ru, _ in value_pairs(model, by_text, sid):
            if len(ru) > VALUE_MAX:
                a(
                    f"| значение `{sid}` | {esc(en)} | {esc(ru)} | {len(ru)} | {VALUE_MAX} |"
                )
    a("")
    a("### 5.2. Спорные места")
    a("")
    a("| Оригинал | Сейчас | Почему плохо |")
    a("| --- | --- | --- |")
    a(
        "| COMFORT (заголовок страницы) | КОМФОРТНЫЙ | прилагательное в названии вкладки; нужен «КОМФОРТ» |"
    )
    a(
        "| ROOM-SCALE | МАСШТАБ | совпадает с WORLD SCALE — «МАСШТАБ МИРА»; нужен «В КОМНАТЕ» |"
    )
    a(
        "| LEFT HAND / RIGHT HAND | ЛЕВАЯ / ПРАВАЯ | рядом HEAD — «ГОЛОВА»; нужно «ЛЕВАЯ РУКА» / «ПРАВАЯ РУКА» |"
    )
    a("| GRIP | ХВАТ | в подсказках тот же термин — «ЗАХВАТ»; выбрать одно слово |")
    a(
        "| WEAPON GRIP ANGLE | УГОЛ ХВАТА ОРУЖИЯ | если GRIP — «ЗАХВАТ», то «УГОЛ ЗАХВАТА ОРУЖИЯ» |"
    )
    a(
        "| HOLD / TOGGLE | УДЕРЖ. / ПЕРЕКЛ. | сокращения непонятны без подсказки; 18 символов есть |"
    )
    a("| SIGHTING EYE | ГЛАЗ ПРИЦЕЛА | не читается как «какой глаз смотрит в прицел» |")
    a(
        "| LEFT / RIGHT (для глаза) | ЛЕВАЯ / ПРАВАЯ | глаз мужского рода: «ЛЕВЫЙ» / «ПРАВЫЙ» |"
    )
    a(
        "| MIRROR HEADSET UI | ЗЕРКАЛИРОВАТЬ UI ШЛЕМА | «UI» не переведено; «ИНТЕРФЕЙС ШЛЕМА» |"
    )
    a("| UPSCALER | АПСКЕЙЛЕР | транслит; «МАСШТАБИРОВАНИЕ» |")
    a("| UPSCALING MODE | РЕЖИМ АПСКЕЙЛА | согласовать с «МАСШТАБИРОВАНИЕ» |")
    a(
        "| FOVEATED UPSCALING / FOVEATED RENDERING | ФОВЕАЛЬНЫЙ АПСКЕЙЛ / ФОВЕАЛЬНЫЙ РЕНДЕРИНГ | «фовеальный» — транслит |"
    )
    a(
        "| RENDER SCALE (RESTART) | МАСШТАБ РЕНДЕРА | рядом HUD RESOLUTION — «РАЗРЕШЕНИЕ HUD»; выбрать одно |"
    )
    a(
        "| RESET HIGHLIGHT COUNTS | СБРОСИТЬ СЧЕТЧИКИ ПОДСВЕТКИ | 27 символов, обрезается |"
    )
    a(
        "| BELT WHEN CROUCHING | ПОЯС В ПРИСЕДЕ | «присед» — жаргон; «ПОЯС ПРИ ПРИСЕДАНИИ» |"
    )
    a("| CROUCH BUTTON | КНОПКА ПРИСЕДА | «КНОПКА ПРИСЕДАНИЯ» |")
    a(
        "| HIP (значение MAGAZINE POUCH) | БЕДРО | это место, а не часть тела: «НА БЕДРЕ» |"
    )
    a("| DEEP BLACKS | ГЛУБОКИЙ ЧЕРНЫЙ | о цветах: «ГЛУБОКИЕ ЧЕРНЫЕ» |")
    a(
        "| CINEMATIC TRACK | СЦЕНАРНЫЙ ПУТЬ | читается как «сценарий», а не «путь камеры» |"
    )
    a(
        "| STAY WITH YOU | ОСТАВАТЬСЯ С ВАМИ | в моде всюду «ты»-стиль; рядом FOLLOW — «СЛЕДОВАТЬ» |"
    )
    a(
        "| HINT HEIGHT / HINT SIZE | ВЫСОТА ПОДСКАЗКИ / РАЗМЕР ПОДСКАЗКИ | не отличает «карточку» от «текста» |"
    )
    a(
        "| OTHER EYE WHILE SCOPED | ВТОРОЙ ГЛАЗ В ПРИЦЕЛЕ | читается как «второй прицел» |"
    )
    a("| SCOPE STEERING | НАВЕДЕНИЕ ПРИЦЕЛА | «наведение» и «поворот» смешаны |")
    a(
        "| ACTION PROMPT SIZE | РАЗМЕР ПОДСКАЗКИ ДЕЙСТВИЯ | калька; «РАЗМЕР ПОДСКАЗОК ДЕЙСТВИЙ» |"
    )
    a(
        "| USE REACH / USE BY LOOKING | РАДИУС ВЗАИМОДЕЙСТВИЯ / ИСПОЛЬЗОВАТЬ ВЗГЛЯДОМ | пара должна быть симметричной |"
    )
    a("")
    a("### 5.3. Строки, намеренно оставленные латиницей")
    a("")
    a("Это не пропуски перевода: технические имена, их трогать не нужно.")
    a("")
    same = [s for s in strings if s["en"] == s["ru"]]
    a(", ".join(f"`{s['en']}`" for s in same) + ".")
    a("")
    a("## 6. Чек-лист агента-редактора")
    a("")
    a("- [ ] Раздел 1: одинаковые термины на всех страницах, единый регистр.")
    a("- [ ] Раздел 2: подсказка объясняет именно этот пункт, а не соседний.")
    a("- [ ] Раздел 3.1–3.3: единый голос (везде «вы»), единые названия кнопок.")
    a("- [ ] Ни одна подстановка `{}`/`{:g}`/`{:.2f}` не потеряна.")
    a("- [ ] Все `<...>`-теги на месте и не переведены.")
    a("- [ ] Строки не длиннее лимитов из 5.1.")
    a("- [ ] Нет символов вне таблицы глифов.")
    a("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print("written", OUT, len(L), "lines")
    print(
        "settings",
        num,
        "hints",
        len(ui2["options"]),
        "popups",
        len(ui2["popups"]),
        "hintpages",
        len(ui2["hintpages"]),
        "hints",
        len(ui2["hints"]),
    )
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" ", p)


if __name__ == "__main__":
    main()
