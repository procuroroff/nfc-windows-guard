"""Apple Typography Manager.
Dynamically registers and provisions authentic Apple SF Pro Display fonts on Windows.
"""

import os
import ctypes
import customtkinter as ctk

_FONTS_INITIALIZED = False
_SF_PRO_AVAILABLE = False


def init_apple_fonts():
    """Registers bundled SF Pro Display font files with Windows GDI."""
    global _FONTS_INITIALIZED, _SF_PRO_AVAILABLE
    if _FONTS_INITIALIZED:
        return _SF_PRO_AVAILABLE

    fonts_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
    loaded = 0
    if os.path.isdir(fonts_dir):
        for f in os.listdir(fonts_dir):
            if f.lower().endswith((".otf", ".ttf")):
                font_path = os.path.abspath(os.path.join(fonts_dir, f))
                # 0x10 = FR_PRIVATE (process-local font registration)
                res = ctypes.windll.gdi32.AddFontResourceExW(font_path, 0x10, 0)
                if res > 0:
                    loaded += 1

    _SF_PRO_AVAILABLE = (loaded > 0)
    _FONTS_INITIALIZED = True
    return _SF_PRO_AVAILABLE


def get_apple_font_family() -> str:
    """Returns 'SF Pro Display' if available, otherwise 'Segoe UI Variable Display' or 'Segoe UI'."""
    init_apple_fonts()
    if _SF_PRO_AVAILABLE:
        return "SF Pro Display"
    return "Segoe UI"


def font_clock(size: int = 68, weight: str = "normal") -> ctk.CTkFont:
    """Apple Lock Screen clock font (light, clean, grand)."""
    return ctk.CTkFont(family=get_apple_font_family(), size=size, weight=weight)


def font_large_title(size: int = 24, weight: str = "bold") -> ctk.CTkFont:
    return ctk.CTkFont(family=get_apple_font_family(), size=size, weight=weight)


def font_title(size: int = 18, weight: str = "bold") -> ctk.CTkFont:
    return ctk.CTkFont(family=get_apple_font_family(), size=size, weight=weight)


def font_headline(size: int = 14, weight: str = "bold") -> ctk.CTkFont:
    return ctk.CTkFont(family=get_apple_font_family(), size=size, weight=weight)


def font_body(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=get_apple_font_family(), size=size, weight=weight)


def font_caption(size: int = 11, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=get_apple_font_family(), size=size, weight=weight)


def font_mono(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family="Consolas", size=size, weight=weight)
