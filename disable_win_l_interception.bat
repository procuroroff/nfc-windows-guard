@echo off
chcp 65001 > nul
echo ===================================================================
echo  NFC Windows Guard — Отключение перехвата Win+L
echo ===================================================================
echo.
pause

powershell -Command "Start-Process cmd -ArgumentList '/c reg delete \"HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\System\" /v DisableLockWorkstation /f' -Verb RunAs -Wait"

echo.
echo Стандартное поведение Win+L восстановлено.
echo.
pause
