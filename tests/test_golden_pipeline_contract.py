"""Golden contract tests for Step1-4 workflow metadata handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult
from ms_preprocessing.workflow.export_service import ExportService
from ms_preprocessing.workflow.pipeline_session import PipelineSession
from ms_preprocessing.workflow.workflow_runner import WorkflowRunner


class _CaptureFileHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[pd.DataFrame, Path, dict[str, Any]]] = []

    def save_data(self, df, file_path, **kwargs):
        path = Path(file_path)
        self.calls.append((df, path, kwargs))
        return path


def test_step1_to_step4_golden_contract_preserves_metadata_and_export_sheets(
    monkeypatch,
    project_temp_dir,
) -> None:
    import ms_preprocessing.workflow.workflow_runner as runner_module

    sample_info = pd.DataFrame(
        {
            "Sample_Name": ["SampleA", "SampleB"],
            "Sample_Type": ["case", "control"],
            "Injection_Order": [1, 2],
        }
    )
    deleted_feature = pd.DataFrame(
        {
            "Mz/RT": ["200.0000/2.00"],
            "exposure_ratio": [0.0],
            "normal_ratio": [0.05],
            "control_ratio": [0.0],
            "QC_ratio": [1.0],
            "Feature_Filter_Delete_Reasons": ["no_keep_rule"],
            "SampleA": [0.0],
            "SampleB": [10.0],
        }
    )
    step_frames = {
        "data_organizer": pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.0000/1.00", "200.0000/2.00"],
                "SampleA": ["case", 1000.0, 0.0],
                "SampleB": ["control", 900.0, 10.0],
            }
        ),
        "istd_marker": pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.0000/1.00", "200.0000/2.00"],
                "SampleA": ["case", 1000.0, 0.0],
                "SampleB": ["control", 900.0, 10.0],
            }
        ),
        "duplicate_remover": pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.0000/1.00", "200.0000/2.00"],
                "SampleA": ["case", 1000.0, 0.0],
                "SampleB": ["control", 900.0, 10.0],
            }
        ),
        "feature_filter": pd.DataFrame(
            {
                "Mz/RT": ["Sample_Type", "100.0000/1.00"],
                "SampleA": ["case", 1000.0],
                "SampleB": ["control", 900.0],
                "is_Presence_Absence_Marker": ["na", False],
                "Feature_Filter_Keep_Reasons": ["Feature_Filter_Keep_Reasons", "stable"],
                "Imputation_Tag_Reasons": ["Imputation_Tag_Reasons", ""],
                "exposure_ratio": ["exposure_ratio", 1.0],
                "normal_ratio": ["normal_ratio", 1.0],
                "control_ratio": ["control_ratio", 1.0],
                "QC_ratio": ["QC_ratio", 1.0],
            }
        ),
    }
    protected_seen: dict[str, set[int]] = {}

    def _result(step: str, metadata: ProcessingMetadata) -> ProcessingResult:
        return ProcessingResult(
            success=True,
            step=step,
            output_path=None,
            data=step_frames[step],
            metadata=metadata,
            statistics={"contract_step": step},
        )

    monkeypatch.setattr(
        runner_module._adapter_do,
        "run_from_df",
        lambda data, **kwargs: _result(
            "data_organizer",
            ProcessingMetadata(sample_info=sample_info, protected_rows={1}),
        ),
    )
    monkeypatch.setattr(
        runner_module._adapter_istd,
        "run_from_df",
        lambda data, **kwargs: _result(
            "istd_marker",
            ProcessingMetadata(red_font_rows={2}, protected_rows={2}),
        ),
    )

    def _run_step3(data, **kwargs):
        protected_seen["step3"] = set(kwargs["protected_rows"])
        return _result(
            "duplicate_remover",
            ProcessingMetadata(red_font_rows={1, 2}, protected_rows={1, 2}),
        )

    def _run_step4(data, **kwargs):
        protected_seen["step4"] = set(kwargs["protected_rows"])
        return _result(
            "feature_filter",
            ProcessingMetadata(
                red_font_rows={1},
                protected_rows={1, 2},
                deleted_feature_df=deleted_feature,
            ),
        )

    monkeypatch.setattr(runner_module._adapter_dr, "run_from_df", _run_step3)
    monkeypatch.setattr(runner_module._adapter_ff, "run_from_df", _run_step4)

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        xic_results_file = base / "xic_results.xlsx"
        xic_results_file.write_text("placeholder", encoding="utf-8")
        session = PipelineSession(output_dir=base / "out", source_file=base / "input.xlsx")

        run_result = WorkflowRunner().run(
            pd.DataFrame({"raw": [1]}),
            step="all",
            resolved_parameters={
                "step1": {"method_file": None},
                "step2": {"xic_results_file": xic_results_file},
                "step3": {"mz_tolerance_ppm": 20.0, "rt_tolerance": 0.1},
                "step4": {"high_det_thresh": 0.8, "low_det_thresh": 0.2},
            },
            session=session,
        )

        file_handler = _CaptureFileHandler()
        ExportService(file_handler=file_handler).export_final(
            run_result.data,
            output_path=base / "final.xlsx",
            input_path=base / "input.xlsx",
            step="all",
            session=session,
            export_deleted_feature=True,
        )

    assert run_result.success is True
    assert run_result.completed_steps == [
        "data_organizer",
        "istd_marker",
        "duplicate_remover",
        "feature_filter",
    ]
    assert list(run_result.data.columns) == [
        "Mz/RT",
        "SampleA",
        "SampleB",
        "is_Presence_Absence_Marker",
        "Feature_Filter_Keep_Reasons",
        "Imputation_Tag_Reasons",
        "exposure_ratio",
        "normal_ratio",
        "control_ratio",
        "QC_ratio",
    ]
    assert "Detection_Profile" not in run_result.data.columns
    assert protected_seen == {"step3": {2}, "step4": {1, 2}}
    assert session.metadata.protected_rows == {1, 2}
    assert session.metadata.sample_info is sample_info
    assert session.metadata.deleted_feature_df is deleted_feature

    snapshot = session.snapshot()
    assert snapshot["metadata_refs"] == {
        "sample_info_ref": "SampleInfo",
        "deleted_feature_ref": "deleted_feature",
    }

    extra_sheets = file_handler.calls[-1][2]["extra_sheets"]
    assert extra_sheets["SampleInfo"] is sample_info
    assert extra_sheets["deleted_feature"] is deleted_feature
    assert list(extra_sheets["deleted_feature"].columns) == [
        "Mz/RT",
        "exposure_ratio",
        "normal_ratio",
        "control_ratio",
        "QC_ratio",
        "Feature_Filter_Delete_Reasons",
        "SampleA",
        "SampleB",
    ]
    assert file_handler.calls[-1][2]["red_font_rows"] == {1}
    assert file_handler.calls[-1][2]["save_parquet_cache"] is False

    from ms_core.utils.sample_classification import identify_sample_columns

    sample_columns, dropped_columns = identify_sample_columns(run_result.data, sample_info)
    assert sample_columns == ["SampleA", "SampleB"]
    assert "is_Presence_Absence_Marker" not in sample_columns
    assert "Feature_Filter_Keep_Reasons" not in sample_columns
    assert "Imputation_Tag_Reasons" not in sample_columns
    assert {"exposure_ratio", "normal_ratio", "control_ratio", "QC_ratio"} <= set(dropped_columns)


def test_step4_golden_contract_clears_stale_deleted_feature_sheet(
    monkeypatch,
    project_temp_dir,
) -> None:
    import ms_preprocessing.workflow.workflow_runner as runner_module

    stale_deleted_feature = pd.DataFrame(
        {
            "Mz/RT": ["stale"],
            "Feature_Filter_Delete_Reasons": ["no_keep_rule"],
        }
    )
    step4_output = pd.DataFrame(
        {
            "Mz/RT": ["Sample_Type", "100.0000/1.00"],
            "SampleA": ["case", 1000.0],
            "SampleB": ["control", 900.0],
            "is_Presence_Absence_Marker": ["na", False],
            "Feature_Filter_Keep_Reasons": ["Feature_Filter_Keep_Reasons", "stable"],
            "Imputation_Tag_Reasons": ["Imputation_Tag_Reasons", ""],
            "exposure_ratio": ["exposure_ratio", 1.0],
            "normal_ratio": ["normal_ratio", 1.0],
            "control_ratio": ["control_ratio", 1.0],
            "QC_ratio": ["QC_ratio", 1.0],
        }
    )

    monkeypatch.setattr(
        runner_module._adapter_ff,
        "run_from_df",
        lambda data, **kwargs: ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=step4_output,
            metadata=ProcessingMetadata(
                red_font_rows=set(),
                protected_rows=set(kwargs["protected_rows"]),
                deleted_feature_df=None,
            ),
        ),
    )

    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base / "out", source_file=base / "input.xlsx")
        session.update_context_from_metadata({"deleted_feature_df": stale_deleted_feature})

        run_result = WorkflowRunner().run(
            pd.DataFrame({"raw": [1]}),
            step="filter",
            resolved_parameters={
                "step4": {"high_det_thresh": 0.8, "low_det_thresh": 0.2},
            },
            session=session,
        )

        file_handler = _CaptureFileHandler()
        ExportService(file_handler=file_handler).export_final(
            run_result.data,
            output_path=base / "final.xlsx",
            input_path=base / "input.xlsx",
            step="filter",
            session=session,
            export_deleted_feature=True,
        )

    assert run_result.success is True
    assert session.metadata.deleted_feature_df is None
    assert session.context["deleted_feature_df"] is None
    assert session.snapshot()["metadata_refs"]["deleted_feature_ref"] is None
    extra_sheets = file_handler.calls[-1][2]["extra_sheets"] or {}
    assert "deleted_feature" not in extra_sheets
