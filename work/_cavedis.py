import sys

sys.path.insert(0, r"F:\Projects\MetroExodusVR\work")
from pefuncs import PE

D = PE(r"F:\Projects\MetroExodusVR\build\MetroExodusVR-0.9.3.dll")
print("=== DllMain entry")
off = D.rva2off(0x4641A0)
for i in D.md.disasm(D.d[off : off + 0x10], 0x4641A0):
    print("  %#08x  %-16s %-8s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
print("=== cave")
off = D.rva2off(0xC56030)
for i in D.md.disasm(D.d[off : off + 200], 0xC56030):
    print("  %#08x  %-16s %-8s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
