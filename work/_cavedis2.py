import sys

sys.path.insert(0, r"F:\Projects\MetroExodusVR\work")
from pefuncs import PE

D = PE(r"F:\Projects\MetroExodusVR\build\MetroExodusVR-0.9.3.dll")
base = 0xC56030
off = D.rva2off(base)
for i in D.md.disasm(D.d[off : off + 300], base):
    print(
        "  +%#04x  %#08x  %-18s %-8s %s"
        % (i.address - base, i.address, i.bytes.hex(), i.mnemonic, i.op_str)
    )
