"""Tests for platform-aware GUI theme defaults."""

from __future__ import annotations


def test_windows_font_theme_prefers_native_windows_fonts() -> None:
    from ms_preprocessing.gui.styles import build_font_theme

    fonts = build_font_theme("Windows")

    assert fonts["body"][0] == "Microsoft JhengHei UI"
    assert fonts["mono"][0] == "Consolas"


def test_macos_font_theme_prefers_native_macos_fonts() -> None:
    from ms_preprocessing.gui.styles import build_font_theme

    fonts = build_font_theme("Darwin")

    assert fonts["body"][0] == "PingFang TC"
    assert fonts["mono"][0] == "Menlo"
