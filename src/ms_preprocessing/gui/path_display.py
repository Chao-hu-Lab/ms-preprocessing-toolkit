"""Helpers for compact user-facing path display."""

from __future__ import annotations

from pathlib import PurePath, PureWindowsPath
from typing import Any


def display_basename(value: Any) -> str:
    """Return a filename for Windows or POSIX-style path strings."""
    text = str(value)
    return PureWindowsPath(text).name or PurePath(text).name or text
