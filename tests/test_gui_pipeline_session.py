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


def test_update_from_result_merges_metadata_and_tracks_completed_steps(tmp_path) -> None:
    from ms_preprocessing.gui.pipeline_session import PipelineSession
    from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

    base = tmp_path
    session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
    context_alias = session.context
    sample_info = pd.DataFrame({"Sample_Name": ["A"]})

    session.update_from_result(
        ProcessingResult(
            success=True,
            step="data_organizer",
            output_path=str(base / "step1.parquet"),
            data=None,
            metadata=ProcessingMetadata(
                red_font_rows={1},
                protected_rows={1},
                blue_font_cells=["B2"],
                highlight_rows={4},
                sample_info=sample_info,
            ),
        )
    )
    session.update_from_result(
        ProcessingResult(
            success=True,
            step="duplicate_remover",
            output_path=str(base / "step3.parquet"),
            data=None,
            metadata=ProcessingMetadata(
                protected_rows={2},
                blue_font_cells=["C3"],
                highlight_rows={5},
            ),
        )
    )

    assert session.can_run_step("duplicate_remover") is True
    assert session.can_run_step("feature_filter") is True
    assert session.completed_steps == {"data_organizer", "duplicate_remover"}
    assert session.metadata.red_font_rows == {1}
    assert session.metadata.protected_rows == {1, 2}
    assert session.metadata.blue_font_cells == ["B2", "C3"]
    assert session.metadata.highlight_rows == {4, 5}
    assert session.metadata.sample_info is sample_info
    assert context_alias is session.context
    assert context_alias["red_font_rows"] == {1}
    assert context_alias["protected_rows"] == {1, 2}
    assert context_alias["blue_font_cells"] == ["B2", "C3"]
    assert context_alias["highlight_rows"] == {4, 5}
    assert session.context["sample_info"] is sample_info
    assert session.step_outputs["data_organizer"].endswith("step1.parquet")


def test_update_context_from_metadata_merges_legacy_formatting_across_steps(tmp_path) -> None:
    from ms_preprocessing.gui.pipeline_session import PipelineSession

    base = tmp_path
    session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")

    session.update_context_from_metadata(
        {
            "red_font_rows": [1],
            "protected_rows": [1],
            "blue_font_cells": ["B2"],
            "highlight_rows": [4],
        }
    )
    session.update_context_from_metadata(
        {
            "protected_rows": [2],
            "blue_font_cells": ["C3"],
            "highlight_rows": [5],
        }
    )

    assert session.metadata.red_font_rows == {1}
    assert session.metadata.protected_rows == {1, 2}
    assert session.metadata.blue_font_cells == ["B2", "C3"]
    assert session.metadata.highlight_rows == {4, 5}
    assert session.context["red_font_rows"] == {1}
    assert session.context["protected_rows"] == {1, 2}
    assert session.context["blue_font_cells"] == ["B2", "C3"]
    assert session.context["highlight_rows"] == {4, 5}
