"""Lock Screen Window for NFC Windows Guard.
Displays fullscreen, topmost blocking overlay across ALL monitors requiring authorized NFC card.
Handles attempt tracking, buzzer feedback, and fallback to Windows authentication.
"""

import time
import threading
import tkinter as tk
from tkinter import simpledialog
import customtkinter as ctk
from typing import Optional, Callable, List

from .config import ConfigManager, normalize_uid
from .reader import ACR122UReader
from .hooks import KeyboardBlocker, set_task_manager_disabled, lock_workstation_now
from .utils import shutdown_pc, restart_pc, get_all_monitors, is_light_color


class SecondaryLockOverlay(tk.Toplevel):
    """Fullscreen blocking shield for secondary displays (Monitor 2, 3, etc.)."""

    def __init__(self, master, monitor_info: dict, theme: dict, title_text: str):
        super().__init__(master)
        self.master_ref = master
        self.theme = theme

        self.overrideredirect(True)
        self.attributes("-topmost", True)

        w, h = monitor_info["width"], monitor_info["height"]
        x, y = monitor_info["left"], monitor_info["top"]
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.configure(bg=theme["bg_color"])

        # Center frame
        center_frame = tk.Frame(
            self,
            bg=theme["card_bg"],
            highlightbackground=theme["border_color"],
            highlightthickness=2,
            padx=40,
            pady=40
        )
        center_frame.place(relx=0.5, rely=0.5, anchor="center")

        icon_lbl = tk.Label(
            center_frame,
            text="🔒",
            font=("Segoe UI", 48),
            bg=theme["card_bg"],
            fg=theme["accent_color"]
        )
        icon_lbl.pack(pady=(10, 15))

        title_lbl = tk.Label(
            center_frame,
            text=title_text,
            font=("Segoe UI", 20, "bold"),
            bg=theme["card_bg"],
            fg=theme["text_primary"]
        )
        title_lbl.pack(pady=(0, 5))

        status_lbl = tk.Label(
            center_frame,
            text="ДОСТУП ЗАБЛОКИРОВАН",
            font=("Segoe UI", 12, "bold"),
            bg=theme["card_bg"],
            fg=theme["accent_color"]
        )
        status_lbl.pack(pady=(0, 15))

        sub_lbl = tk.Label(
            center_frame,
            text="Приложите ключ-карту к считывателю ACR122U на основном экране",
            font=("Segoe UI", 12),
            bg=theme["card_bg"],
            fg=theme["text_secondary"]
        )
        sub_lbl.pack(pady=(0, 10))

        # Forward focus to main lock window on any interaction
        self.bind("<Button-1>", self._redirect_focus)
        self.bind("<Key>", self._redirect_focus)

    def _redirect_focus(self, event=None):
        if self.master_ref and self.master_ref.winfo_exists():
            self.master_ref.focus_force()
            self.master_ref.lift()


class NFCLockScreen(ctk.CTk):
    """Fullscreen Secure Lock Screen Overlay on Primary Monitor."""

    def __init__(self, config_manager: Optional[ConfigManager] = None, on_unlock: Optional[Callable[[], None]] = None):
        super().__init__()

        self.cfg = config_manager or ConfigManager()
        self.cfg.load()
        self.on_unlock_callback = on_unlock
        self.theme = self.cfg.get_current_theme()

        # Appearance mode based on theme luminance
        if is_light_color(self.theme["bg_color"]):
            ctk.set_appearance_mode("light")
        else:
            ctk.set_appearance_mode("dark")

        # Security state
        self.max_attempts = self.cfg.config.get("security", {}).get("max_attempts", 3)
        self.attempts_left = self.max_attempts
        self.is_unlocked = False

        # Secondary monitor windows list
        self.secondary_overlays: List[SecondaryLockOverlay] = []

        # System blocking
        self.kbd_blocker = KeyboardBlocker()
        self.kbd_blocker.install()
        set_task_manager_disabled(True)

        # Reader initialization
        self.reader = ACR122UReader(
            on_card_detected=self._on_card_detected_threadsafe,
            on_card_removed=self._on_card_removed_threadsafe,
            on_status_change=self._on_reader_status_threadsafe,
        )

        # Setup Windows & Multi-Monitor
        self._setup_multi_monitor_windows()
        self._build_ui()

        # Start Reader loop
        self.reader.start_listening()

        # Fail-safe keyboard binding: Escape opens Emergency PIN prompt
        self.bind("<Escape>", lambda e: self.prompt_master_pin())

    def _setup_multi_monitor_windows(self):
        """Identifies primary and secondary monitors and spawns coverage on ALL displays."""
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        all_monitors = get_all_monitors()
        primary_mon = next((m for m in all_monitors if m.get("primary")), all_monitors[0])

        # Position main interactive window on Primary monitor
        pw, ph = primary_mon["width"], primary_mon["height"]
        px, py = primary_mon["left"], primary_mon["top"]
        self.geometry(f"{pw}x{ph}+{px}+{py}")
        self.configure(fg_color=self.theme["bg_color"])

        # Title for screens
        title_text = self.cfg.config.get("appearance", {}).get("title_text", "NFC WINDOWS GUARD")

        # Spawn blocking overlay on every secondary monitor
        for mon in all_monitors:
            if mon == primary_mon:
                continue
            try:
                overlay = SecondaryLockOverlay(self, mon, self.theme, title_text)
                self.secondary_overlays.append(overlay)
            except Exception as e:
                print(f"[MultiMonitor] Error creating overlay for monitor {mon}: {e}")

        # Force grab focus
        self.focus_force()
        self.grab_set()

    def _build_ui(self):
        """Constructs the modern lock screen interface with active theme colors."""
        self.main_container = ctk.CTkFrame(
            self,
            fg_color=self.theme["bg_color"],
            corner_radius=0
        )
        self.main_container.pack(fill="both", expand=True)

        # --- Top Header Bar ---
        top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent")
        top_bar.pack(fill="x", padx=40, pady=25)

        # App Brand & Status Badge
        self.status_badge = ctk.CTkLabel(
            top_bar,
            text="● Считыватель: поиск ACR122U...",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self.theme["warning_color"]
        )
        self.status_badge.pack(side="left")

        # Emergency fallback button in top right
        if self.cfg.config.get("security", {}).get("allow_manual_fallback", True):
            self.fallback_btn = ctk.CTkButton(
                top_bar,
                text="Штатный вход Windows (Пароль) ➔",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                fg_color="transparent",
                border_width=1,
                border_color=self.theme["border_color"],
                text_color=self.theme["text_secondary"],
                hover_color=self.theme["card_bg"],
                command=self.fallback_to_windows_login,
                height=32,
            )
            self.fallback_btn.pack(side="right")

        # --- Center Shield Panel ---
        center_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        center_frame.pack(expand=True)

        # Card container with glowing border
        self.card_panel = ctk.CTkFrame(
            center_frame,
            fg_color=self.theme["card_bg"],
            corner_radius=20,
            border_width=2,
            border_color=self.theme["border_color"],
            width=540,
            height=460,
        )
        self.card_panel.pack(padx=20, pady=20)
        self.card_panel.pack_propagate(False)

        # Title
        title_text = self.cfg.config.get("appearance", {}).get("title_text", "NFC WINDOWS GUARD")
        self.title_lbl = ctk.CTkLabel(
            self.card_panel,
            text=title_text,
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=self.theme["text_primary"],
        )
        self.title_lbl.pack(pady=(35, 10))

        # Subtitle
        sub_text = self.cfg.config.get("appearance", {}).get("subtitle_text", "Приложите карту к считывателю")
        self.sub_lbl = ctk.CTkLabel(
            self.card_panel,
            text=sub_text,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=self.theme["text_secondary"],
        )
        self.sub_lbl.pack(pady=(0, 20))

        # Visual NFC Icon / Badge
        self.icon_frame = ctk.CTkFrame(
            self.card_panel,
            width=110,
            height=110,
            corner_radius=55,
            fg_color=self.theme["bg_color"],
            border_width=2,
            border_color=self.theme["accent_color"],
        )
        self.icon_frame.pack(pady=10)
        self.icon_frame.pack_propagate(False)

        self.nfc_icon = ctk.CTkLabel(
            self.icon_frame,
            text="📡",
            font=ctk.CTkFont(size=44),
        )
        self.nfc_icon.place(relx=0.5, rely=0.5, anchor="center")

        # Dynamic Status Feedback Label
        self.feedback_lbl = ctk.CTkLabel(
            self.card_panel,
            text="Ожидание карты...",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=self.theme["accent_color"],
        )
        self.feedback_lbl.pack(pady=(20, 5))

        # Detected UID detail label
        self.uid_lbl = ctk.CTkLabel(
            self.card_panel,
            text="",
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color=self.theme["text_secondary"],
        )
        self.uid_lbl.pack(pady=(0, 15))

        # Attempts Counter
        self.attempts_frame = ctk.CTkFrame(self.card_panel, fg_color="transparent")
        self.attempts_frame.pack(pady=(5, 10))

        self.attempts_lbl = ctk.CTkLabel(
            self.attempts_frame,
            text=f"Попыток осталось: {self.attempts_left} из {self.max_attempts}",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self.theme["text_primary"],
        )
        self.attempts_lbl.pack()

        # Dots representation
        self.dots_lbl = ctk.CTkLabel(
            self.attempts_frame,
            text="● " * self.attempts_left,
            font=ctk.CTkFont(family="Segoe UI", size=18),
            text_color=self.theme["accent_color"],
        )
        self.dots_lbl.pack(pady=(2, 0))

        # Bottom Footer in Card
        self.footer_btn = ctk.CTkButton(
            self.card_panel,
            text="Ввести мастер-PIN",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            text_color=self.theme["text_secondary"],
            hover_color=self.theme["bg_color"],
            command=self.prompt_master_pin,
            height=26,
            width=140
        )
        self.footer_btn.pack(side="bottom", pady=15)

    # --- Thread-Safe Callbacks from Reader ---

    def _on_reader_status_threadsafe(self, connected: bool, name: str):
        self.after(0, self._update_reader_status, connected, name)

    def _update_reader_status(self, connected: bool, name: str):
        if connected:
            self.status_badge.configure(
                text=f"● Считыватель: {name} (Готов)",
                text_color=self.theme["success_color"]
            )
        else:
            self.status_badge.configure(
                text="● Считыватель: не подключен! Вставьте ACR122U",
                text_color=self.theme["error_color"]
            )

    def _on_card_detected_threadsafe(self, uid: str):
        self.after(0, self._handle_card_detected, uid)

    def _on_card_removed_threadsafe(self):
        self.after(0, self._handle_card_removed)

    def _handle_card_detected(self, uid: str):
        if self.is_unlocked:
            return

        norm_uid = normalize_uid(uid)
        is_auth = self.cfg.is_card_authorized(norm_uid)
        card_info = self.cfg.get_card_by_uid(norm_uid)
        card_name = card_info.get("name", "Неизвестная карта") if card_info else "Неизвестная карта"

        # Show detected UID
        if self.cfg.config.get("appearance", {}).get("show_uid_on_screen", True):
            self.uid_lbl.configure(text=f"UID: {norm_uid}")

        if is_auth:
            self._access_granted(norm_uid, card_name)
        else:
            self._access_denied(norm_uid)

    def _handle_card_removed(self):
        if not self.is_unlocked and self.attempts_left > 0:
            self.card_panel.configure(border_color=self.theme["border_color"])
            self.icon_frame.configure(border_color=self.theme["accent_color"])
            self.feedback_lbl.configure(
                text="Ожидание карты...",
                text_color=self.theme["accent_color"]
            )

    def _access_granted(self, uid: str, name: str):
        """Handles successful card authentication."""
        self.is_unlocked = True
        self.cfg.log_event("SUCCESS", f"Доступ разрешен: {name}", uid)

        # Hardware Buzzer
        if self.cfg.config.get("security", {}).get("beep_on_success", True):
            self.reader.beep_success()

        # UI Visual Flash
        self.card_panel.configure(border_color=self.theme["success_color"])
        self.icon_frame.configure(border_color=self.theme["success_color"])
        self.feedback_lbl.configure(
            text=f"✓ Доступ разрешен: {name}!",
            text_color=self.theme["success_color"]
        )
        self.nfc_icon.configure(text="🔓")

        # Smooth unlock after 600ms
        self.after(600, self.unlock_and_close)

    def _access_denied(self, uid: str):
        """Handles unauthorized card tap."""
        self.attempts_left -= 1
        self.cfg.log_event("DENIED", f"Отклонено. Попыток осталось {self.attempts_left}/{self.max_attempts}", uid)

        # Hardware Buzzer
        if self.cfg.config.get("security", {}).get("beep_on_error", True):
            self.reader.beep_error()

        # UI Visual Alert
        self.card_panel.configure(border_color=self.theme["error_color"])
        self.icon_frame.configure(border_color=self.theme["error_color"])
        self.feedback_lbl.configure(
            text=f"✗ Неверная карта! Попытка {self.max_attempts - self.attempts_left} из {self.max_attempts}",
            text_color=self.theme["error_color"]
        )
        self.nfc_icon.configure(text="⛔")

        # Update attempts
        self.attempts_lbl.configure(
            text=f"Попыток осталось: {self.attempts_left} из {self.max_attempts}",
            text_color=self.theme["error_color"]
        )
        self.dots_lbl.configure(
            text=("✗ " * (self.max_attempts - self.attempts_left)) + ("● " * self.attempts_left),
            text_color=self.theme["error_color"]
        )

        # Check if attempts exhausted
        if self.attempts_left <= 0:
            self._handle_attempts_exhausted()

    def _handle_attempts_exhausted(self):
        """Triggered when 3 attempts fail."""
        self.cfg.log_event("LOCKOUT", "Превышено число попыток. Переход к штатному способу входа.")
        self.reader.beep_lockout()

        self.feedback_lbl.configure(
            text="Превышено число попыток! Переход к штатному входу...",
            text_color=self.theme["error_color"]
        )

        action = self.cfg.config.get("security", {}).get("action_on_fail", "lock_workstation")
        self.after(1000, lambda: self._execute_fail_action(action))

    def _execute_fail_action(self, action: str):
        """Releases the overlay and activates standard Windows login or action."""
        self._cleanup()

        if action == "shutdown":
            shutdown_pc()
        elif action == "restart":
            restart_pc()
        else:
            # Default: lock_workstation ("штатным способом")
            lock_workstation_now()

        self.destroy()

    def fallback_to_windows_login(self):
        """Immediately closes lock overlay and invokes native Windows lock screen."""
        self.cfg.log_event("FALLBACK", "Ручной переход к штатному входу Windows")
        self._cleanup()
        lock_workstation_now()
        self.destroy()

    def prompt_master_pin(self):
        """Emergency PIN entry modal for master bypass."""
        pin = simpledialog.askstring("Экстренный вход", "Введите мастер-PIN или пароль:", parent=self, show="*")
        if pin is not None:
            if self.cfg.verify_master_pin(pin):
                self.cfg.log_event("MASTER_PIN", "Разблокировка по мастер-PIN")
                self.is_unlocked = True
                self.feedback_lbl.configure(
                    text="✓ Мастер-PIN подтвержден! Вход...",
                    text_color=self.theme["success_color"]
                )
                self.after(500, self.unlock_and_close)
            else:
                self.cfg.log_event("MASTER_PIN_FAIL", "Неверный ввод мастер-PIN")
                self.feedback_lbl.configure(
                    text="✗ Неверный мастер-PIN!",
                    text_color=self.theme["error_color"]
                )

    def unlock_and_close(self):
        """Safely tears down hooks, stops reader, destroys secondary overlays, and closes."""
        self._cleanup()
        self.destroy()
        if self.on_unlock_callback:
            self.on_unlock_callback()

    def _cleanup(self):
        """Releases secondary overlays, system hooks, and reader."""
        # Destroy all secondary monitor screens
        for overlay in self.secondary_overlays:
            try:
                overlay.destroy()
            except Exception:
                pass
        self.secondary_overlays.clear()

        try:
            self.reader.stop_listening()
        except Exception:
            pass
        try:
            self.kbd_blocker.uninstall()
        except Exception:
            pass
        try:
            set_task_manager_disabled(False)
        except Exception:
            pass
