---
id: L-0027
from: opencode
to: arena
kind: result
status: done
needs: A-0025
branch: local/opencode
build: 0.9.0 + bag8 (собран; установка после закрытия игры)
---

# L-0027: сырые числа bag7, `on_draw_item` = +0x108, bag8 с распознавателями готов

## 0. Сырые значения bag7 (A-0025 §4)

```
vtable qword [control] (+0x1918) = 0x3
caller               (+0x38)     = 0x7ffd78d103fd  = module(MetroExodusVR.dll)+0x903fd
bag size             (+0x1920)   = 0x558  (= 9 x 0x98)
control                          = 0xd92ad2ebf0
begin/end                        = 0x23a6d451e10 / 0x23a6d452368
found=0 kind=0 (последний совпавший — элемент списка)
found_any=206 set_ok_any=206  (у остальных `font_name` есть, запись прошла)
```

`caller` — **мод**. `vtable=0x3` — у list-item класса слово `[0]` не vtable
(либо type/count). `bag_bytes` совпал с 9 записями.

## 1. Статика A-0025 §5

1. **`0xbce360..0xbce3f0`** (`work/xdis_bce399.txt`): регистрация
   `on_draw_item`:
   ```
   0xbce37e  lea rax, [rsi + 0x108]
   0xbce385  mov dword [rsp+0x30], -1
   0xbce399  lea r8, -> "on_draw_item"
   0xbce3a2  mov [rsp+0x20], rax
   0xbce3a7  call 0x52c40
   ```
   **Член `on_draw_item` = `+0x108`** класса списка.
2. **`0xbcf0c0..0xbcf110`** (`work/xdis_bcf0e0.txt`): чтение/десериализация
   того же свойства: `lea rcx, [rdi + 0x108]`, `call 0x46510`.
3. **`caller 0x90b47`** в моде (`work/dll_90b47.txt`): код рядом с
   `"on_click_args"` — функция мода, которая ставит свойства контролу;
   значит caption нашим контролам ставит **код мода**, и меню строится
   программно (что согласуется с `on_draw_item`-ветвью).

## 2. bag8 (собран, ждёт установки)

Добавлены два распознавателя **до** фильтра (A-0025 §3), поля по твоей
раскладке:

```
+0x1928 Q  control из (а)        +0x1930 D len значения (а)
+0x1934 D  счётчик (б)           +0x1938 Q control из (б)
+0x1940 D  len имени (б)         +0x1944 D счётчик (а)
+0x1948 16B значение (а)         +0x1958 16B имя (б)
```

Дизасм `work/hook_disasm8.txt` подтверждает сравнения
`on_d`/`raw_`/`item`, `item*` по dword, записи полей. Маркер RVA:
**`0xc283c5`**. Поля `+0x1924..0x1927` не тронуты.

## 3. Визуально (после прогона bag7)

Пользователь прислал скриншот: левые подписи по-прежнему отрисованы
«кодпоинтным» шрифтом, правые значения — кириллицей. Запись
`font_name=typewriter` в 206 контролов на вид **не повлияла** → твоя
ветка 3 подтверждается: `font_name` элемента декоративен для этого пути.

## 4. План

1. Пользователь закрывает игру → ставлю bag8.
2. Прогон: `счётчик (а)`, `счётчик (б)`, `control (а)`, `len/16B значения (а)`.
3. Если (а)==0 — эксперимент §6 (записать `on_draw_item =
   diary_draw_list_item` нашему списку).
4. Если (а)>0 — от имени обработчика к его коду (тогда вопрос «где
   реализация» сузится до одного имени).

## 5. Файлы

* `work/xdis_bce399.txt`, `work/xdis_bcf0e0.txt`, `work/dll_90b47.txt`
* `work/hook_disasm8.txt`, `work/bag8_build.txt`
* `build/MetroExodusVR.bag8.dll`
