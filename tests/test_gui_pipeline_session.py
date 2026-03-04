"""Tests for GUI pipeline session orchestration."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd


class _FakeFileHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, dict]] = []

    def save_data(self, df, file_path, **kwargs):
        path = Path(file_path)
        self.calls.append((path, kwargs))
        return path


def test_gui_pipeline_session_stores_step_outputs_as_parquet_until_final_export() -> None:
    from ms_preprocessing.gui.pipeline_session import PipelineSession

    with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        handler = _FakeFileHandler()
        df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.1/1.0"], "Case1": ["case", 1234]})

        paths = [session.save_step_output(step_index=i, data=df, file_handler=handler) for i in range(4)]
        assert all(path.suffix == ".parquet" for path in paths)

        final_path = session.build_final_export_path(last_completed_step=3, last_run_all=True)
        assert final_path.suffix == ".xlsx"


def test_gui_parameters_are_collected_in_single_pipeline_session_context() -> None:
    from ms_preprocessing.gui.pipeline_session import PipelineSession

    with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        base = Path(temp_dir)
        session = PipelineSession(output_dir=base, source_file=base / "input.xlsx")
        session.record_step_parameters(0, {"mode": "normalization"})
        session.record_step_parameters(3, {"qc_ratio_threshold": 0.25})
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
        assert snapshot["metadata_refs"]["sample_info_ref"] == "SampleInfo"
        assert snapshot["metadata_refs"]["deleted_feature_ref"] == "deleted_feature"
