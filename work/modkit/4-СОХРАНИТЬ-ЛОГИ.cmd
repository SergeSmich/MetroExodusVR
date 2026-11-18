@echo off
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
cd /d "F:\Projects\MetroExodusVR"
set GAME=F:\SteamLibrary\steamapps\common\Metro Exodus

echo === СОХРАНЯЮ ЛОГИ ПОСЛЕДНЕГО ПРОГОНА ===
echo.
set /p NOTE=Коротко, что было на экране: 
python -u -X utf8 work\modkit\mod_switch.py collect "" --shots --note "%NOTE%"
echo.
echo Логи лежат в work\modkit\runs\
echo (при переключении на другой билд они сохраняются автоматически)
echo.
pause
