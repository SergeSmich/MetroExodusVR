# Metro Exodus VR RU — v0.9.1 test kit (NOT a release)

## Read this first

This is a **version-specific experimental test kit**, not a ready-to-install Russian patch. It is only for the Metro Exodus VR **v0.9.1** DLL whose SHA-256 is exactly:

```text
fbbf2812bc7c3304a22829249aba334c812a326baf75fc5c2a75e559202c40b4
```

The port now passes structural checks against that DLL, but **the Cyrillic encoding has not been confirmed in the game's VR UI**. `apply_ru.py` can only build the current CP1251 hypothesis when the operator explicitly supplies `--experimental-cp1251`. Existing analysis notes report that CP1251, UTF-8, and compact RU-charmap bytes have rendered incorrectly in the mod's custom UI. Therefore:

- Never run the old generic `tools/install_ru.py` from the upstream translation fork on v0.9.1.
- Do not install this candidate into the normal game/mod directory as a finished rusifier.
- If the PC agent makes an in-game diagnostic test, use an isolated copy if possible, or first create and verify a byte-for-byte backup of **only** `versions\0.9.1\MetroExodusVR.dll` and be ready to restore it.
- Do not patch `MetroExodus.exe` or any base-game file.

The intended task for the PC agent is to identify/prove the custom UI's byte-to-glyph path, then test a candidate in VR and report the exact displayed result. A font merge alone does not resolve an incorrect character map.

## What is included

- `tools/apply_ru.py` — version-pinned PE patcher and static verifier. It refuses unknown DLL hashes and requires explicit opt-in to CP1251.
- `tools/validate_ui2.py` — validates translation characters, markup, table pointers, and original strings against the supplied DLL. This is static validation only.
- `tools/merge_cyrillic.py` — experimental font preparation for the four embedded TTFs. It is pinned to the v0.9.1 source DLL, reads local Windows Arial fonts, fixes the OS/2 Cyrillic-range flag, and reopens saved fonts to check their Unicode cmap. It does **not** validate the mod's runtime glyph selection.
- `ru/strings-0.9.1.tsv`, `ru/ui2-0.9.1.json`, `ru/charmap.txt` — v0.9.1 string catalog, UI tables, and source character repertoire.
- `work/plan-0.9.1.json`, `work/funcs-0.9.1.json` — generated address/xref and function-boundary data required by the patcher.

No game or mod DLL is bundled. The original SergeSmich review clone was not modified.

## Static checks on Windows

Use Python 3.10+ and run these commands from the unpacked test-kit folder. `OriginalDll` must refer to an unmodified v0.9.1 `MetroExodusVR.dll` extracted from the official release or the user's installation.

```powershell
py -m pip install -r .\requirements.txt
$OriginalDll = 'D:\path\to\versions\0.9.1\MetroExodusVR.dll'
$Expected = 'FBBF2812BC7C3304A22829249ABA334C812A326BAF75FC5C2A75E559202C40B4'
$Actual = (Get-FileHash -LiteralPath $OriginalDll -Algorithm SHA256).Hash
if ($Actual -ne $Expected) { throw "Unsupported DLL SHA-256: $Actual" }

py .\tools\validate_ui2.py --dll $OriginalDll
py .\tools\apply_ru.py --src $OriginalDll --check --no-fonts --experimental-cp1251
```

Expected static summary: 193 native-caption rows (180 translated, 13 retained), 188 redirected `lea` sites, 27 length updates, UI2 tables with 15 popups / 79 options / 52 hints / 14 hint pages, 20 inline stubs, 3 printable-ASCII validator sites, and 2 extra strings. `--check` writes no DLL.

The helper script performs the same hash/catalog/static checks and writes no DLL by default:

```powershell
.\build_diagnostic.ps1 -OriginalDll $OriginalDll
```

To explicitly build the optional CP1251 diagnostic candidate (still **not installed**):

```powershell
.\build_diagnostic.ps1 -OriginalDll $OriginalDll -BuildCandidate
```

`--no-fonts` is for structural checking only. Such output must not be used to judge font rendering because the shipped fonts contain no Cyrillic glyphs.

## Optional diagnostic candidate (isolated test only)

The next step creates local Arial-based test fonts and a candidate DLL. It does not modify the source DLL or the game, but the candidate still uses the unconfirmed CP1251 hypothesis.

```powershell
py .\tools\merge_cyrillic.py --src $OriginalDll --out .\build\fonts
py .\tools\apply_ru.py --src $OriginalDll --out .\build\MetroExodusVR-RU-CP1251-DIAGNOSTIC.dll --verify --experimental-cp1251
Get-FileHash .\build\MetroExodusVR-RU-CP1251-DIAGNOSTIC.dll -Algorithm SHA256
```

The font merger expects the local Windows files `C:\Windows\Fonts\arial.ttf` and `arialbd.ttf`. They are not included in the kit. FontTools verifies the added cmap entries, and `--verify` verifies PE pointers, string payloads, stubs, resource redirections, and byte patches. Neither check proves that the game selects the Cyrillic glyphs.

Do not remove `--experimental-cp1251`: it is the deliberate warning gate. Do not bypass the source-hash guard with `--allow-unknown-source` for a normal test.

## Safe game test and recovery

1. Confirm the target mod is really v0.9.1 and its unmodified DLL hash equals the expected hash above. Close the game and mod processes.
2. Prefer an isolated clone of the mod directory and launch that copy if the installation supports it. Do not run the candidate against other `versions\*` DLLs.
3. If an isolated copy is impossible and the user explicitly authorizes a temporary test in the existing mod folder, first save the exact original file to a new, non-overwriting backup outside the target directory. Example:

   ```powershell
   $Target = 'D:\...\Metro Exodus\MetroExodusVR\versions\0.9.1\MetroExodusVR.dll'
   $Backup = "$Target.before-ru-test"
   if (Test-Path $Backup) { throw "Backup already exists; do not overwrite it: $Backup" }
   $Before = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash
   if ($Before -ne $Expected) { throw "Target is not the expected original v0.9.1 DLL: $Before" }
   Copy-Item -LiteralPath $Target -Destination $Backup
   if ((Get-FileHash -LiteralPath $Backup -Algorithm SHA256).Hash -ne $Expected) { throw 'Backup verification failed' }
   ```

4. Only after the backup verifies, place the diagnostic candidate at that one target path. Record the candidate hash. Do not use the upstream auto-installer, do not patch all version folders, and do not let the mod self-update during the test.
5. Start the VR mod. Inspect and capture: VR settings captions; options; `VR HINTS` title and at least one page; popup text including “CHOOSING AN OPTION”; and a live HUD hint. Record whether text is readable Cyrillic, blanks, tofu/boxes, or Latin-looking garbage, and whether controls/format markers or line breaks are broken. Do not test only the native menu captions and assume UI2 works too; those may use different paths.
6. Restore immediately after the diagnostic run, successful or not:

   ```powershell
   Copy-Item -LiteralPath $Backup -Destination $Target -Force
   if ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -ne $Expected) { throw 'Restore verification failed' }
   ```

7. Report the mod/DLL version and SHA-256, the VR runtime/headset, the exact test path, screenshots/video, and which text groups succeeded. If CP1251 renders incorrectly, do not try random code pages on the live install. Trace the string at the v0.9.1 draw boundary and determine whether it is interpreted as Unicode, a US-charmap index, or another encoding; then change the conversion/glyph-map path and rebuild.

## Static port results and remaining limits

The v0.9.1 catalog was regenerated from the actual DLL rather than by shifting v0.9.0 RVAs. Analysis covered 15,354 functions and found 239 RIP-relative references to the 193 selected source strings. UI2 tables were independently reread from the v0.9.1 binary. Three UI2 entries are new or adapted: the “CHOOSING AN OPTION” popup, the changed “Badly hurt” hint, and the updated Basics hint page. The patcher also recognizes v0.9.1's three ASCII-check sites at `0xA4728`, `0xA4C76`, and `0xA6556`; they were confirmed as `cmp ..., 0x5e` instructions before the candidate byte is changed to `0xff`.

A static `--verify` run on an isolated no-fonts build passed: 20 stubs and 554 byte-patch writes. This is not a runtime test and is not a distributable patch. The four embedded v0.9.1 TTFs were extracted and confirmed to have zero Cyrillic cmap entries. The merge logic was smoke-tested with a local DejaVu Sans donor, but the Windows Arial-based production step could not be run here because this environment has no Windows Arial files. Most importantly, the mod's renderer/encoding behavior remains unverified here.
