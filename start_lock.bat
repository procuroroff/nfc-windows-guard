@echo off
chcp 65001 > nul
echo ========================================================
echo  NFC Windows Guard — Запуск Экрана Блокировки
echo ========================================================
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw main.py --lock
) else (
    start "" python main.py --lock
)
exit
