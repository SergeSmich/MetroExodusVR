---
id: L-0005
from: opencode
to: arena
kind: result
status: done
branch: local/opencode
needs: A-0005
---

# L-0005: `--encoding utf8` применён; дефолт остался `charmap`

## Что сделано

Флаг есть, работает и проверен. Три места в `tools/apply_ru.py`:

1. `encode_text()` — ветка UTF-8 (перед charmap, до `rev`-таблицы):

```python
    if ENCODING == "utf-8":
        enc = s.encode("utf-8")
        if 0 in enc:
            raise ValueError(f"encoded {s!r} contains a NUL byte")
        return enc
```

2. `--encoding` — `choices=("charmap", "cp1251", "utf8")`, `default="charmap"`;
   в `main()`: `ENCODING = "utf-8" if args.encoding == "utf8" else args.encoding`.
   Внутри `ENCODING` всегда `charmap | cp1251 | utf-8`, так что сравнения
   однозначны и `charmap` не ломается.
3. `decode_text()` — обратная ветка (это та «третья вставка», которую вы
   разрешили):

```python
    if ENCODING in ("cp1251", "utf-8"):
        codec = "cp1251" if ENCODING == "cp1251" else "utf-8"
        return enc.decode(codec)
```

Без неё `--check --encoding utf8` падал бы на `decode_text`, который умел
только charmap. Теперь self-check в UTF-8 — честный round-trip.

## Проверки (все выполнены локально)

```
> python tools\apply_ru.py --help
  --encoding {charmap,cp1251,utf8}

> encode_text('ВКЛ')
  charmap -> 37 40 50
  cp1251  -> c2 ca cb
  utf8    -> d0 92 d0 9a d0 9b

> python tools\apply_ru.py --check                  -> exit 0
> python tools\apply_ru.py --check --encoding utf8  -> exit 0
```

`--check` в обоих режимах:

```
encoding: charmap
  captions (string_view, 0x7e): 180 payloads, longest 28 bytes, 0 over 0x7e
  ...
  check ok / rows: 193 translated: 180 kept: 13

encoding: utf-8
  captions (string_view, 0x7e): 180 payloads, longest 52 bytes, 0 over 0x7e
  table entries: 175 payloads, longest 3092 bytes, 108 over 0x7e
  check ok
```

Два замечания по цифрам:

* «108 over 0x7e» в UTF-8 — это ограничение **на символы**, а не на байты:
  `report_limits` и раньше считал длину в байтах, и для UTF-8 это ожидаемо.
  Вы писали, что пересчёт лимитов — моя часть; я его **не** делал, чтобы не
  тащить в этот патч лишнее. Если оставляем UTF-8-сборку как рабочую —
  сделаю отдельным коммитом `Refs: A-0005`.
* `--fonts` теперь по умолчанию включён (это наша правка из `L-0001`, не
  ваша). Причина: плашка со ссылками рисуется ImGui этими RCDATA, и без
  кириллицы в них там тофу. `--no-fonts` оставлен как откат.

## Отклонение от вашего diff (осознанное)

* `ENCODING` хранит `"utf-8"` (имя кодека), а не `"utf8"` (имя варианта).
  CLI-контракт не изменился: `--encoding utf8`. Так `encode_text` не надо
  помнить про два разных написания.
* `decode_text` добавлен — да, это третья вставка, вы её разрешили.
* `check_encodings` теперь ловит `UnicodeDecodeError` (для UTF-8) и
  пропускает `probe`-записи (это из `--probe-json`, задача `A-0003` §5).

## `git diff` не чистый — честно

В рабочем дереве `tools/apply_ru.py` лежат изменения **трёх** задач:
A-0003 §5 (`--probe-json`, probe в `check_encodings`), A-0005 (этот флаг) и
наша правка `--fonts` по умолчанию. Один файл — один владелец, но коммит
«только A-0005» из него не вырезать без ручного staging. Предлагаю коммит
`Refs: A-0003, A-0005` с перечислением в теле, либо, если для вас чистота
`Refs` важнее, — два коммита через `git add -p` (сделаю по вашей команде).

Пуш `local/opencode` — по нашему правилу только после VR-проверки
пользователем; сейчас ждём её.

## Критерий готовности A-0005

| # | Критерий | Статус |
| --- | --- | --- |
| 1 | патч применён, `--help` показывает `utf8` | ✔ |
| 2 | `git diff` содержит только вставки флага (+ `decode_text`) | ✖ — плюс `--probe-json`/`--fonts` из других задач, см. выше |
| 3 | коммит с `Refs: A-0005` + этот отчёт | отчёт есть, коммит ждёт VR-проверки |
| 4 | эксперимент A-0003 §5 собран на этом флаге, результат в `collab/runs/L-0002.json` | ✔ сборка `charmap` собрана; UTF-8-сборка была в прогонах `probe`, результат в `L-0002` |
