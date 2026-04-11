"""
GUI styles and theme configuration for MS Preprocessing Toolkit.
"""

from __future__ import annotations

import platform

# Color scheme
COLORS = {
    "primary": "#1f538d",
    "secondary": "#2d6a4f",
    "accent": "#52b788",
    "warning": "#f9c74f",
    "error": "#f94144",
    "success": "#52b788",
    "background": "#1a1a2e",
    "surface": "#16213e",
    "sidebar_bg": "#1E1E1E",
    "sidebar_divider": "#2A2A2A",
    "action_primary": "#2E8B57",
    "action_primary_hover": "#3CB371",
    "action_primary_border": "#3CB371",
    "action_secondary": "#333333",
    "action_secondary_hover": "#404040",
    "action_secondary_border": "#555555",
    "action_secondary_border_hover": "#777777",
    "action_disabled_border": "#444444",
    "action_disabled_text": "#666666",
    "text": "#ffffff",
    "text_secondary": "#a0a0a0",
}

def _font_families_for_platform(system_name: str | None = None) -> dict[str, str]:
    system = system_name or platform.system()
    if system == "Darwin":
        return {
            "ui": "PingFang TC",
            "mono": "Menlo",
        }
    if system == "Windows":
        return {
            "ui": "Microsoft JhengHei UI",
            "mono": "Consolas",
        }
    return {
        "ui": "Noto Sans CJK TC",
        "mono": "DejaVu Sans Mono",
    }


def build_font_theme(system_name: str | None = None) -> dict[str, tuple]:
    families = _font_families_for_platform(system_name)
    return {
        "title": (families["ui"], 20, "bold"),
        "heading": (families["ui"], 16, "bold"),
        "body": (families["ui"], 15),
        "small": (families["ui"], 13),
        "mono": (families["mono"], 13),
    }


# Font settings
FONTS = build_font_theme()

# Padding and spacing
PADDING = {
    "small": 6,
    "medium": 12,
    "large": 20,
}

# Widget dimensions
DIMENSIONS = {
    "button_width": 120,
    "entry_width": 200,
    "sidebar_width": 240,
    "log_height": 110,
    "action_bar_height": 52,
    "left_panel_width": 420,
    "content_top_offset": 48,
    "form_label_width": 180,
    "form_switch_width": 220,
    "form_value_width": 160,
    "numeric_input_width": 130,
}
