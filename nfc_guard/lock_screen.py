"""Apple Human Interface Design Lock Screen for NFC Windows Guard.
Dual unlock methods: NFC Keycard (ACR122U) or Standard Windows Password/PIN.
"""

from datetime import datetime
import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable, List

from .config import ConfigManager, normalize_uid
from .reader import ACR122UReader
from .hooks import KeyboardBlocker, set_task_manager_disabled, lock_workstation_now
from .utils import (
    shutdown_pc,
    restart_pc,
    get_all_monitors,
    is_light_color,
    verify_windows_password,
)
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
from .icons import create_nfc_glyph, create_status_dot


class SecondaryLockOverlay(tk.Toplevel):
    """Clean Apple-styled lock screen overlay for secondary displays."""

    def __init__(self, master, monitor_info: dict, theme: dict):
        super().__init__(master)
        self.master_ref = master
        self.theme = theme

        self.overrideredirect(True)
        self.attributes("-topmost", True)

        w, h = monitor_info["width"], monitor_info["height"]
        x, y = monitor_info["left"], monitor_info["top"]
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.configure(bg=theme["bg_color"])

        # Clock centered at 18% height
        clock_frame = tk.Frame(self, bg=theme["bg_color"])
        clock_frame.place(relx=0.5, rely=0.20, anchor="center")

        now = datetime.now()
        date_str = now.strftime("%A, %d %B").capitalize()
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

        self.sec_date_lbl = tk.Label(
            clock_frame,
            text=date_str,
            font=(get_apple_font_family(), 15),
            bg=theme["bg_color"],
            fg=theme["text_secondary"]
        )
        self.sec_date_lbl.pack()

        self.sec_time_lbl = tk.Label(
            clock_frame,
            text=now.strftime("%H:%M"),
            font=(get_apple_font_family(), 64),
            bg=theme["bg_color"],
            fg=theme["text_primary"]
        )
        self.sec_time_lbl.pack(pady=(2, 0))

        # Card centered at 55%
        card = tk.Frame(
            self,
            bg=theme["card_bg"],
            highlightbackground=theme["border_color"],
            highlightthickness=1,
            padx=40,
            pady=32
        )
        card.place(relx=0.5, rely=0.55, anchor="center")

        padlock = tk.Label(
            card,
            text="🔒",
            font=("Segoe UI", 32),
            bg=theme["card_bg"],
            fg=theme["accent_color"]
        )
        padlock.pack(pady=(0, 8))

        h_lbl = tk.Label(
            card,
            text="Система заблокирована",
            font=(get_apple_font_family(), 16, "bold"),
            bg=theme["card_bg"],
            fg=theme["text_primary"]
        )
        h_lbl.pack(pady=(0, 4))

        p_lbl = tk.Label(
            card,
            text="Приложите ключ-карту или введите пароль на основном экране",
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
    """Apple-styled interactive Lock Screen supporting both NFC and Password authentication."""

    def __init__(self, config_manager: Optional[ConfigManager] = None, on_unlock: Optional[Callable[[], None]] = None):
        super().__init__()

        init_apple_fonts()

        self.cfg = config_manager or ConfigManager()
        self.cfg.load()
        self.on_unlock_callback = on_unlock
        self.theme = self.cfg.get_current_theme()

        if is_light_color(self.theme["bg_color"]):
            ctk.set_appearance_mode("light")
        else:
            ctk.set_appearance_mode("dark")

        # Security state
        self.max_attempts = self.cfg.config.get("security", {}).get("max_attempts", 3)
        self.attempts_left = self.max_attempts
        self.is_unlocked = False
        self.card_locked_out = False

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

        self._setup_multi_monitor_windows()
        self._build_ui()

        self.reader.start_listening()
        self._tick_clock()

        self.bind("<Escape>", lambda e: self.fallback_to_windows_login())

    def _setup_multi_monitor_windows(self):
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        all_monitors = get_all_monitors()
        primary_mon = next((m for m in all_monitors if m.get("primary")), all_monitors[0])

        pw, ph = primary_mon["width"], primary_mon["height"]
        px, py = primary_mon["left"], primary_mon["top"]
        self.geometry(f"{pw}x{ph}+{px}+{py}")
        self.configure(fg_color=self.theme["bg_color"])

        for mon in all_monitors:
            if mon == primary_mon:
                continue
            try:
                overlay = SecondaryLockOverlay(self, mon, self.theme)
                self.secondary_overlays.append(overlay)
            except Exception as e:
                print(f"[MultiMonitor] Overlay error: {e}")

        self.focus_force()
        self.grab_set()

    def _build_ui(self):
        """Constructs balanced, Apple-inspired layout with clean vertical spacing."""
        self.main_container = ctk.CTkFrame(
            self,
            fg_color=self.theme["bg_color"],
            corner_radius=0
        )
        self.main_container.pack(fill="both", expand=True)

        # --- Top Header: Status Pill & Native Fallback Link ---
        top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent")
        top_bar.pack(fill="x", padx=48, pady=(28, 0))

        # Status Capsule
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
            text="ACR122U: Поиск...",
            font=font_caption(11),
            text_color=self.theme["text_secondary"]
        )
        self.status_text_lbl.pack(side="left", padx=(0, 14), pady=6)

        # Native Windows Lock button (top right)
        self.fallback_btn = ctk.CTkButton(
            top_bar,
            text="Штатный экран Windows ➔",
            font=font_body(12),
            fg_color=self.theme["card_bg"],
            border_width=1,
            border_color=self.theme["border_color"],
            text_color=self.theme["text_secondary"],
            hover_color=self.theme["border_color"],
            corner_radius=14,
            command=self.fallback_to_windows_login,
            height=30,
            width=190
        )
        self.fallback_btn.pack(side="right")

        # --- Apple Clock (Centered at ~18% height) ---
        self.clock_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.clock_container.place(relx=0.5, rely=0.18, anchor="center")

        self.date_lbl = ctk.CTkLabel(
            self.clock_container,
            text="",
            font=font_body(15),
            text_color=self.theme["text_secondary"]
        )
        self.date_lbl.pack()

        self.clock_lbl = ctk.CTkLabel(
            self.clock_container,
            text="",
            font=font_clock(68),
            text_color=self.theme["text_primary"]
        )
        self.clock_lbl.pack(pady=(2, 0))

        # --- Center Authentication Card (Centered at ~55% height) ---
        self.card_panel = ctk.CTkFrame(
            self.main_container,
            fg_color=self.theme["card_bg"],
            corner_radius=24,
            border_width=1,
            border_color=self.theme["border_color"],
            width=460,
        )
        self.card_panel.place(relx=0.5, rely=0.55, anchor="center")

        card_content = ctk.CTkFrame(self.card_panel, fg_color="transparent")
        card_content.pack(padx=36, pady=30, fill="both")

        # Contactless Icon Glyph
        self.icon_badge = ctk.CTkLabel(
            card_content,
            text="",
            image=create_nfc_glyph(
                size=68,
                color_hex=self.theme["accent_color"],
                bg_hex=self.theme["bg_color"],
                border_hex=self.theme["border_color"]
            )
        )
        self.icon_badge.pack(pady=(0, 10))

        # Title & Subtitle
        title_text = self.cfg.config.get("appearance", {}).get("title_text", "Вход в систему")
        self.title_lbl = ctk.CTkLabel(
            card_content,
            text=title_text,
            font=font_title(19),
            text_color=self.theme["text_primary"]
        )
        self.title_lbl.pack()

        sub_text = self.cfg.config.get("appearance", {}).get("subtitle_text", "Приложите карту доступа или введите пароль")
        self.sub_lbl = ctk.CTkLabel(
            card_content,
            text=sub_text,
            font=font_body(12),
            text_color=self.theme["text_secondary"]
        )
        self.sub_lbl.pack(pady=(2, 12))

        # Dynamic Status / Feedback
        self.feedback_lbl = ctk.CTkLabel(
            card_content,
            text="Ожидание NFC-карты",
            font=font_headline(13),
            text_color=self.theme["accent_color"]
        )
        self.feedback_lbl.pack()

        # Attempts Indicator: 3 Apple capsule pills
        self.dots_container = ctk.CTkFrame(card_content, fg_color="transparent")
        self.dots_container.pack(pady=(6, 14))

        self.dot_widgets = []
        for i in range(self.max_attempts):
            dot = ctk.CTkFrame(
                self.dots_container,
                width=24,
                height=5,
                corner_radius=3,
                fg_color=self.theme.get("border_color", "#27272a")
            )
            dot.pack(side="left", padx=3)
            self.dot_widgets.append(dot)

        # Standard Password / PIN Input Row (Seamless Alternative Unlock)
        pwd_row = ctk.CTkFrame(card_content, fg_color="transparent")
        pwd_row.pack(fill="x", pady=(0, 6))

        self.pwd_entry = ctk.CTkEntry(
            pwd_row,
            placeholder_text="Пароль Windows или PIN",
            font=font_body(13),
            show="•",
            fg_color=self.theme["bg_color"],
            border_color=self.theme["border_color"],
            corner_radius=12,
            height=38,
            width=290
        )
        self.pwd_entry.pack(side="left", padx=(0, 8))
        self.pwd_entry.bind("<Return>", lambda e: self.verify_password_entered())

        self.submit_btn = ctk.CTkButton(
            pwd_row,
            text="➔",
            font=font_headline(14),
            fg_color=self.theme["accent_color"],
            hover_color=self.theme["accent_hover"],
            corner_radius=12,
            height=38,
            width=48,
            command=self.verify_password_entered
        )
        self.submit_btn.pack(side="left")

        # Focus password entry
        self.pwd_entry.focus_set()

    def _tick_clock(self):
        if not self.winfo_exists() or self.is_unlocked:
            return

        now = datetime.now()
        self.clock_lbl.configure(text=now.strftime("%H:%M"))

        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                  "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        self.date_lbl.configure(text=f"{weekdays[now.weekday()]}, {now.day} {months[now.month - 1]}")

        for sec in self.secondary_overlays:
            try:
                sec.sec_time_lbl.configure(text=now.strftime("%H:%M"))
            except Exception:
                pass

        self.after(1000, self._tick_clock)

    # --- Callbacks ---

    def _on_reader_status_threadsafe(self, connected: bool, name: str):
        self.after(0, self._update_reader_status, connected, name)

    def _update_reader_status(self, connected: bool, name: str):
        if connected:
            self.status_dot_icon.configure(image=create_status_dot(8, self.theme["success_color"]))
            clean_name = "ACR122U" if "ACR122" in name.upper() else name[:20]
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
        if self.is_unlocked or self.card_locked_out:
            return

        norm_uid = normalize_uid(uid)
        is_auth = self.cfg.is_card_authorized(norm_uid)
        card_info = self.cfg.get_card_by_uid(norm_uid)
        card_name = card_info.get("name", "Ключ") if card_info else "Неизвестная карта"

        if is_auth:
            self._access_granted_by_card(norm_uid, card_name)
        else:
            self._access_denied_card(norm_uid)

    def _handle_card_removed(self):
        if not self.is_unlocked and not self.card_locked_out:
            self.feedback_lbl.configure(
                text="Ожидание NFC-карты",
                text_color=self.theme["accent_color"]
            )

    def _access_granted_by_card(self, uid: str, name: str):
        self.is_unlocked = True
        self.cfg.log_event("SUCCESS", f"Разблокировка по NFC: {name}", uid)

        if self.cfg.config.get("security", {}).get("beep_on_success", True):
            self.reader.beep_success()

        self.icon_badge.configure(
            image=create_nfc_glyph(
                size=68,
                color_hex=self.theme["success_color"],
                bg_hex=self.theme["bg_color"],
                border_hex=self.theme["success_color"]
            )
        )
        self.feedback_lbl.configure(
            text=f"Доступ разрешен · {name}",
            text_color=self.theme["success_color"]
        )

        self.after(450, self.unlock_and_close)

    def _access_denied_card(self, uid: str):
        self.attempts_left -= 1
        self.cfg.log_event("DENIED", f"Неверная карта. Осталось {self.attempts_left}/{self.max_attempts}", uid)

        if self.cfg.config.get("security", {}).get("beep_on_error", True):
            self.reader.beep_error()

        self.icon_badge.configure(
            image=create_nfc_glyph(
                size=68,
                color_hex=self.theme["error_color"],
                bg_hex=self.theme["bg_color"],
                border_hex=self.theme["error_color"]
            )
        )
        self.feedback_lbl.configure(
            text=f"Карта не распознана · Попытка {self.max_attempts - self.attempts_left} из {self.max_attempts}",
            text_color=self.theme["error_color"]
        )

        failed_count = self.max_attempts - self.attempts_left
        for i, dot in enumerate(self.dot_widgets):
            if i < failed_count:
                dot.configure(fg_color=self.theme["error_color"])

        if self.attempts_left <= 0:
            self.card_locked_out = True
            self.reader.beep_lockout()
            self.feedback_lbl.configure(
                text="Лимит попыток карты исчерпан. Введите пароль.",
                text_color=self.theme["error_color"]
            )
            self.pwd_entry.focus_set()

    def verify_password_entered(self):
        """Standard method authentication right from the lock screen."""
        pwd = self.pwd_entry.get().strip()
        if not pwd:
            return

        # Check either Master PIN or real Windows password
        is_pin_ok = self.cfg.verify_master_pin(pwd)
        is_win_ok = verify_windows_password(pwd)

        if is_pin_ok or is_win_ok:
            method = "Мастер-PIN" if is_pin_ok else "Штатный пароль Windows"
            self.is_unlocked = True
            self.cfg.log_event("SUCCESS", f"Разблокировка: {method}")

            self.feedback_lbl.configure(
                text=f"✓ {method} подтвержден",
                text_color=self.theme["success_color"]
            )
            self.pwd_entry.configure(border_color=self.theme["success_color"])
            self.after(400, self.unlock_and_close)
        else:
            self.cfg.log_event("AUTH_FAIL", "Неверный ввод пароля/PIN")
            self.feedback_lbl.configure(
                text="✗ Неверный пароль или PIN",
                text_color=self.theme["error_color"]
            )
            self.pwd_entry.configure(border_color=self.theme["error_color"])
            self.pwd_entry.delete(0, "end")
            self.pwd_entry.focus_set()

    def fallback_to_windows_login(self):
        """Immediately delegates to native Windows lock screen without looping."""
        self.cfg.log_event("FALLBACK", "Переход к штатному экрану Windows")
        self._cleanup()
        lock_workstation_now()
        self.destroy()

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
