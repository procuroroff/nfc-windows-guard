"""System utilities: Autostart registration, Windows Power management, and Path resolution.
"""

import sys
import os
import winreg
from typing import Tuple

AUTOSTART_KEY_NAME = "NFCWindowsGuard"
REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_startup_command() -> str:
    """Returns the command line string to launch NFC Guard on Windows boot."""
    # Find pythonw.exe or python.exe
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable

    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{exe}" "{main_py}" --lock'


def is_autostart_enabled() -> bool:
    """Checks if NFC Guard is registered in Windows Startup (Run registry key)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, AUTOSTART_KEY_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart(enabled: bool) -> Tuple[bool, str]:
    """Registers or unregisters NFC Guard in Windows Startup registry."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ
        )
        if enabled:
            cmd = get_startup_command()
            winreg.SetValueEx(key, AUTOSTART_KEY_NAME, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            return True, "Автозапуск успешно включен"
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_KEY_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            return True, "Автозапуск отключен"
    except Exception as e:
        return False, f"Ошибка настройки реестра: {e}"


def shutdown_pc():
    """Powers down the system."""
    os.system("shutdown /s /t 0")


def restart_pc():
    """Reboots the system."""
    os.system("shutdown /r /t 0")
