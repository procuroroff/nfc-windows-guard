"""Main entry point for NFC Windows Guard.
Usage:
    python main.py             # Opens Settings (or lock if whitelist is populated and configured)
    python main.py --lock      # Forces full-screen NFC Lock Screen
    python main.py --settings  # Forces Control Panel / Settings Window
"""

import sys
import os
import argparse
import ctypes

from nfc_guard.config import ConfigManager
from nfc_guard.lock_screen import NFCLockScreen
from nfc_guard.settings_window import SettingsWindow


def acquire_single_instance_mutex(name: str = "Global\\NFCWindowsGuardMutex"):
    """Prevents multiple copies of the lock screen from running at the same time."""
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, name)
    last_err = kernel32.GetLastError()
    ERROR_ALREADY_EXISTS = 183
    if last_err == ERROR_ALREADY_EXISTS:
        return None
    return mutex


def main():
    parser = argparse.ArgumentParser(description="NFC Windows Guard (ACR122U)")
    parser.add_argument("--lock", action="store_true", help="Launch fullscreen lock screen")
    parser.add_argument("--settings", action="store_true", help="Launch settings & card management window")
    args = parser.parse_args()

    cfg = ConfigManager()

    if args.lock:
        # Enforce single instance for lock screen
        mutex = acquire_single_instance_mutex("Global\\NFCWindowsGuardLockMutex")
        if not mutex:
            print("[NFC Guard] Lock screen instance is already active.")
            sys.exit(0)

        app = NFCLockScreen(config_manager=cfg)
        app.mainloop()
    elif args.settings:
        app = SettingsWindow(config_manager=cfg)
        app.mainloop()
    else:
        # If no arguments provided:
        # If cards are registered and lock_on_boot is enabled, lock screen.
        # Otherwise, open settings panel for first-time onboarding.
        if cfg.get_cards() and cfg.config.get("security", {}).get("lock_on_boot", False):
            app = NFCLockScreen(config_manager=cfg)
            app.mainloop()
        else:
            app = SettingsWindow(config_manager=cfg)
            app.mainloop()


if __name__ == "__main__":
    main()
