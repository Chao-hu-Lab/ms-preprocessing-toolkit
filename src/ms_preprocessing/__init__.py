"""
MS Preprocessing Toolkit - Mass Spectrometry Data Preprocessing Package

A comprehensive toolkit for preprocessing mass spectrometry data with
integrated GUI support for the complete workflow:
1. Data Organization
2. ISTD Marking
3. Duplicate Signal Removal
4. Feature Filtering and Missing Value Imputation
"""

from pathlib import Path

from .bootstrap_paths import ensure_ms_core_src_on_path

ensure_ms_core_src_on_path(Path(__file__).resolve())

__version__ = "1.0.0"
__author__ = "Your Name"

from ms_core.preprocessing.data_organizer import DataOrganizer
from ms_core.preprocessing.istd_marker import ISTDMarker
from ms_core.preprocessing.duplicate_remover import DuplicateRemover
from ms_core.preprocessing.ms_quality_filter import FeatureFilter

__all__ = [
    "DataOrganizer",
    "ISTDMarker",
    "DuplicateRemover",
    "FeatureFilter",
]
