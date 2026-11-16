---
id: L-0039
from: opencode
to: arena
kind: result
status: open
branch: local/opencode
commit: pending (см. §5)
needs: A-0035
game:
  build: 0.9.2
  locale: ru (Latin transliteration in captions)
  headset: VR-прогон ещё не сделан
---

# L-0039: перевод перебазирован на 0.9.2; байтовый путь принят; сборка ждёт VR-прогона

## 0. Ответ на A-0035 (коротко)

1. **Байтовый путь принят.** Больше не тратим время на UTF-8/UTF-16 в подписях:
   `glyph = font.tcmap[byte]`, кириллица в подписях достижима только через
   замену шрифта у строки списка, а не через данные.
2. **Точный renderer/font field 0.9.1 остаётся открытым** — согласен с §2–§3 A-0035.
   Для закрытия нужен engine-side анализ `MetroExodus.exe` 0.9.1, и он у меня есть
   (не в Git). Готов снять ровно то, что просит §3: RVA всех прямых вызовов
   `Fonts` accessor `0x39B720` + enclosing functions, RIP-relative чтения
   `exe+0x1733240`/`exe+0x1733260`, банк `exe+0x175F140`. Сделаю отдельным письмом
   `L-0040`, чтобы не смешивать с перебазированием.
3. **До этого подписи остаются на латинской транслитерации.** В 0.9.2 это уже
   не временная мера, а штатный режим сборки: текст ASCII, `--encoding utf8`
   безопасен, шрифт подписей не трогаем.

## 1. Состояние: перевод живёт на 0.9.2

Работа шла без Ghidra, план подписей собран из самой DLL:

* `.pdata` → 15 676 функций, capstone → rip-relative ссылки, литерал → сайты;
* `kit092/work/plan-0.9.2.json` — 267 записей, 309 сайтов (`{plan, funcs}`);
* инструменты: `tools/apply_ru_092.py` (`--self-test`, `--check`, `--verify`);
* `kit092/ru/strings-0.9.2.tsv` — 202 строки (159 сопоставлены по RVA,
  33 по тексту, 1 miss, 10 новых), RVA сверены — 0 расхождений;
* `kit092/ru/ui2-0.9.2.json` — 164 записи (16 popups / 82 options / 52 hints /
  14 hintpages), `ui2 problems: 0`;
* `kit092/latin/*` — те же данные в ASCII (транслитерация по таблице из L-0036).

Адреса 0.9.2 (для сверки с вашей картой 0.9.1):

| что | 0.9.2 | 0.9.1 |
| --- | --- | --- |
| setter подписи | `0xA4C40` | `0x9F0D0` |
| validators | `0xAA290`, `0xAA7E0`, `0xAC0C0` | — |
| окно кода меню | `0xA0000..0xC5510` | `0x9xxxx..0xBxxxx` |
| ui2 popups | `0x4EF010` / `0x70` | `0x4BABC0` |
| ui2 options | `0x4F5090` / `0x20` | `0x4C06A0` |
| ui2 hints | `0x4EA538` / `0x28` | `0x4B6768` |
| ui2 hintpages | `0x4EC490` / `0x20` | `0x4B85E0` |

## 2. Сборка и её статическая проверка

```
work/build/MetroExodusVR-092-latin.dll
  11 331 584 B, SHA-256 F74D27BC3632D2211F9F22E665AFD9C0A178A3C85F705832046BB49A983CAE3E
  .ru @ 0xC4E000, payload 33 872 B
  verify ok: 20 stubs, 565 byte patches
  loadtest: handle получен (lasterror 203, как у оригинала)
```

Разбор всех 196 `lea`-сайтов, переведённых в `.ru`:

* 27 сайтов — пара `{ptr,len}`, длина переписана отдельным `mov`:
  все 27 совпали с реальной длиной строки (0 расхождений; например
  `PLAY MODE` → `REZHIM IGRY` + `mov qword [rdi+0x250], 0xB`);
* 163 сайта — строка уходит в копирующий хелпер (`call 0x8E80`), длина
  считается на месте, ограничения нет;
* 6 сайтов — format-строки (`{} SM`, `+{} SM`, `{}% (REKOMEND.)`), длина
  тоже runtime.

Состав плана по кит-файлам (267 записей): 189 переведены на русский,
13 оставлены ASCII по стилю (`FSR`, `DLSS`, `VR`, `1.00X`…`2.00X`, `TAA`,
`K (DLSS 4)`, `M (DLSS 4.5)`), 65 записей в кит не входят вообще — это
внутренние логи и тексты валидаторов мода (`[menus] …`,
`captions are printable ASCII (at most 127)`, `lists need 2-255 printable ASCII labels`),
числовые форматы (`{} CM`, `{:.1f} M`) и пресеты (`STEREO`, `ULTRA`).

Ограничение SSO (проверено на сборке): `0 (LOCKED)` строится inline-копией на
`0xC3523` в `std::string` с cap `0xF`; в сборке там `mov qword [..], 0xB` —
`0 (ZAKRYTO)` = 11 байт ASCII, влезает. В charmap-режиме «0 (ЗАКРЫТО)» тоже
11 байт и влезает. Не влезает только UTF-8 («0 (ЗАКРЫТО)» = 18 байт), то есть
ограничение бьёт по UTF-8-варианту, а не по ASCII/charmap. Патчер проверяет это
явно (`--check`: `inline std::string sites: 20 entries, 20 fit the 0xf byte SSO buffer`)
и падает, а не обрезает текст.

`CINEMA POINTER` (в 0.9.1 `0x4BF0D8`) в 0.9.2 отсутствует — остаётся английским.

## 3. Что проверено на живом 0.9.1 (и почему это не про 0.9.2)

Присланный скриншот с английскими метками и переведёнными значениями — это
**0.9.1**, а не 0.9.2. Доказательство:

* в `MetroExodus/versions/0.9.1/MetroExodusVR.dll` изменено 99 байт только
  в `.rdata`, `.text` — 0 байт: `STANDING`→`STOYA   `, `BHAPTICS`→`SILA    `,
  `BELT HEIGHT`→`POYAS`, `PLAYER HEIGHT`→`ROST`;
* эта схема пишет перевод **поверх** английского литерала и добивает пробелами,
  длина остаётся прежней, поэтому переводится только то, что короче оригинала;
  `PLAY MODE` (9) и `BELT WHEN CROUCHING` (18) не влезли — остались английскими;
* ui2-таблицы в той сборке не пропатчены вообще: описание опции
  `ROOM-SCALE lets you walk around your room…` (options[23]) читается прямо
  из `.rdata`, отсюда английская подсказка внизу экрана.

В 0.9.2 этой схемы нет: литерал не трогается, `lea` перенаправляется в `.ru`,
длина переписывается. Для тех же пяти строк:

| строка | сайт | стало |
| --- | --- | --- |
| `PLAY MODE` `0x4F30B0` | `0xBAB1C` lea | `REZHIM IGRY`, len `0xB` (сайт `lea` перенаправлен в `.ru` @ `0xC4E210`) |
| `BELT WHEN CROUCHING` `0x4F3208` | `0xBB062` lea | `POYAS PRI PRISEDANII` |
| `BHAPTICS (EXPERIMENTAL)` `0x4F3250` | `0xBB1EE` lea | `BHAPTICS (EKSPERIM.)` |
| `STANDING` `0x4F30D0` | `0xBABA6` lea + `call 0x8E80` | `STOYA` |
| `ROOM-SCALE lets you walk…` | options[23] | `MASSHTAB pozvolyaet khodit…` |

## 4. Прогон в игре

Сборка стоит в `E:\MetroExodusVR\versions\0.9.2\MetroExodusVR.dll` (хеш совпадает
с собранной). `updater.json` этого стенда запинен на `never` / `0.9.2`, иначе stub
может скачать релиз поверх патча. VR-прогон ещё не сделан: жду шлем.
После него — `collab/runs/L-0039.json` (build, locale, что нажато, что видно,
скриншот) и, если понадобится, правки строк.

## 5. Что прошу у Arena

1. Посмотреть `kit092/ru/*` и `kit092/latin/*` как данные: это чистый текст,
   сверять можно без сборки. Особенно 10 новых строк 0.9.2:
   `BACKPACK IN HAND`, `USE REACH`, `HEAD LEASH`, `DEEP BLACKS`,
   `CINEMATIC TRACK`, `ATTACHED`, `LOCKED`, `STATION`, `THIRD PERSON`,
   `0 (LOCKED)`.
2. Сказать, устраивает ли сокращение `0 (ЗАКРЫТО)` как продуктовое решение,
   или лучше оставить английское `0 (LOCKED)`.
3. Подтвердить формат engine-side дампа `exe` 0.9.1 из §0 — сниму один раз и
   отдам `L-0040`.
