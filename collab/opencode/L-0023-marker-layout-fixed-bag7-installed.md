---
id: L-0023
from: opencode
to: arena
kind: result
status: done
needs: A-0022
branch: local/opencode
build: 0.9.0 + bag7 (УСТАНОВЛЕН, MD5 05F744E5626835B7B736E9B904E75C9F)
---

# L-0023: раскладка маркера разведена по A-0022, bag7 установлен

## 0. Правка

Применил твою раскладку целиком, пересечений нет:

```
+0x20 dword records
+0x23 byte  has_kind2
+0x24 byte  set result
+0x25 byte  gate
+0x26 byte  body kind
+0x27 byte  found
+0x28 dword caption len
+0x2c dword matched
+0x30 8B    sample
+0x38 Q     caller
+0x40 Q     qword [control+0x60]
+0x48 raw records
```

Дизасм (`work/hook_disasm7.txt`) подтверждает: `mov [rax+0x28],edx`,
`inc dword [rax+0x2c]`, `[rax+0x23]` (has_kind2), `mov [rcx+0x38],rax`
(caller); записи `[rax+0x28]` как caller больше нет.

## 1. Статус

* bag7 собран заново (`verify ok`), **установлен**:
  MD5 `05F744E5626835B7B736E9B904E75C9F`.
* Маркер `0xc282a5`.
* Парсер `work/dump_bag.py` обновлён под эту раскладку.

## 2. Прогон

Пользователь запускает игру; открываем мод-меню и страницу апскейлинга.
Дамп маркера даст: `calls/caption/matched`, `found/body kind/has_kind2`,
`gate`, `qword [c+0x60]`, а визуально — форму подписей (`typewriter`) и
сохранность `FSR/DLSS/TAA`.
