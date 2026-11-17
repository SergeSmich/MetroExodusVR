import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "a093", r"F:\Projects\MetroExodusVR\tools\apply_ru_093.py"
)
m = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(m)

live = {
    "ТЕЛО": "3f384b35",
    "ИГРА": "333e3127",
    "РУКИ": "314f3433",
    "HUD": "757963",
    "ДВИЖЕНИЕ": "4d24336538393338",
    "ПРИЦЕЛЫ": "36313380384b71",
    "ВИБРАЦИЯ": "2433513127803352",
    "ОРУЖИЕ": "35314f653338",
    "КОМФОРТ": "3435487d35313f",
}
for text, hexdata in live.items():
    enc = m.encode_text(text)
    print(
        f"{text:12s} live {hexdata:20s} ours {enc.hex():20s} {'OK' if enc.hex() == hexdata else 'MISMATCH'}"
    )
print(
    "glyphs",
    len(m.FONT_GLYPHS),
    "max idx",
    max(i for i, cp in enumerate(m.FONT_GLYPHS) if 0x400 <= cp <= 0x4FF),
)
