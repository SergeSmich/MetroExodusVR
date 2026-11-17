# Metro Exodus VR 0.9.3 — перевод интерфейса: полный список строк

Документ для редактора перевода. Версия мода: **0.9.3**. Составлен по исходным
данным сборки (`kit093/ru/*`) и по строковым таблицам самого мода в DLL.

| Раздел | Строк |
| --- | --- |
| 1. Пункты меню (страницы + пункты + значения) | 12 страниц, 102 пункта, 100 значений |
| 2. Подсказки к пунктам меню | 82 |
| 3.1 Стартовые окна (обучение) | 16 |
| 3.2 Раздел «СОВЕТЫ VR» (меню паузы) | 14 |
| 3.3 Контекстные подсказки в игре | 52 |

## Как править

Правятся два файла, больше ничего трогать не нужно:

- `kit093/ru/strings-0.9.3.tsv` — пункты меню, значения переключателей
  (колонки: `RVA`, `English`, `Russian`, разделитель — табуляция; строки
  с `#` — комментарии, их не трогать).
- `kit093/ru/ui2-0.9.3.json` — подсказки и обучающие тексты, поля `ru`
  и `ru_title` (индексы в документе совпадают с индексами в файле).

Правила, которые нельзя нарушать:

1. **Заголовки пунктов и значений — ЗАГЛАВНЫМИ.** Это captions мода,
   регистр не пересчитывается.
2. **Сохранять подстановки:** `{}`, `{:g}`, `{:.2f}`, `{:.1f}`, `{:+.0f}`.
   Число и порядок подстановок менять нельзя.
3. **Сохранять игровые теги:** `<stick_left>`, `<start>`, `<xpad_y>`, `<tab>`,
   `<Press:rui>`, `<wpn_fire>`, `<grip_dominant>`, `<dominant>` и т.п. —
   игра подставляет по ним кнопку или название. `<tab>` в начале строки —
   отступ, а не слово.
4. **Сохранять необязательные части** в квадратных скобках:
   `[, or <press:map>]`. Игра показывает их только при определённой раскладке.
5. **Переносы строк** в `ui2` — реальные `\n` внутри текста. Не склеивать
   абзацы и не менять ширину строки без причины.
6. **Длина:** заголовок пункта — до 22 символов, значение — до 18,
   подсказка — до ~150, обучающий текст — как в оригинале по ширине.
   Строки длиннее в игре обрезаются или вылезают за панель.
7. **Не переводить:** `FSR`, `DLSS`, `TAA`, `NVIDIA`, `bHaptics`, `HUD`,
   `Ko-fi`, `GitHub`, `Buy Me a Coffee`, `AER+`, названия моделей DLSS (`K`, `M`,
   `L`, `J`, `E`), `VIP`.
8. **Только символы из таблицы глифов** (ниже). Любой другой символ
   отрисуется мусором или приведёт к отказу строки.

Разрешённые символы (таблица глифов шрифта мода, 269 кодпоинтов):

- латиница: `A-Z`, `a-z`, цифры `0-9`, вся ASCII-пунктуация;
- кириллица: `А-Я` и `а-я` полностью, **кроме `Ё` и `ё`** — вместо них
  пишите `Е` и `е`;
- дополнительно: `«` `»` `©` `®` `–` `—` `‘` `’` `“` `”` `…` `™`.

Нет в шрифте (отрисуется мусором или строка будет отклонена):
`Ё` `ё` `№` `°` `„` — и вообще любой символ, которого нет в таблице глифов.

Термины, которых стоит держаться (сейчас в переводе разнобой):

| English | Рекомендуется | Не использовать |
| --- | --- | --- |
| HUD | HUD | ИНТЕРФЕЙС (для HUD) |
| GRIP | ЗАХВАТ | ХВАТ, СХВАТИТЬ |
| BELT | ПОЯС | РЕМЕНЬ |
| CROUCH | ПРИСЕДАНИЕ / ПРИСЕСТЬ | ПРИСЕД |
| RELOAD | ПЕРЕЗАРЯДКА | ПЕРЕЗАРЯД |
| SCOPE | ПРИЦЕЛ | ОПТИКА |
| HINT | ПОДСКАЗКА | СОВЕТ (кроме раздела «СОВЕТЫ VR») |
| FOLLOW | СЛЕДОВАТЬ / СЛЕЖЕНИЕ | ИДТИ ЗА |
| RENDER SCALE | МАСШТАБ РЕНДЕРА | РАЗРЕШЕНИЕ РЕНДЕРА |

---

## 1. Пункты меню

### 1.1. Страницы (вкладки) меню

| id страницы | Оригинал | Перевод |
| --- | --- | --- |
| `mevr_vr` | VR | VR |
| `mevr_game` | GAME | ИГРА |
| `mevr_graphics` | GRAPHICS | ГРАФИКА |
| `mevr_movement` | MOVEMENT | ДВИЖЕНИЕ |
| `mevr_body` | BODY | ТЕЛО |
| `mevr_hands` | HANDS | РУКИ |
| `mevr_vibration_page` | VIBRATION | ВИБРАЦИЯ |
| `mevr_weapons` | WEAPONS | ОРУЖИЕ |
| `mevr_scopes` | SCOPES | ПРИЦЕЛЫ |
| `mevr_hud` | INTERFACE | ИНТЕРФЕЙС |
| `mevr_comfort` | COMFORT | КОМФОРТНЫЙ |
| `mevr_camera_overrides` | CAMERA OVERRIDES | ПЕРЕОПРЕДЕЛЕНИЯ КАМЕРЫ |
| `mevr_vr_hints_menu` | VR HINTS | СОВЕТЫ VR (см. дефект 4.3) |

### 1.2. Пункты настроек по страницам

Формат: `Оригинал` → `Перевод`; в скобках — значения переключателя.
Столбец RVA — адрес строки в DLL (для сверки со `strings-0.9.3.tsv`).

#### VR

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 1 | `mevr_turn_mode` | 0x4f2f80 | TURN MODE | РЕЖИМ ПОВОРОТА | SNAP → РЕЗКО; SMOOTH → ПЛАВНО |
| 2 | `mevr_snap_turn` | 0x4f2fb0 | SNAP TURN ANGLE | УГОЛ РЕЗКОГО ПОВОРОТА | {:g} DEG → {:g} ГРАД |
| 3 | `mevr_smooth_turn` | 0x4f2fe8 | SMOOTH TURN SPEED | СКОРОСТЬ ПЛАВНОГО ПОВОРОТА | {:g} DEG/S → {:g} ГРАД/С |
| 4 | `mevr_popups_again` | 0x4f3168 | SHOW VR TIPS AGAIN | СНОВА ПОКАЗАТЬ СОВЕТЫ VR | — |

#### ИГРА

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 5 | `mevr_video_legal` | 0x4f42b8 | LEGAL NOTICE VIDEO | ВИДЕО ПРАВОВОЙ ИНФОРМАЦИИ | — |
| 6 | `mevr_video_credits` | 0x4f42f0 | CREDITS VIDEO | ВИДЕО ТИТРОВ | — |
| 7 | `mevr_video_intro` | 0x4f4320 | INTRO VIDEO | ВСТУПИТЕЛЬНОЕ ВИДЕО | — |

#### ГРАФИКА

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 8 | `mevr_alternate_eye` | 0x4f3e28 | RENDER MODE | РЕЖИМ РЕНДЕРА | STEREO → СТЕРЕО; PERFORMANCE (AER+) → ПРОИЗВОДИТЕЛЬНОСТЬ (AER+) |
| 9 | `mevr_render_scale` | 0x4f3e70 | RENDER SCALE (RESTART) | МАСШТАБ РЕНДЕРА (ПЕРЕЗАПУСК) | — |
| 10 | `mevr_upscaler` | 0x4f3e98 | UPSCALER | АПСКЕЙЛЕР | — |
| 11 | `mevr_upscaling_mode` | 0x4f3ec0 | UPSCALING MODE | РЕЖИМ АПСКЕЙЛА | NATIVE AA → НАТИВНОЕ СГЛАЖИВАНИЕ; QUALITY → КАЧЕСТВО; BALANCED → СБАЛАНСИРОВАННЫЙ; PERFORMANCE → ПРОИЗВОДИТЕЛЬНОСТЬ; ULTRA PERFORMANCE → УЛЬТРА ПРОИЗВОДИТЕЛЬНОСТЬ |
| 12 | `mevr_fsr_sharpness` | 0x4f3f38 | FSR SHARPENING | РЕЗКОСТЬ FSR | OFF → ВЫКЛ; LOW → НИЗКО; MEDIUM → СРЕДНИЙ; HIGH → ВЫСОКО |
| 13 | `mevr_dlss_model` | 0x4f3f68 | DLSS MODEL | МОДЕЛЬ DLSS | AUTO (K) → АВТО (K); K (DLSS 4) → K (DLSS 4); M (DLSS 4.5) → M (DLSS 4.5); L (DLSS 4.5) → L (DLSS 4.5); J (DLSS 4) → J (DLSS 4); E (DLSS 3) → E (DLSS 3) |
| 14 | `mevr_upscaling_fovea` | 0x4f3ff0 | FOVEATED UPSCALING | ФОВЕАЛЬНЫЙ АПСКЕЙЛ | OFF → ВЫКЛ; ON (45 DEG) → ВКЛ (45 ГРАД); ON (40 DEG) → ВКЛ (40 ГРАД); ON (35 DEG) → ВКЛ (35 ГРАД); ON (30 DEG) → ВКЛ (30 ГРАД); ON (25 DEG) → ВКЛ (25 ГРАД); ON (20 DEG) → ВКЛ (20 ГРАД) |
| 15 | `mevr_upscaling_periphery` | 0x4f4088 | FOVEATED PERIPHERY | ФОВЕАЛЬНАЯ ПЕРИФЕРИЯ | NATIVE AA → НАТИВНОЕ СГЛАЖИВАНИЕ; TAA → TAA |
| 16 | `mevr_mirror` | 0x4f40b0 | DESKTOP MIRROR | ЗЕРКАЛО РАБОЧЕГО СТОЛА | OFF → ВЫКЛ; LEFT EYE → ЛЕВЫЙ ГЛАЗ; BOTH EYES → ОБА ГЛАЗА |
| 17 | `mevr_mirror_window` | 0x4f40f8 | MIRROR WINDOW | ОКНО ЗЕРКАЛА | WINDOWED → В ОКНЕ; FULLSCREEN → ПОЛНЫЙ ЭКРАН |
| 18 | `mevr_mirror_ui` | 0x4f4138 | MIRROR HEADSET UI | ЗЕРКАЛИРОВАТЬ UI ШЛЕМА | — |
| 19 | `mevr_foveation` | 0x4f4160 | FOVEATED RENDERING | ФОВЕАЛЬНЫЙ РЕНДЕРИНГ | OFF → ВЫКЛ; LIGHT → ЛЕГКИЙ; BALANCED → СБАЛАНСИРОВАННЫЙ; HIGH → ВЫСОКО; AGGRESSIVE → АГРЕССИВНЫЙ; ULTRA → УЛЬТРА; EXTREME → ЭКСТРИМ |
| 20 | `mevr_water_reflections` | 0x4f41b8 | BETTER WATER REFLECTIONS | ЛУЧШИЕ ОТРАЖЕНИЯ ВОДЫ | — |
| 21 | `mevr_disable_blur` | 0x4f41f0 | DISABLE BLUR | ОТКЛЮЧИТЬ РАЗМЫТИЕ | — |
| 22 | `mevr_depth_of_field` | 0x4f4218 | DEPTH OF FIELD | ГЛУБИНА РЕЗКОСТИ | — |
| 23 | `mevr_deep_blacks` | 0x4f4240 | DEEP BLACKS | ГЛУБОКИЙ ЧЕРНЫЙ | — |
| 24 | `mevr_hud_resolution` | 0x4f4268 | HUD RESOLUTION (RESTART) | РАЗРЕШЕНИЕ HUD (ПЕРЕЗАПУСК) | — |
| 25 | `mevr_depth_reprojection` | 0x4f42a0 | DEPTH REPROJECTION | РЕПРОЕКЦИЯ ГЛУБИНЫ | — |

#### ДВИЖЕНИЕ

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 26 | `mevr_move_direction` | 0x4f3028 | MOVEMENT DIRECTION | НАПРАВЛЕНИЕ ДВИЖЕНИЯ | HEAD → ГОЛОВА; LEFT HAND → ЛЕВАЯ; RIGHT HAND → ПРАВАЯ; BODY → ТЕЛО |
| 27 | `mevr_crouch` | 0x4f3080 | CROUCH BUTTON | КНОПКА ПРИСЕДА | HOLD → УДЕРЖ.; TOGGLE → ПЕРЕКЛ. |
| 28 | `mevr_auto_sprint` | 0x4f30b8 | AUTO SPRINT | АВТОБЕГ | — |
| 29 | `mevr_move_deadzone` | 0x4f30e0 | MOVE STICK DEADZONE | МЕРТВАЯ ЗОНА СТИКА | — |
| 30 | `mevr_turn_deadzone` | 0x4f3110 | TURN STICK DEADZONE | МЕРТВАЯ ЗОНА ПОВОРОТА | — |
| 31 | `mevr_reduce_head_bob` | 0x4f3140 | REDUCE HEAD BOB | УМЕНЬШИТЬ КАЧАНИЕ | — |

#### ТЕЛО

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 32 | `mevr_play_mode` | 0x4f3190 | PLAY MODE | РЕЖИМ ИГРЫ | ROOM-SCALE → МАСШТАБ; STANDING → СТОЯ; SEATED → СИДЯ |
| 33 | `mevr_player_height` | 0x4f31e0 | PLAYER HEIGHT | РОСТ ИГРОКА | — |
| 34 | `mevr_world_scale` | 0x4f3208 | WORLD SCALE | МАСШТАБ МИРА | — |
| 35 | `mevr_physical_crouch` | 0x4f3298 | PHYSICAL CROUCH | ФИЗИЧЕСКОЕ ПРИСЕДАНИЕ | — |
| 36 | `mevr_belt_height` | 0x4f32c0 | BELT HEIGHT | ВЫСОТА ПОЯСА | — |
| 37 | `mevr_belt_crouch` | 0x4f32e8 | BELT WHEN CROUCHING | ПОЯС В ПРИСЕДЕ | STAY WITH YOU → ОСТАВАТЬСЯ С ВАМИ; FOLLOW BODY → СЛЕДОВАТЬ ЗА ТЕЛОМ; AUTO → АВТО |
| 38 | `mevr_body_turning` | 0x4f3230 | BODY TURNING | ПОВОРОТ ТЕЛА | FOLLOW HEAD → СЛЕДОВАТЬ ЗА ГОЛОВОЙ; LOCKED → ЗАБЛОКИРОВАНО |
| 39 | `mevr_body_position` | 0x4f3268 | BODY POSITION | ПОЛОЖЕНИЕ ТЕЛА | FOLLOW → СЛЕДОВАТЬ; LOCKED → ЗАБЛОКИРОВАНО |

#### РУКИ

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 40 | `mevr_bhaptics` | 0x4f3330 | BHAPTICS (EXPERIMENTAL) | BHAPTICS (ЭКСПЕРИМ.) | — |
| 41 | `mevr_bhaptics_strength` | 0x4f3360 | BHAPTICS STRENGTH | СИЛА BHAPTICS | — |
| 42 | `mevr_dominant_hand` | 0x4f3390 | DOMINANT HAND | ОСНОВНАЯ РУКА | RIGHT → ПРАВАЯ; LEFT → ЛЕВАЯ |
| 43 | `mevr_grip_angle` | 0x4f33c0 | WEAPON GRIP ANGLE | УГОЛ ХВАТА ОРУЖИЯ | {} DEG → {} ГРАД |
| 44 | `mevr_finger_tracking` | 0x4f33f0 | FINGER TRACKING | ОТСЛЕЖИВАНИЕ ПАЛЬЦЕВ | — |
| 45 | `mevr_grab` | 0x4f340c | GRIP | ХВАТ | HOLD → УДЕРЖ.; TOGGLE → ПЕРЕКЛ. |
| 46 | `mevr_backpack_in_hand` | 0x4f3430 | BACKPACK IN HAND | РЮКЗАК В РУКЕ | — |
| 47 | `mevr_use_reach` | 0x4f3560 | USE REACH | РАДИУС ВЗАИМОДЕЙСТВИЯ | — |
| 48 | `mevr_use_by_looking` | 0x4f3588 | USE BY LOOKING | ИСПОЛЬЗОВАТЬ ВЗГЛЯДОМ | — |

#### ВИБРАЦИЯ

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 49 | `mevr_vibration` | 0x4f3458 | VIBRATION | ВИБРАЦИЯ | — |
| 50 | `mevr_vibration_cues` | 0x4f3480 | HAND CUES | ПОДСКАЗКИ РУК | — |
| 51 | `mevr_vibration_weapons` | 0x4f34a8 | WEAPONS | ОРУЖИЕ | — |
| 52 | `mevr_vibration_damage` | 0x4f34c8 | DAMAGE | УРОН | — |
| 53 | `mevr_vibration_world` | 0x4f34e8 | EXPLOSIONS | ВЗРЫВЫ | — |
| 54 | `mevr_vibration_scenes` | 0x4f3510 | SCENES AND VEHICLES | СЦЕНЫ И ТРАНСПОРТ | — |
| 55 | `mevr_vibration_movement` | 0x4f3540 | MOVEMENT | ДВИЖЕНИЕ | — |

#### ОРУЖИЕ

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 56 | `mevr_weapon_weight` | 0x4f35b0 | WEAPON WEIGHT | ВЕС ОРУЖИЯ | — |
| 57 | `mevr_manual_reload` | 0x4f35d8 | MANUAL RELOADING | РУЧНАЯ ПЕРЕЗАРЯДКА | — |
| 58 | `mevr_part_highlights` | 0x4f3608 | PART HIGHLIGHTS | ПОДСВЕТКА ЧАСТЕЙ | OFF → ВЫКЛ; FIRST RELOADS → ПЕРВЫЕ ПЕРЕЗАРЯДКИ; ALWAYS → ВСЕГДА |
| 59 | `mevr_part_highlights_reset` | 0x4f3650 | RESET HIGHLIGHT COUNTS | СБРОСИТЬ СЧЕТЧИКИ ПОДСВЕТКИ | — |
| 60 | `mevr_revolver_flick` | 0x4f3680 | WEAPON FLICK | ВСТРЯХИВАНИЕ ОРУЖИЯ | OFF → ВЫКЛ; GENTLE → МЯГКО; NORMAL → ОБЫЧНО; HARD → СИЛЬНО |
| 61 | `mevr_reload_pouch` | 0x4f36c0 | MAGAZINE POUCH | ПОДСУМОК ДЛЯ МАГАЗИНОВ | HIP → БЕДРО |

#### ПРИЦЕЛЫ

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 62 | `mevr_sighting_eye` | 0x4f36f0 | SIGHTING EYE | ГЛАЗ ПРИЦЕЛА | AUTO → АВТО; LEFT → ЛЕВАЯ; RIGHT → ПРАВАЯ |
| 63 | `mevr_other_eye` | 0x4f3710 | OTHER EYE WHILE SCOPED | ВТОРОЙ ГЛАЗ В ПРИЦЕЛЕ | VISIBLE → ВИДИМО; BLURRED → РАЗМЫТО; BLACK → ЧЕРНЫЙ |
| 64 | `mevr_reticle` | 0x4f3750 | RETICLE TILT | НАКЛОН ПРИЦЕЛА | WITH WEAPON → С ОРУЖИЕМ; LEVEL → УРОВЕНЬ; FIXED TO VIEW → ФИКСИРОВАНО |
| 65 | `mevr_scope_steering` | 0x4f37a0 | SCOPE STEERING | НАВЕДЕНИЕ ПРИЦЕЛА | WEAPON → ОРУЖИЕ; WEAPON + HEAD → ОРУЖИЕ + ГОЛОВА |
| 66 | `mevr_night_vision_tube` | 0x4f37e0 | REALISTIC NIGHT VISION | РЕАЛИСТИЧНОЕ НОЧНОЕ ВИДЕНИЕ | — |

#### ИНТЕРФЕЙС

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 67 | `mevr_hud_shape` | 0x4f3808 | HUD SHAPE | ФОРМА HUD | — |
| 68 | `mevr_hud_position` | 0x4f3838 | HUD POSITION | ПОЛОЖЕНИЕ HUD | LOCKED → ЗАБЛОКИРОВАНО; FOLLOW → СЛЕДОВАТЬ |
| 69 | `mevr_hud_distance` | 0x4f3860 | HUD DISTANCE | РАССТОЯНИЕ HUD | — |
| 70 | `mevr_hud_size` | 0x4f3880 | HUD SIZE | РАЗМЕР HUD | {:.2f} M → {:.2f} М |
| 71 | `mevr_hud_height` | 0x4f38a0 | HUD HEIGHT | ВЫСОТА HUD | {:+.0f} DEG → {:+.0f} ГРАД |
| 72 | `mevr_hud_opacity` | 0x4f38d8 | HUD OPACITY | ПРОЗРАЧНОСТЬ HUD | — |
| 73 | `mevr_hint_height` | 0x4f3900 | HINT HEIGHT | ВЫСОТА ПОДСКАЗКИ | — |
| 74 | `mevr_hint_size` | 0x4f3928 | HINT SIZE | РАЗМЕР ПОДСКАЗКИ | — |
| 75 | `mevr_hint_time` | 0x4f3950 | HINT TIME | ВРЕМЯ ПОДСКАЗКИ | 1.00X → 1.00X; 1.25X → 1.25X; 1.50X → 1.50X; 2.00X → 2.00X |
| 76 | `mevr_prompt_size` | 0x4f3998 | ACTION PROMPT SIZE | РАЗМЕР ПОДСКАЗКИ ДЕЙСТВИЯ | — |
| 77 | `mevr_menu_distance` | 0x4f39d0 | MENU DISTANCE | РАССТОЯНИЕ МЕНЮ | — |
| 78 | `mevr_menu_size` | 0x4f39f0 | MENU SIZE | РАЗМЕР МЕНЮ | {:.1f} M → {:.1f} М |
| 79 | `mevr_damage_effects` | 0x4f3a28 | DAMAGE EFFECTS | ЭФФЕКТЫ УРОНА | — |
| 80 | `mevr_damage_size` | 0x4f3a50 | DAMAGE EFFECT SIZE | РАЗМЕР ЭФФЕКТОВ УРОНА | SMALL → МАЛЫЙ; MEDIUM → СРЕДНИЙ; LARGE → БОЛЬШОЙ |
| 81 | `mevr_hit_direction` | 0x4f3a98 | HIT DIRECTION | НАПРАВЛЕНИЕ УДАРА | — |
| 82 | `mevr_health_pulse` | 0x4f3ac0 | LOW-HEALTH PULSE | ПУЛЬС ПРИ РАНЕНИИ | — |
| 83 | `mevr_debug_overlay` | 0x4f3af0 | DEBUG OVERLAY | ОТЛАДОЧНЫЙ ОВЕРЛЕЙ | — |

#### КОМФОРТ

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 84 | `mevr_camera_preset` | 0x4f3bc0 | CAMERA PRESET | ПРЕСЕТ КАМЕРЫ | IMMERSIVE → ИММЕРСИВНЫЙ; CINEMATIC → КИНЕМАТОГРАФИЧНЫЙ; COMFORT → КОМФОРТНЫЙ |
| 85 | `mevr_realign` | 0x4f3c08 | RE-ALIGN AFTER SCENES | ВЫРАВНИВАТЬ ПОСЛЕ СЦЕН | OFF → ВЫКЛ; SNAP → РЕЗКО; SMOOTH → ПЛАВНО |
| 86 | `mevr_head_leash` | 0x4f3c30 | HEAD LEASH | ПРИВЯЗКА ГОЛОВЫ | — |
| 87 | `mevr_cinema_floor` | 0x4f3b18 | CINEMA FLOOR | ПОЛ КИНО | — |
| 88 | `mevr_cinema_controllers` | 0x4f3b40 | CINEMA CONTROLLERS | КОНТРОЛЛЕРЫ КИНО | — |
| 89 | `mevr_cinema_info` | 0x4f3b70 | CINEMA INFO | ИНФО КИНО | — |
| 90 | `mevr_cinema_links` | 0x4f3b98 | CINEMA LINKS | ССЫЛКИ КИНО | — |
| 91 | `mevr_cinema_distance` | 0x4f3c58 | CINEMA SCREEN DISTANCE | РАССТОЯНИЕ ЭКРАНА КИНО | — |
| 92 | `mevr_cinema_size` | 0x4f3c88 | CINEMA SCREEN SIZE | РАЗМЕР ЭКРАНА КИНО | — |

#### ПЕРЕОПРЕДЕЛЕНИЯ КАМЕРЫ

| # | id | RVA | Оригинал | Перевод | Значения |
| --- | --- | --- | --- | --- | --- |
| 93 | `mevr_camera_cinematic_track` | 0x4e3158 | CINEMATIC TRACK | СЦЕНАРНЫЙ ПУТЬ | — |
| 94 | `mevr_camera_attached` | 0x4e3168 | ATTACHED | ПРИКРЕПЛЕНА | — |
| 95 | `mevr_camera_third_person` | 0x4e31a0 | THIRD PERSON | ТРЕТЬЕ ЛИЦО | — |
| 96 | `mevr_camera_free_cam` | 0x4f3cf8 | FREE CAMERA | СВОБОДНАЯ КАМЕРА | — |
| 97 | `mevr_camera_station` | 0x4e3198 | STATION | СТАЦИОНАРНАЯ | — |
| 98 | `mevr_camera_animation_lock` | 0x4f3d90 | ANIMATION LOCK | БЛОКИРОВКА АНИМАЦИИ | — |
| 99 | `mevr_camera_scripted_lock` | 0x4f3d60 | SCRIPTED LOCK | БЛОКИРОВКА СКРИПТОМ | — |
| 100 | `mevr_camera_bone_angles` | 0x4f3d38 | BONE ANGLES | УГЛЫ КОСТЕЙ | — |
| 101 | `mevr_camera_axis_locked` | 0x4f3dc0 | AXIS LOCKED | ОСЬ ЗАБЛОКИРОВАНА | — |
| 102 | `mevr_camera_gameplay_ui` | 0x4f3de8 | GAMEPLAY UI | ИГРОВОЙ ИНТЕРФЕЙС | — |

---

## 2. Подсказки к пунктам меню

Показываются внизу экрана, когда курсор стоит на пункте. «Индекс» —
позиция в `ui2-0.9.3.json` → `options` (по ней искать строку в файле).

### VR

**0. SHOW VR TIPS AGAIN — СНОВА ПОКАЗАТЬ СОВЕТЫ VR**

- EN: Reset the VR tips you have already seen, as on a first playthrough.
- RU: Сбрасывает уже показанные советы VR, как при первом прохождении.

### ГРАФИКА

**1. RENDER MODE — РЕЖИМ РЕНДЕРА**

- EN: STEREO renders both eyes every frame. PERFORMANCE renders one eye per frame, in turn, and rebuilds the other: much faster at a very slight cost of quality in fast motion.
- RU: СТЕРЕО рендерит оба глаза каждый кадр. ПРОИЗВОДИТЕЛЬНОСТЬ рендерит по одному глазу за кадр по очереди и восстанавливает второй: намного быстрее при очень небольшой потере качества в быстром движении.

**2. RENDER SCALE (RESTART) — МАСШТАБ РЕНДЕРА (ПЕРЕЗАПУСК)**

- EN: The rendering resolution against what your VR runtime asks for. Higher is sharper, lower is faster. Takes effect after a restart.
- RU: Разрешение рендеринга относительно запрошенного вашей средой VR. Выше – четче, ниже – быстрее. Применяется после перезапуска.

**3. UPSCALER — АПСКЕЙЛЕР**

- EN: Renders the game at a lower resolution and upscales it, for more performance. FSR works on any GPU, DLSS on NVIDIA RTX cards.
- RU: Рендерит игру в более низком разрешении и масштабирует изображение для большей производительности. FSR работает на любых GPU, DLSS – на картах NVIDIA RTX.

**4. UPSCALING MODE — РЕЖИМ АПСКЕЙЛА**

- EN: How low the upscaler renders. NATIVE AA keeps the full resolution and only smooths edges; the lower modes are faster but less sharp.
- RU: Насколько низко рендерит апскейлер. НАТИВНОЕ СГЛАЖИВАНИЕ сохраняет полное разрешение и только сглаживает края; более низкие режимы быстрее, но менее четкие.

**5. DLSS MODEL — МОДЕЛЬ DLSS**

- EN: Which DLSS model upscales. The DLSS 4.5 models look best but cost the most; AUTO uses K.
- RU: Какая модель DLSS масштабирует. Модели DLSS 4.5 выглядят лучше всего, но требуют больше всего ресурсов; АВТО использует K.

**6. FOVEATED UPSCALING — ФОВЕАЛЬНЫЙ АПСКЕЙЛ**

- EN: Upscales only the middle of each eye's view, where you look, and keeps the edges simpler. Smaller angles are faster.
- RU: Масштабирует только середину обзора каждого глаза, куда вы смотрите, а края оставляет проще. Меньшие углы быстрее.

**7. FOVEATED PERIPHERY — ФОВЕАЛЬНАЯ ПЕРИФЕРИЯ**

- EN: How the edges outside FOVEATED UPSCALING's middle area are smoothed. NATIVE (FSR/FSR) is sharper but slower, TAA is faster and more blurry.
- RU: Как сглаживаются края за пределами средней области ФОВЕАЛЬНОГО АПСКЕЙЛА. НАТИВНОЕ (FSR/FSR) четче, но медленнее, TAA быстрее и более размыто.

**8. DESKTOP MIRROR — ЗЕРКАЛО РАБОЧЕГО СТОЛА**

- EN: What the desktop window shows while you play.
- RU: Что показывает окно на рабочем столе во время игры.

**9. MIRROR HEADSET UI — ЗЕРКАЛИРОВАТЬ UI ШЛЕМА**

- EN: The mirror also shows the HUD, menus and use prompts where the headset shows them, so it matches the headset exactly. For recording; slight performance cost.
- RU: Зеркало также показывает HUD, меню и подсказки использования там, где их показывает шлем, поэтому точно совпадает со шлемом. Для записи; небольшое снижение производительности.

**10. FOVEATED RENDERING — ФОВЕАЛЬНЫЙ РЕНДЕРИНГ**

- EN: Renders the edges of your view in less detail, where you notice it least, for more performance. NVIDIA GPUs only.
- RU: Рендерит края обзора с меньшей детализацией, там, где вы это меньше всего замечаете, для большей производительности. Только GPU NVIDIA.

**11. BETTER WATER REFLECTIONS — ЛУЧШИЕ ОТРАЖЕНИЯ ВОДЫ**

- EN: More accurate reflections on water, reaching further. Small performance penalty.
- RU: Более точные отражения на воде, простирающиеся дальше. Небольшое снижение производительности.

**12. DISABLE BLUR — ОТКЛЮЧИТЬ РАЗМЫТИЕ**

- EN: Turns off the game's motion blur, which can be uncomfortable in VR.
- RU: Отключает размытие движения в игре, которое может быть некомфортным в VR.

**13. DEPTH OF FIELD — ГЛУБИНА РЕЗКОСТИ**

- EN: Controls game's Depth of Field which may look weird/blurry in VR. All bars is the game's own amount.
- RU: Управляет глубиной резкости игры, которая в VR может выглядеть странно или размыто. Все ползунки – собственное значение игры.

**14. DEEP BLACKS — ГЛУБОКИЙ ЧЕРНЫЙ**

- EN: Darker, truer blacks: removes the grey lift some areas' color grading adds, as the Enhanced Edition's -deependark option does. Best on OLED headsets.
- RU: Более глубокий и точный черный: убирает серую засветку, которую цветокоррекция некоторых зон добавляет к черному, как опция -deependark в Enhanced Edition. Лучше всего смотрится на OLED-шлемах.

**15. HUD RESOLUTION (RESTART) — РАЗРЕШЕНИЕ HUD (ПЕРЕЗАПУСК)**

- EN: How sharp the HUD and menus are. Higher is crisper and costs a little more. Takes effect after a restart.
- RU: Насколько четкие HUD и меню. Выше – четче и немного затратнее. Применяется после перезапуска.

**16. DEPTH REPROJECTION — РЕПРОЕКЦИЯ ГЛУБИНЫ**

- EN: Gives the VR runtime the depth of each frame, so a late frame is shown steadier. Used only where the headset supports it.
- RU: Передает среде VR глубину каждого кадра, чтобы запоздавший кадр отображался стабильнее. Используется только там, где шлем это поддерживает.

### ДВИЖЕНИЕ

**17. MOVEMENT DIRECTION — НАПРАВЛЕНИЕ ДВИЖЕНИЯ**

- EN: Which way pushing the move stick forward takes you: where you look, where your body faces, or where a controller points.
- RU: Куда ведет наклон стика движения вперед: туда, куда вы смотрите, куда повернуто тело или куда указывает контроллер.

**18. CROUCH BUTTON — КНОПКА ПРИСЕДА**

- EN: HOLD crouches while the button is held. TOGGLE crouches with one press and stands up with the next.
- RU: УДЕРЖ. приседает, пока кнопка удерживается. ПЕРЕКЛ. приседает одним нажатием и встает следующим.

**19. AUTO SPRINT — АВТОБЕГ**

- EN: Sprint without a button: flick the move stick fully forward, let go, then push it fully forward again and hold to start sprinting.
- RU: Бег без кнопки: резко отклоните стик движения до упора вперед, отпустите, затем снова отклоните до упора вперед и удерживайте, чтобы начать бег.

**20. MOVE STICK DEADZONE — МЕРТВАЯ ЗОНА СТИКА**

- EN: How far the move stick must be pushed before you move. Raise it if you drift with the stick untouched.
- RU: Насколько далеко нужно отклонить стик движения, прежде чем вы начнете двигаться. Увеличьте, если вас сносит при нетронутом стике.

**21. TURN STICK DEADZONE — МЕРТВАЯ ЗОНА ПОВОРОТА**

- EN: How far the turn stick must be pushed before you turn. Raise it if you turn by accident.
- RU: Насколько далеко нужно отклонить стик поворота, прежде чем вы начнете поворачиваться. Увеличьте, если поворачиваетесь случайно.

**22. REDUCE HEAD BOB — УМЕНЬШИТЬ КАЧАНИЕ**

- EN: Tones down the game's camera bob while walking and running, which can be uncomfortable in VR.
- RU: Уменьшает качание камеры в игре при ходьбе и беге, которое может быть некомфортным в VR.

### ТЕЛО

**23. PLAY MODE — РЕЖИМ ИГРЫ**

- EN: ROOM-SCALE lets you walk around your room. STANDING keeps you in one place. SEATED is for playing sitting down.
- RU: МАСШТАБ позволяет ходить по комнате. СТОЯ удерживает вас на одном месте. СИДЯ предназначен для игры сидя.

**24. PLAYER HEIGHT — РОСТ ИГРОКА**

- EN: Your real height, so the game can tell when you crouch. NOT SET uses the headset alone.
- RU: Ваш реальный рост, чтобы игра определяла, когда вы приседаете. НЕТ использует только данные шлема.

**25. WORLD SCALE — МАСШТАБ МИРА**

- EN: How big the world looks. The game assets are built larger than in real life; 94% looks closest to real sizes.
- RU: Насколько большим выглядит мир. Игровые модели построены крупнее, чем в реальности; 94% выглядит ближе всего к реальным размерам.

**26. PHYSICAL CROUCH — ФИЗИЧЕСКОЕ ПРИСЕДАНИЕ**

- EN: Crouching in real life crouches in the game. Needs PLAYER HEIGHT.
- RU: Приседание в реальной жизни приседает в игре. Требуется РОСТ ИГРОКА.

**27. BELT HEIGHT — ВЫСОТА ПОЯСА**

- EN: Moves everything worn on the belt up or down: the holster, the magazine pouch, the gas mask, throwables, and the binoculars and charger on your back.
- RU: Двигает вверх или вниз все, что носится на поясе: кобуру, подсумок для магазинов, противогаз, метательные предметы, а также бинокль и зарядное устройство на спине.

**28. BELT WHEN CROUCHING — ПОЯС В ПРИСЕДЕ**

- EN: STAY WITH YOU keeps the belt where your own is when you crouch. FOLLOW BODY moves it with the character's body. AUTO follows a real-life crouch only; set PLAYER HEIGHT for it (NOT SET: 178 CM).
- RU: ОСТАВАТЬСЯ С ВАМИ сохраняет пояс там, где ваш собственный, когда вы приседаете. СЛЕДОВАТЬ ЗА ТЕЛОМ двигает его вместе с телом персонажа. АВТО следует за приседанием в реальной жизни; укажите РОСТ ИГРОКА (НЕТ: 178 СМ).

**29. BODY TURNING — ПОВОРОТ ТЕЛА**

- EN: FOLLOW HEAD turns your body after your head once you look far enough to the side. LOCKED turns it only with the turn stick.
- RU: СЛЕДОВАТЬ ЗА ГОЛОВОЙ поворачивает тело за головой, когда вы достаточно далеко посмотрите в сторону. ЗАБЛОКИРОВАНО поворачивает его только стиком поворота.

**30. BODY POSITION — ПОЛОЖЕНИЕ ТЕЛА**

- EN: FOLLOW lets you lean and step freely, the body walking after you. LOCKED keeps your view over the body, and real steps move the body along.
- RU: СЛЕДОВАТЬ позволяет свободно наклоняться и шагать, тело идет за вами. ЗАБЛОКИРОВАНО удерживает взгляд над телом, а реальные шаги двигают тело вперед.

### РУКИ

**31. BHAPTICS (EXPERIMENTAL) — BHAPTICS (ЭКСПЕРИМ.)**

- EN: Experimental: enables support for bHaptics. Requires the bHaptics Player to be installed. You feel shots, hits, explosions, the heartbeat, landings and steps.
- RU: Экспериментально: включает поддержку bHaptics. Требуется установленный bHaptics Player. Вы чувствуете выстрелы, удары, взрывы, сердцебиение, приземления и шаги.

**32. WEAPON GRIP ANGLE — УГОЛ ХВАТА ОРУЖИЯ**

- EN: Tilts weapons and items in your hand up or down, to match how you hold your controller.
- RU: Наклоняет оружие и предметы в руке вверх или вниз, чтобы соответствовать тому, как вы держите контроллер.

**33. FINGER TRACKING — ОТСЛЕЖИВАНИЕ ПАЛЬЦЕВ**

- EN: Your fingers follow your real ones where the controllers sense them. Off, they follow the trigger, grip and buttons.
- RU: Ваши пальцы следуют за реальными там, где контроллеры их распознают. Если выключено, они следуют за триггером, хватом и кнопками.

**34. GRIP — ХВАТ**

- EN: HOLD keeps what you take while the grip is held. TOGGLE takes it with one grip and puts it back with a grip where it was taken.
- RU: УДЕРЖ. держит взятое, пока удерживается хват. ПЕРЕКЛ. берет одним хватом и возвращает хватом туда, откуда взяли.

**35. BACKPACK IN HAND — РЮКЗАК В РУКЕ**

- EN: Gripping over your support shoulder takes the backpack into that hand. Take things hanging on it with your other hand; pull the trigger to open it. Off, the grip opens the backpack at once.
- RU: Хват над вторым плечом берет рюкзак в эту руку. Висящие на нем предметы берите другой рукой; нажмите триггер, чтобы открыть его. Если выключено, хват сразу открывает рюкзак.

**36. USE REACH — РАДИУС ВЗАИМОДЕЙСТВИЯ**

- EN: How far from your hand you can grab and use things. Raise it if things are hard to reach. Some small switches still need you closer.
- RU: Насколько далеко от руки можно хватать и использовать предметы. Увеличьте, если до предметов трудно дотянуться. Некоторые мелкие переключатели все равно требуют подойти ближе.

**37. USE BY LOOKING — ИСПОЛЬЗОВАТЬ ВЗГЛЯДОМ**

- EN: With nothing in your hand's reach, the use button uses what you look at, as in the flat game. Helps with things a hand cannot reach.
- RU: Когда в пределах досягаемости руки ничего нет, кнопка использования применяет то, на что вы смотрите, как в обычной игре. Помогает с предметами, до которых рука не достает.

### ВИБРАЦИЯ

**38. VIBRATION — ВИБРАЦИЯ**

- EN: How strongly the controllers vibrate. 50% is as the game made it, 100% twice that; 0% turns all vibration off.
- RU: Насколько сильно вибрируют контроллеры. 50% – как задумано игрой, 100% – вдвое сильнее; 0% отключает всю вибрацию.

**39. HAND CUES — ПОДСКАЗКИ РУК**

- EN: Light ticks as your hand reaches a body slot, something to take, a weapon part or a device.
- RU: Легкие толчки, когда рука достигает ячейки на теле, предмета, части оружия или устройства.

**40. WEAPONS — ОРУЖИЕ**

- EN: The kick of every shot in the hands holding the gun, and the weapons' own vibration.
- RU: Отдача каждого выстрела в руках, держащих оружие, и собственная вибрация оружия.

**41. DAMAGE — УРОН**

- EN: Vibration when you are hit or hurt.
- RU: Вибрация, когда вас ударяют или ранят.

**42. SCENES AND VEHICLES — СЦЕНЫ И ТРАНСПОРТ**

- EN: Vibration in scripted scenes and while riding vehicles.
- RU: Вибрация в сюжетных сценах и при езде на транспорте.

**43. MOVEMENT — ДВИЖЕНИЕ**

- EN: Light steps while running, and landings.
- RU: Легкие шаги при беге и приземления.

### ОРУЖИЕ

**44. WEAPON WEIGHT — ВЕС ОРУЖИЯ**

- EN: How heavy weapons feel. Fast swings trail your hand and settle; slow aiming stays precise. Lighter with two hands. 0% only steadies hand shake.
- RU: Насколько тяжелым ощущается оружие. Быстрые взмахи следуют за рукой и затухают; медленное прицеливание остается точным. Легче при удержании двумя руками. 0% только стабилизирует дрожание рук.

**45. MANUAL RELOADING — РУЧНАЯ ПЕРЕЗАРЯДКА**

- EN: Reload with your hands: work magazines, bolts, levers and pumps yourself.
- RU: Перезаряжайте руками: самостоятельно управляйтесь с магазинами, затворами, рычагами и помпами.

**46. PART HIGHLIGHTS — ПОДСВЕТКА ЧАСТЕЙ**

- EN: Outlines the next weapon part to work while reloading: always, only for your first few reloads, or never.
- RU: Обводит следующую часть оружия, с которой нужно работать при перезарядке: всегда, только для первых нескольких перезарядок или никогда.

**47. RESET HIGHLIGHT COUNTS — СБРОСИТЬ СЧЕТЧИКИ ПОДСВЕТКИ**

- EN: Turn on to start the FIRST RELOADS count over, so the highlights show again.
- RU: Включите, чтобы начать счет ПЕРВЫХ ПЕРЕЗАРЯДОК заново, и подсветка снова показывалась.

**48. WEAPON FLICK — ВСТРЯХИВАНИЕ ОРУЖИЯ**

- EN: Flick your wrist to swing a revolver or the Ashot open (to the left) and shut (to the right). Sets how hard the flick must be.
- RU: Встряхните кистью, чтобы открыть револьвер или Ашот (влево) и закрыть (вправо). Задает силу, с которой нужно встряхивать.

### ПРИЦЕЛЫ

**49. SIGHTING EYE — ГЛАЗ ПРИЦЕЛА**

- EN: Which eye looks through scopes. AUTO uses the eye on the side of your head the scope is on.
- RU: Какой глаз смотрит через прицелы. АВТО использует глаз с той стороны головы, с которой находится прицел.

**50. OTHER EYE WHILE SCOPED — ВТОРОЙ ГЛАЗ В ПРИЦЕЛЕ**

- EN: What your other eye sees while you look through a scope.
- RU: Что видит второй глаз, пока вы смотрите через прицел.

**51. RETICLE TILT — НАКЛОН ПРИЦЕЛА**

- EN: How the scope's reticle tilts: with the weapon, level with the horizon, or fixed in your view.
- RU: Как наклоняется сетка прицела: вместе с оружием, по горизонту или фиксировано в вашем обзоре.

**52. SCOPE STEERING — НАВЕДЕНИЕ ПРИЦЕЛА**

- EN: WEAPON: the scope's view follows the gun alone. WEAPON + HEAD: your head helps too, keeping the scope's picture in the middle of your view.
- RU: ОРУЖИЕ: вид в прицеле следует только за оружием. ОРУЖИЕ + ГОЛОВА: голова тоже помогает, удерживая изображение прицела в середине обзора.

**53. REALISTIC NIGHT VISION — РЕАЛИСТИЧНОЕ НОЧНОЕ ВИДЕНИЕ**

- EN: Night vision is seen through a tube, dark around it, as with real goggles. Off, it fills your whole view.
- RU: Ночное видение видно через трубку, вокруг темно, как в настоящих очках. Если выключено, оно заполняет весь обзор.

### ИНТЕРФЕЙС

**54. HUD SHAPE — ФОРМА HUD**

- EN: The HUD's layout. 4:3 brings its edges closer to the middle of your view.
- RU: Раскладка HUD. 4:3 приближает его края к середине обзора.

**55. HUD POSITION — ПОЛОЖЕНИЕ HUD**

- EN: LOCKED keeps the HUD fixed in front of your eyes. FOLLOW leaves it in place and brings it back once you look away.
- RU: ЗАБЛОКИРОВАНО фиксирует HUD перед глазами. СЛЕДОВАТЬ оставляет его на месте и возвращает, когда вы отводите взгляд.

**56. HUD DISTANCE — РАССТОЯНИЕ HUD**

- EN: Moves the HUD above or below your line of sight.
- RU: Двигает HUD выше или ниже линии взгляда.

**57. HINT HEIGHT — ВЫСОТА ПОДСКАЗКИ**

- EN: Moves the game's hint cards up or down.
- RU: Двигает подсказки игры вверх или вниз.

**58. HINT TIME — ВРЕМЯ ПОДСКАЗКИ**

- EN: How much longer the game's timed hints stay up.
- RU: Насколько дольше остаются подсказки игры с таймером.

**59. ACTION PROMPT SIZE — РАЗМЕР ПОДСКАЗКИ ДЕЙСТВИЯ**

- EN: The size of the prompts in the middle of the view: quick-time events, use and melee.
- RU: Размер подсказок в середине обзора: быстрых событий, использования и ближнего боя.

**60. DAMAGE EFFECTS — ЭФФЕКТЫ УРОНА**

- EN: Shows hits and low health as a glow around the edge of your view, in place of the game's flat screen effects.
- RU: Показывает попадания и низкое здоровье свечением по краю обзора вместо плоских экранных эффектов игры.

**61. DAMAGE EFFECT SIZE — РАЗМЕР ЭФФЕКТОВ УРОНА**

- EN: How far into your view the damage glow reaches.
- RU: Насколько далеко в обзор проникает свечение урона.

**62. HIT DIRECTION — НАПРАВЛЕНИЕ УДАРА**

- EN: Shows an arc toward whoever just hit you.
- RU: Показывает дугу в сторону того, кто вас только что ударил.

**63. LOW-HEALTH PULSE — ПУЛЬС ПРИ РАНЕНИИ**

- EN: The edge of your view pulses while your health is low.
- RU: Край обзора пульсирует, пока здоровье низкое.

**64. DEBUG OVERLAY — ОТЛАДОЧНЫЙ ОВЕРЛЕЙ**

- EN: Shows camera details in a corner of the view. Meant for testing.
- RU: Показывает данные камеры в углу обзора. Предназначено для тестирования.

### КОМФОРТ

**69. CAMERA PRESET — ПРЕСЕТ КАМЕРЫ**

- EN: What plays in VR and what on a flat Cinema screen. IMMERSIVE: all in VR. COMFORT: cutscenes on the screen. CINEMATIC: all but gameplay on the screen.
- RU: Что воспроизводится в VR, а что на плоском экране кино. ИММЕРСИВНЫЙ: все в VR. КОМФОРТНЫЙ: катсцены на экране. КИНЕМАТОГРАФИЧНЫЙ: все, кроме геймплея, на экране.

**70. RE-ALIGN AFTER SCENES — ВЫРАВНИВАТЬ ПОСЛЕ СЦЕН**

- EN: After a scene moves your view, lines it back up with where the game expects it: at once (SNAP) or gliding (SMOOTH).
- RU: После того как сцена сместит ваш взгляд, выравнивает его с тем, что ожидает игра: сразу (РЕЗКО) или плавно (ПЛАВНО).

**71. HEAD LEASH — ПРИВЯЗКА ГОЛОВЫ**

- EN: In a car or a scene, where the game moves you: if your head moves this far from where the game has it, your view jumps back there. LOCKED keeps your view there all the time; you can still look around.
- RU: В машине или сцене, где вас перемещает игра: если голова уходит от положения, заданного игрой, на это расстояние, взгляд возвращается туда. ЗАБЛОКИРОВАНО удерживает взгляд там все время; осматриваться при этом можно.

**65. CINEMA FLOOR — ПОЛ КИНО**

- EN: A dim dotted floor under the Cinema screen, so you do not float in the dark.
- RU: Тусклый точечный пол под экраном кино, чтобы вы не парили в темноте.

**66. CINEMA CONTROLLERS — КОНТРОЛЛЕРЫ КИНО**

- EN: Shows your controllers while the Cinema screen is up.
- RU: Показывает ваши контроллеры, пока открыт экран кино.

**67. CINEMA INFO — ИНФО КИНО**

- EN: In the main menu, a plaque under the Cinema screen with the mod's name and version.
- RU: В главном меню – табличка под экраном кино с названием и версией мода.

**68. CINEMA LINKS — ССЫЛКИ КИНО**

- EN: In the main menu, links under the Cinema screen (Buy Me a Coffee, Ko-fi, GitHub). Point at the plaque to show them; a click opens the page in your desktop browser, behind the game.
- RU: В главном меню – ссылки под экраном кино (Buy Me a Coffee, Ko-fi, GitHub). Наведите на табличку, чтобы показать их; щелчок открывает страницу в браузере на рабочем столе, за игрой.

### ПЕРЕОПРЕДЕЛЕНИЯ КАМЕРЫ

**72. CINEMATIC TRACK — СЦЕНАРНЫЙ ПУТЬ**

- EN: Scenes where the camera follows a scripted path. AUTO follows CAMERA PRESET.
- RU: Сцены, где камера следует по заданному пути. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**73. ATTACHED — ПРИКРЕПЛЕНА**

- EN: Scenes where the camera rides on someone or something else. AUTO follows CAMERA PRESET.
- RU: Сцены, где камера закреплена на ком-то или чем-то другом. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**74. THIRD PERSON — ТРЕТЬЕ ЛИЦО**

- EN: Third-person views. AUTO follows CAMERA PRESET.
- RU: Вид от третьего лица. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**75. FREE CAMERA — СВОБОДНАЯ КАМЕРА**

- EN: Scenes with a free-flying camera. AUTO follows CAMERA PRESET.
- RU: Сцены со свободно летающей камерой. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**76. STATION — СТАЦИОНАРНАЯ**

- EN: Seats and mounted guns. AUTO follows CAMERA PRESET.
- RU: Сиденья и станковые орудия. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**77. ANIMATION LOCK — БЛОКИРОВКА АНИМАЦИИ**

- EN: Scenes where an animation turns your view. AUTO follows CAMERA PRESET.
- RU: Сцены, где анимация поворачивает ваш взгляд. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**78. SCRIPTED LOCK — БЛОКИРОВКА СКРИПТОМ**

- EN: Moments when the story locks the camera. AUTO follows CAMERA PRESET.
- RU: Моменты, когда сюжет блокирует камеру. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**79. BONE ANGLES — УГЛЫ КОСТЕЙ**

- EN: Moments when your character's own animation holds the camera. AUTO follows CAMERA PRESET.
- RU: Моменты, когда камеру удерживает анимация вашего персонажа. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**80. AXIS LOCKED — ОСЬ ЗАБЛОКИРОВАНА**

- EN: Short moments when the game holds your body without locking the camera, such as getting down into a crawl. AUTO follows CAMERA PRESET.
- RU: Короткие моменты, когда игра удерживает ваше тело, не блокируя камеру, например когда вы опускаетесь на четвереньки. АВТО следует ПРЕСЕТУ КАМЕРЫ.

**81. GAMEPLAY UI — ИГРОВОЙ ИНТЕРФЕЙС**

- EN: Game screens over gameplay, such as the backpack. AUTO follows CAMERA PRESET.
- RU: Игровые экраны поверх геймплея, например рюкзак. АВТО следует ПРЕСЕТУ КАМЕРЫ.

---

## 3. Обучение в игре

### 3.1. Стартовые окна (popups)

Показываются при первом запуске и по кнопке «СНОВА ПОКАЗАТЬ СОВЕТЫ VR».
Индекс — `popups` в `ui2-0.9.3.json`.

#### 0. WELCOME → ДОБРО ПОЖАЛОВАТЬ

Оригинал:
```
WELCOME

Thank you for playing Metro Exodus VR!

Before you start I'd like to point out few things worth
checking that will improve your experience.
```
Перевод:
```
ДОБРО ПОЖАЛОВАТЬ

Спасибо, что играете в Metro Exodus VR!

Перед началом я хотел бы отметить несколько вещей,
которые стоит проверить, чтобы улучшить ваши впечатления.
```

#### 1. VR OPTIONS → НАСТРОЙКИ VR

Оригинал:
```
VR OPTIONS

Before starting your journey please check out VR tab in the
Options menu and familiarize yourself with what's available,
how it's configured and what you can change.

All of these options are also available from Pause Menu
while playing.


```
Перевод:
```
НАСТРОЙКИ VR

Перед началом путешествия загляните на вкладку VR в меню
настроек и ознакомьтесь с тем, что доступно,
как это устроено и что можно изменить.

Все эти настройки также доступны в меню паузы
во время игры.


```

#### 2. VR HINTS → СОВЕТЫ VR

Оригинал:
```
VR HINTS

While playing you will also have access to VR HINTS tab in the Pause Menu which cover VR-specific mechanics and interactions.

Check it out if you feel lost or unsure how to proceed.
```
Перевод:
```
СОВЕТЫ VR

Во время игры вам также будет доступна вкладка СОВЕТЫ VR в меню паузы, где описаны механики и взаимодействия, специфичные для VR.

Загляните туда, если потеряетесь или не будете знать, что делать.
```

#### 3. MANUAL RELOADING → РУЧНАЯ ПЕРЕЗАРЯДКА

Оригинал:
```
MANUAL RELOADING

To help with manual reloading this mod offers option to highlight the next weapon's part that needs to be operated to finish reloading.

You can configure this option later in Options / VR / Weapons.

Would you like to enable it for first few reloads of each weapon now?


```
Перевод:
```
РУЧНАЯ ПЕРЕЗАРЯДКА

Чтобы упростить ручную перезарядку, мод может подсвечивать следующую часть оружия, с которой нужно взаимодействовать, чтобы завершить перезарядку.

Настроить это можно позже в Настройки / VR / Оружие.

Включить подсветку для первых нескольких перезарядок каждого оружия?


```

#### 4. CHOOSING AN OPTION → ВЫБОР ВАРИАНТА

Оригинал:
```
CHOOSING AN OPTION

When icons appear around a thumbstick symbol in the corner of your view, push <stick_left> towards an icon and keep holding until the choice completes.
```
Перевод:
```
ВЫБОР ВАРИАНТА

Когда в углу обзора вокруг значка стика появляются значки, наклоните <stick_left> в сторону нужного значка и удерживайте стик, пока выбор не завершится.
```

#### 5. PAUSE MENU → МЕНЮ ПАУЗЫ

Оригинал:
```
PAUSE MENU

To enter pause menu press <start>, or hold the left trigger and press <xpad_y>.
Hold the same buttons to recenter.

Everything about VR controls is in the Pause Menu under VR HINTS section.
```
Перевод:
```
МЕНЮ ПАУЗЫ

Чтобы открыть меню паузы, нажмите <start> или удерживайте левый триггер и нажмите <xpad_y>.
Для повторного центрирования удерживайте те же кнопки.

Все об управлении в VR описано в меню паузы, в разделе СОВЕТЫ VR.
```

#### 6. YOUR GEAR IS ON YOUR BODY → СНАРЯЖЕНИЕ НА ВАШЕМ ТЕЛЕ

Оригинал:
```
YOUR GEAR IS ON YOUR BODY

Reach for the item/place and grip with <grip_dominant> or <grip_nondominant>.

You can find details of where each device is located in Pause Menu in VR HINTS tab.
```
Перевод:
```
СНАРЯЖЕНИЕ НА ВАШЕМ ТЕЛЕ

Потянитесь к предмету или месту и схватите с помощью <grip_dominant> или <grip_nondominant>.

Где находятся все устройства, описано в меню паузы на вкладке СОВЕТЫ VR.
```

#### 7. YOUR GEAR IS ON YOUR BACKPACK → СНАРЯЖЕНИЕ В ВАШЕМ РЮКЗАКЕ

Оригинал:
```
YOUR GEAR IS ON YOUR BACKPACK

Most of your gear is also available to grab from your backpack. Simply reach for your backpack with your <nondominant> hand over <nondominant> shoulder, grab it (<grip_nondominant>), move in front of your view and use <dominant> hand's grip (<grip_dominant>) to grab items from it (gas mask, filters, binoculars, charger, throwables).


```
Перевод:
```
СНАРЯЖЕНИЕ В ВАШЕМ РЮКЗАКЕ

Большая часть снаряжения доступна и в рюкзаке. Потянитесь к рюкзаку второй рукой над вторым плечом, схватите его (<grip_nondominant>), вынесите перед собой и хватайте из него предметы ведущей рукой (<grip_dominant>) (противогаз, фильтры, бинокль, зарядное устройство, метательные предметы).


```

#### 8. WEAPONS → ОРУЖИЕ

Оригинал:
```
WEAPONS

Take a weapon with <grip_dominant> from over your shoulders or <dominant> hip. Let go to put it away.

Pointing a gun down holsters it and aiming down sight stabilizes it.
```
Перевод:
```
ОРУЖИЕ

Возьмите оружие с помощью <grip_dominant> из-за плеча или с ведущего бедра. Отпустите, чтобы убрать его.

Если направить оружие вниз, оно убирается, а при прицеливании стабилизируется.
```

#### 9. RELOADING → ПЕРЕЗАРЯДКА

Оригинал:
```
RELOADING

You reload by hand: take the old magazine out, take a new one from your <dominant> hip, push it in, then operate the bolt.

To reload with a button, turn Manual Reloading off in
Options / VR / Weapons.
```
Перевод:
```
ПЕРЕЗАРЯДКА

Перезарядка ручная: выньте старый магазин, достаньте новый с ведущего бедра, вставьте его, затем передерните затвор.

Чтобы перезаряжаться кнопкой, отключите ручную перезарядку в
Настройки / VR / Оружие.
```

#### 10. ACTION PROMPTS → ПОДСКАЗКИ ДЕЙСТВИЙ

Оригинал:
```
ACTION PROMPTS

Some scripted QTEs ask for quick button presses. Do as the prompt shows: tap, press or hold <rui>.

You can change the QTEs mode in game's options.
```
Перевод:
```
ПОДСКАЗКИ ДЕЙСТВИЙ

В некоторых сценах QTE требуют быстрых нажатий. Делайте так, как показано в подсказке: коснитесь, нажмите или удерживайте <rui>.

Режим QTE можно изменить в настройках игры.
```

#### 11. GAS MASK → ПРОТИВОГАЗ

Оригинал:
```
GAS MASK

Put on: <grip_nondominant> at <nondominant> hip and bring it to your face.
Take off: grip it on your face and pull it away.

Filter: (while mask is equipped) <grip_nondominant> at <nondominant> hip and bring it to your face.

Wipe: rub the visor with an open hand.

Fix crack: (while mask is equipped and cracked) <grip_nondominant> tape from <nondominant> hip and take it to the cracked visor.

The mask, filter and tape are also on your backpack: grip <grip_nondominant> over <nondominant> shoulder, then take them with <grip_dominant>.
```
Перевод:
```
ПРОТИВОГАЗ

Надеть: <grip_nondominant> у второго бедра и поднесите к лицу.
Снять: схватите его на лице и отведите в сторону.

Фильтр: (когда маска надета) <grip_nondominant> у второго бедра и поднесите к лицу.

Протереть: потрите стекло открытой ладонью.

Заделать трещину: (когда маска надета и треснула) <grip_nondominant> скотч со второго бедра и поднесите к треснувшему стеклу.

Маска, фильтр и скотч также есть в рюкзаке: схватите <grip_nondominant> над вторым плечом, затем берите их <grip_dominant>.
```

#### 12. BACKPACK → РЮКЗАК

Оригинал:
```
BACKPACK

You can craft consumables and throwables or modify your weapons in your backpack / inventory.

Grip <grip_nondominant> over <nondominant> shoulder to take it in your hand, then press <trigger_nondominant> to open it[, or <press:inventory>].

While you hold it, take mask, filters, binoculars, charger and throwables from it with <grip_dominant>.
```
Перевод:
```
РЮКЗАК

В рюкзаке или инвентаре можно создавать расходники и метательные предметы, а также улучшать оружие.

Схватите <grip_nondominant> над вторым плечом, чтобы взять его в руку, затем нажмите <trigger_nondominant>, чтобы открыть его[, или <press:inventory>].

Пока вы держите его, берите из него маску, фильтры, бинокль, зарядное устройство и метательные предметы с помощью <grip_dominant>.
```

#### 13. MAP → КАРТА

Оригинал:
```
MAP

To equip map grip <grip_dominant> at <dominant> chest[, or <press:map>].

```
Перевод:
```
КАРТА

Чтобы взять карту, схватите <grip_dominant> у ведущей стороны груди[, или <press:map>].

```

#### 14. TIKHAR AMMUNITION → БОЕПРИПАСЫ ТИХАР

Оригинал:
```
TIKHAR AMMUNITION

Tikhar can fire Incendiary Ammunition.

With Tikhar in your hands, hold <popup_equipment> and press <rui> at the same time. A pulse confirms that your next reload loads the other ammo.

Then reload as usual. Do the same to switch back.
```
Перевод:
```
БОЕПРИПАСЫ ТИХАР

Тихар может стрелять зажигательными боеприпасами.

Держа Тихар в руках, удерживайте <popup_equipment> и одновременно нажмите <rui>. Импульс подтвердит, что при следующей перезарядке зарядятся другие боеприпасы.

Затем перезаряжайтесь как обычно. Повторите, чтобы переключиться обратно.
```

#### 15. HELSING AMMUNITION → БОЕПРИПАСЫ ХЕЛЬСИНГ

Оригинал:
```
HELSING AMMUNITION

Helsing can fire explosive bolts.

With Helsing in your hands, hold <popup_equipment> and press <rui> at the same time to switch between regular and explosive bolts. Do the same to switch back.
```
Перевод:
```
БОЕПРИПАСЫ ХЕЛЬСИНГ

Хельсинг может стрелять разрывными болтами.

Держа Хельсинг в руках, удерживайте <popup_equipment> и одновременно нажмите <rui>, чтобы переключаться между обычными и разрывными болтами. Повторите, чтобы переключиться обратно.
```

### 3.2. Раздел «СОВЕТЫ VR» (hintpages)

Вкладка в меню паузы. Индекс — `hintpages` в `ui2-0.9.3.json`;
`orig_title`/`ru_title` — заголовок страницы, `orig`/`ru` — текст.

#### 0. Basics → ОСНОВЫ

Оригинал:
```
PAUSE MENU

<tab>Press the menu button or right trackpad. If your headset's software keeps that button for itself, hold the left trigger and press <xpad_y>.

RECENTER

<tab>Hold the menu button or right trackpad, or the left trigger and <xpad_y> together.

VR SETTINGS

<tab>In the main or pause menu, click Options, then VR. Allows configuring VR-specific settings and the mod's behavior.

MENUS

<tab>Point at the menu and click with <trigger_dominant>. <trigger_nondominant> goes back, whether you point at the menu or not. Every other button works while you point, as the menu shows: click an item, then press the button for what you want to do. Push <stick_right> up or down to scroll long texts.

<tab>Controllers without A and B buttons (Vive, Windows Mixed Reality): point away from the menu to use the buttons. A red laser and two short buzzes remind you.


```
Перевод:
```
МЕНЮ ПАУЗЫ

<tab>Нажмите кнопку меню или правый тачпад. Если программное обеспечение шлема перехватывает эту кнопку, удерживайте левый триггер и нажмите <xpad_y>.

ПОВТОРНОЕ ЦЕНТРИРОВАНИЕ

<tab>Удерживайте кнопку меню или правый тачпад либо одновременно левый триггер и <xpad_y>.

НАСТРОЙКИ VR

<tab>В главном меню или меню паузы откройте «Настройки», затем VR. Здесь можно настроить параметры VR и поведение мода.

МЕНЮ

<tab>Наведите указатель на меню и щелкните <trigger_dominant>. <trigger_nondominant> возвращает назад, наведен указатель на меню или нет. Остальные кнопки работают при наведении, как показывает меню: щелкните пункт, затем нажмите кнопку нужного действия. Двигайте <stick_right> вверх или вниз, чтобы прокручивать длинные тексты.

<tab>Контроллеры без кнопок A и B (Vive, Windows Mixed Reality): отведите указатель от меню, чтобы пользоваться кнопками. Об этом напоминают красный луч и два коротких сигнала.


```

#### 1. Movement → ДВИЖЕНИЕ

Оригинал:
```
WALKING

<tab>Move your left thumbstick (<stick_left>) in the direction you want to go.

TURNING

<tab>Press or hold <xpad_right_thumb_left> or <xpad_right_thumb_right> to turn in the desired direction. You can switch between snap and smooth turning in Options - VR - Movement.

RUNNING

<tab>Double-tap <sprint> and keep holding it.

JUMPING

<tab>To jump, press <jump>.

CROUCHING

<tab><Press:crouch_toggle>, or crouch in real life. You can change crouching options in Options - VR - Movement.


```
Перевод:
```
ХОДЬБА

<tab>Отклоняйте левый стик (<stick_left>) в нужную сторону.

ПОВОРОТЫ

<tab>Нажимайте или удерживайте <xpad_right_thumb_left> или <xpad_right_thumb_right>, чтобы поворачиваться в нужную сторону. Переключение между резким и плавным поворотом – в Настройки – VR – Движение.

БЕГ

<tab>Дважды нажмите <sprint> и продолжайте удерживать.

ПРЫЖКИ

<tab>Чтобы прыгнуть, нажмите <jump>.

ПРИСЕДАНИЕ

<tab><Press:crouch_toggle> или присядьте в реальной жизни. Настройки приседания – в Настройки – VR – Движение.


```

#### 2. Interactions → ВЗАИМОДЕЙСТВИЯ

Оригинал:
```
INTERACTIONS

<tab>To interact with world objects (e.g. doors, ladders) or perform an action (e.g. take loot, grab/swap weapon), reach out with either hand and grip (<grip_dominant> or <grip_nondominant>).

<tab>In some cases you will be offered a choice (e.g. lethal vs non-lethal takedowns, take/swap weapon or just take its parts) - in such cases you can choose by either gripping with that hand (<grip_dominant> or <grip_nondominant>) or pressing/holding a trigger (<trigger_dominant> or <trigger_nondominant>).

QTEs

<tab>Throughout the game you will encounter quick-time events. During them - depending on your game's settings - you will have to press, hold or quickly tap the <rui> button.


```
Перевод:
```
ВЗАИМОДЕЙСТВИЯ

<tab>Чтобы взаимодействовать с объектами мира (например, дверями, лестницами) или выполнить действие (взять добычу, схватить или сменить оружие), потянитесь любой рукой и схватите (<grip_dominant> или <grip_nondominant>).

<tab>Иногда вам предложат выбор (например, смертельное или несмертельное устранение, взять или сменить оружие либо забрать только его части) – в таких случаях выбирайте хватом (<grip_dominant> или <grip_nondominant>) либо нажатием или удержанием триггера (<trigger_dominant> или <trigger_nondominant>).

БЫСТРЫЕ СОБЫТИЯ

<tab>По ходу игры вам будут встречаться быстрые события. В зависимости от настроек игры в них нужно нажимать, удерживать или быстро многократно нажимать кнопку <rui>.


```

#### 3. Weapons → ОРУЖИЕ

Оригинал:
```
STORAGE

<tab>Weapons you carry can be grabbed from over your shoulders and from your <dominant> hip:

* main weapon - over <dominant> shoulder
* secondary weapon - <dominant> hip
* special weapon - over <nondominant> shoulder

EQUIPPING

<tab>To grab a weapon you will have to grip the holster area with your <dominant> hand (<grip_dominant>). Once equipped you can grab its main handle or foregrip with your <nondominant> hand for stabilization and easier aiming.

MODES / POSES

<tab>The mod switches the weapon between normal, Aim Down Sights (ADS, for more accurate aiming) and Holstered (e.g. for faster running) modes based on how you hold it. Lower the weapon to holster it, or bring it up to your eyes to aim down sights.

THROWABLES

<tab>Throwables you find or craft (decoys, knives, molotovs, grenades) go on your belt in front of you, and on your backpack while you hold it (see Items and devices). Switch between them with <trigger_nondominant>, or grab them with <grip_dominant> or <grip_nondominant>.[ <Press:wpn_dynamite> to throw the selected one.]

WEAPONS AND AMMO

<tab>Hold <popup_equipment> to see your weapons and ammunition. While holding it, press <rui> to switch the ammunition type of the weapon in your hands (see Manual reloading).

MELEE

<tab>Press <wpn_fast_knife>.


```
Перевод:
```
ХРАНЕНИЕ

<tab>Носимое оружие можно достать из-за плеча и с ведущего бедра:

* основное оружие – из-за ведущего плеча
* запасное оружие – с ведущего бедра
* особое оружие – из-за второго плеча

ЭКИПИРОВКА

<tab>Чтобы взять оружие, схватите область кобуры ведущей рукой (<grip_dominant>). Взяв его, можно взяться второй рукой за основную рукоять или цевье для стабилизации и более удобного прицеливания.

РЕЖИМЫ И ПОЛОЖЕНИЯ

<tab>В зависимости от того, как вы держите оружие, мод переключает его между обычным режимом, прицеливанием (ADS, для более точной стрельбы) и убранным положением (например, для быстрого бега). Опустите оружие, чтобы убрать его, или поднесите к глазам, чтобы прицелиться.

МЕТАТЕЛЬНЫЕ ПРЕДМЕТЫ

<tab>Найденные или созданные метательные предметы (приманки, ножи, коктейли Молотова, гранаты) крепятся на поясе спереди, а пока вы держите рюкзак – и на нем (см. Предметы и устройства). Переключайтесь между ними с помощью <trigger_nondominant> или берите их <grip_dominant> либо <grip_nondominant>.[ <Press:wpn_dynamite>, чтобы бросить выбранный.]

ОРУЖИЕ И БОЕПРИПАСЫ

<tab>Удерживайте <popup_equipment>, чтобы увидеть оружие и боеприпасы. Удерживая ее, нажмите <rui>, чтобы сменить тип боеприпасов оружия в руках (см. Ручная перезарядка).

БЛИЖНИЙ БОЙ

<tab>Нажмите <wpn_fast_knife>.


```

#### 4. Manual reloading → РУЧНАЯ ПЕРЕЗАРЯДКА

Оригинал:
```
MANUAL RELOADING

<tab>Most weapons will require you to perform these actions with <trigger_nondominant>:

* remove old magazine
* grab a new magazine from the pouch (<nondominant> hip or chest) and insert it
* optionally pull the bolt

Some weapons might have special needs such as:

* pushing the magazine through the weapon before you can take it out
* pulling a lever to release the magazine or chamber a new slug
* drawing the bow before inserting an arrow
* pumping the pneumatic system (see below)

<tab>If you're unsure what to do, enable PART HIGHLIGHTS in Options - VR - Weapons. It highlights the next part you need to work to reload the weapon.

PNEUMATIC WEAPONS

<tab>Tikhar, Helsing and Gatling need pressure. Pump manually with your <nondominant> hand: take the pump handle with <trigger_nondominant> and pump it back and forth; it lets go by itself when full. Or hold <rui> and tap <wpn_fire>.

SPECIAL AMMUNITION

<tab>Tikhar can fire Incendiary Ammunition and Helsing explosive bolts. With the weapon in your hands, hold <popup_equipment> and press <rui> at the same time. A pulse confirms that your next reload loads the other ammunition; reload by hand as usual. Do it again to cancel, or later to switch back. The single-arrow Helsing switches at once, with the game's own reload.

JAMMING

<tab>Weapons in Metro Exodus can get jammed. Their condition affects how often that happens. To reduce the jamming rate, find a Workbench and clean your weapons. To unjam your weapon operate the bolt.

AUTOMATIC RELOADS

<tab>You can also disable manual reloads in Options - VR - Weapons and reload by pressing <rui> instead.
```
Перевод:
```
РУЧНАЯ ПЕРЕЗАРЯДКА

<tab>Для большинства оружий потребуется выполнять эти действия с помощью <trigger_nondominant>:

* вынуть старый магазин
* достать новый магазин из подсумка (второе бедро или вторая сторона груди) и вставить его
* при необходимости передернуть затвор

У некоторых оружий есть особые требования:

* протолкнуть магазин через оружие, прежде чем его можно будет вынуть
* потянуть рычаг, чтобы освободить магазин или дослать новый патрон
* натянуть лук перед вставкой стрелы
* накачать пневматическую систему (см. ниже)

<tab>Если не знаете, что делать, включите ПОДСВЕТКУ ЧАСТЕЙ в Настройки – VR – Оружие. Она подсветит следующую часть, с которой нужно работать для перезарядки.

ПНЕВМАТИЧЕСКОЕ ОРУЖИЕ

<tab>Тихару, Хельсингу и Гатлингу нужно давление. Качайте вручную второй рукой: возьмите рукоятку помпы с помощью <trigger_nondominant> и качайте вперед-назад; при полной накачке она отпустится сама. Либо удерживайте <rui> и нажимайте <wpn_fire>.

ОСОБЫЕ БОЕПРИПАСЫ

<tab>Тихар может стрелять зажигательными боеприпасами, а Хельсинг – разрывными болтами. Держа оружие в руках, удерживайте <popup_equipment> и одновременно нажмите <rui>. Импульс подтвердит, что при следующей перезарядке зарядятся другие боеприпасы; перезаряжайтесь вручную как обычно. Повторите, чтобы отменить, или позже, чтобы переключиться обратно. Однострельный Хельсинг переключается сразу, при перезарядке самой игры.

ЗАКЛИНИВАНИЕ

<tab>Оружие в Metro Exodus может заклинивать. Его состояние влияет на частоту заклиниваний. Чтобы снизить вероятность, найдите верстак и почистите оружие. Чтобы устранить заклинивание, передерните затвор.

АВТОМАТИЧЕСКАЯ ПЕРЕЗАРЯДКА

<tab>Также можно отключить ручную перезарядку в Настройки – VR – Оружие и перезаряжаться нажатием <rui>.
```

#### 5. Items and devices → ПРЕДМЕТЫ И УСТРОЙСТВА

Оригинал:
```
EQUIPPING GEAR

<tab>Most of your gear is accessible directly from your body by moving your hand to a given area and gripping it with <grip_dominant> or <grip_nondominant>. Some gear can only be grabbed with a specific hand.

BACKPACK

<tab>Hard to reach equipment is also available to grab from your  backpack. Simply grip (<grip_nondominant>) over your <nondominant> shoulder to take the backpack into that hand and move it in front of you. Gas mask, filter, crack tape, binoculars, charger and throwables hang on it: grab them with your <dominant> hand (<grip_dominant>). Let go of the backpack to put it back, or press <trigger_nondominant> to open it.

GEAR AREAS

* chest:
  * <dominant> - map
  * <nondominant> - lighter
* shoulders:
  * over <dominant> - main weapon (<grip_dominant>)
  * over <nondominant> - special weapon (<grip_dominant>) or backpack (<grip_nondominant>, then <trigger_nondominant> to open)
  * on <dominant> - medkit (<grip_nondominant>)
* hips:
  * <dominant> - secondary weapon (<grip_dominant>)
  * <nondominant> - mask*, filter*, tape* (<grip_nondominant>) or new ammo (<trigger_nondominant>)
* lower back:
  * <dominant> - charger* (<grip_dominant>)
  * <nondominant> - binoculars* (<grip_nondominant>)
* belt:
  * front - throwables*
* forehead:
  * flashlight (<trigger_nondominant>)
  * night vision (<grip_dominant> - pull up or down)

* also on the backpack when you hold it


```
Перевод:
```
ЭКИПИРОВКА СНАРЯЖЕНИЯ

<tab>Большинство снаряжения доступно прямо на теле: поднесите руку к нужной области и схватите предмет с помощью <grip_dominant> или <grip_nondominant>. Некоторое снаряжение можно взять только определенной рукой.

РЮКЗАК

<tab>Труднодоступное снаряжение можно взять и из рюкзака. Просто схватите (<grip_nondominant>) над вторым плечом, чтобы взять рюкзак в эту руку, и вынесите его перед собой. На нем висят противогаз, фильтр, скотч, бинокль, зарядное устройство и метательные предметы: берите их ведущей рукой (<grip_dominant>). Отпустите рюкзак, чтобы вернуть его, или нажмите <trigger_nondominant>, чтобы открыть.

ЗОНЫ СНАРЯЖЕНИЯ

* грудь:
  * ведущая – карта
  * вторая – зажигалка
* плечи:
  * из-за ведущего – основное оружие (<grip_dominant>)
  * из-за второго – особое оружие (<grip_dominant>) или рюкзак (<grip_nondominant>, затем <trigger_nondominant>, чтобы открыть)
  * на ведущем – аптечка (<grip_nondominant>)
* бедра:
  * ведущее – запасное оружие (<grip_dominant>)
  * второе – маска*, фильтр*, скотч* (<grip_nondominant>) или новые боеприпасы (<trigger_nondominant>)
* поясница:
  * ведущая – зарядное устройство* (<grip_dominant>)
  * вторая – бинокль* (<grip_nondominant>)
* пояс:
  * спереди – метательные предметы*
* лоб:
  * фонарь (<trigger_nondominant>)
  * ночное видение (<grip_dominant> – потяните вверх или вниз)

* также в рюкзаке, пока вы его держите


```

#### 6. Gas mask → ПРОТИВОГАЗ

Оригинал:
```
GAS MASK

<tab>The gas mask is usually located on your <nondominant> hip, or on your backpack while you hold it (grab it from there with <grip_dominant>). To put it on you have to grab it (<grip_nondominant>) and bring it to your face. To take it off you have to grab it from your face (<grip_nondominant>), move it away and let it go.

FILTERS

<tab>When the mask is equipped and your filters can be changed, a new filter will be available for grabbing (<grip_nondominant>) at your <nondominant> hip or on your backpack (<grip_dominant>). Once grabbed, move it close to where it sits on the mask and it will be replaced automatically.[ Alternatively <press:filter>.]

WIPING

<tab>Rub the visor with an open hand to wipe rain, blood or dirt off it.[ Alternatively <press:facepalm>.]

FIXING CRACKS

<tab>When your mask is cracked, a piece of tape will be available for grabbing (<grip_nondominant>) at your <nondominant> hip or on your backpack (<grip_dominant>), in place of the filter. Once grabbed, bring it to the front of your visor and the cracks will be sealed. Let go of it anywhere else to put it back.[ Alternatively <press:facepalm>.]


```
Перевод:
```
ПРОТИВОГАЗ

<tab>Противогаз обычно висит на втором бедре или в рюкзаке, пока вы его держите (оттуда берите его с помощью <grip_dominant>). Чтобы надеть его, схватите (<grip_nondominant>) и поднесите к лицу. Чтобы снять, схватите его на лице (<grip_nondominant>), отведите в сторону и отпустите.

ФИЛЬТРЫ

<tab>Когда маска надета и фильтры можно менять, новый фильтр появится на втором бедре или в рюкзаке (<grip_dominant>), и его можно будет схватить (<grip_nondominant>). Схватив, поднесите его к месту установки на маске – он заменится автоматически.[ Либо <press:filter>.]

ПРОТИРАНИЕ

<tab>Потрите стекло открытой ладонью, чтобы стереть дождь, кровь или грязь.[ Либо <press:facepalm>.]

УСТРАНЕНИЕ ТРЕЩИН

<tab>Когда маска треснула, на втором бедре или в рюкзаке (<grip_dominant>) появляется кусок скотча вместо фильтра, который можно схватить (<grip_nondominant>). Схватив, поднесите его к передней части стекла, и трещины заделаются. Отпустите его в любом другом месте, чтобы вернуть.[ Либо <press:facepalm>.]


```

#### 7. Medkit → АПТЕЧКА

Оригинал:
```
HEALING

<tab>When you're hurt you will hear specific audio cues and see a red overlay around your field of view. To heal yourself (assuming you have any medkits left):

1. grip and hold (<grip_nondominant>) at your <dominant> shoulder
2. move it away from your body until you feel a pulse
3. bring it back to your body - anywhere from above your shoulder down to your stomach - to inject

<tab>Letting go before that puts it back unused.[ Alternatively <press:medkit>.]


```
Перевод:
```
ЛЕЧЕНИЕ

<tab>Когда вы ранены, вы услышите характерные звуки и увидите красную рамку по краям обзора. Чтобы вылечиться (если остались аптечки):

1. схватите и удерживайте (<grip_nondominant>) у ведущего плеча
2. отведите от тела, пока не почувствуете импульс
3. верните к телу – от уровня выше плеча до живота – чтобы сделать укол

<tab>Если отпустить раньше, аптечка вернется неиспользованной.[ Либо <press:medkit>.]


```

#### 8. Flashlight and charger → ФОНАРЬ И ЗАРЯДКА

Оригинал:
```
FLASHLIGHT

<tab>To toggle the flashlight, press <trigger_nondominant> at your forehead[, or <press:wpn_light>].

CHARGER

<tab>To charge your batteries, grip (<grip_dominant>) at the <dominant> side of your lower back or on your backpack[, or <press:charger>]. Once equipped, pump it with <wpn_fire>.


```
Перевод:
```
ФОНАРЬ

<tab>Чтобы включить или выключить фонарь, нажмите <trigger_nondominant> у лба[, или <press:wpn_light>].

ЗАРЯДНОЕ УСТРОЙСТВО

<tab>Чтобы зарядить аккумуляторы, схватите (<grip_dominant>) устройство с ведущей стороны поясницы или в рюкзаке[, или <press:charger>]. Взяв его, качайте с помощью <wpn_fire>.


```

#### 9. Map / journal → КАРТА И ЖУРНАЛ

Оригинал:
```
MAP

<tab>To equip the map, simply grip it (<grip_dominant>) at the <dominant> side of your chest[, or <press:map>].

JOURNAL

<tab>Once the map is equipped, flip the map over with your hands, or press <wpn_fire> to switch sides.


```
Перевод:
```
КАРТА

<tab>Чтобы взять карту, просто схватите ее (<grip_dominant>) у ведущей стороны груди[, или <press:map>].

ЖУРНАЛ

<tab>Взяв карту, переверните ее руками или нажмите <wpn_fire>, чтобы сменить сторону.


```

#### 10. Backpack / inventory → РЮКЗАК И ИНВЕНТАРЬ

Оригинал:
```
OPENING BACKPACK

<tab>To open your inventory, grip (<grip_nondominant>) over your <nondominant> shoulder to take the backpack in that hand, then press <trigger_nondominant>[, or <press:inventory>]. Letting go of the grip puts it back. While you hold it, take gear from it with your <dominant> hand (see Items and devices). Once opened you can craft consumables/throwables and modify your weapons. Click an item with the pointer, then press the buttons shown at the bottom; see MENUS on the Basics page.


```
Перевод:
```
ОТКРЫТИЕ РЮКЗАКА

<tab>Чтобы открыть инвентарь, схватите (<grip_nondominant>) над вторым плечом, чтобы взять рюкзак в эту руку, затем нажмите <trigger_nondominant>[, или <press:inventory>]. Если отпустить хват, рюкзак вернется на место. Пока вы держите его, берите из него снаряжение ведущей рукой (см. Предметы и устройства). Открыв инвентарь, можно создавать расходники и метательные предметы, а также улучшать оружие. Щелкните предмет указателем, затем нажмите кнопки, показанные внизу; см. МЕНЮ на странице Основы.


```

#### 11. Binoculars and NV → БИНОКЛЬ И НОЧНОЕ ВИДЕНИЕ

Оригинал:
```
BINOCULARS

<tab>Once you have binoculars, grip (<grip_nondominant>) at the <nondominant> side of your lower back or on your backpack[, or <press:binoculars>]. You can pass them between hands. To use them, bring them to your eyes. Zoom in with <wpn_fire> and out with <aim>.

NIGHT VISION

<tab>To equip night vision, grip (<grip_dominant>) above your forehead and pull them down in front of your eyes[, or <press:nightvision>]. To take them off, grip (<grip_dominant>) in front of your eyes and pull them back up[, or <press:nightvision> again].


```
Перевод:
```
БИНОКЛЬ

<tab>Получив бинокль, схватите (<grip_nondominant>) его со второй стороны поясницы или в рюкзаке[, или <press:binoculars>]. Его можно передавать между руками. Чтобы использовать, поднесите к глазам. Приближайте с помощью <wpn_fire>, отдаляйте с помощью <aim>.

НОЧНОЕ ВИДЕНИЕ

<tab>Чтобы надеть ночное видение, схватите (<grip_dominant>) над лбом и потяните вниз перед глазами[, или <press:nightvision>]. Чтобы снять, схватите (<grip_dominant>) перед глазами и потяните вверх[, или снова <press:nightvision>].


```

#### 12. Weapon scopes → ОРУЖЕЙНЫЕ ПРИЦЕЛЫ

Оригинал:
```
<tab>To use weapon scopes simply bring them to your eye. You can configure related options in Options - VR - Scopes.


```
Перевод:
```
<tab>Чтобы использовать прицел, просто поднесите его к глазу. Связанные настройки – в Настройки – VR – Прицелы.


```

#### 13. Workbenches → ВЕРСТАКИ

Оригинал:
```
<tab>To use a workbench, reach out to it and grip (<grip_dominant> or <grip_nondominant>). Once in the workbench view click an item with the pointer, then press the buttons shown at the bottom; see MENUS on the Basics page.


```
Перевод:
```
<tab>Чтобы воспользоваться верстаком, потянитесь к нему и схватите (<grip_dominant> или <grip_nondominant>). В режиме верстака щелкните предмет указателем, затем нажмите кнопки, показанные внизу; см. МЕНЮ на странице Основы.


```

### 3.3. Контекстные подсказки в игре (hints)

Всплывают по ходу игры. Индекс — `hints` в `ui2-0.9.3.json`. В тексте
`[...]` — необязательная часть, `<...>` — кнопки.

**0.**

- EN: Use <wpn_fire> to accelerate and <wpn_aim> to brake. Press <jump> to rotate the seat in the opposite direction. <Press:rui> to exit.
- RU: Используйте <wpn_fire> для ускорения и <wpn_aim> для торможения. Нажмите <jump>, чтобы развернуть сиденье в противоположную сторону. <Press:rui>, чтобы выйти.

**1.**

- EN: Map: grab <grip_dominant> from <dominant> side of chest[, or <press:map>]
- RU: Карта: схватите <grip_dominant> с ведущей стороны груди[, или <press:map>]

**2.**

- EN: Map: grab <grip_dominant> from <dominant> side of chest[, or <press:map>]
- RU: Карта: схватите <grip_dominant> с ведущей стороны груди[, или <press:map>]

**3.**

- EN: Check your journal. Map: grab <grip_dominant> from <dominant> side of chest[, or <press:map>]
- RU: Проверьте журнал. Карта: схватите <grip_dominant> с ведущей стороны груди[, или <press:map>]

**4.**

- EN: Backpack: grab <grip_nondominant> from over <nondominant> shoulder, then press <trigger_nondominant> to open it[, or <press:inventory>]
- RU: Рюкзак: схватите <grip_nondominant> над вторым плечом, затем нажмите <trigger_nondominant>, чтобы открыть его[, или <press:inventory>]

**5.**

- EN: Backpack: grab <grip_nondominant> from over <nondominant> shoulder, then press <trigger_nondominant> to open it[, or <press:inventory>]
- RU: Рюкзак: схватите <grip_nondominant> над вторым плечом, затем нажмите <trigger_nondominant>, чтобы открыть его[, или <press:inventory>]

**6.**

- EN: Weapons: grab <grip_dominant> from your shoulders or <dominant> hip[, or <press:popup_equipment>]
- RU: Оружие: схватите <grip_dominant> из-за плеча или с ведущего бедра[, или <press:popup_equipment>]

**7.**

- EN: Pump manually with <nondominant> hand (<trigger_nondominant> on the pump handle) or by holding <rui> and tapping <wpn_fire>
- RU: Качайте вручную второй рукой (<trigger_nondominant> на рукоятке помпы) или удерживая <rui> и нажимая <wpn_fire>

**8.**

- EN: Pump manually (<trigger_nondominant>) or hold <rui> and tap <wpn_fire>
- RU: Качайте вручную (<trigger_nondominant>) или удерживайте <rui> и нажимайте <wpn_fire>

**9.**

- EN: Pump manually with <nondominant> hand (<trigger_nondominant> on the pump handle) or by holding <rui> and tapping <wpn_fire>
- RU: Качайте вручную второй рукой (<trigger_nondominant> на рукоятке помпы) или удерживая <rui> и нажимая <wpn_fire>

**10.**

- EN: Pump manually (<trigger_nondominant>) or hold <rui> and tap <wpn_fire>
- RU: Качайте вручную (<trigger_nondominant>) или удерживайте <rui> и нажимайте <wpn_fire>

**11.**

- EN: Point your weapon down to lower it
- RU: Направьте оружие вниз, чтобы опустить его

**12.**

- EN: Point your weapon down
- RU: Направьте оружие вниз

**13.**

- EN: To sprint further, point your weapon down
- RU: Чтобы бежать дальше, направьте оружие вниз

**14.**

- EN: <Press:crouch_toggle> to crouch
- RU: <Press:crouch_toggle>, чтобы присесть

**15.**

- EN: Weapon jammed! Pull the bolt[ or <press:rui>]
- RU: Оружие заклинило! Передерните затвор[ или <press:rui>]

**16.**

- EN: Incendiary ammo: with Tikhar in hand, hold <popup_equipment> and press <rui> at the same time
- RU: Зажигательные боеприпасы: держа Тихар в руке, удерживайте <popup_equipment> и одновременно нажмите <rui>

**17.**

- EN: Holding <popup_equipment>, press <rui>: your next reload loads the other ammo
- RU: Удерживая <popup_equipment>, нажмите <rui>: при следующей перезарядке зарядятся другие боеприпасы

**18.**

- EN: Explosive bolts: with Helsing in hand, hold <popup_equipment> and press <rui> at the same time
- RU: Разрывные болты: держа Хельсинг в руке, удерживайте <popup_equipment> и одновременно нажмите <rui>

**19.**

- EN: You found a Molotov. Grab <grip_dominant> from your belt or backpack[, or <press:wpn_dynamite>]
- RU: Вы нашли коктейль Молотова. Схватите <grip_dominant> с пояса или из рюкзака[, или <press:wpn_dynamite>]

**20.**

- EN: You found a grenade. Grab <grip_dominant> from your belt or backpack[, or <press:wpn_dynamite>]
- RU: Вы нашли гранату. Схватите <grip_dominant> с пояса или из рюкзака[, или <press:wpn_dynamite>]

**21.**

- EN: You found a throwing knife. Grab <grip_dominant> from your belt or backpack[, or <press:wpn_dynamite>]
- RU: Вы нашли метательный нож. Схватите <grip_dominant> с пояса или из рюкзака[, или <press:wpn_dynamite>]

**22.**

- EN: Throw: grab <grip_dominant> from your belt or backpack[, or <press:wpn_dynamite>]
- RU: Бросок: схватите <grip_dominant> с пояса или из рюкзака[, или <press:wpn_dynamite>]

**23.**

- EN: You found a decoy. Grab <grip_dominant> from your belt or backpack
- RU: Вы нашли приманку. Схватите <grip_dominant> с пояса или из рюкзака

**24.**

- EN: You found a decoy. Grab <grip_dominant> from your belt or backpack
- RU: Вы нашли приманку. Схватите <grip_dominant> с пояса или из рюкзака

**25.**

- EN: Binoculars: grab <grip_nondominant> from <nondominant> side of lower back or from backpack[, or <press:binoculars>]
- RU: Бинокль: схватите <grip_nondominant> со второй стороны поясницы или из рюкзака[, или <press:binoculars>]

**26.**

- EN: Binoculars: grab <grip_nondominant> from <nondominant> side of lower back or from backpack[, or <press:binoculars>]
- RU: Бинокль: схватите <grip_nondominant> со второй стороны поясницы или из рюкзака[, или <press:binoculars>]

**27.**

- EN: Night vision: grab <grip_dominant> above your forehead, pull down[, or <press:nightvision>]
- RU: Ночное видение: схватите <grip_dominant> над лбом, потяните вниз[, или <press:nightvision>]

**28.**

- EN: Night vision: grab <grip_dominant> above your forehead, pull down[, or <press:nightvision>]
- RU: Ночное видение: схватите <grip_dominant> над лбом, потяните вниз[, или <press:nightvision>]

**29.**

- EN: Flashlight: <trigger_nondominant> at your forehead[, or <press:wpn_light>]
- RU: Фонарь: <trigger_nondominant> у лба[, или <press:wpn_light>]

**30.**

- EN: Charger: grab <grip_dominant> from <dominant> side of lower back or from backpack[, or <press:charger>]
- RU: Зарядное устройство: схватите <grip_dominant> с ведущей стороны поясницы или из рюкзака[, или <press:charger>]

**31.**

- EN: Charger: grab <grip_dominant> from <dominant> side of lower back or from backpack[, or <press:charger>]
- RU: Зарядное устройство: схватите <grip_dominant> с ведущей стороны поясницы или из рюкзака[, или <press:charger>]

**32.**

- EN: Charger: grab <grip_dominant> from <dominant> side of lower back or from backpack[, or <press:charger>]
- RU: Зарядное устройство: схватите <grip_dominant> с ведущей стороны поясницы или из рюкзака[, или <press:charger>]

**33.**

- EN: Lighter: grab <grip_nondominant> from <nondominant> chest, then light the web[, or <press:lighter>]
- RU: Зажигалка: схватите <grip_nondominant> со второй стороны груди, затем подожгите паутину[, или <press:lighter>]

**34.**

- EN: Lighter: grab <grip_nondominant> from <nondominant> chest[, or <press:lighter>]
- RU: Зажигалка: схватите <grip_nondominant> со второй стороны груди[, или <press:lighter>]

**35.**

- EN: Lighter: grab <grip_nondominant> from <nondominant> chest[, or <press:lighter>]
- RU: Зажигалка: схватите <grip_nondominant> со второй стороны груди[, или <press:lighter>]

**36.**

- EN: Lighter: grab <grip_nondominant> from <nondominant> chest[, or <press:lighter>]
- RU: Зажигалка: схватите <grip_nondominant> со второй стороны груди[, или <press:lighter>]

**37.**

- EN: Medkit: grab <grip_nondominant> at <dominant> shoulder, move it away, then back to your body[, or <press:medkit>]
- RU: Аптечка: схватите <grip_nondominant> у ведущего плеча, отведите, затем верните к телу[, или <press:medkit>]

**38.**

- EN: Badly hurt: use a medkit. Grab <grip_nondominant> at <dominant> shoulder, move it away, then back to your body[, or <press:medkit>]
- RU: Сильно ранены: используйте аптечку. Схватите <grip_nondominant> у ведущего плеча, отведите от тела и верните обратно[, или <press:medkit>]

**39.**

- EN: Check the radiation detector on your left wrist
- RU: Проверьте дозиметр на левом запястье

**40.**

- EN: Radiation detector: check your left wrist
- RU: Дозиметр: проверьте левое запястье

**41.**

- EN: Gas mask: grab <grip_nondominant> from <nondominant> hip (or <grip_dominant> from backpack) and bring it to your face[, or <press:gasmask>]
- RU: Противогаз: схватите <grip_nondominant> у второго бедра (или <grip_dominant> из рюкзака) и поднесите к лицу[, или <press:gasmask>]

**42.**

- EN: Filter: grab <grip_nondominant> from <nondominant> hip (or <grip_dominant> from backpack)[, or <press:filter>]
- RU: Фильтр: схватите <grip_nondominant> у второго бедра (или <grip_dominant> из рюкзака)[, или <press:filter>]

**43.**

- EN: Swap filter: grab <grip_nondominant> from <nondominant> hip (or <grip_dominant> from backpack)[, or <press:filter>]
- RU: Сменить фильтр: схватите <grip_nondominant> у второго бедра (или <grip_dominant> из рюкзака)[, или <press:filter>]

**44.**

- EN: Wipe your mask: rub the visor with an open hand[, or <press:facepalm>]
- RU: Протрите маску: потрите стекло открытой ладонью[, или <press:facepalm>]

**45.**

- EN: Wipe: rub the visor with an open hand[, or <press:facepalm>]
- RU: Протрите: потрите стекло открытой ладонью[, или <press:facepalm>]

**46.**

- EN: Seal your mask: grab the tape <grip_nondominant> from <nondominant> hip (or <grip_dominant> from backpack) and bring it to your visor[, or <press:facepalm>]
- RU: Заделайте маску: схватите скотч <grip_nondominant> со второго бедра (или <grip_dominant> из рюкзака) и поднесите к стеклу[, или <press:facepalm>]

**47.**

- EN: Seal: tape from <nondominant> hip <grip_nondominant> or backpack <grip_dominant> to the visor[, or <press:facepalm>]
- RU: Заделать: скотч со второго бедра <grip_nondominant> или из рюкзака <grip_dominant> к стеклу[, или <press:facepalm>]

**48.**

- EN: New note - read it in the pause menu
- RU: Новая заметка – прочитайте ее в меню паузы

**49.**

- EN: New note - read it in the pause menu
- RU: Новая заметка – прочитайте ее в меню паузы

**50.**

- EN: New postcard - watch it in the pause menu
- RU: Новая открытка – посмотрите ее в меню паузы

**51.**

- EN: New postcard - watch it in the pause menu
- RU: Новая открытка – посмотрите ее в меню паузы

---

## 4. Дефекты сборки (не перевод)

Это не текст, а рендер/сборка. Правкой `strings`/`ui2` не лечится,
редактору перевода можно игнорировать:

1. `МАСШТАБ МИРА` показывает литерал `{}% (РЕКОМЕНД.)` вместо числа —
   подстановка формата не срабатывает (дефект обработчика).
2. Перед `НАЗАД` в футере виден лишний символ — это игровой футер
   (`Esc … НАЗАД`), строки мода там нет.
3. Литерал `VR HINTS` (`0x4ec548`) пока лежит в ASCII-байтах и рисуется как
   `EЯ!МbЗХA` — строка ещё не перекодирована в глифы.
4. Две строки на странице `ОРУЖИЕ` и пункт `MAGAZINE POUCH` отклоняются
   проверками мода (`lists need 2-255 printable ASCII labels`) — строки
   в таблице есть, но в игре не появляются.

## 5. Автоматически найденные проблемы перевода

### 5.1. Слишком длинные строки (риск обрезки)

| Где | Оригинал | Перевод | Длина | Лимит |
| --- | --- | --- | --- | --- |
| пункт `mevr_smooth_turn` | SMOOTH TURN SPEED | СКОРОСТЬ ПЛАВНОГО ПОВОРОТА | 26 | 22 |
| пункт `mevr_popups_again` | SHOW VR TIPS AGAIN | СНОВА ПОКАЗАТЬ СОВЕТЫ VR | 24 | 22 |
| пункт `mevr_video_legal` | LEGAL NOTICE VIDEO | ВИДЕО ПРАВОВОЙ ИНФОРМАЦИИ | 25 | 22 |
| значение `mevr_alternate_eye` | PERFORMANCE (AER+) | ПРОИЗВОДИТЕЛЬНОСТЬ (AER+) | 25 | 18 |
| пункт `mevr_render_scale` | RENDER SCALE (RESTART) | МАСШТАБ РЕНДЕРА (ПЕРЕЗАПУСК) | 28 | 22 |
| значение `mevr_upscaling_mode` | NATIVE AA | НАТИВНОЕ СГЛАЖИВАНИЕ | 20 | 18 |
| значение `mevr_upscaling_mode` | ULTRA PERFORMANCE | УЛЬТРА ПРОИЗВОДИТЕЛЬНОСТЬ | 25 | 18 |
| значение `mevr_upscaling_periphery` | NATIVE AA | НАТИВНОЕ СГЛАЖИВАНИЕ | 20 | 18 |
| пункт `mevr_hud_resolution` | HUD RESOLUTION (RESTART) | РАЗРЕШЕНИЕ HUD (ПЕРЕЗАПУСК) | 27 | 22 |
| значение `mevr_body_turning` | FOLLOW HEAD | СЛЕДОВАТЬ ЗА ГОЛОВОЙ | 20 | 18 |
| пункт `mevr_part_highlights_reset` | RESET HIGHLIGHT COUNTS | СБРОСИТЬ СЧЕТЧИКИ ПОДСВЕТКИ | 27 | 22 |
| пункт `mevr_night_vision_tube` | REALISTIC NIGHT VISION | РЕАЛИСТИЧНОЕ НОЧНОЕ ВИДЕНИЕ | 27 | 22 |
| пункт `mevr_prompt_size` | ACTION PROMPT SIZE | РАЗМЕР ПОДСКАЗКИ ДЕЙСТВИЯ | 25 | 22 |

### 5.2. Спорные места

| Оригинал | Сейчас | Почему плохо |
| --- | --- | --- |
| COMFORT (заголовок страницы) | КОМФОРТНЫЙ | прилагательное в названии вкладки; нужен «КОМФОРТ» |
| ROOM-SCALE | МАСШТАБ | совпадает с WORLD SCALE — «МАСШТАБ МИРА»; нужен «В КОМНАТЕ» |
| LEFT HAND / RIGHT HAND | ЛЕВАЯ / ПРАВАЯ | рядом HEAD — «ГОЛОВА»; нужно «ЛЕВАЯ РУКА» / «ПРАВАЯ РУКА» |
| GRIP | ХВАТ | в подсказках тот же термин — «ЗАХВАТ»; выбрать одно слово |
| WEAPON GRIP ANGLE | УГОЛ ХВАТА ОРУЖИЯ | если GRIP — «ЗАХВАТ», то «УГОЛ ЗАХВАТА ОРУЖИЯ» |
| HOLD / TOGGLE | УДЕРЖ. / ПЕРЕКЛ. | сокращения непонятны без подсказки; 18 символов есть |
| SIGHTING EYE | ГЛАЗ ПРИЦЕЛА | не читается как «какой глаз смотрит в прицел» |
| LEFT / RIGHT (для глаза) | ЛЕВАЯ / ПРАВАЯ | глаз мужского рода: «ЛЕВЫЙ» / «ПРАВЫЙ» |
| MIRROR HEADSET UI | ЗЕРКАЛИРОВАТЬ UI ШЛЕМА | «UI» не переведено; «ИНТЕРФЕЙС ШЛЕМА» |
| UPSCALER | АПСКЕЙЛЕР | транслит; «МАСШТАБИРОВАНИЕ» |
| UPSCALING MODE | РЕЖИМ АПСКЕЙЛА | согласовать с «МАСШТАБИРОВАНИЕ» |
| FOVEATED UPSCALING / FOVEATED RENDERING | ФОВЕАЛЬНЫЙ АПСКЕЙЛ / ФОВЕАЛЬНЫЙ РЕНДЕРИНГ | «фовеальный» — транслит |
| RENDER SCALE (RESTART) | МАСШТАБ РЕНДЕРА | рядом HUD RESOLUTION — «РАЗРЕШЕНИЕ HUD»; выбрать одно |
| RESET HIGHLIGHT COUNTS | СБРОСИТЬ СЧЕТЧИКИ ПОДСВЕТКИ | 27 символов, обрезается |
| BELT WHEN CROUCHING | ПОЯС В ПРИСЕДЕ | «присед» — жаргон; «ПОЯС ПРИ ПРИСЕДАНИИ» |
| CROUCH BUTTON | КНОПКА ПРИСЕДА | «КНОПКА ПРИСЕДАНИЯ» |
| HIP (значение MAGAZINE POUCH) | БЕДРО | это место, а не часть тела: «НА БЕДРЕ» |
| DEEP BLACKS | ГЛУБОКИЙ ЧЕРНЫЙ | о цветах: «ГЛУБОКИЕ ЧЕРНЫЕ» |
| CINEMATIC TRACK | СЦЕНАРНЫЙ ПУТЬ | читается как «сценарий», а не «путь камеры» |
| STAY WITH YOU | ОСТАВАТЬСЯ С ВАМИ | в моде всюду «ты»-стиль; рядом FOLLOW — «СЛЕДОВАТЬ» |
| HINT HEIGHT / HINT SIZE | ВЫСОТА ПОДСКАЗКИ / РАЗМЕР ПОДСКАЗКИ | не отличает «карточку» от «текста» |
| OTHER EYE WHILE SCOPED | ВТОРОЙ ГЛАЗ В ПРИЦЕЛЕ | читается как «второй прицел» |
| SCOPE STEERING | НАВЕДЕНИЕ ПРИЦЕЛА | «наведение» и «поворот» смешаны |
| ACTION PROMPT SIZE | РАЗМЕР ПОДСКАЗКИ ДЕЙСТВИЯ | калька; «РАЗМЕР ПОДСКАЗОК ДЕЙСТВИЙ» |
| USE REACH / USE BY LOOKING | РАДИУС ВЗАИМОДЕЙСТВИЯ / ИСПОЛЬЗОВАТЬ ВЗГЛЯДОМ | пара должна быть симметричной |

### 5.3. Строки, намеренно оставленные латиницей

Это не пропуски перевода: технические имена, их трогать не нужно.

`FSR`, `DLSS`, `VR`, `1.00X`, `1.25X`, `1.50X`, `2.00X`, `K (DLSS 4)`, `M (DLSS 4.5)`, `L (DLSS 4.5)`, `J (DLSS 4)`, `E (DLSS 3)`, `TAA`.

## 6. Чек-лист агента-редактора

- [ ] Раздел 1: одинаковые термины на всех страницах, единый регистр.
- [ ] Раздел 2: подсказка объясняет именно этот пункт, а не соседний.
- [ ] Раздел 3.1–3.3: единый голос (везде «вы»), единые названия кнопок.
- [ ] Ни одна подстановка `{}`/`{:g}`/`{:.2f}` не потеряна.
- [ ] Все `<...>`-теги на месте и не переведены.
- [ ] Строки не длиннее лимитов из 5.1.
- [ ] Нет символов вне таблицы глифов.
