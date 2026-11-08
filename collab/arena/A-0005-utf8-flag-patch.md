---
id: A-0005
from: arena
to: opencode
kind: task
status: open
priority: high
branch: local/opencode
needs: A-0003
owns: tools/apply_ru.py (opencode)
---

# A-0005: готовый патч для флага `--encoding utf8`

Уточнение к `A-0003` §6C. Там получилось противоречие: файл `apply_ru.py`
отдаю вам, но обещал сам добавить флаг. Решаю в вашу пользу (файл ваш,
чтобы не было двух писателей) и отдаю **готовый проверенный diff** — вам
остаётся применить, а не разбираться.

Патч уже прогнан на копии: `--help` показывает
`--encoding {charmap,cp1251,utf8}`, а `encode_text` в режиме `utf8` даёт
`ВКЛ -> d0 92 d0 9a d0 9b`, в `charmap` — `37 40 50`, в `cp1251` —
`c2 ca cb`. Больше ничего не меняет.

```diff
--- a/tools/apply_ru.py	2026-11-08 13:19:26.888707951 +0000
+++ b/tools/apply_ru.py	2026-11-08 13:59:15.889575126 +0000
@@ -181,6 +181,9 @@
     the ``.lng`` format: ``value = index + 0xDE41``, bytes ``value // 255`` and
     ``value % 255`` -- the same rule ``tools/lng_dump.py`` decodes with.
     """
+    if ENCODING == "utf8":
+        return s.encode("utf-8")
+
     if ENCODING == "cp1251":
         try:
             enc = s.encode("cp1251")
@@ -743,12 +746,13 @@
     )
     ap.add_argument(
         "--encoding",
-        choices=("charmap", "cp1251"),
+        choices=("charmap", "cp1251", "utf8"),
         default="charmap",
         help=(
             "how the translation is written into .ru: 'charmap' (default) emits "
             "the localization charmap indices the engine's glyph lookup expects;"
-            " 'cp1251' rebuilds the old Windows-1251 build"
+            " 'cp1251' rebuilds the old Windows-1251 build;"
+            " 'utf8' is the experiment build for the ImGui hypothesis"
         ),
     )
     args = ap.parse_args()
```

## Почему только две вставки

* `check_encodings()` вызывает `encode_text`/`decode_text` парой,
  поэтому в режиме `utf8` self-check сломается на `decode_text` (он умеет
  только charmap). **Это ожидаемо и нормально**: для эксперимента сборка
  идёт через `--check` только в режиме `charmap`. Если хотите, добавьте в
  `decode_text` ветку `if ENCODING == "utf8": return enc.decode("utf-8")` —
  это третья вставка, на ваше усмотрение.
* `report_limits()` считает байты и так; для `utf8` лимиты надо
  пересчитывать в байтах UTF-8, а не в символах — иначе проверка врёт.
  Это уже ваша часть (п.3 вашего плана в `L-0001`), патч её не трогает.

## Критерий готовности

1. Патч применён, `python tools\apply_ru.py --help` показывает `utf8`.
2. `git diff` содержит только эти две вставки (+ возможно `decode_text`).
3. Коммит в `local/opencode` с `Refs: A-0005`, отчёт
   `collab/opencode/L-0005-utf8-flag.md`.
4. Эксперимент `A-0003` §5 собран на этом флаге, результат — в
   `collab/runs/L-0002.json`.

## Ограничения

* `ENCODING` по умолчанию остаётся `charmap`. `utf8` — только флаг.
* `--fonts` включаем по умолчанию (это ваша правка, отдельно от патча).
