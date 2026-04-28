"""Tests for workflow input loading boundaries."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ms_preprocessing.workflow.input_loader import InputLoader
from ms_preprocessing.workflow.pipeline_session import PipelineSession


class _FakeFileHandler:
    def __init__(self, data: pd.DataFrame, metadata: dict) -> None:
        self.data = data
        self.metadata = metadata
        self.loaded_paths: list[Path] = []

    def load_data(self, file_path, sheet_name=0, header_row=0):
        _ = (sheet_name, header_row)
        self.loaded_paths.append(Path(file_path))
        return self.data.copy(), dict(self.metadata)


def test_input_loader_updates_session_from_file_metadata(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        input_path = base / "input.csv"
        input_path.write_text("placeholder", encoding="utf-8")
        data = pd.DataFrame({"Mz/RT": ["Sample_Type"], "S1": ["case"]})
        handler = _FakeFileHandler(
            data=data,
            metadata={"red_font_rows": [2], "protected_rows": [2, 5], "blue_font_cells": [(1, 1)]},
        )
        session = PipelineSession(output_dir=base / "out")

        loaded = InputLoader(file_handler=handler).load(input_path, session=session)

        assert handler.loaded_paths == [input_path]
        pd.testing.assert_frame_equal(loaded.data, data)
        assert loaded.metadata["red_font_rows"] == [2]
        assert session.source_file == input_path
        assert session.metadata.red_font_rows == {2}
        assert session.metadata.protected_rows == {2, 5}
        assert session.metadata.blue_font_cells == [(1, 1)]


def test_input_loader_preserves_sample_info_and_deleted_feature_sheets(project_temp_dir) -> None:
    with project_temp_dir() as temp_dir:
        base = Path(temp_dir)
        input_path = base / "input.xlsx"
        raw = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 100]})
        sample_info = pd.DataFrame({"Sample_Name": ["S1"], "Batch": ["B1"]})
        deleted_feature = pd.DataFrame({"Feature": ["F1"]})
        notes = pd.DataFrame({"Note": ["keep"]})
        with pd.ExcelWriter(input_path, engine="openpyxl") as writer:
            raw.to_excel(writer, sheet_name="RawIntensity", index=False)
            sample_info.to_excel(writer, sheet_name="SampleInfo", index=False)
            deleted_feature.to_excel(writer, sheet_name="deleted_feature", index=False)
            notes.to_excel(writer, sheet_name="Notes", index=False)

        handler = _FakeFileHandler(
            data=raw,
            metadata={"format": "excel", "sheet_name": "RawIntensity", "red_font_rows": []},
        )
        session = PipelineSession(output_dir=base / "out")

        loaded = InputLoader(file_handler=handler).load(input_path, session=session)

        pd.testing.assert_frame_equal(session.metadata.sample_info, sample_info)
        pd.testing.assert_frame_equal(session.metadata.deleted_feature_df, deleted_feature)
        pd.testing.assert_frame_equal(loaded.preserved_sheets["Notes"], notes)
        pd.testing.assert_frame_equal(session.preserved_sheets["Notes"], notes)
