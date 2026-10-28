"""Apple macOS-inspired System Settings Control Panel for NFC Windows Guard.
Clean sidebar navigation, grouped cards, SF Pro typography, and live lock screen preview.
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import Optional

from .config import ConfigManager, THEME_PRESETS, normalize_uid
from .reader import ACR122UReader
from .utils import (
    is_autostart_enabled,
    set_autostart,
    is_daemon_running,
    get_pythonw_executable,
    is_win_l_intercepted,
)
from .fonts import (
    init_apple_fonts,
    font_large_title,
    font_title,
    font_headline,
    font_body,
    font_caption,
    font_mono,
    font_clock,
)
from .icons import create_nfc_glyph, create_status_dot


class SettingsWindow(ctk.CTk):
    """macOS-inspired Control Panel with sidebar navigation and grouped surfaces."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        super().__init__()

        init_apple_fonts()
        self.cfg = config_manager or ConfigManager()
        self.cfg.load()
        self.reader = ACR122UReader()

        self.title("NFC Guard — Настройки")
        self.geometry("980x660")
        self.minsize(920, 620)

        self.current_theme = self.cfg.get_current_theme()
        ctk.set_appearance_mode("dark")
        self.configure(fg_color="#0d0d0f")

        self.active_nav = "cards"
        self._build_layout()
        self.show_view("cards")
        self._update_daemon_status_lbl()

    def _build_layout(self):
        self.sidebar = ctk.CTkFrame(self, width=230, fg_color="#141417", corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.content_area = ctk.CTkFrame(self, fg_color="#0d0d0f", corner_radius=0)
        self.content_area.pack(side="right", fill="both", expand=True)

        # Header in sidebar
        sb_brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sb_brand.pack(fill="x", padx=18, pady=(24, 20))

        title_row = ctk.CTkFrame(sb_brand, fg_color="transparent")
        title_row.pack(fill="x")

        app_title = ctk.CTkLabel(
            title_row,
            text="NFC Guard",
            font=font_large_title(18),
            text_color="#f5f5f7"
        )
        app_title.pack(side="left")

        ver_pill = ctk.CTkFrame(title_row, fg_color="#27272a", corner_radius=8, height=20)
        ver_pill.pack(side="right")
        ctk.CTkLabel(
            ver_pill,
            text="v2.1",
            font=font_caption(10),
            text_color="#86868b"
        ).pack(padx=6, pady=1)

        sb_sub = ctk.CTkLabel(
            sb_brand,
            text="ACS ACR122U Security",
            font=font_caption(11),
            text_color="#86868b"
        )
        sb_sub.pack(anchor="w", pady=(2, 0))

        # Nav items
        self.nav_buttons = {}
        items = [
            ("cards", "💳  Ключ-карты"),
            ("themes", "🎨  Оформление"),
            ("security", "🛡️  Безопасность"),
            ("daemon", "⚡  Служба и Win+L"),
            ("logs", "📋  Журнал аудита"),
        ]

        nav_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_box.pack(fill="x", padx=12, pady=5)

        for key, label in items:
            btn = ctk.CTkButton(
                nav_box,
                text=label,
                font=font_body(13),
                anchor="w",
                height=38,
                corner_radius=10,
                fg_color="transparent",
                text_color="#a1a1aa",
                hover_color="#1f1f23",
                command=lambda k=key: self.show_view(k)
            )
            btn.pack(fill="x", pady=3)
            self.nav_buttons[key] = btn

        # Footer button in sidebar
        sb_footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sb_footer.pack(side="bottom", fill="x", padx=14, pady=20)

        test_btn = ctk.CTkButton(
            sb_footer,
            text="Проверить экран ➔",
            font=font_headline(12),
            fg_color="#0a84ff",
            hover_color="#0071e3",
            corner_radius=10,
            height=34,
            command=self.launch_lock_test
        )
        test_btn.pack(fill="x")

        self.view_container = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.view_container.pack(fill="both", expand=True, padx=32, pady=28)

    def show_view(self, view_name: str):
        self.active_nav = view_name

        for k, btn in self.nav_buttons.items():
            if k == view_name:
                btn.configure(fg_color="#1f1f23", text_color="#f5f5f7")
            else:
                btn.configure(fg_color="transparent", text_color="#a1a1aa")

        for widget in self.view_container.winfo_children():
            widget.destroy()

        if view_name == "cards":
            self._render_cards_view()
        elif view_name == "themes":
            self._render_themes_view()
        elif view_name == "security":
            self._render_security_view()
        elif view_name == "daemon":
            self._render_daemon_view()
        elif view_name == "logs":
            self._render_logs_view()

    # ==========================================
    # VIEW 1: KEYCARDS
    # ==========================================

    def _render_cards_view(self):
        h_box = ctk.CTkFrame(self.view_container, fg_color="transparent")
        h_box.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            h_box,
            text="Ключ-карты и считыватель",
            font=font_large_title(22),
            text_color="#f5f5f7"
        ).pack(anchor="w")
        ctk.CTkLabel(
            h_box,
            text="Управление физическими NFC-ключами и считывателем ACS ACR122U.",
            font=font_body(13),
            text_color="#86868b"
        ).pack(anchor="w", pady=(2, 0))

        add_card = ctk.CTkFrame(self.view_container, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        add_card.pack(fill="x", pady=(0, 18))

        top_row = ctk.CTkFrame(add_card, fg_color="transparent")
        top_row.pack(fill="x", padx=20, pady=(16, 12))

        ctk.CTkLabel(
            top_row,
            text="Быстрое добавление карты",
            font=font_headline(14),
            text_color="#f5f5f7"
        ).pack(side="left")

        self.scan_status_badge = ctk.CTkLabel(
            top_row,
            text="Ридер готов к чтению",
            font=font_caption(11),
            text_color="#86868b"
        )
        self.scan_status_badge.pack(side="right")

        inputs_row = ctk.CTkFrame(add_card, fg_color="transparent")
        inputs_row.pack(fill="x", padx=20, pady=(0, 16))

        self.scan_btn = ctk.CTkButton(
            inputs_row,
            text="Сканировать с ридера",
            font=font_headline(12),
            fg_color="#0a84ff",
            hover_color="#0071e3",
            corner_radius=10,
            height=36,
            width=180,
            command=self.start_card_scan
        )
        self.scan_btn.pack(side="left", padx=(0, 12))

        self.uid_entry = ctk.CTkEntry(
            inputs_row,
            placeholder_text="UID (например: 04:A1:B2:C3)",
            font=font_mono(12),
            fg_color="#1c1c1f",
            border_color="#2c2c2e",
            corner_radius=10,
            height=36,
            width=210
        )
        self.uid_entry.pack(side="left", padx=(0, 12))

        self.name_entry = ctk.CTkEntry(
            inputs_row,
            placeholder_text="Название ключа",
            font=font_body(13),
            fg_color="#1c1c1f",
            border_color="#2c2c2e",
            corner_radius=10,
            height=36,
            width=200
        )
        self.name_entry.pack(side="left", padx=(0, 12))

        add_btn = ctk.CTkButton(
            inputs_row,
            text="+ Добавить",
            font=font_headline(12),
            fg_color="#30d158",
            text_color="#000000",
            hover_color="#28b84d",
            corner_radius=10,
            height=36,
            width=110,
            command=self.add_card_clicked
        )
        add_btn.pack(side="left")

        list_card = ctk.CTkFrame(self.view_container, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        list_card.pack(fill="both", expand=True)

        list_header = ctk.CTkFrame(list_card, fg_color="transparent")
        list_header.pack(fill="x", padx=20, pady=(14, 8))

        ctk.CTkLabel(
            list_header,
            text="Зарегистрированные ключи доступа",
            font=font_headline(14),
            text_color="#f5f5f7"
        ).pack(side="left")

        self.cards_scroll = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        self.cards_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._load_cards_list()

    def start_card_scan(self):
        self.scan_btn.configure(state="disabled", text="Ожидание карты...")
        self.scan_status_badge.configure(text="Приложите карту к ACR122U...", text_color="#0a84ff")

        def worker():
            uid = self.reader.read_single_card(timeout_seconds=7.0)
            self.after(0, self._on_scan_finished, uid)

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_finished(self, uid: Optional[str]):
        self.scan_btn.configure(state="normal", text="Сканировать с ридера")
        if uid:
            norm = normalize_uid(uid)
            self.uid_entry.delete(0, "end")
            self.uid_entry.insert(0, norm)
            self.scan_status_badge.configure(text=f"Карта распознана: {norm}", text_color="#30d158")
            self.reader.beep_success()
        else:
            self.scan_status_badge.configure(text="Таймаут считывания", text_color="#ff453a")

    def add_card_clicked(self):
        uid = self.uid_entry.get().strip()
        name = self.name_entry.get().strip()
        if not uid:
            messagebox.showwarning("Внимание", "Пожалуйста, укажите UID карты.")
            return

        norm = normalize_uid(uid)
        self.cfg.add_card(norm, name or f"Ключ {norm[-5:]}")
        self.uid_entry.delete(0, "end")
        self.name_entry.delete(0, "end")
        self.scan_status_badge.configure(text=f"Ключ {norm} сохранен", text_color="#30d158")
        self._load_cards_list()

    def _load_cards_list(self):
        for w in self.cards_scroll.winfo_children():
            w.destroy()

        cards = self.cfg.get_cards()
        if not cards:
            empty_box = ctk.CTkFrame(self.cards_scroll, fg_color="transparent")
            empty_box.pack(pady=40)
            ctk.CTkLabel(
                empty_box,
                text="Список пуст",
                font=font_headline(14),
                text_color="#71717a"
            ).pack()
            ctk.CTkLabel(
                empty_box,
                text="Добавьте хотя бы одну карту для активации аппаратной защиты.",
                font=font_body(12),
                text_color="#52525b"
            ).pack(pady=(4, 0))
            return

        for card in cards:
            row = ctk.CTkFrame(self.cards_scroll, fg_color="#1c1c1f", corner_radius=10, height=52)
            row.pack(fill="x", pady=4)
            row.pack_propagate(False)

            is_active = card.get("enabled", True)
            pill_color = "#30d158" if is_active else "#71717a"
            pill_text = "Активна" if is_active else "Отключена"

            pill = ctk.CTkFrame(row, fg_color="#27272a" if not is_active else "#16281b", corner_radius=8, height=24)
            pill.pack(side="left", padx=(14, 12))
            ctk.CTkLabel(
                pill,
                text=pill_text,
                font=font_caption(10),
                text_color=pill_color
            ).pack(padx=8, pady=2)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(
                info,
                text=card.get("name", "Ключ"),
                font=font_headline(13),
                text_color="#f5f5f7"
            ).pack(anchor="w")

            ctk.CTkLabel(
                info,
                text=f"UID: {card.get('uid')}  ·  {card.get('added_at', '')}",
                font=font_mono(11),
                text_color="#86868b"
            ).pack(anchor="w")

            toggle_btn = ctk.CTkButton(
                row,
                text="Отключить" if is_active else "Включить",
                font=font_caption(11),
                fg_color="#27272a",
                hover_color="#323236",
                corner_radius=8,
                height=28,
                width=80,
                command=lambda u=card["uid"]: self.toggle_card(u)
            )
            toggle_btn.pack(side="right", padx=6)

            del_btn = ctk.CTkButton(
                row,
                text="Удалить",
                font=font_caption(11),
                fg_color="#2e1a1c",
                text_color="#ff453a",
                hover_color="#3d2124",
                corner_radius=8,
                height=28,
                width=70,
                command=lambda u=card["uid"]: self.delete_card(u)
            )
            del_btn.pack(side="right", padx=(6, 14))

    def toggle_card(self, uid: str):
        self.cfg.toggle_card(uid)
        self._load_cards_list()

    def delete_card(self, uid: str):
        if messagebox.askyesno("Подтверждение", f"Удалить ключ {uid}?"):
            self.cfg.remove_card(uid)
            self._load_cards_list()

    # ==========================================
    # VIEW 2: APPEARANCE & THEMES
    # ==========================================

    def _render_themes_view(self):
        h_box = ctk.CTkFrame(self.view_container, fg_color="transparent")
        h_box.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            h_box,
            text="Оформление и темы",
            font=font_large_title(22),
            text_color="#f5f5f7"
        ).pack(anchor="w")
        ctk.CTkLabel(
            h_box,
            text="Настройка визуального стиля экрана блокировки и Apple-типографики.",
            font=font_body(13),
            text_color="#86868b"
        ).pack(anchor="w", pady=(2, 0))

        grid = ctk.CTkFrame(self.view_container, fg_color="transparent")
        grid.pack(fill="both", expand=True)

        left = ctk.CTkFrame(grid, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 16))

        right = ctk.CTkFrame(grid, fg_color="transparent", width=330)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        # Controls Card
        ctrl_card = ctk.CTkFrame(left, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        ctrl_card.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            ctrl_card,
            text="Цветовая палитра Apple",
            font=font_headline(14),
            text_color="#f5f5f7"
        ).pack(anchor="w", padx=20, pady=(18, 10))

        self.theme_dropdown = ctk.CTkOptionMenu(
            ctrl_card,
            values=list(THEME_PRESETS.keys()),
            command=self.on_theme_selected,
            font=font_body(13),
            fg_color="#1c1c1f",
            button_color="#27272a",
            button_hover_color="#3f3f46",
            corner_radius=10,
            height=36,
            width=320
        )
        self.theme_dropdown.set(self.cfg.config.get("appearance", {}).get("theme_name", "Apple Dark (Тёмная macOS)"))
        self.theme_dropdown.pack(anchor="w", padx=20, pady=(0, 18))

        # Text Card
        text_card = ctk.CTkFrame(left, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        text_card.pack(fill="x")

        ctk.CTkLabel(
            text_card,
            text="Настройка текстов экрана",
            font=font_headline(14),
            text_color="#f5f5f7"
        ).pack(anchor="w", padx=20, pady=(18, 12))

        ctk.CTkLabel(text_card, text="Заголовок:", font=font_caption(11), text_color="#86868b").pack(anchor="w", padx=20)
        self.title_input = ctk.CTkEntry(
            text_card,
            font=font_body(13),
            fg_color="#1c1c1f",
            border_color="#2c2c2e",
            corner_radius=10,
            height=34,
            width=340
        )
        self.title_input.insert(0, self.cfg.config.get("appearance", {}).get("title_text", "Вход в систему"))
        self.title_input.pack(anchor="w", padx=20, pady=(4, 12))

        ctk.CTkLabel(text_card, text="Подсказка:", font=font_caption(11), text_color="#86868b").pack(anchor="w", padx=20)
        self.sub_input = ctk.CTkEntry(
            text_card,
            font=font_body(13),
            fg_color="#1c1c1f",
            border_color="#2c2c2e",
            corner_radius=10,
            height=34,
            width=340
        )
        self.sub_input.insert(0, self.cfg.config.get("appearance", {}).get("subtitle_text", "Приложите карту доступа или введите пароль"))
        self.sub_input.pack(anchor="w", padx=20, pady=(4, 14))

        self.show_uid_var = ctk.BooleanVar(value=self.cfg.config.get("appearance", {}).get("show_uid_on_screen", True))
        ctk.CTkCheckBox(
            text_card,
            text="Отображать считанный UID на экране",
            font=font_body(12),
            variable=self.show_uid_var,
            corner_radius=6,
            border_width=1,
            fg_color="#0a84ff"
        ).pack(anchor="w", padx=20, pady=(0, 16))

        save_txt_btn = ctk.CTkButton(
            text_card,
            text="Сохранить параметры",
            font=font_headline(12),
            fg_color="#0a84ff",
            hover_color="#0071e3",
            corner_radius=10,
            height=34,
            width=180,
            command=self.save_appearance
        )
        save_txt_btn.pack(anchor="w", padx=20, pady=(0, 20))

        # Live Preview
        ctk.CTkLabel(
            right,
            text="Предпросмотр экрана блокировки",
            font=font_headline(13),
            text_color="#86868b"
        ).pack(anchor="w", pady=(0, 8))

        theme = self.cfg.get_current_theme()
        self.prev_box = ctk.CTkFrame(right, fg_color=theme["bg_color"], corner_radius=16, border_width=1, border_color="#27272a")
        self.prev_box.pack(fill="both", expand=True)

        self.prev_clock = ctk.CTkLabel(
            self.prev_box,
            text="18:05",
            font=font_clock(38),
            text_color=theme["text_primary"]
        )
        self.prev_clock.pack(pady=(28, 2))

        self.prev_card = ctk.CTkFrame(
            self.prev_box,
            fg_color=theme["card_bg"],
            corner_radius=16,
            border_width=1,
            border_color=theme["border_color"],
            width=260,
            height=250
        )
        self.prev_card.pack(pady=(10, 0))
        self.prev_card.pack_propagate(False)

        self.prev_glyph = ctk.CTkLabel(
            self.prev_card,
            text="",
            image=create_nfc_glyph(44, theme["accent_color"], theme["bg_color"], theme["border_color"])
        )
        self.prev_glyph.pack(pady=(16, 6))

        self.prev_title = ctk.CTkLabel(
            self.prev_card,
            text=self.title_input.get(),
            font=font_headline(13),
            text_color=theme["text_primary"]
        )
        self.prev_title.pack()

        self.prev_status = ctk.CTkLabel(
            self.prev_card,
            text="Ожидание NFC-карты",
            font=font_caption(11),
            text_color=theme["accent_color"]
        )
        self.prev_status.pack(pady=(4, 6))

        self.prev_dots = ctk.CTkFrame(self.prev_card, fg_color="transparent")
        self.prev_dots.pack(pady=(0, 10))
        for _ in range(3):
            ctk.CTkFrame(self.prev_dots, width=16, height=4, corner_radius=2, fg_color=theme["border_color"]).pack(side="left", padx=2)

        # Mini input mockup
        mock_input = ctk.CTkFrame(self.prev_card, fg_color=theme["bg_color"], corner_radius=8, width=180, height=28)
        mock_input.pack()
        mock_input.pack_propagate(False)
        ctk.CTkLabel(mock_input, text="••••••••", font=font_caption(10), text_color=theme["text_secondary"]).pack(side="left", padx=8)

    def on_theme_selected(self, theme_name: str):
        self.cfg.set_theme(theme_name)
        theme = self.cfg.get_current_theme()

        self.prev_box.configure(fg_color=theme["bg_color"])
        self.prev_clock.configure(text_color=theme["text_primary"])
        self.prev_card.configure(fg_color=theme["card_bg"], border_color=theme["border_color"])
        self.prev_glyph.configure(
            image=create_nfc_glyph(44, theme["accent_color"], theme["bg_color"], theme["border_color"])
        )
        self.prev_title.configure(text_color=theme["text_primary"])
        self.prev_status.configure(text_color=theme["accent_color"])

    def save_appearance(self):
        self.cfg.config["appearance"]["title_text"] = self.title_input.get().strip()
        self.cfg.config["appearance"]["subtitle_text"] = self.sub_input.get().strip()
        self.cfg.config["appearance"]["show_uid_on_screen"] = self.show_uid_var.get()
        self.cfg.save()
        self.prev_title.configure(text=self.title_input.get().strip())
        messagebox.showinfo("Успешно", "Параметры сохранены!")

    # ==========================================
    # VIEW 3: SECURITY
    # ==========================================

    def _render_security_view(self):
        h_box = ctk.CTkFrame(self.view_container, fg_color="transparent")
        h_box.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            h_box,
            text="Безопасность и способы разблокировки",
            font=font_large_title(22),
            text_color="#f5f5f7"
        ).pack(anchor="w")
        ctk.CTkLabel(
            h_box,
            text="Разблокировка по NFC-карте или штатному паролю/PIN учетной записи Windows.",
            font=font_body(13),
            text_color="#86868b"
        ).pack(anchor="w", pady=(2, 0))

        sec_card = ctk.CTkFrame(self.view_container, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        sec_card.pack(fill="x", pady=(0, 16))

        row_att = ctk.CTkFrame(sec_card, fg_color="transparent")
        row_att.pack(fill="x", padx=20, pady=(18, 10))

        curr_att = self.cfg.config.get("security", {}).get("max_attempts", 3)
        self.att_lbl = ctk.CTkLabel(row_att, text=f"Количество попыток карты: {curr_att}", font=font_headline(13), width=280, anchor="w")
        self.att_lbl.pack(side="left")

        self.att_slider = ctk.CTkSlider(
            row_att,
            from_=1,
            to=10,
            number_of_steps=9,
            command=lambda v: self.att_lbl.configure(text=f"Количество попыток карты: {int(v)}"),
            button_color="#0a84ff",
            progress_color="#0a84ff",
            width=220
        )
        self.att_slider.set(curr_att)
        self.att_slider.pack(side="left", padx=10)

        row_act = ctk.CTkFrame(sec_card, fg_color="transparent")
        row_act.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(row_act, text="Действие при исчерпании:", font=font_headline(13), width=280, anchor="w").pack(side="left")
        self.action_dropdown = ctk.CTkOptionMenu(
            row_act,
            values=["lock_workstation (Штатный экран Windows)", "shutdown (Выключение)", "restart (Перезагрузка)"],
            font=font_body(12),
            fg_color="#1c1c1f",
            button_color="#27272a",
            corner_radius=10,
            width=280
        )
        curr_act = self.cfg.config.get("security", {}).get("action_on_fail", "lock_workstation")
        for val in self.action_dropdown._values:
            if curr_act in val:
                self.action_dropdown.set(val)
                break
        self.action_dropdown.pack(side="left")

        self.beep_success_var = ctk.BooleanVar(value=self.cfg.config.get("security", {}).get("beep_on_success", True))
        ctk.CTkCheckBox(
            sec_card,
            text="Звуковой сигнал зуммера ACR122U при успешном входе",
            font=font_body(12),
            variable=self.beep_success_var,
            corner_radius=6,
            fg_color="#0a84ff"
        ).pack(anchor="w", padx=20, pady=6)

        self.beep_error_var = ctk.BooleanVar(value=self.cfg.config.get("security", {}).get("beep_on_error", True))
        ctk.CTkCheckBox(
            sec_card,
            text="Предупреждающий сигнал ACR122U при неверной карте",
            font=font_body(12),
            variable=self.beep_error_var,
            corner_radius=6,
            fg_color="#0a84ff"
        ).pack(anchor="w", padx=20, pady=(6, 16))

        pin_card = ctk.CTkFrame(self.view_container, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        pin_card.pack(fill="x")

        row_pin = ctk.CTkFrame(pin_card, fg_color="transparent")
        row_pin.pack(fill="x", padx=20, pady=18)

        ctk.CTkLabel(row_pin, text="Экстренный мастер-PIN (опционально):", font=font_headline(13), width=280, anchor="w").pack(side="left")
        self.pin_entry = ctk.CTkEntry(
            row_pin,
            placeholder_text="PIN / мастер-пароль",
            font=font_body(13),
            show="*",
            fg_color="#1c1c1f",
            border_color="#2c2c2e",
            corner_radius=10,
            width=200
        )
        self.pin_entry.pack(side="left")

        save_sec_btn = ctk.CTkButton(
            self.view_container,
            text="Сохранить настройки безопасности",
            font=font_headline(12),
            fg_color="#0a84ff",
            hover_color="#0071e3",
            corner_radius=10,
            height=36,
            width=260,
            command=self.save_security
        )
        save_sec_btn.pack(anchor="w", pady=18)

    def save_security(self):
        sec = self.cfg.config["security"]
        sec["max_attempts"] = int(self.att_slider.get())

        chosen_act = self.action_dropdown.get()
        if "shutdown" in chosen_act:
            sec["action_on_fail"] = "shutdown"
        elif "restart" in chosen_act:
            sec["action_on_fail"] = "restart"
        else:
            sec["action_on_fail"] = "lock_workstation"

        sec["beep_on_success"] = self.beep_success_var.get()
        sec["beep_on_error"] = self.beep_error_var.get()

        new_pin = self.pin_entry.get().strip()
        if new_pin:
            self.cfg.set_master_pin(new_pin)
            self.pin_entry.delete(0, "end")

        self.cfg.save()
        messagebox.showinfo("Успешно", "Настройки сохранены!")

    # ==========================================
    # VIEW 4: BACKGROUND DAEMON SERVICE & WIN+L
    # ==========================================

    def _render_daemon_view(self):
        h_box = ctk.CTkFrame(self.view_container, fg_color="transparent")
        h_box.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            h_box,
            text="Фоновая служба и перехват Win + L",
            font=font_large_title(22),
            text_color="#f5f5f7"
        ).pack(anchor="w")
        ctk.CTkLabel(
            h_box,
            text="Управление службой в трее и вызовом экрана NFC Guard напрямую по Win+L.",
            font=font_body(13),
            text_color="#86868b"
        ).pack(anchor="w", pady=(2, 0))

        # Status & Control Card
        srv_card = ctk.CTkFrame(self.view_container, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        srv_card.pack(fill="x", pady=(0, 16))

        d_row = ctk.CTkFrame(srv_card, fg_color="transparent")
        d_row.pack(fill="x", padx=20, pady=18)

        self.daemon_status_lbl = ctk.CTkLabel(
            d_row,
            text="Проверка службы...",
            font=font_headline(13),
            width=230,
            anchor="w"
        )
        self.daemon_status_lbl.pack(side="left")

        self.btn_start_daemon = ctk.CTkButton(
            d_row,
            text="Запустить службу",
            font=font_headline(12),
            fg_color="#30d158",
            text_color="#000000",
            hover_color="#28b84d",
            corner_radius=10,
            height=34,
            width=160,
            command=self.start_daemon_clicked
        )
        self.btn_start_daemon.pack(side="left", padx=8)

        self.btn_stop_daemon = ctk.CTkButton(
            d_row,
            text="Остановить",
            font=font_headline(12),
            fg_color="#27272a",
            hover_color="#323236",
            corner_radius=10,
            height=34,
            width=120,
            command=self.stop_daemon_clicked
        )
        self.btn_stop_daemon.pack(side="left")

        # Win+L Direct Interception Card
        win_l_card = ctk.CTkFrame(self.view_container, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        win_l_card.pack(fill="x", pady=(0, 16))

        wl_box = ctk.CTkFrame(win_l_card, fg_color="transparent")
        wl_box.pack(fill="x", padx=20, pady=18)

        ctk.CTkLabel(
            wl_box,
            text="Перехват клавиши Win + L",
            font=font_headline(14),
            text_color="#f5f5f7"
        ).pack(anchor="w")

        ctk.CTkLabel(
            wl_box,
            text="Позволяет вызывать экран авторизации NFC Guard напрямую по Win+L вместо стандартного экрана блокировки Windows.",
            font=font_body(12),
            text_color="#86868b"
        ).pack(anchor="w", pady=(3, 10))

        wl_btn_row = ctk.CTkFrame(wl_box, fg_color="transparent")
        wl_btn_row.pack(fill="x")

        self.btn_win_l_uac = ctk.CTkButton(
            wl_btn_row,
            text="🔒 Настроить перехват Win+L (UAC)",
            font=font_headline(12),
            fg_color="#0a84ff",
            hover_color="#0071e3",
            corner_radius=10,
            height=34,
            width=240,
            command=self.enable_win_l_interception_clicked
        )
        self.btn_win_l_uac.pack(side="left", padx=(0, 10))

        self.btn_restore_win_l = ctk.CTkButton(
            wl_btn_row,
            text="Сбросить Win+L",
            font=font_body(12),
            fg_color="#27272a",
            hover_color="#323236",
            corner_radius=10,
            height=34,
            width=140,
            command=self.disable_win_l_interception_clicked
        )
        self.btn_restore_win_l.pack(side="left")

        # Startup Card
        start_card = ctk.CTkFrame(self.view_container, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        start_card.pack(fill="x")

        s_box = ctk.CTkFrame(start_card, fg_color="transparent")
        s_box.pack(fill="x", padx=20, pady=18)

        self.autostart_var = ctk.BooleanVar(value=is_autostart_enabled())
        ctk.CTkCheckBox(
            s_box,
            text="Автозапуск службы при включении компьютера (Windows Startup)",
            font=font_body(13),
            variable=self.autostart_var,
            corner_radius=6,
            fg_color="#0a84ff",
            command=self._on_autostart_toggled
        ).pack(anchor="w")

        ctk.CTkLabel(
            s_box,
            text="Быстрая горячая клавиша блокировки в любой момент: Ctrl + Alt + L",
            font=font_caption(11),
            text_color="#86868b"
        ).pack(anchor="w", pady=(8, 0))

        self._update_daemon_status_lbl()

    def enable_win_l_interception_clicked(self):
        bat_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "enable_win_l_interception.bat"))
        subprocess.Popen(["cmd.exe", "/c", bat_path])

    def disable_win_l_interception_clicked(self):
        bat_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "disable_win_l_interception.bat"))
        subprocess.Popen(["cmd.exe", "/c", bat_path])

    def _update_daemon_status_lbl(self):
        active = is_daemon_running()
        if hasattr(self, "daemon_status_lbl") and self.daemon_status_lbl.winfo_exists():
            if active:
                self.daemon_status_lbl.configure(text="● Служба активна в трее", text_color="#30d158")
                self.btn_start_daemon.configure(state="disabled")
                self.btn_stop_daemon.configure(state="normal")
            else:
                self.daemon_status_lbl.configure(text="○ Служба не запущена", text_color="#86868b")
                self.btn_start_daemon.configure(state="normal")
                self.btn_stop_daemon.configure(state="disabled")

        self.after(3000, self._update_daemon_status_lbl)

    def start_daemon_clicked(self):
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        exe = get_pythonw_executable()
        subprocess.Popen([exe, main_py, "--daemon"])
        self.after(800, self._update_daemon_status_lbl)
        messagebox.showinfo("Служба", "Фоновая служба запущена.")

    def stop_daemon_clicked(self):
        subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe"], capture_output=True)
        self.after(800, self._update_daemon_status_lbl)
        messagebox.showinfo("Служба", "Служба остановлена.")

    def _on_autostart_toggled(self):
        enabled = self.autostart_var.get()
        success, msg = set_autostart(enabled)
        if success:
            messagebox.showinfo("Автозапуск", msg)
        else:
            messagebox.showerror("Ошибка", msg)
            self.autostart_var.set(not enabled)

    # ==========================================
    # VIEW 5: AUDIT LOGS
    # ==========================================

    def _render_logs_view(self):
        h_box = ctk.CTkFrame(self.view_container, fg_color="transparent")
        h_box.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            h_box,
            text="Журнал событий доступа",
            font=font_large_title(22),
            text_color="#f5f5f7"
        ).pack(anchor="w")
        ctk.CTkLabel(
            h_box,
            text="История успешных авторизаций, отклоненных карт и системных событий.",
            font=font_body(13),
            text_color="#86868b"
        ).pack(anchor="w", pady=(2, 0))

        log_card = ctk.CTkFrame(self.view_container, fg_color="#161618", corner_radius=16, border_width=1, border_color="#27272a")
        log_card.pack(fill="both", expand=True)

        btn_row = ctk.CTkFrame(log_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(14, 10))

        ctk.CTkButton(
            btn_row,
            text="Обновить",
            font=font_caption(11),
            fg_color="#27272a",
            hover_color="#323236",
            corner_radius=8,
            height=30,
            width=100,
            command=self._refresh_logs
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="Очистить",
            font=font_caption(11),
            fg_color="#2e1a1c",
            text_color="#ff453a",
            hover_color="#3d2124",
            corner_radius=8,
            height=30,
            width=90,
            command=self._clear_logs
        ).pack(side="left")

        self.log_textbox = ctk.CTkTextbox(
            log_card,
            font=font_mono(11),
            fg_color="#111113",
            corner_radius=10,
            border_width=1,
            border_color="#27272a"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self._refresh_logs()

    def _refresh_logs(self):
        if not hasattr(self, "log_textbox") or not self.log_textbox.winfo_exists():
            return
        logs = self.cfg.read_recent_logs(200)
        self.log_textbox.delete("1.0", "end")
        if not logs:
            self.log_textbox.insert("end", "Журнал пуст.")
        else:
            self.log_textbox.insert("end", "\n".join(logs))

    def _clear_logs(self):
        if messagebox.askyesno("Подтверждение", "Очистить историю событий?"):
            self.cfg.clear_logs()
            self._refresh_logs()

    def launch_lock_test(self):
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        exe = get_pythonw_executable()
        subprocess.Popen([exe, main_py, "--lock"])
