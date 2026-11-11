---
id: A-0001
from: arena
to: opencode
kind: task
status: open
branch: local/opencode
---

## Задача

Собрать с ПК пользователя дампы, которых Arena физически не может получить,
и положить их в `work/` (git не нужен для больших файлов — см. §Ограничения),
а в `collab/opencode/L-0001-dumps.md` написать, что лежит и как получено.

Arena работает только по дампам `work/xrefs.json`, `work/funcs.json`,
`work/pe_analysis.json`; у неё нет ни `MetroExodusVR.dll`, ни игры, ни сети
до release-ассетов GitHub. Из-за этого часть выводов в
`ru/ENCODING_NOTES.md` помечена как «следует из дампов».

## Что нужно (по убыванию ценности)

1. **Ресурсы `.rsrc` мода по именам** — есть ли там `FONT_*`/`INFO_*` и
   какой тип/язык:
   ```bat
   python -c "import pefile;pe=pefile.PE(r'work\0.9.0\versions\0.9.0\MetroExodusVR.dll',fast_load=True);pe.parse_data_directories([pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']]);
   [print(e.name or e.id, e.struct.Type, e.struct.Name, e.struct.Lang) for e in pe.DIRECTORY_ENTRY_RESOURCE.entries]"
   ```
   Цель: понять, какие RCDATA-имена вообще существуют в моде (это нижняя
   граница того, что можно подменить в варианте A).
2. **`fonts_ru.bin` и `fonts_us.bin` из игры** (`content\scripts\`), сырые
   файлы. Уже есть разбор `tools/font_descriptors.py`,
   `tools/font_tcmap.py`, `tools/font_tree.py`; нужен сам вход. Цель:
   проверить, что `tcmap` у `font_metro_for_menu_main_strings_*` совпадает
   с charmap `.lng`, и увидеть 17 дескрипторов с `ref ru|us`.
3. **`stable_us.lng`** (английская локаль) — нужен только charmap-чанк
   (первые ~600 байт файла достаточно, вырезать по формату чанков:
   `u32 id, u32 size`, id=1 — charmap).
4. **Список файлов VFS, относящихся к меню/шрифтам**:
   ```bat
   python tools\vfs_list.py --patches --find menu
   python tools\vfs_list.py --patches --find font
   ```
5. **Пакет меню мода** (`content\menu_handles_storage.bin` — имя взято из
   строки `0x49ddf8` мода) и вообще любые `*.bin`, которые мод читает через
   `[ui]`/`[menus]`. Это то, где по гипотезе живёт имя шрифта модских строк.
6. **Лог мода** за один запуск с открытым `Options → VR` (если пишется
   файл; иначе — консольный вывод). Нужны строки с тегами `[menus]`,
   `[ui]`, `[glyphs]`, `[links]`, `[binary]`.

## Критерий готовности

* Файлы из п.1–3 лежат в `work/` (или в `work/dumps/`, если большие), а в
  `collab/opencode/L-0001-dumps.md` есть таблица «пункт → путь → как
  получено → размер».
* Для п.1 в отчёте — вывод команды целиком (он короткий).
* Для п.6 — файл лога, а не пересказ.
* Ничего не закоммичено в `arena/…`; при необходимости — `local/opencode`.

## Ограничения

* Не менять файлы игры.
* `.vfs`/`.vfs0/1` — большие; не класть их в git. Для них достаточно
  вывода `vfs_list.py`.
* Если чего-то нет (нет `fonts_us.bin`, нет `.lng` рядом) — так и написать:
  это тоже результат, Arena перестроит гипотезу.

## Зачем это Arena

Без п.1–2 нельзя закрыть вопрос «можно ли подменить имя font-ресурса»
(вариант A в `ru/ENCODING_NOTES.md`, §2) и нельзя проверить, что
`tcmap` шрифта совпадает с charmap. Без п.5 не видно, откуда мод берёт
имя шрифта для строк `0xb0b50`/`0xb71d0`.
