@echo off
chcp 65001 > nul
echo ===================================================================
echo  NFC Windows Guard — Перехват Win+L для экрана NFC
echo ===================================================================
echo.
echo Для того, чтобы нажатие Win+L сразу вызывало экран NFC Guard
echo (а не стандартный экран Windows), требуется однократное подтверждение
echo прав администратора в окне UAC.
echo.
pause

powershell -Command "Start-Process cmd -ArgumentList '/c reg add \"HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\System\" /v DisableLockWorkstation /t REG_DWORD /d 1 /f' -Verb RunAs -Wait"

echo.
echo Готово! Теперь при нажатии Win+L сразу открывается экран NFC Guard.
echo (Для возврата стандартного поведения запустите disable_win_l_interception.bat)
echo.
pause
