@echo off
chcp 65001 > nul
echo ========================================================
echo  NFC Windows Guard — Установка зависимостей (Python)
echo ========================================================
cd /d "%~dp0"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ========================================================
echo  Установка завершена!
echo ========================================================
pause
