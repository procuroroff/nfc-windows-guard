"""System utilities: Autostart registration, Multi-monitor detection, and Daemon status.
"""

import sys
import os
import winreg
import ctypes
from ctypes import wintypes
from typing import Tuple, List, Dict

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

AUTOSTART_KEY_NAME = "NFCWindowsGuard"
REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
DAEMON_MUTEX_NAME = "Global\\NFCWindowsGuardDaemonMutex"
LOCK_MUTEX_NAME = "Global\\NFCWindowsGuardLockMutex"


# --- Multi-Monitor Geometry ---

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
)


def get_all_monitors() -> List[Dict[str, int]]:
    """Returns list of all active display monitors with coordinates and primary flag."""
    monitors: List[Dict[str, int]] = []

    def enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi))
        r = mi.rcMonitor
        monitors.append({
            "left": int(r.left),
            "top": int(r.top),
            "width": int(r.right - r.left),
            "height": int(r.bottom - r.top),
            "primary": bool(mi.dwFlags & 1)
        })
        return 1

    proc = MONITORENUMPROC(enum_proc)
    user32.EnumDisplayMonitors(None, None, proc, 0)

    # Fallback if no monitor enumerated
    if not monitors:
        monitors.append({
            "left": 0,
            "top": 0,
            "width": user32.GetSystemMetrics(0),
            "height": user32.GetSystemMetrics(1),
            "primary": True
        })

    return monitors


def is_light_color(hex_str: str) -> bool:
    """Calculates perceived brightness of a hex color (returns True if bright)."""
    try:
        clean = hex_str.lstrip("#")
        r = int(clean[0:2], 16)
        g = int(clean[2:4], 16)
        b = int(clean[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return luminance > 140
    except Exception:
        return False


# --- Startup & Process Helpers ---

def get_pythonw_executable() -> str:
    """Finds pythonw.exe to run without a console window."""
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    return pythonw if os.path.exists(pythonw) else sys.executable


def get_startup_command() -> str:
    """Returns command line to launch NFC Guard Daemon on Windows boot."""
    exe = get_pythonw_executable()
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{exe}" "{main_py}" --daemon'


def is_autostart_enabled() -> bool:
    """Checks if NFC Guard Daemon is registered in Windows Startup."""
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
            return True, "Автозапуск фоновой службы успешно включен"
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_KEY_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            return True, "Автозапуск отключен"
    except Exception as e:
        return False, f"Ошибка настройки реестра: {e}"


def is_daemon_running() -> bool:
    """Checks if background daemon mutex exists."""
    mutex = kernel32.OpenMutexW(0x00100000, False, DAEMON_MUTEX_NAME)
    if mutex:
        kernel32.CloseHandle(mutex)
        return True
    return False


def is_lock_active() -> bool:
    """Checks if lock screen mutex exists."""
    mutex = kernel32.OpenMutexW(0x00100000, False, LOCK_MUTEX_NAME)
    if mutex:
        kernel32.CloseHandle(mutex)
        return True
    return False


def shutdown_pc():
    """Powers down the system."""
    os.system("shutdown /s /t 0")


def restart_pc():
    """Reboots the system."""
    os.system("shutdown /r /t 0")
