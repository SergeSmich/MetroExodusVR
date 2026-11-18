#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mod_switch.py - переключение билдов мода Metro Exodus VR 0.9.3.

Система держит игровую папку в одном из трёх состояний:
  vanilla  - мод не установлен (Steam запускает чистую игру)
  orig     - чистая поставка мода 0.9.3 + оригинальная DLL
  ours     - чистая поставка мода 0.9.3 + наша собранная DLL

Все действия обратимы: удаляемые из игры файлы не стираются, а переносятся
в work/modkit/archive/<время>-<что>/ (rename внутри тома - мгновенно).

Команды:
  status                 что сейчас установлено (режим, DLL, sha, логи)
  apply <профиль>        снести текущий мод и поставить профиль (orig|ours)
  clean                  убрать мод из игры (в архив) -> vanilla
  verify                 сверить установленное с installed.json
  collect <id> [--shots] собрать логи последнего прогона в runs/<id>/
  purge [--yes]          показать/удалить архивы
  hashes                 sha256 всех известных сборок

Запуск (Windows, UTF-8):
  $env:PYTHONIOENCODING='utf-8'; python -u -X utf8 work\\modkit\\mod_switch.py status
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent
CFG_PATH = KIT / "profiles.json"
ARCHIVE = KIT / "archive"
RUNS = KIT / "runs"
STATE_PATH = KIT / "installed.json"

# --- файлы/каталоги в корне игры, которые принадлежат моду ----------------
MOD_TOP = ["MetroExodusVR.exe", "updater.json", "versions", "logs"]
MOD_GLOBS = ["MetroExodusVR.exe.bak-*", "updater.json.bak-*"]

SAVED_GAMES = Path(os.environ.get("USERPROFILE", "")) / "Saved Games" / "Metro Exodus"
SHOTS = Path(r"F:\Projects\MetroExodusVR\work\shots")


def die(msg, code=1):
    print("ОШИБКА: " + msg)
    sys.exit(code)


def load_cfg():
    if not CFG_PATH.exists():
        die("нет %s" % CFG_PATH)
    with open(CFG_PATH, encoding="utf-8") as f:
        return json.load(f)


def cfg():
    return load_cfg()


def game_root(c):
    g = Path(c["game_root"])
    if not g.is_dir():
        die("игровая папка не найдена: %s" % g)
    if not (g / "MetroExodus.exe").exists():
        die("в %s нет MetroExodus.exe - это не папка игры" % g)
    return g


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def fmt(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def dir_size(p):
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def installed_dll(g, ver):
    return g / "versions" / ver / "MetroExodusVR.dll"


def game_running():
    """Имена процессов, из-за которых нельзя трогать файлы мода."""
    names = ("MetroExodus.exe", "MetroExodusVR.exe", "MetroExodusVR-launcher.exe")
    alive = []
    try:
        import subprocess

        out = subprocess.run(
            ["tasklist", "/NH"],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="replace",
        ).stdout
        for n in names:
            if n.lower() in out.lower():
                alive.append(n)
    except Exception:
        pass
    return alive


def require_game_closed():
    alive = game_running()
    if alive:
        die("игра запущена (%s) - закрой её и повтори" % ", ".join(alive))


def footprint(g):
    """Что из мода реально лежит в игре (список путей)."""
    items = []
    for name in MOD_TOP:
        p = g / name
        if p.exists():
            items.append(p)
    for pat in MOD_GLOBS:
        items.extend(sorted(g.glob(pat)))
    return items


def label_of(c, digest):
    if not digest:
        return "нет"
    labels = []
    for name, prof in c["profiles"].items():
        dll = Path(prof["dll"])
        if dll.exists():
            try:
                if sha256(dll) == digest:
                    labels.append(name)
            except OSError:
                pass
    return "профиль " + "/".join(labels) if labels else "НЕИЗВЕСТНАЯ сборка"


def updater_mode(g):
    p = g / "updater.json"
    if not p.exists():
        return "нет updater.json"
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return "mode=%s pinned=%s" % (d.get("mode"), d.get("pinned_version"))
    except Exception as e:
        return "updater.json битый: %s" % e


def newest_logs(g, ver, n=3):
    d = g / "versions" / ver / "logs"
    if not d.is_dir():
        return []
    files = [p for p in d.iterdir() if p.is_file() and p.suffix == ".log"]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:n]


# ------------------------------------------------------------------ status
def cmd_status(c, args):
    g = game_root(c)
    ver = c["version"]
    print("игра:   %s" % g)
    print("версия: %s" % ver)
    items = footprint(g)
    print("режим:  %s" % ("МОД УСТАНОВЛЕН" if items else "VANILLA (мода нет)"))
    if items:
        print("мод-файлы в корне: %s" % ", ".join(p.name for p in items))
    dll = installed_dll(g, ver)
    if dll.exists():
        h = sha256(dll)
        print(
            "DLL:    %s  sha=%s  (%s)" % (dll, h[:16] + "..." + h[-4:], label_of(c, h))
        )
    else:
        print("DLL:    нет")
    print("updater: %s" % updater_mode(g))
    if STATE_PATH.exists():
        with open(STATE_PATH, encoding="utf-8") as f:
            st = json.load(f)
        print(
            "последний apply: %s (%s), %s, dll sha %s..."
            % (
                st.get("profile"),
                st.get("title"),
                st.get("ts"),
                str(st.get("dll_sha"))[:16],
            )
        )
        if dll.exists() and st.get("dll_sha") and sha256(dll) != st["dll_sha"]:
            print(
                "  !! DLL в игре отличается от установленной: %s"
                % label_of(c, sha256(dll))
            )
    logs = newest_logs(g, ver)
    if logs:
        print("свежие логи:")
        for p in logs:
            print(
                "  %s  %s  %s"
                % (
                    time.strftime("%m-%d %H:%M", time.localtime(p.stat().st_mtime)),
                    fmt(p.stat().st_size),
                    p.name,
                )
            )
    else:
        print("свежих логов мода нет")


# ------------------------------------------------------------------- clean
def archive_move(g, items, tag):
    ts = time.strftime("%Y-%m-%d_%H%M%S")
    dest = ARCHIVE / ("%s-%s" % (ts, tag))
    dest.mkdir(parents=True, exist_ok=True)
    manifest = []
    for src in items:
        rel = src.relative_to(g)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(target))
        rec = {
            "path": str(rel),
            "bytes": dir_size(target) if target.is_dir() else target.stat().st_size,
        }
        if not target.is_dir() and rec["bytes"] < (32 << 20):
            rec["sha256"] = sha256(target)
        manifest.append(rec)
        print("  архив: %-40s %10s" % (rel, fmt(rec["bytes"])))
    (dest / "manifest.json").write_text(
        json.dumps(
            {"ts": ts, "tag": tag, "game_root": str(g), "items": manifest},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return dest


def cmd_clean(c, args):
    g = game_root(c)
    items = footprint(g)
    if not items:
        print("игра уже без мода (vanilla).")
        return
    require_game_closed()
    print("будет убрано из игры в архив:")
    for p in items:
        size = dir_size(p) if p.is_dir() else p.stat().st_size
        print("  %-40s %10s" % (p.relative_to(g), fmt(size)))
    if not args.yes:
        print("\nэто предпросмотр. Повтори с --yes, чтобы убрать мод.")
        return
    dest = archive_move(g, items, "clean")
    left = footprint(g)
    if left:
        die("после очистки остались мод-файлы: %s" % ", ".join(p.name for p in left))
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    print("готово: %s\nигра в состоянии vanilla (архив: %s)" % (g, dest))


# ------------------------------------------------------------------- apply
def check_profile(c, name):
    prof = c["profiles"].get(name)
    if not prof:
        die("нет профиля %r; есть: %s" % (name, ", ".join(c["profiles"])))
    tree = Path(prof["tree"])
    ver = c["version"]
    for rel in (
        "MetroExodusVR.exe",
        "versions/%s/MetroExodusVR-stub.exe" % ver,
        "versions/%s/MetroExodusVR-launcher.exe" % ver,
        "versions/%s/version.json" % ver,
    ):
        if not (tree / rel).exists():
            die("в поставке %s нет %s" % (tree, rel))
    dll = Path(prof["dll"])
    if not dll.exists():
        die("нет DLL профиля: %s" % dll)
    return prof, tree, dll


def cmd_apply(c, args):
    prof, tree, dll = check_profile(c, args.profile)
    g = game_root(c)
    ver = c["version"]
    src_ver = tree / "versions" / ver
    dll_sha = sha256(dll)
    print("профиль: %s" % prof["title"])
    print("поставка: %s" % tree)
    print("DLL: %s  sha=%s" % (dll, dll_sha[:16] + "..." + dll_sha[-4:]))

    old = footprint(g)
    if old:
        require_game_closed()
        if any(p.is_dir() and p.name == "versions" for p in old):
            cur = installed_dll(g, ver)
            if cur.exists():
                print(
                    "текущая DLL: %s (%s)"
                    % (sha256(cur)[:16], label_of(c, sha256(cur)))
                )
        print("сношу текущий мод в архив:")
        archive_move(g, old, "before-%s" % args.profile)

    print("ставлю:")
    print("  стаб + versions/%s (%s) из %s" % (ver, fmt(dir_size(src_ver)), tree))
    print("  DLL профиля -> versions/%s/MetroExodusVR.dll" % ver)
    dst_ver = g / "versions" / ver
    (g / "versions").mkdir(exist_ok=True)
    ignore = shutil.ignore_patterns("logs", "cache")
    shutil.copytree(str(src_ver), str(dst_ver), ignore=ignore, dirs_exist_ok=True)
    (dst_ver / "logs").mkdir(exist_ok=True)
    shutil.copy2(str(tree / "MetroExodusVR.exe"), str(g / "MetroExodusVR.exe"))

    (g / "updater.json").write_text(
        json.dumps(
            {
                "mode": "never",
                "pinned_version": ver,
                "last_check": {
                    "version": ver,
                    "page_url": "https://github.com/RippeR37/MetroExodusVR/releases/tag/v"
                    + ver,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    shutil.copy2(str(dll), str(dst_ver / "MetroExodusVR.dll"))

    # --- контроль -------------------------------------------------------
    got_dll = sha256(dst_ver / "MetroExodusVR.dll")
    got_stub = sha256(g / "MetroExodusVR.exe")
    if got_dll != dll_sha:
        die("DLL после копирования не совпала по sha")
    if got_stub != sha256(tree / "MetroExodusVR.exe"):
        die("стаб после копирования не совпал по sha")
    verj = json.loads((dst_ver / "version.json").read_text(encoding="utf-8-sig"))
    if str(verj.get("version")) != ver:
        die("version.json поставки = %r, ожидалось %s" % (verj.get("version"), ver))
    if updater_mode(g) != "mode=never pinned=%s" % ver:
        die("updater.json записан неверно: %s" % updater_mode(g))

    st = {
        "profile": args.profile,
        "title": prof["title"],
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dll_sha": got_dll,
        "stub_sha": got_stub,
        "tree": str(tree),
        "version": ver,
    }
    STATE_PATH.write_text(
        json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("готово. установлено: %s" % prof["title"])
    print("запуск: %s" % (g / "MetroExodusVR.exe"))
    print("после прогона: mod_switch.py collect <id>  (до следующего apply!)")
    print("затем проверь: mod_switch.py verify")


# ------------------------------------------------------------------ verify
def cmd_verify(c, args):
    g = game_root(c)
    ver = c["version"]
    ok = True
    if not STATE_PATH.exists():
        print("installed.json нет: мод не ставился через mod_switch (или уже clean).")
        return
    with open(STATE_PATH, encoding="utf-8") as f:
        st = json.load(f)
    dll = installed_dll(g, ver)
    checks = [
        ("DLL на месте", dll.exists()),
        ("DLL sha = установленной", dll.exists() and sha256(dll) == st.get("dll_sha")),
        ("стаб на месте", (g / "MetroExodusVR.exe").exists()),
        (
            "стаб sha = установленному",
            (g / "MetroExodusVR.exe").exists()
            and sha256(g / "MetroExodusVR.exe") == st.get("stub_sha"),
        ),
        ("updater mode=never", updater_mode(g) == "mode=never pinned=%s" % ver),
        ("версия %s на месте" % ver, (g / "versions" / ver / "version.json").exists()),
    ]
    for name, good in checks:
        print(("  ok   " if good else "  FAIL ") + name)
        ok = ok and good
    if dll.exists():
        print("DLL: %s (%s)" % (sha256(dll)[:16], label_of(c, sha256(dll))))
    if not ok:
        print(
            "\nСОСТОЯНИЕ НЕ СОВПАДАЕТ с установленным профилем (стаб мог обновиться?)."
        )
        sys.exit(2)
    print("\nвсё на месте: %s" % st.get("profile"))


# ----------------------------------------------------------------- collect
def cmd_collect(c, args):
    g = game_root(c)
    ver = c["version"]
    logs = newest_logs(g, ver, 6)
    if not logs:
        die(
            "нет логов мода в %s - игра не запускалась с модом?"
            % (g / "versions" / ver / "logs")
        )
    hook = [p for p in logs if "_hook_" in p.name]
    if not hook:
        die("нет hook-лога в %s" % (g / "versions" / ver / "logs"))
    newest = hook[0]
    run_dir = RUNS / args.id
    run_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for p in logs:
        if p.stat().st_mtime < newest.stat().st_mtime - 3600:
            continue
        shutil.copy2(str(p), str(run_dir / p.name))
        copied.append(
            {
                "file": p.name,
                "bytes": p.stat().st_size,
                "mtime": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime)
                ),
            }
        )
    cfgs = []
    if SAVED_GAMES.is_dir():
        for cfgp in SAVED_GAMES.glob("*/user_vr.cfg"):
            if time.time() - cfgp.stat().st_mtime < 86400:
                shutil.copy2(str(cfgp), str(run_dir / "user_vr.cfg"))
                cfgs.append(cfgp.name)
                break
    shots = []
    if args.shots and SHOTS.is_dir():
        for p in sorted(SHOTS.glob("*.png")):
            if p.stat().st_mtime >= newest.stat().st_mtime - 120:
                shutil.copy2(str(p), str(run_dir / p.name))
                shots.append(p.name)
    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    run = {
        "id": args.id,
        "collected": time.strftime("%Y-%m-%d %H:%M:%S"),
        "profile": state.get("profile"),
        "dll_sha": state.get("dll_sha"),
        "progress": args.note or "",
        "logs": copied,
        "user_vr_cfg": cfgs,
        "shots": shots,
    }
    (run_dir / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("собрано в %s:" % run_dir)
    for r in copied:
        print("  %-50s %s" % (r["file"], fmt(r["bytes"])))
    for s in shots:
        print("  скрин: %s" % s)
    if cfgs:
        print("  user_vr.cfg скопирован")


# ------------------------------------------------------------------- purge
def cmd_purge(c, args):
    if not ARCHIVE.is_dir():
        print("архивов нет.")
        return
    dirs = sorted([p for p in ARCHIVE.iterdir() if p.is_dir()])
    if not dirs:
        print("архивов нет.")
        return
    total = 0
    for d in dirs:
        s = dir_size(d)
        total += s
        print("  %-45s %10s" % (d.name, fmt(s)))
    print("итого: %s" % fmt(total))
    if not args.yes:
        print(
            "\nэто предпросмотр. Повтори с --yes, чтобы удалить всё (или --keep N, чтобы оставить N свежих)."
        )
        return
    keep = max(0, args.keep)
    doomed = dirs[:-keep] if keep else dirs
    for d in doomed:
        shutil.rmtree(str(d), ignore_errors=True)
    print("удалено архивов: %d, оставлено: %d" % (len(doomed), len(dirs) - len(doomed)))


# ------------------------------------------------------------------ hashes
def cmd_hashes(c, args):
    g = game_root(c)
    ver = c["version"]
    print("%-10s %-64s %s" % ("что", "sha256", "файл"))
    seen = set()
    for name, prof in c["profiles"].items():
        dll = Path(prof["dll"])
        if dll.exists():
            h = sha256(dll)
            if h in seen:
                continue
            seen.add(h)
            print("%-10s %s  %s" % (name, h[:16] + "..." + h[-4:], dll))
    cur = installed_dll(g, ver)
    if cur.exists():
        h = sha256(cur)
        tag = "установлена" if h not in seen else "= профиль"
        print(
            "%-10s %s  %s  (%s)" % (tag, h[:16] + "..." + h[-4:], cur, label_of(c, h))
        )


def main():
    ap = argparse.ArgumentParser(description="переключение билдов мода Metro Exodus VR")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="что сейчас установлено")

    p = sub.add_parser("apply", help="поставить профиль")
    p.add_argument("profile")

    p = sub.add_parser("clean", help="убрать мод из игры в архив")
    p.add_argument("--yes", action="store_true")

    sub.add_parser("verify", help="сверить установленное")

    p = sub.add_parser("collect", help="собрать логи прогона")
    p.add_argument("id")
    p.add_argument("--shots", action="store_true", help="копировать свежие скрины")
    p.add_argument("--note", default="", help="что проверяли/что видно")

    p = sub.add_parser("purge", help="удалить архивы")
    p.add_argument("--yes", action="store_true")
    p.add_argument(
        "--keep", type=int, default=0, help="оставить N самых свежих архивов"
    )

    sub.add_parser("hashes", help="sha256 сборок")

    args = ap.parse_args()
    c = cfg()
    fn = {
        "status": cmd_status,
        "apply": cmd_apply,
        "clean": cmd_clean,
        "verify": cmd_verify,
        "collect": cmd_collect,
        "purge": cmd_purge,
        "hashes": cmd_hashes,
    }[args.cmd]
    fn(c, args)


if __name__ == "__main__":
    main()
