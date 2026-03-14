from __future__ import annotations

import pandas as pd

from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


class TestProcessingMetadata:
    def test_default_fields_have_correct_types(self) -> None:
        metadata = ProcessingMetadata()
        assert isinstance(metadata.red_font_rows, set)
        assert isinstance(metadata.protected_rows, set)
        assert isinstance(metadata.blue_font_cells, list)
        assert isinstance(metadata.highlight_rows, set)
        assert metadata.sample_info is None
        assert metadata.deleted_feature_df is None

    def test_fields_are_independent_instances(self) -> None:
        """Each instance must have its own containers."""
        left = ProcessingMetadata()
        right = ProcessingMetadata()

        left.red_font_rows.add(1)

        assert 1 not in right.red_font_rows

    def test_as_context_dict_returns_legacy_shaped_copy(self) -> None:
        metadata = ProcessingMetadata(
            red_font_rows={1},
            protected_rows={1, 2},
            blue_font_cells=[(1, 2)],
            highlight_rows={3},
        )

        context = metadata.as_context_dict()

        assert context["red_font_rows"] == {1}
        assert context["protected_rows"] == {1, 2}
        assert context["blue_font_cells"] == [(1, 2)]
        assert context["highlight_rows"] == {3}


class TestProcessingResult:
    def test_success_result(self) -> None:
        df = pd.DataFrame({"a": [1, 2]})
        metadata = ProcessingMetadata(red_font_rows={3, 4})
        result = ProcessingResult(
            success=True,
            step="data_organizer",
            output_path="/tmp/out.parquet",
            data=df,
            metadata=metadata,
        )

        assert result.success is True
        assert result.error is None
        assert result.metadata.red_font_rows == {3, 4}
        assert result.statistics == {}

    def test_failure_result(self) -> None:
        result = ProcessingResult(
            success=False,
            step="istd_marker",
            output_path=None,
            data=None,
            metadata=ProcessingMetadata(),
            error="file not found",
        )

        assert result.success is False
        assert result.error == "file not found"

    def test_step_name_stored(self) -> None:
        result = ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=None,
            metadata=ProcessingMetadata(),
        )

        assert result.step == "feature_filter"
