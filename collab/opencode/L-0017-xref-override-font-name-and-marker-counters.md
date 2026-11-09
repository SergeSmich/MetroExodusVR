---
id: L-0017
from: opencode
to: arena
kind: result
status: done
needs: A-0017
branch: local/opencode
build: 0.9.0 + bag6 (пересобран, не установлен — игра запущена)
---

# L-0017: xref `0x14af808` в exe; маркер получил счётчик и байты подписи; делегирую статику

## 0. Коротко

1. **xref найден** (§1): `0x14af808` — строка `.rdata` exe
   `override_font_name`; три `lea`-сайта: `0xc46a4d` (регистратор схемы,
   рядом `local_text`, член объекта `[rbx+0x60]`, вызов `0x52c40`) и
   `0xc4708e`/`0xc470b1` (лукап свойства, вызов `0x4ed40`, подсказки
   `choose`/`_default`, гейт `[obj+0xac]&1`).
2. **Твой §6.1 выполнен**: маркер bag6 теперь несёт **счётчик
   caption-совпадений** (`+0x04` dword), **длину** (`+0x2c`) и **первые
   16 байт** последней подписи (`+0x30..+0x40`). Результат сеттера
   переехал на `+0x24`. Маркер RVA: `0xc27f18`.
3. **Твоё §6.2 закрывается первым же прогоном** — сырые записи в маркере
   дают kind/значения `override_font_name`, `text_render_mode`,
   `local_text` (парсер `work/dump_bag.py` обновлён).
4. **По просьбе пользователя делегирую тебе всю дальнейшую статику**
   (§4): фильтр, разбор `0x4ed40`, таблицу 13 ASCII. Я оставляю только
   локальное: установка DLL, VR-прогон, дамп маркера.

## 1. xref `override_font_name` (exe, `.rdata`)

`work/tmp_xrel.py 0x14af808` → ровно три ссылки:

```
0xc46a4d  4c8d05b48d8600   lea r8, [rip + 0x868db4]   -> 0x14af808
0xc4708e  4c8d0573878600   lea r8, [rip + 0x868773]   -> 0x14af808
0xc470b1  4c8d0550878600   lea r8, [rip + 0x868750]   -> 0x14af808
```

### 1.1 `0xc46a4d` — регистратор свойств (схема класса)

```
0xc46a1f  lea r8, [rip+0x84ba5a]      ; -> 0x1492480 "local_text"
0xc46a28  mov [rsp+0x20], rax          ; rax = lea [rbx+??]   (член объекта)
0xc46a2d  call 0x52c40                 ; register(obj, 0, name, hint, member, ...)
0xc46a32  mov rcx, [rdi]
0xc46a35  lea rax, [rbx+0x60]
0xc46a39  mov dword [rsp+0x30], -1
0xc46a41  lea r9, [rip+0x868f40]       ; -> 0x14af588 "grenade_flamethrower_slo..."
0xc46a48  mov [rsp+0x28], rsi
0xc46a4d  lea r8, [rip+0x868db4]       ; -> "override_font_name"
0xc46a54  xor edx, edx
0xc46a56  mov [rsp+0x20], rax          ; member = [rbx+0x60]
0xc46a5b  call 0x52c40
```

Подтверждает A-0016 §2/§3: `local_text` и `override_font_name` — соседи в
одной схеме, член **`+0x60`**, дефолт `-1` (пустая строка). `0x14af588`
(«grenade_flamethrower_slo…») — значение по умолчанию соседнего свойства,
не наша строка.

### 1.2 `0xc4708e` / `0xc470b1` — лукап свойства в объекте

```
0xc47077  mov rsi, [rbx]
0xc4707a  movzx eax, byte [rsi+0xac]
0xc47081  test al, 1
0xc47083  je 0xc470c0
0xc47085  lea r9,  [rip+0x835750]      ; -> "choose"
0xc4708e  lea r8,  [rip+0x868773]      ; -> "override_font_name"
0xc47095  mov rcx, rsi
0xc47098  call 0x4ed40                 ; lookup(obj, 0, name, hint)
...
0xc470a8  lea r9,  [rip+0x8352c9]      ; -> "_default"
0xc470b1  lea r8,  ...                 ; -> "override_font_name"
0xc470bb  call 0x4ed40
```

`0x4ed40` принимает `(obj, 0, name, hint, r9…)`, проверяет гейт
`[obj+0xac] & 1` и работает с таблицей свойств. Это **не** итоговый
resolve «имя → пакетная ссылка» (тот идёт через `0x86b8d0`/interner),
а property-менеджер схемы. Дальше веду не я — см. §4.

## 2. Маркер bag6 (новая раскладка)

```
+0x00 dword  calls (все вызовы сеттера)
+0x04 dword  caption matches
+0x08 Q      последний контрол
+0x10 Q      bag begin     +0x18 Q  bag end
+0x20 dword  записей скопировано (<=40)
+0x24 byte   результат вложенного set
+0x28 Q      caller retaddr
+0x2c dword  длина последней подписи
+0x30..0x40   16 байт последней подписи (sample)
+0x40 ..    40 x 0x98 сырых записей
```

Проверено дизасмом собранного DLL (`work/hook_disasm.py`): счётчик, clamp
0x10, цикл `movzx r8d,[r9+r11] / mov [rax+r11+0x30]`, результат на
`+0x24`. Сборка: `verify ok: 21 stubs, 560 byte patches`.

**Маркер RVA: `0xc27f18`** (старый `0xc27ed8` устарел — прошу обновить у
себя).

## 3. Что покажет прогон (я запущу сам)

1. `calls` vs `caption`: сколько подписей вообще ловит хук.
2. `sample`: первые 16 байт — по ним офлайн видно, кириллица это или
   ASCII (`FSR`/`DLSS`).
3. `set_ok` и наличие `override_font_name` (kind=1) в сырых записях.
4. `text_render_mode`/`local_text` — по сырым записям.

## 4. Делегирую тебе (статический объём, у меня лимит)

По просьбе пользователя беру на себя только DLL+игру. Прошу тебя:

1. **Фильтр подписи** (A-0017 §1–2): таблица из 193 наших строк
   (длина+16-бит хеш) против 13 ASCII `skip`. Формат — JSON
   (`ru/caption_filter.json`?) + правило сравнения; я встрою генерацию
   байтов в `apply_ru.py` по твоей таблице. Нужен и список 13 точных
   строк с байтами.
2. **Разбор `0x4ed40` и `0x52c40`** по вызовам выше: где свойство
   реально превращается в шрифт (и не является ли `+0x60` не строкой,
   а чем-то ещё в объекте контрола). Мои дизасмы: `work/xdis_c46a4d.txt`,
   `work/xdis_c4708e.txt`, `work/xdis_4ed40.txt` — могу закоммитить в
   твой доступ, скажи.
3. **Решение по `text_render_mode`** из схемы: если у нашего контрола он
   не 0 — это может быть ответ раньше шрифта.

## 5. Файлы

* `build/MetroExodusVR.bag6.dll` — пересобран (verify ok)
* `tools/apply_ru.py` — counter+sample в хуке
* `work/dump_bag.py`, `work/probe_control_fields.py`, `work/probe_glyph.py` —
  новый заголовок маркера
* `work/xref_ofn.txt`, `work/xdis_c46a4d.txt`, `work/xdis_c4708e.txt`,
  `work/xdis_4ed40.txt` — exe-пруфы §1
* `work/hook_disasm.txt` — дизасм собранного хука

## 6. Ограничения

* Правки только `MetroExodusVR.dll`; exe только читаем.
* bag6 не установлен: игра запущена (DLL залочен), прогон — при следующем
  запуске.
