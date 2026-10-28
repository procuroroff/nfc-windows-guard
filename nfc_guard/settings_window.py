"""Settings & Control Panel for NFC Windows Guard.
Manage authorized cards, themes, security policies, hardware buzzer, multi-monitor, and background daemon.
"""

import sys
import os
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import Optional

from .config import ConfigManager, THEME_PRESETS, normalize_uid
from .reader import ACR122UReader
from .utils import is_autostart_enabled, set_autostart, is_daemon_running, get_pythonw_executable


class SettingsWindow(ctk.CTk):
    """Configuration & Card Management GUI."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        super().__init__()

        self.cfg = config_manager or ConfigManager()
        self.cfg.load()
        self.reader = ACR122UReader()

        self.title("NFC Windows Guard — Центр Управления")
        self.geometry("960x700")
        self.minsize(850, 620)

        self.current_theme = self.cfg.get_current_theme()
        ctk.set_appearance_mode("dark")
        self.configure(fg_color="#12131a")

        self._build_ui()
        self._load_cards_list()
        self._refresh_logs()
        self._update_daemon_status_lbl()

    def _build_ui(self):
        # Top Header
        self.top_header = ctk.CTkFrame(self, fg_color="#181a24", height=70, corner_radius=0)
        self.top_header.pack(fill="x")
        self.top_header.pack_propagate(False)

        self.brand_lbl = ctk.CTkLabel(
            self.top_header,
            text="🛡️ NFC Windows Guard",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=self.current_theme.get("accent_color", "#00f0ff")
        )
        self.brand_lbl.pack(side="left", padx=25)

        self.sub_brand_lbl = ctk.CTkLabel(
            self.top_header,
            text="ACR122U Smart Card Security System",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#7f8ea3"
        )
        self.sub_brand_lbl.pack(side="left", padx=(0, 20))

        self.test_lock_btn = ctk.CTkButton(
            self.top_header,
            text="🔒 Тест экрана блокировки",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=self.current_theme.get("accent_color", "#3b82f6"),
            text_color="#000000" if self.current_theme.get("accent_color", "#3b82f6") in ["#00f0ff", "#00ff41"] else "#ffffff",
            hover_color=self.current_theme.get("accent_hover", "#2563eb"),
            command=self.launch_lock_test,
            height=34,
            width=200
        )
        self.test_lock_btn.pack(side="right", padx=25)

        # Tabview
        self.tabs = ctk.CTkTabview(
            self,
            fg_color="#181a24",
            segmented_button_selected_color=self.current_theme.get("accent_color", "#00f0ff"),
            segmented_button_selected_hover_color=self.current_theme.get("accent_hover", "#00c4d4")
        )
        self.tabs.pack(fill="both", expand=True, padx=20, pady=15)

        self.tab_cards = self.tabs.add("💳 Ключ-карты")
        self.tab_themes = self.tabs.add("🎨 Темы и Оформление")
        self.tab_security = self.tabs.add("🛡️ Безопасность и Служба")
        self.tab_logs = self.tabs.add("📋 Журнал событий")

        self._build_cards_tab()
        self._build_themes_tab()
        self._build_security_tab()
        self._build_logs_tab()

    # --- TAB 1: CARDS MANAGEMENT ---

    def _build_cards_tab(self):
        add_frame = ctk.CTkFrame(self.tab_cards, fg_color="#1f2333", corner_radius=12)
        add_frame.pack(fill="x", padx=15, pady=10)

        add_title = ctk.CTkLabel(
            add_frame,
            text="Добавить новую ключ-карту",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ffffff"
        )
        add_title.pack(anchor="w", padx=20, pady=(15, 10))

        inputs_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        inputs_row.pack(fill="x", padx=20, pady=(0, 15))

        self.scan_btn = ctk.CTkButton(
            inputs_row,
            text="📡 Сканировать с ридера",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#00f0ff",
            text_color="#000000",
            hover_color="#00c4d4",
            command=self.start_card_scan,
            width=180,
            height=36
        )
        self.scan_btn.pack(side="left", padx=(0, 15))

        self.uid_entry = ctk.CTkEntry(
            inputs_row,
            placeholder_text="UID карты (например: 04:A1:B2:C3)",
            font=ctk.CTkFont(family="Consolas", size=13),
            width=230,
            height=36
        )
        self.uid_entry.pack(side="left", padx=(0, 15))

        self.name_entry = ctk.CTkEntry(
            inputs_row,
            placeholder_text="Название (например: Основной брелок)",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            width=230,
            height=36
        )
        self.name_entry.pack(side="left", padx=(0, 15))

        add_card_btn = ctk.CTkButton(
            inputs_row,
            text="+ Добавить",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            command=self.add_card_clicked,
            width=120,
            height=36
        )
        add_card_btn.pack(side="left")

        self.scan_status_lbl = ctk.CTkLabel(
            add_frame,
            text="Приложите карту к ACR122U или нажмите 'Сканировать'",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#7f8ea3"
        )
        self.scan_status_lbl.pack(anchor="w", padx=20, pady=(0, 12))

        cards_list_header = ctk.CTkLabel(
            self.tab_cards,
            text="Зарегистрированные ключ-карты (Белый список):",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#ffffff"
        )
        cards_list_header.pack(anchor="w", padx=20, pady=(10, 5))

        self.cards_scroll = ctk.CTkScrollableFrame(self.tab_cards, fg_color="#141724", corner_radius=10)
        self.cards_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    def start_card_scan(self):
        self.scan_btn.configure(state="disabled", text="⏳ Ожидание карты...")
        self.scan_status_lbl.configure(text="Приложите карту к ACR122U прямо сейчас...", text_color="#00f0ff")

        def worker():
            uid = self.reader.read_single_card(timeout_seconds=8.0)
            self.after(0, self._on_scan_finished, uid)

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_finished(self, uid: Optional[str]):
        self.scan_btn.configure(state="normal", text="📡 Сканировать с ридера")
        if uid:
            norm = normalize_uid(uid)
            self.uid_entry.delete(0, "end")
            self.uid_entry.insert(0, norm)
            self.scan_status_lbl.configure(text=f"✓ Карта обнаружена! UID: {norm}", text_color="#10b981")
            self.reader.beep_success()
        else:
            self.scan_status_lbl.configure(
                text="✗ Таймаут. Карта не была приложена или ридер не подключен",
                text_color="#ef4444"
            )

    def add_card_clicked(self):
        uid = self.uid_entry.get().strip()
        name = self.name_entry.get().strip()
        if not uid:
            messagebox.showwarning("Внимание", "Пожалуйста, укажите или отсканируйте UID карты.")
            return

        norm = normalize_uid(uid)
        self.cfg.add_card(norm, name or f"Карта {norm[-5:]}")
        self.uid_entry.delete(0, "end")
        self.name_entry.delete(0, "end")
        self.scan_status_lbl.configure(text=f"✓ Карта {norm} успешно сохранена!", text_color="#10b981")
        self._load_cards_list()

    def _load_cards_list(self):
        for widget in self.cards_scroll.winfo_children():
            widget.destroy()

        cards = self.cfg.get_cards()
        if not cards:
            empty_lbl = ctk.CTkLabel(
                self.cards_scroll,
                text="Белый список пуст. Добавьте хотя бы одну карту, чтобы активировать защиту!",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color="#f59e0b"
            )
            empty_lbl.pack(pady=40)
            return

        for card in cards:
            c_frame = ctk.CTkFrame(self.cards_scroll, fg_color="#1e2233", corner_radius=8)
            c_frame.pack(fill="x", pady=5, padx=5)

            is_enabled = card.get("enabled", True)
            status_text = "● АКТИВНА" if is_enabled else "○ ОТКЛЮЧЕНА"
            status_color = "#10b981" if is_enabled else "#7f8ea3"

            status_lbl = ctk.CTkLabel(
                c_frame,
                text=status_text,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=status_color,
                width=100
            )
            status_lbl.pack(side="left", padx=10)

            info_frame = ctk.CTkFrame(c_frame, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            name_lbl = ctk.CTkLabel(
                info_frame,
                text=card.get("name", "Без названия"),
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                text_color="#ffffff",
                anchor="w"
            )
            name_lbl.pack(anchor="w")

            detail_lbl = ctk.CTkLabel(
                info_frame,
                text=f"UID: {card.get('uid')}  |  Добавлена: {card.get('added_at', 'Н/Д')}",
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color="#7f8ea3",
                anchor="w"
            )
            detail_lbl.pack(anchor="w")

            toggle_text = "Отключить" if is_enabled else "Включить"
            toggle_btn = ctk.CTkButton(
                c_frame,
                text=toggle_text,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#2e354f",
                hover_color="#3d4669",
                width=90,
                height=30,
                command=lambda u=card["uid"]: self.toggle_card(u)
            )
            toggle_btn.pack(side="right", padx=6)

            delete_btn = ctk.CTkButton(
                c_frame,
                text="Удалить",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#ef4444",
                hover_color="#dc2626",
                width=80,
                height=30,
                command=lambda u=card["uid"]: self.delete_card(u)
            )
            delete_btn.pack(side="right", padx=(6, 12))

    def toggle_card(self, uid: str):
        self.cfg.toggle_card(uid)
        self._load_cards_list()

    def delete_card(self, uid: str):
        if messagebox.askyesno("Подтверждение", f"Удалить карту {uid} из белого списка?"):
            self.cfg.remove_card(uid)
            self._load_cards_list()

    # --- TAB 2: THEMES & APPEARANCE ---

    def _build_themes_tab(self):
        # Two-column container: Left = Settings, Right = Live Theme Preview
        themes_container = ctk.CTkFrame(self.tab_themes, fg_color="transparent")
        themes_container.pack(fill="both", expand=True, padx=10, pady=10)

        left_col = ctk.CTkFrame(themes_container, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_col = ctk.CTkFrame(themes_container, fg_color="transparent", width=380)
        right_col.pack(side="right", fill="both", padx=(10, 0))
        right_col.pack_propagate(False)

        # Left Column: Theme Selector
        theme_frame = ctk.CTkFrame(left_col, fg_color="#1f2333", corner_radius=12)
        theme_frame.pack(fill="x", pady=(0, 10))

        t_title = ctk.CTkLabel(
            theme_frame,
            text="Выбор темы оформления",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ffffff"
        )
        t_title.pack(anchor="w", padx=20, pady=(15, 10))

        preset_row = ctk.CTkFrame(theme_frame, fg_color="transparent")
        preset_row.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(preset_row, text="Тема экрана:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 15))

        self.theme_dropdown = ctk.CTkOptionMenu(
            preset_row,
            values=list(THEME_PRESETS.keys()),
            command=self.on_theme_selected,
            width=260,
            height=34
        )
        current_theme_name = self.cfg.config.get("appearance", {}).get("theme_name", "Cyberpunk (Неон)")
        self.theme_dropdown.set(current_theme_name)
        self.theme_dropdown.pack(side="left")

        # Text Customizations
        text_frame = ctk.CTkFrame(left_col, fg_color="#1f2333", corner_radius=12)
        text_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            text_frame,
            text="Кастомизация текста экрана",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=20, pady=(15, 10))

        t_row1 = ctk.CTkFrame(text_frame, fg_color="transparent")
        t_row1.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(t_row1, text="Заголовок:", width=110, anchor="w").pack(side="left")
        self.title_input = ctk.CTkEntry(t_row1, width=300)
        self.title_input.insert(0, self.cfg.config.get("appearance", {}).get("title_text", "NFC WINDOWS GUARD"))
        self.title_input.pack(side="left")

        t_row2 = ctk.CTkFrame(text_frame, fg_color="transparent")
        t_row2.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(t_row2, text="Подсказка:", width=110, anchor="w").pack(side="left")
        self.sub_input = ctk.CTkEntry(t_row2, width=300)
        self.sub_input.insert(0, self.cfg.config.get("appearance", {}).get("subtitle_text", "Приложите карту к считывателю"))
        self.sub_input.pack(side="left")

        self.show_uid_var = ctk.BooleanVar(value=self.cfg.config.get("appearance", {}).get("show_uid_on_screen", True))
        t_chk = ctk.CTkCheckBox(
            text_frame,
            text="Отображать считанный UID на экране во время проверки",
            variable=self.show_uid_var
        )
        t_chk.pack(anchor="w", padx=20, pady=12)

        save_appearance_btn = ctk.CTkButton(
            text_frame,
            text="💾 Сохранить текст",
            fg_color="#00f0ff",
            text_color="#000000",
            hover_color="#00c4d4",
            command=self.save_appearance,
            width=180,
            height=34
        )
        save_appearance_btn.pack(anchor="w", padx=20, pady=(0, 15))

        # Right Column: Interactive Live Theme Preview Card
        ctk.CTkLabel(
            right_col,
            text="Предпросмотр темы экрана блокировки:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", pady=(0, 8))

        self.preview_box = ctk.CTkFrame(right_col, fg_color=self.current_theme["bg_color"], corner_radius=12)
        self.preview_box.pack(fill="both", expand=True)

        self.preview_card = ctk.CTkFrame(
            self.preview_box,
            fg_color=self.current_theme["card_bg"],
            border_width=2,
            border_color=self.current_theme["border_color"],
            corner_radius=15,
            width=320,
            height=380
        )
        self.preview_card.place(relx=0.5, rely=0.5, anchor="center")
        self.preview_card.pack_propagate(False)

        self.prev_title = ctk.CTkLabel(
            self.preview_card,
            text="NFC WINDOWS GUARD",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=self.current_theme["text_primary"]
        )
        self.prev_title.pack(pady=(25, 4))

        self.prev_sub = ctk.CTkLabel(
            self.preview_card,
            text="Приложите ключ-карту к ACR122U",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.current_theme["text_secondary"]
        )
        self.prev_sub.pack(pady=(0, 15))

        self.prev_icon_box = ctk.CTkFrame(
            self.preview_card,
            width=70,
            height=70,
            corner_radius=35,
            fg_color=self.current_theme["bg_color"],
            border_width=2,
            border_color=self.current_theme["accent_color"]
        )
        self.prev_icon_box.pack(pady=5)
        self.prev_icon_box.pack_propagate(False)

        self.prev_icon = ctk.CTkLabel(self.prev_icon_box, text="📡", font=ctk.CTkFont(size=28))
        self.prev_icon.place(relx=0.5, rely=0.5, anchor="center")

        self.prev_status = ctk.CTkLabel(
            self.preview_card,
            text="Ожидание карты...",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self.current_theme["accent_color"]
        )
        self.prev_status.pack(pady=(12, 2))

        self.prev_dots = ctk.CTkLabel(
            self.preview_card,
            text="● ● ●",
            font=ctk.CTkFont(size=14),
            text_color=self.current_theme["accent_color"]
        )
        self.prev_dots.pack(pady=(0, 10))

        self.prev_fallback = ctk.CTkButton(
            self.preview_card,
            text="Штатный вход Windows ➔",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            border_color=self.current_theme["border_color"],
            text_color=self.current_theme["text_secondary"],
            height=26,
            width=180
        )
        self.prev_fallback.pack(side="bottom", pady=15)

    def on_theme_selected(self, theme_name: str):
        self.cfg.set_theme(theme_name)
        self.current_theme = self.cfg.get_current_theme()

        # Update preview card colors
        self.preview_box.configure(fg_color=self.current_theme["bg_color"])
        self.preview_card.configure(
            fg_color=self.current_theme["card_bg"],
            border_color=self.current_theme["border_color"]
        )
        self.prev_title.configure(text_color=self.current_theme["text_primary"])
        self.prev_sub.configure(text_color=self.current_theme["text_secondary"])
        self.prev_icon_box.configure(
            fg_color=self.current_theme["bg_color"],
            border_color=self.current_theme["accent_color"]
        )
        self.prev_status.configure(text_color=self.current_theme["accent_color"])
        self.prev_dots.configure(text_color=self.current_theme["accent_color"])
        self.prev_fallback.configure(
            border_color=self.current_theme["border_color"],
            text_color=self.current_theme["text_secondary"]
        )

        # Update top brand & test button in settings window
        self.brand_lbl.configure(text_color=self.current_theme.get("accent_color", "#00f0ff"))
        self.test_lock_btn.configure(
            fg_color=self.current_theme.get("accent_color", "#3b82f6"),
            text_color="#000000" if self.current_theme.get("accent_color", "#3b82f6") in ["#00f0ff", "#00ff41"] else "#ffffff",
            hover_color=self.current_theme.get("accent_hover", "#2563eb")
        )

    def save_appearance(self):
        self.cfg.config["appearance"]["title_text"] = self.title_input.get().strip()
        self.cfg.config["appearance"]["subtitle_text"] = self.sub_input.get().strip()
        self.cfg.config["appearance"]["show_uid_on_screen"] = self.show_uid_var.get()
        self.cfg.save()
        self.prev_title.configure(text=self.title_input.get().strip())
        self.prev_sub.configure(text=self.sub_input.get().strip())
        messagebox.showinfo("Успешно", "Настройки оформления сохранены!")

    # --- TAB 3: SECURITY & DAEMON SERVICE ---

    def _build_security_tab(self):
        # Service Control Section
        daemon_frame = ctk.CTkFrame(self.tab_security, fg_color="#1f2333", corner_radius=12)
        daemon_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            daemon_frame,
            text="Фоновая служба защиты (Win+L и блокировка сессий)",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=20, pady=(15, 8))

        ctk.CTkLabel(
            daemon_frame,
            text="Служба отслеживает ручную блокировку (Win+L), сочетание Ctrl+Alt+L, выход из сна и блокировку всех мониторов.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#7f8ea3"
        ).pack(anchor="w", padx=20, pady=(0, 10))

        d_ctrl_row = ctk.CTkFrame(daemon_frame, fg_color="transparent")
        d_ctrl_row.pack(fill="x", padx=20, pady=(0, 15))

        self.daemon_status_lbl = ctk.CTkLabel(
            d_ctrl_row,
            text="Статус: проверка...",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            width=220,
            anchor="w"
        )
        self.daemon_status_lbl.pack(side="left")

        self.btn_start_daemon = ctk.CTkButton(
            d_ctrl_row,
            text="▶ Запустить службу",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            width=150,
            command=self.start_daemon_clicked
        )
        self.btn_start_daemon.pack(side="left", padx=10)

        self.btn_stop_daemon = ctk.CTkButton(
            d_ctrl_row,
            text="⏹ Остановить",
            font=ctk.CTkFont(size=12),
            fg_color="#ef4444",
            hover_color="#dc2626",
            width=120,
            command=self.stop_daemon_clicked
        )
        self.btn_stop_daemon.pack(side="left", padx=5)

        # Policy & Attempts
        sec_frame = ctk.CTkFrame(self.tab_security, fg_color="#1f2333", corner_radius=12)
        sec_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            sec_frame,
            text="Политика попыток и действий",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=20, pady=(15, 10))

        row_att = ctk.CTkFrame(sec_frame, fg_color="transparent")
        row_att.pack(fill="x", padx=20, pady=5)

        curr_att = self.cfg.config.get("security", {}).get("max_attempts", 3)
        self.att_lbl = ctk.CTkLabel(row_att, text=f"Количество попыток ввода карты: {curr_att}", width=300, anchor="w")
        self.att_lbl.pack(side="left")

        self.att_slider = ctk.CTkSlider(
            row_att,
            from_=1,
            to=10,
            number_of_steps=9,
            command=self._on_slider_change,
            width=200
        )
        self.att_slider.set(curr_att)
        self.att_slider.pack(side="left", padx=10)

        row_act = ctk.CTkFrame(sec_frame, fg_color="transparent")
        row_act.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(row_act, text="Действие после исчерпания попыток:", width=300, anchor="w").pack(side="left")
        self.action_dropdown = ctk.CTkOptionMenu(
            row_act,
            values=["lock_workstation (Штатный вход Windows)", "shutdown (Выключение)", "restart (Перезагрузка)"],
            width=300
        )
        curr_act = self.cfg.config.get("security", {}).get("action_on_fail", "lock_workstation")
        for val in self.action_dropdown._values:
            if curr_act in val:
                self.action_dropdown.set(val)
                break
        self.action_dropdown.pack(side="left")

        self.fallback_var = ctk.BooleanVar(value=self.cfg.config.get("security", {}).get("allow_manual_fallback", True))
        chk_fallback = ctk.CTkCheckBox(
            sec_frame,
            text="Разрешить кнопку перехода к штатному входу сразу (до исчерпания попыток)",
            variable=self.fallback_var
        )
        chk_fallback.pack(anchor="w", padx=20, pady=8)

        self.beep_success_var = ctk.BooleanVar(value=self.cfg.config.get("security", {}).get("beep_on_success", True))
        chk_beep1 = ctk.CTkCheckBox(
            sec_frame,
            text="Звуковой сигнал ACR122U при успешном входе",
            variable=self.beep_success_var
        )
        chk_beep1.pack(anchor="w", padx=20, pady=5)

        self.beep_error_var = ctk.BooleanVar(value=self.cfg.config.get("security", {}).get("beep_on_error", True))
        chk_beep2 = ctk.CTkCheckBox(
            sec_frame,
            text="Звуковой сигнал ошибки ACR122U при чужой карте",
            variable=self.beep_error_var
        )
        chk_beep2.pack(anchor="w", padx=20, pady=5)

        row_pin = ctk.CTkFrame(sec_frame, fg_color="transparent")
        row_pin.pack(fill="x", padx=20, pady=(10, 15))

        ctk.CTkLabel(row_pin, text="Экстренный мастер-PIN (на случай утери карт):", width=320, anchor="w").pack(side="left")
        self.pin_entry = ctk.CTkEntry(row_pin, placeholder_text="Новый PIN / пароль", show="*", width=180)
        self.pin_entry.pack(side="left", padx=10)

        # Autostart Registration
        start_frame = ctk.CTkFrame(self.tab_security, fg_color="#1f2333", corner_radius=12)
        start_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            start_frame,
            text="Интеграция с системой (Автозапуск Windows)",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=20, pady=(15, 10))

        self.autostart_var = ctk.BooleanVar(value=is_autostart_enabled())
        self.chk_autostart = ctk.CTkCheckBox(
            start_frame,
            text="Запускать фоновую службу защиты при старте Windows (Windows Startup)",
            variable=self.autostart_var,
            command=self._on_autostart_toggled
        )
        self.chk_autostart.pack(anchor="w", padx=20, pady=10)

        save_sec_btn = ctk.CTkButton(
            self.tab_security,
            text="💾 Применить настройки безопасности",
            fg_color="#00f0ff",
            text_color="#000000",
            hover_color="#00c4d4",
            command=self.save_security,
            width=260,
            height=36
        )
        save_sec_btn.pack(anchor="w", padx=15, pady=10)

    def _update_daemon_status_lbl(self):
        active = is_daemon_running()
        if active:
            self.daemon_status_lbl.configure(text="● Служба: АКТИВНА", text_color="#10b981")
            self.btn_start_daemon.configure(state="disabled")
            self.btn_stop_daemon.configure(state="normal")
        else:
            self.daemon_status_lbl.configure(text="○ Служба: ОСТАНОВЛЕНА", text_color="#ef4444")
            self.btn_start_daemon.configure(state="normal")
            self.btn_stop_daemon.configure(state="disabled")

        # Periodically refresh status
        self.after(3000, self._update_daemon_status_lbl)

    def start_daemon_clicked(self):
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        exe = get_pythonw_executable()
        subprocess.Popen([exe, main_py, "--daemon"])
        self.after(1000, self._update_daemon_status_lbl)
        messagebox.showinfo("Служба запущена", "Фоновая служба NFC Guard успешно запущена и работает в трее!")

    def stop_daemon_clicked(self):
        # Kill daemon process via taskkill
        subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe"], capture_output=True)
        self.after(1000, self._update_daemon_status_lbl)
        messagebox.showinfo("Служба остановлена", "Фоновая служба остановлена.")

    def _on_slider_change(self, val):
        self.att_lbl.configure(text=f"Количество попыток ввода карты: {int(val)}")

    def _on_autostart_toggled(self):
        enabled = self.autostart_var.get()
        success, msg = set_autostart(enabled)
        if success:
            messagebox.showinfo("Автозапуск", msg)
        else:
            messagebox.showerror("Ошибка", msg)
            self.autostart_var.set(not enabled)

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

        sec["allow_manual_fallback"] = self.fallback_var.get()
        sec["beep_on_success"] = self.beep_success_var.get()
        sec["beep_on_error"] = self.beep_error_var.get()

        new_pin = self.pin_entry.get().strip()
        if new_pin:
            self.cfg.set_master_pin(new_pin)
            self.pin_entry.delete(0, "end")

        self.cfg.save()
        messagebox.showinfo("Успешно", "Настройки безопасности успешно обновлены!")

    # --- TAB 4: AUDIT LOGS ---

    def _build_logs_tab(self):
        log_ctrl_row = ctk.CTkFrame(self.tab_logs, fg_color="transparent")
        log_ctrl_row.pack(fill="x", padx=15, pady=10)

        ctk.CTkButton(
            log_ctrl_row,
            text="🔄 Обновить",
            width=120,
            height=32,
            command=self._refresh_logs
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            log_ctrl_row,
            text="🗑️ Очистить журнал",
            fg_color="#ef4444",
            hover_color="#dc2626",
            width=140,
            height=32,
            command=self._clear_logs
        ).pack(side="left")

        self.log_textbox = ctk.CTkTextbox(
            self.tab_logs,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#141724"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def _refresh_logs(self):
        logs = self.cfg.read_recent_logs(200)
        self.log_textbox.delete("1.0", "end")
        if not logs:
            self.log_textbox.insert("end", "Журнал событий пока пуст.")
        else:
            self.log_textbox.insert("end", "\n".join(logs))

    def _clear_logs(self):
        if messagebox.askyesno("Подтверждение", "Очистить историю журнала событий?"):
            self.cfg.clear_logs()
            self._refresh_logs()

    def launch_lock_test(self):
        """Launches the real lock screen in a separate clean process across all monitors."""
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        exe = get_pythonw_executable()
        subprocess.Popen([exe, main_py, "--lock"])
