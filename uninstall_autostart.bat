@echo off
chcp 65001 > nul
echo ========================================================
echo  NFC Windows Guard — Удаление из автозагрузки Windows
echo ========================================================
cd /d "%~dp0"

python -c "from nfc_guard.utils import set_autostart; ok, msg = set_autostart(False); print(msg); exit(0 if ok else 1)"
if %errorlevel% equ 0 (
    echo [УСПЕХ] Программа успешно удалена из автозапуска Windows!
) else (
    echo [ОШИБКА] Не удалось удалить из автозапуска.
)
echo.
pause
