"""Central pytest marker classification rules for the top-level suite."""

from __future__ import annotations

from pathlib import Path

SMOKE_TEST_FILES = frozenset(
    {
        "test_bootstrap_paths.py",
        "test_ms_core_api_contract.py",
        "test_smoke_guardrails.py",
    }
)

ADAPTER_TEST_FILES = frozenset(
    {
        "test_cross_project_adapter_contracts.py",
        "test_ms_core_api_contract.py",
    }
)

INTEGRATION_TEST_FILES = frozenset(
    {
        "test_combined_tsv_service.py",
        "test_cli_parquet_chain.py",
        "test_final_export_handoff.py",
        "test_final_export_cache_policy.py",
        "test_integration_parquet_pipeline.py",
        "test_intermediate_store_bridge.py",
        "test_parquet_compat.py",
        "test_pipeline_baseline_contract.py",
        "test_regressions.py",
        "test_workflow_export_service.py",
        "test_workflow_input_loader.py",
        "test_workflow_runner.py",
    }
)

PERF_TEST_FILES = frozenset(
    {
        "test_perf_guardrails.py",
        "test_pipeline_baseline_contract.py",
        "test_step4_user_dataset_verification.py",
    }
)

SERIAL_TEST_FILES = frozenset(
    {
        "test_root_hygiene.py",
    }
)


def classify_test_markers(path: Path | str) -> set[str]:
    """Return pytest markers implied by a test file path."""
    test_path = Path(path)
    file_name = test_path.name
    parts = {part.lower() for part in test_path.parts}
    markers: set[str] = set()

    if file_name in SMOKE_TEST_FILES:
        markers.add("smoke")

    if "adapters" in parts or file_name in ADAPTER_TEST_FILES:
        markers.add("adapter")

    if file_name.startswith("test_gui_") or file_name.endswith("_widget.py"):
        markers.update({"gui", "serial"})

    if file_name in INTEGRATION_TEST_FILES:
        markers.add("integration")

    if file_name in PERF_TEST_FILES:
        markers.add("perf")

    if file_name in SERIAL_TEST_FILES:
        markers.add("serial")

    return markers
