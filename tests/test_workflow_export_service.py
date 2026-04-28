"""Tests for final workflow export service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.workflow.export_service import ExportService


class _FakeFileHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[pd.DataFrame, Path, dict]] = []

    def save_data(self, df, file_path, **kwargs):
        path = Path(file_path)
        self.calls.append((df, path, kwargs))
        return path


def _data() -> pd.DataFrame:
    return pd.DataFrame({"Mz/RT": ["Sample_Type"], "S1": ["case"]})


def test_export_service_default_output_naming_for_each_cli_step(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        input_path = base / "input.xlsx"
        input_path.write_text("placeholder", encoding="utf-8")

        expected_prefix = {
            "organize": "STEP1_input_",
            "istd": "STEP2_input_",
            "duplicate-removal": "STEP3_input_",
            "filter": "STEP4_input_",
            "all": "ALL_input",
        }

        for step, prefix in expected_prefix.items():
            session = PipelineSession(output_dir=base / step, source_file=input_path)
            service = ExportService(file_handler=_FakeFileHandler())
            output_path = service.export_final(
                _data(),
                output_path=None,
                input_path=input_path,
                step=step,
                session=session,
                export_deleted_feature=False,
            )
            assert output_path.parent == session.output_dir
            assert output_path.name.startswith(prefix)
            assert output_path.suffix == ".xlsx"


def test_export_service_normalizes_output_suffix_to_xlsx(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        input_path = base / "input.csv"
        input_path.write_text("placeholder", encoding="utf-8")
        handler = _FakeFileHandler()
        session = PipelineSession(output_dir=base / "out", source_file=input_path)

        output_path = ExportService(file_handler=handler).export_final(
            _data(),
            output_path=base / "custom.csv",
            input_path=input_path,
            step="filter",
            session=session,
            export_deleted_feature=False,
        )

        assert output_path == base / "custom.xlsx"
        assert handler.calls[-1][1] == output_path


def test_export_service_preserves_explicit_parquet_output_path(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        input_path = base / "input.csv"
        input_path.write_text("placeholder", encoding="utf-8")
        handler = _FakeFileHandler()
        session = PipelineSession(output_dir=base / "out", source_file=input_path)

        output_path = ExportService(file_handler=handler).export_final(
            _data(),
            output_path=base / "custom.parquet",
            input_path=input_path,
            step="filter",
            session=session,
            export_deleted_feature=False,
        )

        assert output_path == base / "custom.parquet"
        assert handler.calls[-1][1] == output_path


def test_export_service_writes_sample_info_extra_sheet(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        handler = _FakeFileHandler()
        session = PipelineSession(output_dir=base / "out", source_file=base / "input.xlsx")
        sample_info = pd.DataFrame({"Sample_Name": ["S1"]})
        session.update_context_from_metadata({"sample_info": sample_info})

        ExportService(file_handler=handler).export_final(
            _data(),
            output_path=base / "out.xlsx",
            input_path=base / "input.xlsx",
            step="all",
            session=session,
            export_deleted_feature=False,
        )

        extra_sheets = handler.calls[-1][2]["extra_sheets"]
        assert extra_sheets["SampleInfo"] is sample_info


def test_export_service_optionally_writes_deleted_feature_extra_sheet(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        handler = _FakeFileHandler()
        session = PipelineSession(output_dir=base / "out", source_file=base / "input.xlsx")
        deleted_feature = pd.DataFrame({"Feature": ["F1"]})
        session.update_context_from_metadata({"deleted_feature_df": deleted_feature})

        ExportService(file_handler=handler).export_final(
            _data(),
            output_path=base / "out.xlsx",
            input_path=base / "input.xlsx",
            step="all",
            session=session,
            export_deleted_feature=True,
        )

        extra_sheets = handler.calls[-1][2]["extra_sheets"]
        assert extra_sheets["deleted_feature"] is deleted_feature


def test_export_service_final_xlsx_export_does_not_write_parquet_cache(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        handler = _FakeFileHandler()
        session = PipelineSession(output_dir=base / "out", source_file=base / "input.xlsx")

        ExportService(file_handler=handler).export_final(
            _data(),
            output_path=base / "out.xlsx",
            input_path=base / "input.xlsx",
            step="all",
            session=session,
            export_deleted_feature=False,
        )

        assert handler.calls[-1][1].suffix == ".xlsx"
        assert handler.calls[-1][2]["save_parquet_cache"] is False
