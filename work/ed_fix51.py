# -*- coding: utf-8 -*-
"""Soglasovanie podskazki 51 s novymi znachenijami LEVEL/FIXED TO VIEW (proverka 4)."""

import json

P = "kit093/ru/ui2-0.9.3.json"
OLD = "по горизонту или фиксировано в вашем обзоре."
NEW = "по горизонту или к обзору."

raw = open(P, encoding="utf-8", newline="").read()
d = json.loads(raw)
if json.dumps(d, ensure_ascii=False, indent=2).replace("\n", "\r\n") != raw:
    raise SystemExit("FAIL: format")
rec = [x for x in d["options"] if x["index"] == 51][0]
if rec["ru"].count(OLD) != 1:
    raise SystemExit("FAIL: najdeno %d" % rec["ru"].count(OLD))
rec["ru"] = rec["ru"].replace(OLD, NEW)
open(P, "w", encoding="utf-8", newline="").write(
    json.dumps(d, ensure_ascii=False, indent=2).replace("\n", "\r\n")
)
print("ok: %s" % rec["ru"])
