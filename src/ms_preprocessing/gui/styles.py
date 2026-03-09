"""
GUI styles and theme configuration for MS Preprocessing Toolkit.
"""

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
    "text": "#ffffff",
    "text_secondary": "#a0a0a0",
}

# Font settings
FONTS = {
    "title": ("Microsoft JhengHei UI", 20, "bold"),
    "heading": ("Microsoft JhengHei UI", 16, "bold"),
    "body": ("Microsoft JhengHei UI", 15),
    "small": ("Microsoft JhengHei UI", 13),
    "mono": ("Consolas", 13),
}

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
    "sidebar_width": 180,     # 縮小（原 220）
    "log_height": 150,        # 微調
    "action_bar_height": 52,  # 新增
    "left_panel_width": 420,  # 新增：雙欄左欄固定寬度
}
