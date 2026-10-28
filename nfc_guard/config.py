"""Configuration Manager for NFC Windows Guard.
Apple Design Language presets, card whitelisting, and security policies.
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "NFCGuard")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")
LOG_FILE = os.path.join(APPDATA_DIR, "access.log")

# Apple Design System Theme Presets
THEME_PRESETS: Dict[str, Dict[str, str]] = {
    "Apple Dark (Тёмная macOS)": {
        "bg_color": "#09090b",
        "card_bg": "#18181b",
        "border_color": "#27272a",
        "accent_color": "#0a84ff",
        "accent_hover": "#0071e3",
        "text_primary": "#f5f5f7",
        "text_secondary": "#86868b",
        "success_color": "#30d158",
        "error_color": "#ff453a",
        "warning_color": "#ff9f0a",
    },
    "Apple Midnight (Полночь)": {
        "bg_color": "#080c14",
        "card_bg": "#0f172a",
        "border_color": "#1e293b",
        "accent_color": "#6366f1",
        "accent_hover": "#4f46e5",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "success_color": "#30d158",
        "error_color": "#ff453a",
        "warning_color": "#ff9f0a",
    },
    "Apple Space Gray (Титан)": {
        "bg_color": "#121214",
        "card_bg": "#1c1c1f",
        "border_color": "#323236",
        "accent_color": "#e2e8f0",
        "accent_hover": "#cbd5e1",
        "text_primary": "#f5f5f7",
        "text_secondary": "#86868b",
        "success_color": "#30d158",
        "error_color": "#ff453a",
        "warning_color": "#ff9f0a",
    },
    "Apple Forest (Альпийская зелень)": {
        "bg_color": "#060d09",
        "card_bg": "#0d1a12",
        "border_color": "#193324",
        "accent_color": "#34d399",
        "accent_hover": "#10b981",
        "text_primary": "#f0fdf4",
        "text_secondary": "#86efac",
        "success_color": "#30d158",
        "error_color": "#ff453a",
        "warning_color": "#ff9f0a",
    },
    "Apple Crimson (Глубокий рубин)": {
        "bg_color": "#0f080a",
        "card_bg": "#1c1014",
        "border_color": "#331c24",
        "accent_color": "#fb7185",
        "accent_hover": "#f43f5e",
        "text_primary": "#fff1f2",
        "text_secondary": "#fda4af",
        "success_color": "#30d158",
        "error_color": "#ff453a",
        "warning_color": "#ff9f0a",
    },
    "Apple Light (Светлая macOS)": {
        "bg_color": "#f5f5f7",
        "card_bg": "#ffffff",
        "border_color": "#e5e5ea",
        "accent_color": "#0071e3",
        "accent_hover": "#0058b0",
        "text_primary": "#1d1d1f",
        "text_secondary": "#86868b",
        "success_color": "#34c759",
        "error_color": "#ff3b30",
        "warning_color": "#ff9500",
    }
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "2.0.0",
    "security": {
        "max_attempts": 3,
        "action_on_fail": "lock_workstation",
        "allow_manual_fallback": True,
        "master_pin_hash": "",
        "lock_on_boot": True,
        "beep_on_success": True,
        "beep_on_error": True,
        "cooldown_seconds": 1.0,
    },
    "appearance": {
        "theme_name": "Apple Dark (Тёмная macOS)",
        "custom_colors": THEME_PRESETS["Apple Dark (Тёмная macOS)"].copy(),
        "title_text": "Ключ-карта",
        "subtitle_text": "Приложите карту доступа к считывателю",
        "show_uid_on_screen": True,
        "show_attempts_counter": True,
        "show_clock": True,
        "fullscreen": True,
    },
    "cards": []
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
            cfg = DEFAULT_CONFIG.copy()
            for key in ["security", "appearance"]:
                if key in data:
                    cfg[key] = {**DEFAULT_CONFIG[key], **data[key]}
            if "cards" in data:
                cfg["cards"] = data["cards"]

            # Migrate old theme names if user had previous cyberpunk/matrix names
            tname = cfg["appearance"].get("theme_name", "")
            if tname not in THEME_PRESETS:
                cfg["appearance"]["theme_name"] = "Apple Dark (Тёмная macOS)"
                cfg["appearance"]["custom_colors"] = THEME_PRESETS["Apple Dark (Тёмная macOS)"].copy()
                cfg["appearance"]["title_text"] = "Ключ-карта"
                cfg["appearance"]["subtitle_text"] = "Приложите карту доступа к считывателю"

            return cfg
        except Exception as e:
            print(f"[Config] Error loading config: {e}")
            return DEFAULT_CONFIG.copy()

    def save(self, data: Optional[Dict[str, Any]] = None):
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
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
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
        norm = normalize_uid(uid)
        for card in self.get_cards():
            if normalize_uid(card.get("uid", "")) == norm:
                card["enabled"] = not card.get("enabled", True)
                self.save()
                return card["enabled"]
        return None

    # --- Theme Methods ---

    def get_current_theme(self) -> Dict[str, str]:
        theme_name = self.config.get("appearance", {}).get("theme_name", "Apple Dark (Тёмная macOS)")
        if theme_name in THEME_PRESETS:
            return THEME_PRESETS[theme_name]
        return THEME_PRESETS["Apple Dark (Тёмная macOS)"]

    def set_theme(self, theme_name: str):
        if theme_name in THEME_PRESETS:
            self.config["appearance"]["theme_name"] = theme_name
            self.config["appearance"]["custom_colors"] = THEME_PRESETS[theme_name].copy()
            self.save()

    # --- Security Methods ---

    def verify_master_pin(self, pin: str) -> bool:
        stored_hash = self.config.get("security", {}).get("master_pin_hash", "")
        if not stored_hash:
            return True
        return hash_pin(pin) == stored_hash

    def set_master_pin(self, pin: str):
        self.config["security"]["master_pin_hash"] = hash_pin(pin) if pin else ""
        self.save()

    def log_event(self, event_type: str, message: str, uid: str = ""):
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{timestamp}] [{event_type:<10}] {message}"
            if uid:
                line += f" · UID: {normalize_uid(uid)}"
            line += "\n"
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            print(f"[Log] Error: {e}")

    def read_recent_logs(self, limit: int = 150) -> List[str]:
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
