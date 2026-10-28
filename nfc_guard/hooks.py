"""Windows Low-Level Keyboard Hook & System Security Utilities.
Blocks Windows key, Alt+Tab, Alt+F4, Alt+Esc, and manages Task Manager policy.
"""

import ctypes
from ctypes import wintypes
import winreg

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Virtual Key Codes
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_F4 = 0x73
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt

LLKHF_ALTDOWN = 0x20


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT)
)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK

user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL

user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    ctypes.POINTER(KBDLLHOOKSTRUCT),
]
user32.CallNextHookEx.restype = ctypes.c_longlong


class KeyboardBlocker:
    """Installs low-level hook to block bypass keys (Alt+Tab, Win, Alt+F4, etc.)."""

    def __init__(self):
        self._hook = None
        self._callback = None

    def install(self) -> bool:
        if self._hook:
            return True

        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and lParam:
                vk = lParam.contents.vkCode
                flags = lParam.contents.flags
                alt_pressed = bool(flags & LLKHF_ALTDOWN)

                # Block Windows keys
                if vk in (VK_LWIN, VK_RWIN):
                    return 1

                # Block Alt+Tab
                if vk == VK_TAB and alt_pressed:
                    return 1

                # Block Alt+Escape
                if vk == VK_ESCAPE and alt_pressed:
                    return 1

                # Block Alt+F4
                if vk == VK_F4 and alt_pressed:
                    return 1

                # Block Alt+Space
                if vk == VK_SPACE and alt_pressed:
                    return 1

                # Block Ctrl+Escape
                ctrl_down = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                if vk == VK_ESCAPE and ctrl_down:
                    return 1

            return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        self._callback = HOOKPROC(hook_proc)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._callback, None, 0)
        return bool(self._hook)

    def uninstall(self):
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
            self._callback = None


def set_task_manager_disabled(disabled: bool):
    """Enables or disables Windows Task Manager via Registry policy."""
    try:
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
        key = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE
        )
        if disabled:
            winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
        else:
            try:
                winreg.DeleteValue(key, "DisableTaskMgr")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        # User might not have write access or key already configured
        pass


def lock_workstation_now():
    """Immediately triggers the native Windows Lock Screen (LockWorkStation)."""
    try:
        user32.LockWorkStation()
    except Exception as e:
        print(f"[System] Failed to lock workstation: {e}")
