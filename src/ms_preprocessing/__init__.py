"""ms-preprocessing package public application-layer API."""

from pathlib import Path

from .bootstrap_paths import ensure_ms_core_src_on_path

ensure_ms_core_src_on_path(Path(__file__).resolve())

__version__ = "1.2.1"
__author__ = "bosschen0429"

from ms_preprocessing.adapters import (
    data_organizer,
    duplicate_remover,
    feature_filter,
    istd_marker,
)
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

__all__ = [
    "__version__",
    "__author__",
    "ProcessingResult",
    "ProcessingMetadata",
    "data_organizer",
    "istd_marker",
    "duplicate_remover",
    "feature_filter",
]
