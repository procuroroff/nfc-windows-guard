"""Vector-rendered Apple SF-style icons using PIL supersampling.
Generates smooth, crisp icons without relying on OS emojis.
"""

from PIL import Image, ImageDraw
import customtkinter as ctk
from typing import Tuple


def hex_to_rgba(hex_str: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Converts hex color string (#RRGGBB) to (r, g, b, a)."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return (r, g, b, alpha)


def create_nfc_glyph(
    size: int = 80,
    color_hex: str = "#0a84ff",
    bg_hex: str = "#18181b",
    border_hex: str = "#27272a"
) -> ctk.CTkImage:
    """Generates the Apple contactless payment wave symbol inside a subtle squircle."""
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded squircle background
    radius = int(s * 0.45)
    bg_color = hex_to_rgba(bg_hex)
    border_color = hex_to_rgba(border_hex)

    draw.rounded_rectangle(
        (0, 0, s - 1, s - 1),
        radius=radius,
        fill=bg_color,
        outline=border_color,
        width=int(s * 0.02)
    )

    # 4 Contactless wave arcs
    cx = s * 0.38
    cy = s * 0.50
    radii = [s * 0.14, s * 0.26, s * 0.38, s * 0.50]
    widths = [int(s * 0.038), int(s * 0.040), int(s * 0.042), int(s * 0.044)]
    fg_color = hex_to_rgba(color_hex)

    for r, w in zip(radii, widths):
        bbox = (cx - r, cy - r, cx + r, cy + r)
        draw.arc(bbox, start=-46, end=46, fill=fg_color, width=w)

    final = img.resize((size, size), Image.Resampling.LANCZOS)
    return ctk.CTkImage(light_image=final, dark_image=final, size=(size, size))


def create_lock_glyph(size: int = 48, color_hex: str = "#f5f5f7") -> ctk.CTkImage:
    """Generates an Apple SF-style minimalist padlock glyph."""
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = hex_to_rgba(color_hex)

    # Padlock shackle (top arch)
    shackle_bbox = (int(s * 0.28), int(s * 0.12), int(s * 0.72), int(s * 0.56))
    shackle_w = int(s * 0.08)
    draw.arc(shackle_bbox, start=180, end=360, fill=color, width=shackle_w)

    # Padlock body
    body_bbox = (int(s * 0.20), int(s * 0.44), int(s * 0.80), int(s * 0.88))
    draw.rounded_rectangle(body_bbox, radius=int(s * 0.09), fill=color)

    # Keyhole
    hole_color = (18, 18, 20, 255)
    kh_center = (int(s * 0.50), int(s * 0.62))
    kh_r = int(s * 0.055)
    draw.ellipse(
        (kh_center[0] - kh_r, kh_center[1] - kh_r, kh_center[0] + kh_r, kh_center[1] + kh_r),
        fill=hole_color
    )
    draw.polygon(
        [
            (kh_center[0] - int(kh_r * 0.6), kh_center[1] + int(kh_r * 0.3)),
            (kh_center[0] + int(kh_r * 0.6), kh_center[1] + int(kh_r * 0.3)),
            (kh_center[0] + int(kh_r * 0.9), kh_center[1] + int(kh_r * 2.4)),
            (kh_center[0] - int(kh_r * 0.9), kh_center[1] + int(kh_r * 2.4)),
        ],
        fill=hole_color
    )

    final = img.resize((size, size), Image.Resampling.LANCZOS)
    return ctk.CTkImage(light_image=final, dark_image=final, size=(size, size))


def create_status_dot(size: int = 10, color_hex: str = "#30d158") -> ctk.CTkImage:
    """Generates a smooth circular indicator dot."""
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = hex_to_rgba(color_hex)
    draw.ellipse((0, 0, s - 1, s - 1), fill=color)
    final = img.resize((size, size), Image.Resampling.LANCZOS)
    return ctk.CTkImage(light_image=final, dark_image=final, size=(size, size))


def create_tray_icon_pil() -> Image.Image:
    """Generates 64x64 icon for Windows System Tray."""
    scale = 4
    s = 64 * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Apple-style squircle background
    draw.rounded_rectangle(
        (int(s * 0.06), int(s * 0.06), int(s * 0.94), int(s * 0.94)),
        radius=int(s * 0.28),
        fill=(22, 22, 24, 255),
        outline=(50, 50, 54, 255),
        width=int(s * 0.03)
    )

    # Padlock shackle
    shackle_bbox = (int(s * 0.30), int(s * 0.22), int(s * 0.70), int(s * 0.60))
    draw.arc(shackle_bbox, start=180, end=360, fill=(10, 132, 255, 255), width=int(s * 0.08))

    # Padlock body
    body_bbox = (int(s * 0.25), int(s * 0.48), int(s * 0.75), int(s * 0.82))
    draw.rounded_rectangle(body_bbox, radius=int(s * 0.08), fill=(10, 132, 255, 255))

    return img.resize((64, 64), Image.Resampling.LANCZOS)
