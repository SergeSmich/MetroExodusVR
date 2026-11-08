#!/usr/bin/env python3
"""Install the Russian patch into a Metro Exodus VR installation.

The mod ships ``versions/<X.Y.Z>/MetroExodusVR.dll`` and updates itself from
GitHub.  This script patches every version DLL it finds (keeping a pristine
``*.orig`` backup) and pins the current version through ``updater.json`` so an
automatic update cannot silently replace the translated DLL.

Usage:
    python tools/install_ru.py --game "F:\\SteamLibrary\\steamapps\\common\\Metro Exodus"
    python tools/install_ru.py --mod-dir "F:\\...\\Metro Exodus" --dry-run

After a deliberate mod update, run the script again: it will patch the newly
downloaded version and re-pin it.
"""

import argparse
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLY = ROOT / "tools" / "apply_ru.py"
DLL_NAME = "MetroExodusVR.dll"
UPDATER = "updater.json"


def log(msg):
    print(f"[install] {msg}")


def is_patched(path):
    """True when the PE already carries the .ru section added by apply_ru."""
    try:
        d = path.read_bytes()
        e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
        nsec = struct.unpack_from("<H", d, e_lfanew + 6)[0]
        st = e_lfanew + 24 + struct.unpack_from("<H", d, e_lfanew + 20)[0]
        for i in range(nsec):
            name = d[st + 40 * i : st + 40 * i + 8].rstrip(b"\0")
            if name == b".ru":
                return True
    except Exception:
        pass
    return False


def version_key(name):
    parts = re.findall(r"\d+", name)
    return tuple(int(p) for p in parts) or (0,)


def find_dlls(mod_dir):
    found = []
    versions = mod_dir / "versions"
    if versions.is_dir():
        for vdir in sorted(versions.iterdir(), key=lambda p: version_key(p.name)):
            dll = vdir / DLL_NAME
            if dll.is_file():
                found.append((vdir.name, dll))
    root_dll = mod_dir / DLL_NAME
    if root_dll.is_file():
        found.append(("", root_dll))
    return found


def patch_one(label, dll, force):
    """Patch dll in place.  Returns True if the file now carries the patch."""
    if is_patched(dll) and not force:
        log(f"{label}: already patched, skipping")
        return True

    backup = dll.with_name(dll.name + ".orig")
    if is_patched(dll) and not backup.is_file():
        log(
            f"{label}: already patched but no pristine {backup.name}; "
            "reinstall this version from the release archive to repatch"
        )
        return False
    if backup.is_file():
        src = backup
    else:
        log(f"{label}: saving pristine copy to {backup.name}")
        backup.write_bytes(dll.read_bytes())
        src = backup

    tmp = dll.with_name(dll.name + ".ru-tmp")
    cmd = [
        sys.executable,
        str(APPLY),
        "--src",
        str(src),
        "--out",
        str(tmp),
        "--verify",
    ]
    log(f"{label}: patching {src.name} -> {dll.name}")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        tmp.unlink(missing_ok=True)
        log(f"{label}: PATCH FAILED")
        for line in (res.stdout or "").splitlines()[-20:]:
            print("   ", line)
        for line in (res.stderr or "").splitlines()[-10:]:
            print("   ", line)
        return False

    tmp.replace(dll)
    log(f"{label}: ok ({dll.stat().st_size} bytes)")
    return True


def read_updater(path):
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:
        log("existing updater.json is not valid JSON; leaving it alone")
        return None


def write_updater(mod_dir, version):
    path = mod_dir / UPDATER
    doc = read_updater(path)
    if doc is None:
        return False
    changed = {}
    if doc.get("mode") != "never":
        doc["mode"] = "never"
        changed["mode"] = "never"
    if version and doc.get("pinned_version") != version:
        doc["pinned_version"] = version
        changed["pinned_version"] = version
    if not changed:
        log(f"{UPDATER}: already pinned to {version}")
        return True
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    log(f"{UPDATER}: set {', '.join(f'{k}={v}' for k, v in changed.items())}")
    return True


def detect_game_dir():
    """Look for Metro Exodus through Steam's library folders."""
    candidates = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf"),
        Path(r"C:\Program Files\Steam\steamapps\libraryfolders.vdf"),
    ]
    for vdf in candidates:
        if not vdf.is_file():
            continue
        text = vdf.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            lib = Path(m.group(1).replace("\\\\", "\\"))
            game = lib / "steamapps" / "common" / "Metro Exodus"
            if (game / "MetroExodus.exe").is_file():
                return game
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", type=Path, help="Metro Exodus installation folder")
    ap.add_argument(
        "--mod-dir",
        type=Path,
        help="folder with MetroExodusVR.exe/versions (defaults to --game)",
    )
    ap.add_argument("--force", action="store_true", help="repatch even if patched")
    ap.add_argument("--no-pin", action="store_true", help="leave updater.json alone")
    ap.add_argument("--dry-run", action="store_true", help="only report the plan")
    args = ap.parse_args()

    mod_dir = args.mod_dir or args.game or detect_game_dir()
    if mod_dir is None:
        print("ERROR: cannot find the game; pass --game or --mod-dir")
        return 2
    mod_dir = mod_dir.resolve()
    if not mod_dir.is_dir():
        print(f"ERROR: {mod_dir} does not exist")
        return 2
    log(f"mod folder: {mod_dir}")

    dlls = find_dlls(mod_dir)
    if not dlls:
        print(
            "ERROR: no MetroExodusVR.dll found. Extract the mod release into the "
            "game folder first (MetroExodusVR.exe + versions/)."
        )
        return 2

    log(f"found {len(dlls)} version(s): {', '.join(v or 'root' for v, _ in dlls)}")
    if args.dry_run:
        for label, dll in dlls:
            state = "patched" if is_patched(dll) else "original"
            print(f"    {label or 'root'}: {state}")
        if not args.no_pin:
            print(f"    would set {UPDATER}: mode=never, pinned_version=<newest>")
        return 0

    ok_versions = []
    failed = []
    for label, dll in dlls:
        if patch_one(label or "root", dll, args.force):
            ok_versions.append(label or "root")
        else:
            failed.append(label or "root")

    if failed:
        log(f"failed: {', '.join(failed)}")
    if ok_versions and not args.no_pin:
        newest = max(ok_versions, key=version_key)
        if newest != "root":
            write_updater(mod_dir, newest)

    log("done. Start MetroExodusVR.exe; the mod will not auto-update while pinned.")
    log("To update later: delete updater.json (or run with --updater-settings),")
    log("let the mod download the new version, then run this script again.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
