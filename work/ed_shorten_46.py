# -*- coding: utf-8 -*-
"""Sokrashchenie podskazki 46 do limita (posle A2 ona stala 153 simvola)."""

import json

P = "kit093/ru/ui2-0.9.3.json"
OLD = "Заделайте маску: схватите скотч <grip_nondominant> с противоположного бедра (или <grip_dominant> из рюкзака) и поднесите к стеклу[, или <press:facepalm>]"
NEW = "Заделайте маску: скотч <grip_nondominant> с противоположного бедра (или <grip_dominant> из рюкзака) поднесите к стеклу[, или <press:facepalm>]"

raw = open(P, encoding="utf-8", newline="").read()
d = json.loads(raw)
if json.dumps(d, ensure_ascii=False, indent=2).replace("\n", "\r\n") != raw:
    raise SystemExit("FAIL: format")
rec = [x for x in d["hints"] if x["index"] == 46][0]
n = rec["ru"].count(OLD)
if n != 1:
    raise SystemExit("FAIL: najdeno %d" % n)
rec["ru"] = rec["ru"].replace(OLD, NEW)
open(P, "w", encoding="utf-8", newline="").write(
    json.dumps(d, ensure_ascii=False, indent=2).replace("\n", "\r\n")
)
print("ok: %d -> %d simvolov" % (len(OLD), len(NEW)))
