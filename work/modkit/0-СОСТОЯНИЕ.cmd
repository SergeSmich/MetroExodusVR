@echo off
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
cd /d "F:\Projects\MetroExodusVR"
set GAME=F:\SteamLibrary\steamapps\common\Metro Exodus

echo === ЧТО СЕЙЧАС УСТАНОВЛЕНО ===
echo.
python -u -X utf8 work\modkit\mod_switch.py status
echo.
echo vanilla = мода нет, orig = оригинальный мод 0.9.3, ours = наш проект
echo.
pause
