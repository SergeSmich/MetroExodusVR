@echo off
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
cd /d "F:\Projects\MetroExodusVR"
set GAME=F:\SteamLibrary\steamapps\common\Metro Exodus

echo === УБИРАЮ МОД, ЗАПУСКАЮ ЧИСТУЮ ИГРУ ===
echo.
python -u -X utf8 work\modkit\mod_switch.py autocollect
python -u -X utf8 work\modkit\mod_switch.py clean --yes
if errorlevel 1 goto fail
if /i "%~1"=="nolaunch" goto ok
echo.
echo Сейчас запустится чистая игра (без мода).
echo.
start "" /d "%GAME%" "%GAME%\MetroExodus.exe"
goto ok
:fail
echo.
echo НЕ ПОЛУЧИЛОСЬ. Скорее всего игра ещё запущена - закрой её и запусти файл снова.
:ok
echo.
pause
