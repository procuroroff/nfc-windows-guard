"""Main entry point for NFC Windows Guard.
Usage:
    python main.py             # Opens Settings (or lock if whitelist is populated and configured)
    python main.py --daemon    # Runs resident background daemon (monitors Win+L, sessions, tray)
    python main.py --lock      # Forces full-screen NFC Lock Screen across all monitors
    python main.py --settings  # Forces Control Panel / Settings Window
"""

import sys
import os
import argparse
import ctypes

from nfc_guard.config import ConfigManager
from nfc_guard.utils import LOCK_MUTEX_NAME, DAEMON_MUTEX_NAME


def acquire_mutex(name: str):
    """Prevents multiple copies of a component from running simultaneously."""
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, name)
    last_err = kernel32.GetLastError()
    ERROR_ALREADY_EXISTS = 183
    if last_err == ERROR_ALREADY_EXISTS:
        return None
    return mutex


def main():
    parser = argparse.ArgumentParser(description="NFC Windows Guard (ACR122U)")
    parser.add_argument("--daemon", action="store_true", help="Launch background service (tray, Win+L watcher)")
    parser.add_argument("--lock", action="store_true", help="Launch fullscreen lock screen across all monitors")
    parser.add_argument("--settings", action="store_true", help="Launch settings & card management window")
    args = parser.parse_args()

    cfg = ConfigManager()

    if args.daemon:
        from nfc_guard.daemon import NFCGuardDaemon
        daemon = NFCGuardDaemon()
        daemon.start()

    elif args.lock:
        mutex = acquire_mutex(LOCK_MUTEX_NAME)
        if not mutex:
            print("[NFC Guard] Lock screen instance is already active.")
            sys.exit(0)

        from nfc_guard.lock_screen import NFCLockScreen
        app = NFCLockScreen(config_manager=cfg)
        app.mainloop()

    elif args.settings:
        from nfc_guard.settings_window import SettingsWindow
        app = SettingsWindow(config_manager=cfg)
        app.mainloop()

    else:
        # Default with no args: open settings for management
        from nfc_guard.settings_window import SettingsWindow
        app = SettingsWindow(config_manager=cfg)
        app.mainloop()


if __name__ == "__main__":
    main()
