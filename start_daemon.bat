@echo off
chcp 65001 > nul
echo ========================================================
echo  NFC Windows Guard — Запуск Фоновой Службы (Win+L / Трей)
echo ========================================================
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw main.py --daemon
) else (
    start "" python main.py --daemon
)
echo Фоновая служба запущена в трее и отслеживает Win+L!
exit
