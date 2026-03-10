"""Tests for GUI pipeline session orchestration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class _FakeFileHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, dict]] = []

    def save_data(self, df, file_path, **kwargs):
        path = Path(file_path)
        self.calls.append((path, kwargs))
        return path


def test_gui_pipeline_session_stores_step_outputs_as_parquet_until_final_export(
    monkeypatch,
    tmp_path,
) -> None:
    from ms_preprocessing.gui.pipeline_session import PipelineSession

    base = tmp_path
    cache_root = base / "internal-cache"
    monkeypatch.setenv("MSPTK_PARQUET_CACHE_ROOT", str(cache_root))
    output_dir = base / "OUTPUT"
    session = PipelineSession(output_dir=output_dir, source_file=base / "input.xlsx")
    handler = _FakeFileHandler()
    df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.1/1.0"], "Case1": ["case", 1234]})

    paths = [session.save_step_output(step_index=i, data=df, file_handler=handler) for i in range(4)]
    assert all(path.suffix == ".parquet" for path in paths)
    assert all(output_dir not in path.parents for path in paths)
    assert all(cache_root in path.parents for path in paths)

    final_path = session.build_final_export_path(last_completed_step=3, last_run_all=True)
    assert final_path.suffix == ".xlsx"


def test_output_directory_contains_only_user_deliverables_after_run_all(
    monkeypatch,
    tmp_path,
) -> None:
    from ms_preprocessing.gui.pipeline_session import PipelineSession

    base = tmp_path
    cache_root = base / "internal-cache"
    monkeypatch.setenv("MSPTK_PARQUET_CACHE_ROOT", str(cache_root))
    session = PipelineSession(output_dir=base / "OUTPUT", source_file=base / "input.xlsx")
    handler = _FakeFileHandler()
    df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.1/1.0"], "Case1": ["case", 1234]})

    step_path = session.save_step_output(step_index=0, data=df, file_handler=handler)
    final_path = session.build_final_export_path(last_completed_step=3, last_run_all=True)

    assert step_path.suffix == ".parquet"
    assert (base / "OUTPUT") not in step_path.parents
    assert final_path.parent == (base / "OUTPUT")


def test_gui_parameters_are_collected_in_single_pipeline_session_context(tmp_path) -> None:
    from ms_preprocessing.gui.pipeline_session import PipelineSession

    base = tmp_path
    session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
    session.record_step_parameters(0, {"mode": "normalization"})
    session.record_step_parameters(
        3,
        {
            "qc_ratio_threshold": 0.25,
            "enable_background_threshold": True,
            "enable_skew_threshold": False,
            "enable_diff_threshold": True,
            "enable_qc_ratio_threshold": False,
        },
    )
    session.update_context_from_metadata(
        {
            "sample_info_ref": "SampleInfo",
            "deleted_feature_ref": "deleted_feature",
            "red_font_rows": [1],
            "protected_rows": [1],
        }
    )

    snapshot = session.snapshot()
    assert snapshot["step_parameters"][0]["mode"] == "normalization"
    assert snapshot["step_parameters"][3]["qc_ratio_threshold"] == 0.25
    assert snapshot["step_parameters"][3]["enable_background_threshold"] is True
    assert snapshot["step_parameters"][3]["enable_skew_threshold"] is False
    assert snapshot["step_parameters"][3]["enable_diff_threshold"] is True
    assert snapshot["step_parameters"][3]["enable_qc_ratio_threshold"] is False
    assert snapshot["metadata_refs"]["sample_info_ref"] == "SampleInfo"
    assert snapshot["metadata_refs"]["deleted_feature_ref"] == "deleted_feature"
