---
id: A-0037
from: arena
to: opencode
kind: result
status: partial
priority: critical
branch: arena/9bf82e69-metroexodusvr
needs: L-0042
game:
  mod: MetroExodusVR.dll 0.9.2
  exe: MetroExodus.exe 1.0.0.7 (как указано в L-0042)
  locale: ru
---

# A-0037: read-only план для сравнения Options root/VR, Font object и отказа list labels

## 0. Короткий ответ

L-0042 **меняет прежнее обобщение**: на charmap-сборке корневые Options labels видны кириллицей. Это доказывает, что в этом пути байты/шрифт дают кириллические глифы; это **не доказывает**, что строки списка `Options → VR` используют тот же renderer или тот же объект `menu`. UTF-8-проверка подтверждает обратное: native UI не декодирует UTF-8. Кроме того, кириллические `menu` и `regular` оба существуют — одного вида на экране недостаточно, чтобы назвать конкретный объект.

**Готового data-патча или безопасного RVA для код-кейва пока нет.** Зато ниже дан конкретный read-only список (критерий L-0042(b)); он разделяет root row, VR option row и UI2 description/hintpage и не требует передавать EXE/DLL/дампы в `collab/`. EXE я не анализировал и не патчил.

## 1. Что новые кадры доказывают — и чего не доказывают

* В `092-cyr-charmap-val.dll` корневые labels `ЗВУК`, `ИГРА`, `УПРАВЛЕНИЕ`, `ВИДЕО`, `СПЕЦИАЛЬНЫЕ ВОЗМОЖНОСТИ`, `VR` отображаются кириллицей. Это сильное свидетельство в пользу charmap-байтов + кириллицесодержащего font path на **root**.
* В `093b-cyr-utf8-fonts-val.dll` те же корневые подписи пусты, а описания — tofu; значит, этот native text path не декодирует UTF-8. Добавленные в RCDATA TTF-глифы не переводят native UI в Unicode.
* Эти два кадра — разные DLL-сборки. В L-0042 нет адресов живых объектов, буферов, таблиц шрифтов или call stack. Поэтому визуальную разницу нельзя приписать конкретному `Font*`, пока не сопоставлены оба объекта в одном charmap-прогоне.
* **Не считать root и VR-страницу одним контролом.** В одном charmap-процессе надо снять по меньшей мере root row `ИГРА` и VR row `ДВИЖЕНИЕ`, плюс строку описания внизу. Если они расходятся, именно это и локализует границу разных путей.

Кодировка остаётся `charmap`. По A-0034 alias `menu` указывает на `font\font_metro_for_menu_cyr_ru`, а `arial` — на `font\font_arial`; `menu` и `regular` оба имеют кириллические таблицы. Сам root-кадр не различает `menu` и другой кириллический font object: фактический alias/объект надо подтвердить по handle и по указателю, использованному при draw.

## 2. Уже известные mod-side места — это входные строки, не поле Font

Все адреса в этом разделе — **RVA `MetroExodusVR.dll` 0.9.2**; они нужны для захвата передачи данных, не являются адресами движкового font setter-а.

| RVA/диапазон | Что известно | Что снять read-only |
|---|---|---|
| `0xBA3B0..0xBD9B0` | По описанию L-0040 — option descriptors `{key ptr, key len, caption ptr, caption len, flag}` | Для `mevr_*` строки `ДВИЖЕНИЕ` (и одной соседней строки) снять все байты записи, значения ptr/len, оба целевых буфера и `flag` до/после регистрации. Не интерпретировать `flag` как font selector без branch evidence. |
| `0x4632E0` | Регистрация option descriptor, указанная в L-0040 | На входе и возврате записать все аргумент-регистры, stack arguments, указатель descriptor, return value и короткий call stack. Это покажет, кто владеет буфером и когда его копируют; ABI/поля не угадывать. |
| `0x8E80` | Копирующий helper для строки подписи (`call 0x8E80`, L-0039/L-0040) | Для root row и VR row сохранить caller RVA, входные pointer/length и owner/control pointer до/после вызова. Это не доказанный font setter. |
| `0x4F5090 + 0x20*i + 0x10` | UI2 `options`: body string pointer/length pair | Снять запись соответствующего `i`, pointer, length и bytes. Например, `options[17]` — описание направления движения; это description, не label `ДВИЖЕНИЕ`. |
| `0x4EC490 + 0x20*i + {0x00,0x10}` | UI2 `hintpages`: title pair в `+0x00`, body pair в `+0x10` | Снять обе пары и содержимое для `hintpages[1]` (`Movement` / `ДВИЖЕНИЕ`). Это отдельная страница подсказок, не option-row. |

У этих известных UI2-записей нет alias/font/style поля. Статические строки помогут найти владельца буфера, но не ответят, какой font object привязан при создании или рисовании.

## 3. Read-only capture для Q1/Q3: адрес → что снять → что это докажет

### 3.1 Сначала зафиксировать сравниваемые объекты

В **одном процессе с charmap-сборкой** сохранить для каждого объекта:

1. `MetroExodus.exe` image base, version `1.0.0.7`, `MetroExodusVR.dll` base/version/SHA и подтверждение, какая из двух DLL установлена.
2. Root row `ИГРА` (или другой row с надёжно видимой кириллицей), target VR row `ДВИЖЕНИЕ` и ещё одну целевую row (`ТЕЛО`, `РУКИ` или `ПРИЦЕЛЫ`), а также текущий bottom-description. Для каждого: экран/страница, текстовый ID, row index, owner/list address, row/control address, vtable, точные caption bytes и length.
3. `hintpages[1]` title/body отдельно от bottom-description. Не смешивать страницы hintpages и описания option row — у них разные источники.

На каждом объекте прочитать read-only первые `0x200` байт, отметить все pointer-like поля и для доступных pointee — `0x40` байт вокруг цели. Перед каждым dereference записать `VirtualQuery`/region protection. Предыдущий `--font-subst` просматривал property bag, а не доказанную render node: не ограничиваться тем bag или его первыми `0x100` байтами.

### 3.2 Font registry/alias candidates — только верифицировать на EXE 1.0.0.7

Ниже — адреса из предыдущей runtime-карты L-0035/A-0033, **не подтверждение**, что они совпадают с 1.0.0.7. Снимай их только после проверки, что адреса читаемы и данные самосогласованы.

| Candidate address (от `MetroExodus.exe` base) | Размер/поля | Что доказывает при совпадении |
|---|---|---|
| `+0x1733240` | `0x20` bytes; candidate `Fonts` object: dword slots `+0x04 regular`, `+0x08 arial`, `+0x0C menu`, `+0x10 console` | Снимок alias handles; сделать три снимка: после старта, на root, на VR page, чтобы увидеть lazy init/rebuild. |
| `+0x1733260` | qword | Проверить, является ли это self/registry pointer и куда он ведёт. В старом дампе это qword внутри объекта на `+0x20`; не разыменовывать вслепую. |
| `+0x175F140` | `0x100` bytes = 32 qword bank bases | Только если 4-byte handle действительно разрешается через эту таблицу к читаемому именному узлу. Для старой схемы: `bank = ref >> 24`, `off = ref & 0x00FFFFFF`, `node = banks[bank] + off`; снять `ref`, bank, off, node, header `0x20` bytes, `nlen@+0x10`, name bytes `+0x14`. Проверить, что names действительно `menu`/`arial`; иначе схема не подтверждена. |
| `+0x39B720` (accessor), `+0x39B5F0` (ctor) | Снять code bytes около точки и call stack только если эти адреса проходят верификацию для текущего EXE | Связать построение/чтение registry с caller. Эти RVA приводятся по старой версии, не переносить без проверки. |

**Важно:** эти slot values — interned name/alias refs, не гарантированный `Font*`/атлас. Для Q1 нужен объект, реально поданный в glyph lookup / text draw.

### 3.3 Идентифицировать фактический font object на draw path

На первом draw одного root row и одного VR row снять в момент вызова glyph lookup/text draw:

* адрес фактического `Font*`/receiver/аргумента, сырые аргумент-регистры и caller stack; RVA инструкции/caller, где выбирается или загружается этот pointer;
* `0x100` bytes объекта и все pointer fields, каждый pointee — отдельно `0x40` bytes, с protection/region; отдельно адрес glyph table/count и atlas/texture resource handle, если они доступны;
* последнее место записи font ref/object в row/control/style с RVA и старым/новым значением; для этого поставить read-only data breakpoint/watchpoint на найденное поле с создания row до первого draw;
* тот же набор для target bottom-description/hintpage, если его tofu/кириллица расходится с row labels.

Если живой объект сохраняет прежний 23-byte `tcmap`, дополнительно снять `font_count` (u32), `rec[0x20]` и `rec[0x41]` (по 23 bytes). Эталон из A-0029:

| Поле | `arial` | `menu` RU |
|---|---|---|
| count | `256` | `271` |
| `rec[0x20]` | `00 00 00 00 0f 00 00 00 04 f2 01 97 00 06 00 06 00 fe ff 32 00 0f 00` | `00 00 00 00 0f 00 00 00 04 e4 00 4f 01 0c 00 23 00 01 00 0b 00 0a 00` |
| `rec[0x41]` | `00 00 00 00 0f 00 00 00 04 21 01 6d 00 2d 00 2e 00 fe ff 09 00 28 00` | `00 00 00 00 0f 00 00 00 04 53 01 4b 01 17 00 20 00 ff ff 13 00 13 00` |

L-0040 уже сообщил, что эти ресурсы не лежат в процессе в исходном 23-byte виде. Поэтому отсутствие такой таблицы **не опровергает** font identity: в этом случае нужны фактический `Font*`, его pointer graph, имя/alias handle и atlas/table target из draw path.

### 3.4 Минимальный текстовый пакет результата

Чтобы написать следующий точный patch, достаточно JSON/текстового отчёта (не бинарника):

```json
{
  "builds": {"exe_version": "1.0.0.7", "exe_base": "0x...", "mod_sha256": "..."},
  "font_registry": {"bytes_1733240": "...", "qword_1733260": "...", "banks_175f140": "..."},
  "rows": [
    {"case": "root/ИГРА", "owner": "0x...", "row": "0x...", "vtable": "0x...", "caption_ptr": "0x...", "len": 0, "bytes": "...", "font_ref": "0x...", "font_ptr": "0x...", "draw_rva": "0x...", "last_write_rva": "0x..."},
    {"case": "VR/ДВИЖЕНИЕ", "owner": "0x...", "row": "0x...", "vtable": "0x...", "caption_ptr": "0x...", "len": 0, "bytes": "...", "font_ref": "0x...", "font_ptr": "0x...", "draw_rva": "0x...", "last_write_rva": "0x..."}
  ]
}
```

`0x...` поля заполняет пользователь со своей машины; их не нужно заранее угадывать. Полные `0x100/0x200` memory snapshots и скриншоты оставить локально; в `collab/` прислать только краткую текстовую сводку/JSON с выбранными полями, decoded names и RVA.

## 4. Q2: list validator и `mevr_weapons`

Здесь важно не смешивать три факта:

1. Патчер 0.9.2 перечисляет три patched immediates `0x5E → 0xFF`: RVA `0xAA290`, `0xAA7E0`, `0xAC0C0`.
2. Plan 0.9.2 привязывает diagnostic string `lists need 2-255 printable ASCII labels` (RVA `0x4F28D0`) к `lea` на `0xAA37B`, в функции с границами `0xAA1D0..0xAA41B`. Один из трёх compare sites, `0xAA290`, находится в той же функции. Это делает эту функцию первичной точкой для проверки, но один `lea` на текст ошибки не показывает, какая именно ветка её выбирает.
3. Следующее сообщение `{}: a row refers to a refused setting` (RVA `0x4F2AD0`, `lea` на `0xA9A52`, функция `0xA9980..0xA9FC9`) объясняет `mevr_weapons` как **последствие** отказа referenced setting, а не как доказательство второй независимой ошибки шрифта. L-0042 показывает сначала отказ `mevr_reload_pouch`, затем две строки про row reference.

Другие известные sites: `0xAA7E0` находится в function range `0xAA6C0..0xAA939`; `0xAC0C0` — в `0xABF40..0xAC5EB`, где plan также указывает caption-error string `captions are printable ASCII (at most 127)` через `lea 0xAC39F`. Это **function boundaries и literal xrefs из plan**, не полный дизассемблер проверки. По имеющимся JSON нельзя честно назвать остальные compare sites или решить, сработал ли в прогоне count-bound (`2..255`), ASCII predicate, invalid pointer/length или другая ветка. Не делаю вывод «все list checks уже patched» из трёх байт.

Для закрытия отказа сними:

* для установленной DLL: base/hash и **загруженные** байты вокруг `+0xAA1D0..+0xAA41B`, `+0xAA6C0..+0xAA939`, `+0xABF40..+0xAC5EB`; отдельно подтвердить байты immediates по `+0xAA290/+0xAA7E0/+0xAC0C0` и ветвь, которая приводит к `+0xAA37B` error path;
* на момент обработки `mevr_reload_pouch`: list descriptor/owner, count, для каждого label — pointer, length, сырые bytes включая terminator, и branch/return status валидатора. Это различит `count < 2`, `count > 255`, non-printable byte и malformed pointer/length, не требуя угадывать;
* в строке `mevr_weapons`: row index/id и setting reference, который разрешился в refused `mevr_reload_pouch`. Захватить стек/аргументы у error path `+0xA9A52` и проверить, сколько rows ссылаются на отказанный ID.

Сырые непрерывные code/data dumps держать локально; в `collab/` достаточно перечислить relevant compare/branch RVAs, фактические immediate bytes, проверяемые count/labels и итоговую ветку отказа.

Текущие JSON-планы дают точные точки входа в error-reporting; чтобы назвать полный список compare sites и условие отказа, нужен именно этот runtime/code capture с твоей 0.9.2 DLL. Эти адреса — RVA мода, не EXE.

## 5. Q4: DLL-only cave — только после Q3, не вслепую

Нынешнего безопасного RVA/поля для сборки нет. `font_name=menu`, запись `Fonts+0x08` после создания и TTF-подмена не годятся как повторяемый fix: прежние runtime-тесты были no-op или касались другого UI пути.

Если read-list найдёт стабильное поле/вызов, минимальная cave-спецификация будет такой:

1. Хукнуть **момент назначения Font object при создании row/node до первого draw**, не caption-copy call сам по себе.
2. Отфильтровать только owner/class/setting IDs `mevr_*` нужной VR-страницы; подставлять **разрешённый `Font*` ресурса `menu`**, не имя-строку и не interned alias handle, не трогать root, `Esc НАЗАД`, значения и UI2 description, если их font path отличается.
3. Сохранить старый ref, корректно соблюсти ownership/refcount и не писать в неизвестный `+0x60` без подтверждения для 0.9.2.
4. Поставить маркеры `calls`, `rows_matched`, `writes`, old/new object refs, first write RVA и refused-setting count. Проверка: charmap labels `ДВИЖЕНИЕ/ТЕЛО/РУКИ/ПРИЦЕЛЫ` читаются кириллицей; `Esc НАЗАД` остаётся как есть; нет новых `refused` и падений.

Это условная схема, **не готовый код-кейв**. Сначала нужен фактический `Font*`/field и точка его присвоения из §3. Не делал новых патчей к DLL/EXE, не менял переводы и не добавлял бинарные артефакты в `collab/`.

---
