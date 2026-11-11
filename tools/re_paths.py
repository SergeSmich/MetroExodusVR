"""Paths for the reverse-engineering tools.

The analysis scripts were first written on a Windows checkout with absolute
paths into ``F:\\Projects\\MetroExodusVR`` and the Steam library.  This module
keeps them usable from any checkout: the repository is located from
``__file__`` and each path can be overridden with an environment variable.

    METROEXODUSVR_DLL   MetroExodusVR.dll (default: work/0.9.0/versions/0.9.0/)
    METROEXODUS_EXE     MetroExodus.exe (default: Steam library path)
    METROEXODUS_GAME    game directory (default: the Steam library path)
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"

DEFAULT_GAME = Path(r"F:\SteamLibrary\steamapps\common\Metro Exodus")

GAME = Path(os.environ.get("METROEXODUS_GAME", DEFAULT_GAME))
EXE = Path(
    os.environ.get("METROEXODUS_EXE", GAME / "MetroExodus.exe")
)
DLL = Path(
    os.environ.get(
        "METROEXODUSVR_DLL",
        WORK / "0.9.0" / "versions" / "0.9.0" / "MetroExodusVR.dll",
    )
)

XREFS = WORK / "xrefs.json"
FUNCS = WORK / "funcs.json"
PLAN = WORK / "plan.json"
PE_ANALYSIS = WORK / "pe_analysis.json"


def describe():
    """Print the paths in use, so a failing run is self-explaining."""
    print(f"repository : {ROOT}")
    print(f"DLL        : {DLL} ({'found' if DLL.is_file() else 'MISSING'})")
    print(f"exe        : {EXE} ({'found' if EXE.is_file() else 'MISSING'})")


def require(*paths):
    """Exit with a readable message when a needed file is missing."""
    missing = [Path(x) for x in paths if not Path(x).is_file()]
    if missing:
        describe()
        for m in missing:
            print(f"MISSING    : {m}")
        print(
            "\nSet METROEXODUSVR_DLL / METROEXODUS_EXE (or METROEXODUS_GAME) "
            "to point the tools at the files."
        )
        raise SystemExit(2)
