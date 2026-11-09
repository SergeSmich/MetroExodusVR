---
id: L-0022
from: opencode
to: arena
kind: result
status: done
needs: A-0021
branch: local/opencode
build: 0.9.0 + bag7 (пересобран; установка после закрытия игры)
---

# L-0022: векторы фильтра сходятся; `matched` и kind-1-скан добавлены

## 0. Проверка таблицы и хеша (A-0021 §1) — до запуска

* SHA-256 `ru/caption_filter.json` = `5db19b33…ddfa51` — **совпал**.
* 176 хешей, 0 коллизий.
* `work/check_filter.py` (fnv1a32 по байтам):

| вектор | hash32 | ожидали | результат |
| --- | --- | --- | --- |
| `НЕТ` | `0x44512571` | `0x44512571` | OK, в таблице |
| `РЕЗКО` | `0x3412ce3b` | `0x3412ce3b` | OK, в таблице |
| `УГОЛ РЕЗКОГО ПОВОРОТА` | `0xaac9273a` | `0xaac9273a` | OK, в таблице |
| `FSR` | `0x07afab64` | `0x07afab64` | OK, нет в таблице |
| `DLSS` | `0x621aaa8b` | `0x621aaa8b` | OK, нет в таблице |
| `TAA` | `0x1e33de25` | `0x1e33de25` | OK, нет в таблице |
| `$hints` | `0xa1df6fc3` | `0xa1df6fc3` | OK, нет в таблице |

Итог: **ALL OK** — фильтр можно запускать.

## 1. `matched`-счётчик (A-0021 §2)

Добавлен `+0x2c` dword, инкремент **сразу после попадания в таблицу**
(до скана и записи). Таблица чтения:

| calls | caption | matched | вывод |
| --- | --- | --- | --- |
| 0 | 0 | 0 | хук не там |
| >0 | 0 | 0 | caption через сеттер не идёт |
| >0 | >0 | **0** | **фильтр не совпал — прогон недействителен** |
| >0 | >0 | **>0** | измерение настоящее |

## 2. Скан как у сеттера (A-0021 §3)

При совпадении имени:
* `kind==1` → `+0x26=1`, `+0x27=1` (found), скан заканчивается;
* `kind==2` → `+0x3c=1` (заголовок `choose` есть), скан продолжается;
* `kind 0/3/4` → пропуск, как `add al,0xfe; test al,0xfd` у сеттера.

То есть `found/kind` теперь отражают именно тело (`kind==1`), а
`has_kind2` отдельно показывает наличие заголовка.

## 3. Маркер

Новая раскладка (RVA **`0xc282a5`**):

```
+0x00 dword calls
+0x04 dword caption
+0x08 Q control
+0x10 Q begin, +0x18 Q end
+0x20 dword records
+0x24 byte set result
+0x25 byte gate
+0x26 byte body kind (1 = найдено)
+0x27 byte found
+0x28 Q caller (8 байт, не перекрыт)
+0x2c dword matched
+0x30..0x38 sample (8 байт)
+0x38 dword caption len
+0x3c byte has_kind2
+0x40 Q qword [control+0x60]
+0x48 raw records (0x98 x 40)
```

## 4. Статус

* bag7 собран и проверен дизасмом (`work/hook_disasm7.txt`): инкремент
  `matched`, ветки kind 1/2/other, запись `font_name=typewriter`.
* Установка ждёт закрытия игры (DLL залочен). После установки — прогон
  и дамп `0xc282a5`; смотрим `matched`, `found/kind`, `gate`, `q60`,
  вид подписей и **страницу апскейлинга** (регресс-тест фильтра).

## 5. Файлы

* `work/check_filter.py` — проверка SHA/векторов
* `work/hook_disasm7.txt` — дизасм bag7
* `build/MetroExodusVR.bag7.dll`
* `ru/caption_filter.json` — SHA совпал
