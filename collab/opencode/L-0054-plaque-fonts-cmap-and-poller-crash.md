---
id: L-0054
from: opencode
to: arena
kind: result
status: done
branch: local/opencode
commit: 6b5d987
needs: L-0053
game:
  build: 0.9.3
  locale: ru
  screen: главное меню, планка под экраном Cinema; проверено пользователем
---

## Задача

Убрать «кириллический мусор» на планке со ссылками мода (`METRO EXODUS VR /
by RippeR37 / v0.9.3 / Buy Me a Coffee / Ko-fi / Discord / GitHub`), не переводя
сам текст, и заодно закрыть два дефекта поллера шрифтовой таблицы.

## Причина: испорченный cmap в build/fonts

Планку рисует **ImGui** (1.92.8) из четырёх RCDATA-шрифтов самого мода:
`INFO_BARLOW_CONDENSED_SEMIBOLD`, `INFO_INTER_REGULAR`, `INFO_INTER_MEDIUM`,
`INFO_INTER_SEMIBOLD` (`[links] plaque ready 1280x300` в логе).

В `build/fonts` лежали шрифты, сделанные скриптом `work/remap_cmap.py`
(«charmap-baked»): их `cmap` отображает **байт кодировки** в глиф другой буквы
(`0x4D` → контур `Я`). Для меню это работало, потому что движок сам подаёт байт
как индекс. ImGui же подаёт **Unicode-кодпоинт** и по такому cmap рисует
`METRO EXODUS VR` как `ЯчцрГ!Ч_ГИфs!ур` — ровно то, что видно на планке.

Проверка: PIL-рендер `build/fonts/INFO_INTER_REGULAR.ttf` строкой
`METRO EXODUS VR` дал тот же мусор пиксель-в-пиксель.

## Решение

`tools/merge_cyrillic.py` теперь:

1. берёт **оригинальные** шрифты из `--src` (`E:\MetroExodusVR\versions\0.9.3\
   MetroExodusVR.dll`, ресурсы `0xbf06c8/0xc0b240/0xc1b7f0/0xc2bd50`), а не
   испорченные копии из `build/fonts`;
2. вливает кириллицу Arial, **не трогая cmap** (он остаётся честным Unicode:
   `M` → контур `M`, gid 58; `T` → gid 93);
3. сжимает результат под размер штатного слота (`subset`, без хинтинга,
   `KEEP_CODEPOINTS` = ASCII + Latin-1 + `U+0400..U+045F` + `– — ‘ ’ “ ” … ™ №`),
   потому что ресурсы переписываются на месте: 27–32 КБ вместо 66–109 КБ;
4. `--no-subset` оставлен для отладки (пишет полный merged-шрифт, в DLL не влезет).

Итоговые файлы (614 глифов Inter, 790 Barlow, кириллица на месте):

```
INFO_BARLOW_CONDENSED_SEMIBOLD  32256 B (slot 109428)
INFO_INTER_MEDIUM               27884 B (slot  66992)
INFO_INTER_REGULAR              27868 B (slot  66912)
INFO_INTER_SEMIBOLD             28108 B (slot  67144)
```

`apply_ru_093.py --fonts --verify` зелёный, сборка
`build/MetroExodusVR-0.9.3.dll` sha `b63b1df454829a8e…e6a2`, установлена,
`mod_switch.py status` = профиль `ours`. **Текст планки не переводился и не
патчился никакими литералами.**

## Побочно: два фикса поллера (L-0054 crash)

1. `CreateThread` в пещерке: `lpThreadId` — указатель, а обнулялись только
   4 байта (`mov dword [rsp+0x28], 0`); верхняя половина слота содержала мусор
   (`0x1600000000`), и `CreateThread` падал внутри `KERNELBASE` при записи id.
   Теперь `mov qword [rsp+0x28], 0`.
2. Гейт `cmp edx, 1 / jne done`: DllMain зовётся с `DLL_THREAD_ATTACH` для
   каждого потока, и пещерка спавнила поллер из его же attach-нотификации.

## Проверено в игре (пользователь)

* планка: `METRO EXODUS VR`, `by RippeR37`, `v0.9.3`, `Buy Me a Coffee`,
  `Ko-fi`, `Discord`, `GitHub` — нормальной латиницей, без искажений;
* футер паузы и `СОВЕТЫ` (L-0053) не сломались;
* игра стартует без краша.

## Замечание на будущее

`work/remap_cmap.py` (charmap-запекание) **непригоден** для этих четырёх
шрифтов: движок их не использует, их читает только ImGui-планка. Если
понадобится править планку — правится текст, а не cmap.
