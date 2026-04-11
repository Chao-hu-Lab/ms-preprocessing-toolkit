"""API surface contract tests for ms-core.

These tests do NOT verify behaviour — they verify that the public API
symbols exist at the expected locations. CI failure here means ms-core
changed a public API without notifying consumers (toolkit, DNP).

When ms-core removes or renames a symbol listed here:
  1. Bump ms-core minor version (v0.x+1.0)
  2. Update this file to match the new API
  3. Update all adapter call sites
"""

from __future__ import annotations


def test_preprocessing_package_exports_all_expected_symbols() -> None:
    """ms_core.preprocessing must export these symbols at package level."""
    from ms_core.preprocessing import (  # noqa: F401
        DataOrganizer,
        DataOrganizerConfig,
        DuplicateRemovalConfig,
        DuplicateRemover,
        FeatureFilter,
        FeatureFilterConfig,
        ISTDConfig,
        ISTDMarker,
        Settings,
    )


def test_feature_filter_public_methods_exist() -> None:
    from ms_core.preprocessing import FeatureFilter

    assert callable(getattr(FeatureFilter, "validate_input", None))
    assert callable(getattr(FeatureFilter, "process", None))
    assert callable(getattr(FeatureFilter, "count_analysis_groups", None))
    assert callable(getattr(FeatureFilter, "get_group_summary", None))


def test_istd_marker_public_methods_exist() -> None:
    from ms_core.preprocessing import ISTDMarker

    assert callable(getattr(ISTDMarker, "validate_input", None))
    assert callable(getattr(ISTDMarker, "process", None))


def test_duplicate_remover_public_methods_exist() -> None:
    from ms_core.preprocessing import DuplicateRemover

    assert callable(getattr(DuplicateRemover, "validate_input", None))
    assert callable(getattr(DuplicateRemover, "process", None))


def test_data_organizer_public_methods_exist() -> None:
    from ms_core.preprocessing import DataOrganizer

    assert callable(getattr(DataOrganizer, "validate_input", None))
    assert callable(getattr(DataOrganizer, "process", None))


def test_settings_public_methods_exist() -> None:
    from ms_core.preprocessing import Settings

    assert callable(getattr(Settings, "get_parquet_cache_root", None))
