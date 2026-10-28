"""Configuration Manager for NFC Windows Guard.
Handles loading, saving, card whitelist management, themes, and security settings.
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "NFCGuard")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")
LOG_FILE = os.path.join(APPDATA_DIR, "access.log")

# Theme Presets
THEME_PRESETS: Dict[str, Dict[str, str]] = {
    "Cyberpunk (Неон)": {
        "bg_color": "#0d0e15",
        "card_bg": "#151828",
        "border_color": "#00f0ff",
        "accent_color": "#00f0ff",
        "accent_hover": "#00c4d4",
        "text_primary": "#ffffff",
        "text_secondary": "#7f8ea3",
        "success_color": "#00ff88",
        "error_color": "#ff0055",
        "warning_color": "#ffaa00",
    },
    "Тёмная (Dark Modern)": {
        "bg_color": "#121214",
        "card_bg": "#1e1e24",
        "border_color": "#2e2e38",
        "accent_color": "#3b82f6",
        "accent_hover": "#2563eb",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "success_color": "#10b981",
        "error_color": "#ef4444",
        "warning_color": "#f59e0b",
    },
    "Матрица (Matrix Hacker)": {
        "bg_color": "#040d06",
        "card_bg": "#081a0c",
        "border_color": "#00ff41",
        "accent_color": "#00ff41",
        "accent_hover": "#00cc33",
        "text_primary": "#e6ffe6",
        "text_secondary": "#009926",
        "success_color": "#00ff41",
        "error_color": "#ff3333",
        "warning_color": "#ffcc00",
    },
    "Полночь (Midnight Blue)": {
        "bg_color": "#090d16",
        "card_bg": "#131b2e",
        "border_color": "#1e2c4a",
        "accent_color": "#6366f1",
        "accent_hover": "#4f46e5",
        "text_primary": "#f1f5f9",
        "text_secondary": "#64748b",
        "success_color": "#22c55e",
        "error_color": "#f43f5e",
        "warning_color": "#eab308",
    },
    "Светлая (Clean Minimal)": {
        "bg_color": "#f1f5f9",
        "card_bg": "#ffffff",
        "border_color": "#cbd5e1",
        "accent_color": "#2563eb",
        "accent_hover": "#1d4ed8",
        "text_primary": "#0f172a",
        "text_secondary": "#64748b",
        "success_color": "#16a34a",
        "error_color": "#dc2626",
        "warning_color": "#d97706",
    },
    "Красная тревога (Red Alert)": {
        "bg_color": "#120808",
        "card_bg": "#200d0d",
        "border_color": "#ef4444",
        "accent_color": "#ef4444",
        "accent_hover": "#dc2626",
        "text_primary": "#ffffff",
        "text_secondary": "#995555",
        "success_color": "#22c55e",
        "error_color": "#ef4444",
        "warning_color": "#f59e0b",
    }
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0.0",
    "security": {
        "max_attempts": 3,
        "action_on_fail": "lock_workstation",  # "lock_workstation", "shutdown", "restart"
        "allow_manual_fallback": True,        # Button "Штатный вход Windows"
        "master_pin_hash": "",                 # SHA-256 for admin bypass/settings
        "lock_on_boot": True,                  # Open lock overlay on PC start
        "beep_on_success": True,               # Hardware beep on ACR122U
        "beep_on_error": True,                 # Hardware buzzer on wrong card
        "cooldown_seconds": 1,                 # Debounce delay between reads
    },
    "appearance": {
        "theme_name": "Cyberpunk (Неон)",
        "custom_colors": THEME_PRESETS["Cyberpunk (Неон)"].copy(),
        "title_text": "NFC WINDOWS GUARD",
        "subtitle_text": "Приложите ключ-карту к считывателю ACR122U",
        "show_uid_on_screen": True,
        "show_attempts_counter": True,
        "fullscreen": True,
    },
    "cards": [
        # Example format:
        # {
        #     "uid": "04:A1:B2:C3",
        #     "name": "Основной ключ",
        #     "added_at": "2026-10-28 12:00:00",
        #     "enabled": True
        # }
    ]
}


def normalize_uid(uid: str) -> str:
    """Standardizes card UID to uppercase colon-separated string (e.g. 04:A1:B2:C3)."""
    clean = uid.replace(":", "").replace(" ", "").replace("-", "").upper()
    return ":".join(clean[i:i+2] for i in range(0, len(clean), 2))


def hash_pin(pin: str) -> str:
    """Computes SHA-256 hash of a PIN/Password."""
    if not pin:
        return ""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


class ConfigManager:
    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self._ensure_dirs()
        self.config = self.load()

    def _ensure_dirs(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Loads configuration from JSON file or initializes default."""
        if not os.path.exists(self.config_path):
            self.save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults to ensure missing keys don't break
            cfg = DEFAULT_CONFIG.copy()
            for key in ["security", "appearance"]:
                if key in data:
                    cfg[key] = {**DEFAULT_CONFIG[key], **data[key]}
            if "cards" in data:
                cfg["cards"] = data["cards"]
            return cfg
        except Exception as e:
            print(f"[Config] Error loading config, restoring default: {e}")
            return DEFAULT_CONFIG.copy()

    def save(self, data: Optional[Dict[str, Any]] = None):
        """Saves current configuration to disk."""
        if data is not None:
            self.config = data
        try:
            self._ensure_dirs()
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    # --- Card Whitelist Methods ---

    def get_cards(self) -> List[Dict[str, Any]]:
        return self.config.get("cards", [])

    def is_card_authorized(self, uid: str) -> bool:
        """Checks if a card UID is in the whitelist and enabled."""
        norm = normalize_uid(uid)
        for card in self.get_cards():
            if normalize_uid(card.get("uid", "")) == norm and card.get("enabled", True):
                return True
        return False

    def get_card_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        norm = normalize_uid(uid)
        for card in self.get_cards():
            if normalize_uid(card.get("uid", "")) == norm:
                return card
        return None

    def add_card(self, uid: str, name: str) -> bool:
        """Adds or updates a card in the whitelist."""
        norm = normalize_uid(uid)
        if not norm:
            return False

        cards = self.get_cards()
        for card in cards:
            if normalize_uid(card.get("uid", "")) == norm:
                card["name"] = name
                card["enabled"] = True
                self.save()
                return True

        cards.append({
            "uid": norm,
            "name": name or f"Карта {len(cards) + 1}",
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "enabled": True
        })
        self.config["cards"] = cards
        self.save()
        return True

    def remove_card(self, uid: str) -> bool:
        norm = normalize_uid(uid)
        cards = [c for c in self.get_cards() if normalize_uid(c.get("uid", "")) != norm]
        if len(cards) != len(self.get_cards()):
            self.config["cards"] = cards
            self.save()
            return True
        return False

    def toggle_card(self, uid: str) -> Optional[bool]:
        """Toggles active state of a card."""
        norm = normalize_uid(uid)
        for card in self.get_cards():
            if normalize_uid(card.get("uid", "")) == norm:
                card["enabled"] = not card.get("enabled", True)
                self.save()
                return card["enabled"]
        return None

    # --- Theme Methods ---

    def get_current_theme(self) -> Dict[str, str]:
        theme_name = self.config.get("appearance", {}).get("theme_name", "Cyberpunk (Неон)")
        if theme_name in THEME_PRESETS:
            return THEME_PRESETS[theme_name]
        return self.config.get("appearance", {}).get("custom_colors", THEME_PRESETS["Cyberpunk (Неон)"])

    def set_theme(self, theme_name: str):
        if theme_name in THEME_PRESETS:
            self.config["appearance"]["theme_name"] = theme_name
            self.config["appearance"]["custom_colors"] = THEME_PRESETS[theme_name].copy()
            self.save()

    def update_custom_color(self, key: str, hex_color: str):
        self.config["appearance"]["custom_colors"][key] = hex_color
        self.config["appearance"]["theme_name"] = "Custom"
        self.save()

    # --- Security Methods ---

    def verify_master_pin(self, pin: str) -> bool:
        stored_hash = self.config.get("security", {}).get("master_pin_hash", "")
        if not stored_hash:
            return True  # No PIN set means access granted
        return hash_pin(pin) == stored_hash

    def set_master_pin(self, pin: str):
        self.config["security"]["master_pin_hash"] = hash_pin(pin) if pin else ""
        self.save()

    def log_event(self, event_type: str, message: str, uid: str = ""):
        """Appends an event to the local log file."""
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{timestamp}] [{event_type:<8}] {message}"
            if uid:
                line += f" (UID: {normalize_uid(uid)})"
            line += "\n"
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            print(f"[Log] Error writing log: {e}")

    def read_recent_logs(self, limit: int = 100) -> List[str]:
        if not os.path.exists(LOG_FILE):
            return []
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [line.strip() for line in lines[-limit:]]
        except Exception:
            return []

    def clear_logs(self):
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("")
        except Exception:
            pass
