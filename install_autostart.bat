@echo off
chcp 65001 > nul
echo ========================================================
echo  NFC Windows Guard — Установка в автозагрузку Windows
echo ========================================================
cd /d "%~dp0"

python -c "from nfc_guard.utils import set_autostart; ok, msg = set_autostart(True); print(msg); exit(0 if ok else 1)"
if %errorlevel% equ 0 (
    echo [УСПЕХ] Программа успешно добавлена в автозапуск при старте Windows!
) else (
    echo [ОШИБКА] Не удалось настроить автозапуск.
)
echo.
pause
