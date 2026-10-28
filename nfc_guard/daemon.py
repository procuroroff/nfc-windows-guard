"""Resident Background Daemon for NFC Windows Guard.
Monitors Windows session changes (Win+L lock/unlock), hotkeys, and runs the system tray.
"""

import sys
import os
import time
import subprocess
import ctypes
from ctypes import wintypes
from typing import Optional
import pystray

from .config import ConfigManager
from .utils import (
    get_pythonw_executable,
    is_lock_active,
    DAEMON_MUTEX_NAME,
)
from .icons import create_tray_icon_pil
from .hooks import HOOKPROC, KBDLLHOOKSTRUCT

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
wtsapi32 = ctypes.windll.wtsapi32

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0

WH_KEYBOARD_LL = 13
VK_L = 0x4C
VK_LWIN = 0x5B
VK_RWIN = 0x5C
WM_HOTKEY = 0x0312
HOTKEY_LOCK_ID = 9001
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM
)
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    ctypes.c_uint,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_longlong


class NFCGuardDaemon:
    """Background service guarding Win+L, lock/unlock events, and system tray."""

    def __init__(self):
        self.cfg = ConfigManager()
        self.running = False
        self.tray_icon: Optional[pystray.Icon] = None
        self._mutex = None
        self._hwnd = None
        self._hook = None
        self._hook_cb = None
        self._wnd_proc = None
        self._cls_name = "NFCGuardSessionWatcherCls"
        self._last_lock_time = 0
        self.is_locked = False

    def start(self):
        self._mutex = kernel32.CreateMutexW(None, False, DAEMON_MUTEX_NAME)
        if kernel32.GetLastError() == 183:
            print("[Daemon] Another daemon instance is already active.")
            sys.exit(0)

        self.running = True
        self.cfg.log_event("DAEMON_START", "Фоновая служба NFC Guard запущена")

        # Initial lock on boot if configured
        if self.cfg.config.get("security", {}).get("lock_on_boot", True) and self.cfg.get_cards():
            self.spawn_lock_screen()

        self._start_tray_icon()
        self._run_session_watcher()

    def _start_tray_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("🔒 Заблокировать экран сейчас", self._tray_lock_clicked),
            pystray.MenuItem("⚙️ Настройки", self._tray_settings_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Выход из защиты", self._tray_exit_clicked),
        )
        self.tray_icon = pystray.Icon(
            "NFCWindowsGuard",
            create_tray_icon_pil(),
            "NFC Windows Guard — Защита активна",
            menu=menu,
        )
        self.tray_icon.run_detached()

    def _tray_lock_clicked(self, icon=None, item=None):
        self.spawn_lock_screen()

    def _tray_settings_clicked(self, icon=None, item=None):
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        exe = get_pythonw_executable()
        subprocess.Popen([exe, main_py, "--settings"])

    def _tray_exit_clicked(self, icon=None, item=None):
        self.stop()

    def spawn_lock_screen(self):
        """Spawns the NFC lock screen overlay."""
        if time.time() - self._last_lock_time < 1.5:
            return
        self._last_lock_time = time.time()

        if is_lock_active():
            return

        self.is_locked = True
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        exe = get_pythonw_executable()
        subprocess.Popen([exe, main_py, "--lock"])

    def _run_session_watcher(self):
        hinst = kernel32.GetModuleHandleW(None)

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_WTSSESSION_CHANGE:
                if wparam == WTS_SESSION_LOCK:
                    # Native Windows lock event
                    self.is_locked = True
                    self.cfg.log_event("SESSION_LOCK", "Windows заблокирован")
                elif wparam == WTS_SESSION_UNLOCK:
                    # User authenticated successfully via standard Windows password
                    # DO NOT prompt for card again!
                    self.is_locked = False
                    self.cfg.log_event("SESSION_UNLOCK", "Сессия успешно разблокирована штатным методом")
            elif msg == WM_HOTKEY:
                if wparam == HOTKEY_LOCK_ID:
                    self.spawn_lock_screen()

            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wnd_proc = WNDPROC(wnd_proc)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HCURSOR),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON),
            ]

        wnd_cls = WNDCLASSEXW()
        wnd_cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wnd_cls.lpfnWndProc = self._wnd_proc
        wnd_cls.hInstance = hinst
        wnd_cls.lpszClassName = self._cls_name

        user32.RegisterClassExW(ctypes.byref(wnd_cls))
        self._hwnd = user32.CreateWindowExW(
            0, self._cls_name, "NFCGuardWatcher", 0, 0, 0, 0, 0, None, None, hinst, None
        )

        wtsapi32.WTSRegisterSessionNotification(self._hwnd, NOTIFY_FOR_THIS_SESSION)
        user32.RegisterHotKey(self._hwnd, HOTKEY_LOCK_ID, MOD_CONTROL | MOD_ALT, ord("L"))

        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and lParam:
                vk = lParam.contents.vkCode
                if vk == VK_L:
                    win_down = bool(user32.GetAsyncKeyState(VK_LWIN) & 0x8000) or bool(
                        user32.GetAsyncKeyState(VK_RWIN) & 0x8000
                    )
                    if win_down:
                        # User pressed Win+L
                        self.spawn_lock_screen()
            return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        self._hook_cb = HOOKPROC(hook_proc)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_cb, None, 0)

        msg = wintypes.MSG()
        while self.running:
            bRet = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if bRet <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self._teardown()

    def _teardown(self):
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
        if self._hwnd:
            user32.UnregisterHotKey(self._hwnd, HOTKEY_LOCK_ID)
            wtsapi32.WTSUnRegisterSessionNotification(self._hwnd)
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None
        hinst = kernel32.GetModuleHandleW(None)
        user32.UnregisterClassW(self._cls_name, hinst)
        if self._mutex:
            kernel32.CloseHandle(self._mutex)
            self._mutex = None

    def stop(self):
        self.running = False
        self.cfg.log_event("DAEMON_STOP", "Фоновая служба NFC Guard остановлена")
        if self.tray_icon:
            self.tray_icon.stop()
        if self._hwnd:
            user32.PostMessageW(self._hwnd, 0x0012, 0, 0)
        sys.exit(0)
