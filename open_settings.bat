@echo off
chcp 65001 > nul
echo ========================================================
echo  NFC Windows Guard — Панель Управления и Настроек
echo ========================================================
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw main.py --settings
) else (
    start "" python main.py --settings
)
exit
