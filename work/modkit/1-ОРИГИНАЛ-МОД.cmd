@echo off
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
cd /d "F:\Projects\MetroExodusVR"
set GAME=F:\SteamLibrary\steamapps\common\Metro Exodus

echo === СТАВЛЮ ОРИГИНАЛЬНЫЙ МОД 0.9.3 (английский) ===
echo.
python -u -X utf8 work\modkit\mod_switch.py autocollect
python -u -X utf8 work\modkit\mod_switch.py apply orig
if errorlevel 1 goto fail
if /i "%~1"=="nolaunch" goto ok
echo.
echo Сейчас запустится игра.
echo Когда появится окно "4A Engine" - ОДИН раз кликни ВНУТРЬ окна
echo и больше никуда не переключайся.
echo.
start "" /d "%GAME%" "%GAME%\MetroExodusVR.exe"
goto ok
:fail
echo.
echo НЕ ПОЛУЧИЛОСЬ. Скорее всего игра ещё запущена - закрой её и запусти файл снова.
:ok
echo.
pause
