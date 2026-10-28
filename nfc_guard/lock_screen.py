"""Apple Human Interface Design Lock Screen for NFC Windows Guard.
Displays minimalist, Apple-styled fullscreen lock screen with SF Pro typography across ALL displays.
"""

import time
from datetime import datetime
import tkinter as tk
from tkinter import simpledialog
import customtkinter as ctk
from typing import Optional, Callable, List

from .config import ConfigManager, normalize_uid
from .reader import ACR122UReader
from .hooks import KeyboardBlocker, set_task_manager_disabled, lock_workstation_now
from .utils import shutdown_pc, restart_pc, get_all_monitors, is_light_color
from .fonts import (
    init_apple_fonts,
    get_apple_font_family,
    font_clock,
    font_large_title,
    font_title,
    font_headline,
    font_body,
    font_caption,
    font_mono,
)
from .icons import create_nfc_glyph, create_lock_glyph, create_status_dot


class SecondaryLockOverlay(tk.Toplevel):
    """Apple-styled lock screen overlay for secondary monitors."""

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

        # Top Clock
        now = datetime.now()
        clock_frame = tk.Frame(self, bg=theme["bg_color"])
        clock_frame.pack(side="top", pady=(h * 0.12, 0))

        date_str = now.strftime("%A, %d %B").capitalize()
        # Russian day translation helper
        months_ru = {
            "January": "января", "February": "февраля", "March": "марта",
            "April": "апреля", "May": "мая", "June": "июня",
            "July": "июля", "August": "августа", "September": "сентября",
            "October": "октября", "November": "ноября", "December": "декабря"
        }
        days_ru = {
            "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
            "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье"
        }
        for en, ru in days_ru.items():
            date_str = date_str.replace(en, ru)
        for en, ru in months_ru.items():
            date_str = date_str.replace(en, ru)

        date_lbl = tk.Label(
            clock_frame,
            text=date_str,
            font=(get_apple_font_family(), 15),
            bg=theme["bg_color"],
            fg=theme["text_secondary"]
        )
        date_lbl.pack()

        time_lbl = tk.Label(
            clock_frame,
            text=now.strftime("%H:%M"),
            font=(get_apple_font_family(), 64),
            bg=theme["bg_color"],
            fg=theme["text_primary"]
        )
        time_lbl.pack(pady=(2, 0))

        # Center Card
        card = tk.Frame(
            self,
            bg=theme["card_bg"],
            highlightbackground=theme["border_color"],
            highlightthickness=1,
            padx=45,
            pady=35
        )
        card.place(relx=0.5, rely=0.58, anchor="center")

        padlock = tk.Label(
            card,
            text="🔒",
            font=("Segoe UI", 36),
            bg=theme["card_bg"],
            fg=theme["accent_color"]
        )
        padlock.pack(pady=(0, 10))

        h_lbl = tk.Label(
            card,
            text="Система заблокирована",
            font=(get_apple_font_family(), 17, "bold"),
            bg=theme["card_bg"],
            fg=theme["text_primary"]
        )
        h_lbl.pack(pady=(0, 5))

        p_lbl = tk.Label(
            card,
            text="Приложите ключ-карту к считывателю на основном экране",
            font=(get_apple_font_family(), 12),
            bg=theme["card_bg"],
            fg=theme["text_secondary"]
        )
        p_lbl.pack()

        self.bind("<Button-1>", self._redirect_focus)
        self.bind("<Key>", self._redirect_focus)

    def _redirect_focus(self, event=None):
        if self.master_ref and self.master_ref.winfo_exists():
            self.master_ref.focus_force()
            self.master_ref.lift()


class NFCLockScreen(ctk.CTk):
    """Apple-styled interactive Lock Screen on the Primary display."""

    def __init__(self, config_manager: Optional[ConfigManager] = None, on_unlock: Optional[Callable[[], None]] = None):
        super().__init__()

        # Register SF Pro fonts
        init_apple_fonts()

        self.cfg = config_manager or ConfigManager()
        self.cfg.load()
        self.on_unlock_callback = on_unlock
        self.theme = self.cfg.get_current_theme()

        # Appearance mode
        if is_light_color(self.theme["bg_color"]):
            ctk.set_appearance_mode("light")
        else:
            ctk.set_appearance_mode("dark")

        # Security state
        self.max_attempts = self.cfg.config.get("security", {}).get("max_attempts", 3)
        self.attempts_left = self.max_attempts
        self.is_unlocked = False

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

        # Start Reader loop & Clock ticker
        self.reader.start_listening()
        self._tick_clock()

        self.bind("<Escape>", lambda e: self.prompt_master_pin())

    def _setup_multi_monitor_windows(self):
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        all_monitors = get_all_monitors()
        primary_mon = next((m for m in all_monitors if m.get("primary")), all_monitors[0])

        pw, ph = primary_mon["width"], primary_mon["height"]
        px, py = primary_mon["left"], primary_mon["top"]
        self.geometry(f"{pw}x{ph}+{px}+{py}")
        self.configure(fg_color=self.theme["bg_color"])

        title_text = self.cfg.config.get("appearance", {}).get("title_text", "Ключ-карта")

        for mon in all_monitors:
            if mon == primary_mon:
                continue
            try:
                overlay = SecondaryLockOverlay(self, mon, self.theme, title_text)
                self.secondary_overlays.append(overlay)
            except Exception as e:
                print(f"[MultiMonitor] Overlay error: {e}")

        self.focus_force()
        self.grab_set()

    def _build_ui(self):
        """Builds clean, Apple-inspired interface with generous spatial rhythm."""
        self.main_container = ctk.CTkFrame(
            self,
            fg_color=self.theme["bg_color"],
            corner_radius=0
        )
        self.main_container.pack(fill="both", expand=True)

        # --- Top Header: Status Pill Badge ---
        top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent")
        top_bar.pack(fill="x", padx=48, pady=(32, 0))

        # Apple Capsule Status Pill
        self.status_pill = ctk.CTkFrame(
            top_bar,
            fg_color=self.theme["card_bg"],
            corner_radius=16,
            border_width=1,
            border_color=self.theme["border_color"],
            height=32
        )
        self.status_pill.pack(side="left")

        self.status_dot_icon = ctk.CTkLabel(
            self.status_pill,
            text="",
            image=create_status_dot(8, self.theme["warning_color"])
        )
        self.status_dot_icon.pack(side="left", padx=(12, 6), pady=6)

        self.status_text_lbl = ctk.CTkLabel(
            self.status_pill,
            text="ACR122U: Поиск считывателя...",
            font=font_caption(11),
            text_color=self.theme["text_secondary"]
        )
        self.status_text_lbl.pack(side="left", padx=(0, 14), pady=6)

        # Fallback button (top right, minimal macOS button)
        if self.cfg.config.get("security", {}).get("allow_manual_fallback", True):
            self.fallback_btn = ctk.CTkButton(
                top_bar,
                text="Вход по паролю Windows",
                font=font_body(12),
                fg_color=self.theme["card_bg"],
                border_width=1,
                border_color=self.theme["border_color"],
                text_color=self.theme["text_secondary"],
                hover_color=self.theme.get("border_color", "#27272a"),
                corner_radius=16,
                command=self.fallback_to_windows_login,
                height=32,
                width=190
            )
            self.fallback_btn.pack(side="right")

        # --- Apple Clock & Date Section ---
        clock_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        clock_container.pack(pady=(20, 10))

        self.date_lbl = ctk.CTkLabel(
            clock_container,
            text="Среда, 28 октября",
            font=font_body(16),
            text_color=self.theme["text_secondary"]
        )
        self.date_lbl.pack()

        self.clock_lbl = ctk.CTkLabel(
            clock_container,
            text="12:00",
            font=font_clock(68),
            text_color=self.theme["text_primary"]
        )
        self.clock_lbl.pack(pady=(2, 0))

        # --- Center Apple Authentication Card ---
        self.card_panel = ctk.CTkFrame(
            self.main_container,
            fg_color=self.theme["card_bg"],
            corner_radius=24,
            border_width=1,
            border_color=self.theme["border_color"],
            width=440,
            height=370,
        )
        self.card_panel.pack(pady=(15, 0))
        self.card_panel.pack_propagate(False)

        # Contactless Wave Icon
        self.icon_badge = ctk.CTkLabel(
            self.card_panel,
            text="",
            image=create_nfc_glyph(
                size=76,
                color_hex=self.theme["accent_color"],
                bg_hex=self.theme["bg_color"],
                border_hex=self.theme["border_color"]
            )
        )
        self.icon_badge.pack(pady=(30, 10))

        # Title & Subtitle
        title_text = self.cfg.config.get("appearance", {}).get("title_text", "Ключ-карта")
        self.title_lbl = ctk.CTkLabel(
            self.card_panel,
            text=title_text,
            font=font_title(19),
            text_color=self.theme["text_primary"]
        )
        self.title_lbl.pack()

        sub_text = self.cfg.config.get("appearance", {}).get("subtitle_text", "Приложите карту к считывателю")
        self.sub_lbl = ctk.CTkLabel(
            self.card_panel,
            text=sub_text,
            font=font_body(12),
            text_color=self.theme["text_secondary"]
        )
        self.sub_lbl.pack(pady=(2, 14))

        # Status Feedback Pill
        self.feedback_lbl = ctk.CTkLabel(
            self.card_panel,
            text="Ожидание NFC карты",
            font=font_headline(13),
            text_color=self.theme["accent_color"]
        )
        self.feedback_lbl.pack()

        # Detected UID Pill
        self.uid_lbl = ctk.CTkLabel(
            self.card_panel,
            text="",
            font=font_mono(11),
            text_color=self.theme["text_secondary"]
        )
        self.uid_lbl.pack(pady=(2, 8))

        # Attempts Indicator: Apple macOS password pill dots
        self.dots_container = ctk.CTkFrame(self.card_panel, fg_color="transparent")
        self.dots_container.pack(pady=(4, 8))

        self.dot_widgets = []
        for i in range(self.max_attempts):
            dot = ctk.CTkFrame(
                self.dots_container,
                width=24,
                height=6,
                corner_radius=3,
                fg_color=self.theme.get("border_color", "#27272a")
            )
            dot.pack(side="left", padx=3)
            self.dot_widgets.append(dot)

        self.attempts_lbl = ctk.CTkLabel(
            self.card_panel,
            text=f"Попыток: {self.attempts_left} из {self.max_attempts}",
            font=font_caption(11),
            text_color=self.theme["text_secondary"]
        )
        self.attempts_lbl.pack()

        # Emergency Master PIN link
        self.pin_link = ctk.CTkButton(
            self.card_panel,
            text="Мастер-PIN",
            font=font_caption(11),
            fg_color="transparent",
            text_color=self.theme["text_secondary"],
            hover_color=self.theme["bg_color"],
            height=24,
            width=90,
            command=self.prompt_master_pin
        )
        self.pin_link.pack(side="bottom", pady=12)

    def _tick_clock(self):
        """Updates date and clock every second with Apple formatting."""
        if not self.winfo_exists() or self.is_unlocked:
            return

        now = datetime.now()
        self.clock_lbl.configure(text=now.strftime("%H:%M"))

        # Localized Russian date
        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                  "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_name = weekdays[now.weekday()]
        month_name = months[now.month - 1]
        self.date_lbl.configure(text=f"{day_name}, {now.day} {month_name}")

        self.after(1000, self._tick_clock)

    # --- Callbacks ---

    def _on_reader_status_threadsafe(self, connected: bool, name: str):
        self.after(0, self._update_reader_status, connected, name)

    def _update_reader_status(self, connected: bool, name: str):
        if connected:
            self.status_dot_icon.configure(image=create_status_dot(8, self.theme["success_color"]))
            clean_name = "ACR122U" if "ACR122" in name.upper() else name[:22]
            self.status_text_lbl.configure(
                text=f"{clean_name} · Готов",
                text_color=self.theme["text_primary"]
            )
        else:
            self.status_dot_icon.configure(image=create_status_dot(8, self.theme["error_color"]))
            self.status_text_lbl.configure(
                text="Считыватель не найден",
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
        card_name = card_info.get("name", "Карта") if card_info else "Неизвестная карта"

        if self.cfg.config.get("appearance", {}).get("show_uid_on_screen", True):
            self.uid_lbl.configure(text=norm_uid)

        if is_auth:
            self._access_granted(norm_uid, card_name)
        else:
            self._access_denied(norm_uid)

    def _handle_card_removed(self):
        if not self.is_unlocked and self.attempts_left > 0:
            self.feedback_lbl.configure(
                text="Ожидание NFC карты",
                text_color=self.theme["accent_color"]
            )

    def _access_granted(self, uid: str, name: str):
        self.is_unlocked = True
        self.cfg.log_event("SUCCESS", f"Доступ: {name}", uid)

        if self.cfg.config.get("security", {}).get("beep_on_success", True):
            self.reader.beep_success()

        # Visual feedback: update glyph to Apple green
        self.icon_badge.configure(
            image=create_nfc_glyph(
                size=76,
                color_hex=self.theme["success_color"],
                bg_hex=self.theme["bg_color"],
                border_hex=self.theme["success_color"]
            )
        )
        self.feedback_lbl.configure(
            text=f"Доступ разрешен · {name}",
            text_color=self.theme["success_color"]
        )

        self.after(550, self.unlock_and_close)

    def _access_denied(self, uid: str):
        self.attempts_left -= 1
        self.cfg.log_event("DENIED", f"Отказ. Попыток осталось {self.attempts_left}/{self.max_attempts}", uid)

        if self.cfg.config.get("security", {}).get("beep_on_error", True):
            self.reader.beep_error()

        # Update glyph to error red
        self.icon_badge.configure(
            image=create_nfc_glyph(
                size=76,
                color_hex=self.theme["error_color"],
                bg_hex=self.theme["bg_color"],
                border_hex=self.theme["error_color"]
            )
        )
        self.feedback_lbl.configure(
            text=f"Карта не распознана · Попытка {self.max_attempts - self.attempts_left} из {self.max_attempts}",
            text_color=self.theme["error_color"]
        )

        # Update Apple pill dots: change failed ones to red
        failed_count = self.max_attempts - self.attempts_left
        for i, dot in enumerate(self.dot_widgets):
            if i < failed_count:
                dot.configure(fg_color=self.theme["error_color"])

        self.attempts_lbl.configure(
            text=f"Попыток: {self.attempts_left} из {self.max_attempts}",
            text_color=self.theme["error_color"]
        )

        if self.attempts_left <= 0:
            self._handle_attempts_exhausted()

    def _handle_attempts_exhausted(self):
        self.cfg.log_event("LOCKOUT", "Исчерпан лимит попыток. Переход к штатному входу Windows.")
        self.reader.beep_lockout()

        self.feedback_lbl.configure(
            text="Лимит исчерпан. Переход к штатному входу...",
            text_color=self.theme["error_color"]
        )

        action = self.cfg.config.get("security", {}).get("action_on_fail", "lock_workstation")
        self.after(900, lambda: self._execute_fail_action(action))

    def _execute_fail_action(self, action: str):
        self._cleanup()
        if action == "shutdown":
            shutdown_pc()
        elif action == "restart":
            restart_pc()
        else:
            lock_workstation_now()
        self.destroy()

    def fallback_to_windows_login(self):
        self.cfg.log_event("FALLBACK", "Штатный вход Windows")
        self._cleanup()
        lock_workstation_now()
        self.destroy()

    def prompt_master_pin(self):
        pin = simpledialog.askstring("Мастер-PIN", "Введите экстренный PIN-код или пароль:", parent=self, show="*")
        if pin is not None:
            if self.cfg.verify_master_pin(pin):
                self.cfg.log_event("MASTER_PIN", "Разблокировка по мастер-PIN")
                self.is_unlocked = True
                self.feedback_lbl.configure(
                    text="Мастер-PIN подтвержден",
                    text_color=self.theme["success_color"]
                )
                self.after(400, self.unlock_and_close)
            else:
                self.cfg.log_event("MASTER_PIN_FAIL", "Неверный мастер-PIN")
                self.feedback_lbl.configure(
                    text="Неверный мастер-PIN",
                    text_color=self.theme["error_color"]
                )

    def unlock_and_close(self):
        self._cleanup()
        self.destroy()
        if self.on_unlock_callback:
            self.on_unlock_callback()

    def _cleanup(self):
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
