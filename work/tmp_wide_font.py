import re

d = open("work/0.9.1/MetroExodusVR.dll.orig", "rb").read()
for label, pat in [
    ("arial u16", "arial".encode("utf-16-le")),
    ("menu u16", "menu".encode("utf-16-le")),
    ("regular u16", "regular".encode("utf-16-le")),
    ("arial ascii", b"arial"),
    ("font_name", b"font_name"),
    ("text_font", b"text_font"),
    ("alt_font_name", b"alt_font_name"),
    ("override_font_name", b"override_font_name"),
]:
    print(label, len(re.findall(re.escape(pat), d)))
