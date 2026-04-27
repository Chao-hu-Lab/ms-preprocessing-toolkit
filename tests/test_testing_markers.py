"""Tests for repo-local pytest marker classification."""

from __future__ import annotations

from pathlib import Path

from tests.testing_markers import classify_test_markers


def test_smoke_marker_selects_only_fast_entrypoint_files() -> None:
    markers = classify_test_markers(Path("tests") / "test_smoke_guardrails.py")

    assert markers == {"smoke"}


def test_adapter_marker_selects_adapter_folder_and_api_contract() -> None:
    adapter_markers = classify_test_markers(
        Path("tests") / "adapters" / "test_adapter_feature_filter.py"
    )
    contract_markers = classify_test_markers(Path("tests") / "test_ms_core_api_contract.py")

    assert adapter_markers == {"adapter"}
    assert contract_markers == {"adapter", "smoke"}


def test_gui_marker_is_serial_by_default() -> None:
    widget_markers = classify_test_markers(Path("tests") / "test_feature_filter_widget.py")
    helper_markers = classify_test_markers(Path("tests") / "test_gui_validation.py")

    assert widget_markers == {"gui", "serial"}
    assert helper_markers == {"gui", "serial"}


def test_integration_and_perf_markers_can_overlap() -> None:
    markers = classify_test_markers(Path("tests") / "test_pipeline_baseline_contract.py")

    assert markers == {"integration", "perf"}


def test_root_hygiene_is_serial_without_being_gui() -> None:
    markers = classify_test_markers(Path("tests") / "test_root_hygiene.py")

    assert markers == {"serial"}
