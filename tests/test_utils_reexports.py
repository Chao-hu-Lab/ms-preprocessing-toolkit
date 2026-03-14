"""Regression tests for utility package re-exports."""

from __future__ import annotations


def test_utils_package_reexports_local_symbols() -> None:
    from ms_preprocessing.utils import DataValidator, FileHandler, detect_fixed_columns
    from ms_preprocessing.utils.file_handler import FileHandler as LocalFileHandler
    from ms_preprocessing.utils.validators import (
        DataValidator as LocalDataValidator,
        detect_fixed_columns as local_detect_fixed_columns,
    )

    assert DataValidator is LocalDataValidator
    assert FileHandler is LocalFileHandler
    assert detect_fixed_columns is local_detect_fixed_columns
