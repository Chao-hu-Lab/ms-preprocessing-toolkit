"""Tests for new validation result and step-prerequisite APIs."""

from __future__ import annotations

import pandas as pd

from ms_preprocessing.gui.pipeline_session import PipelineSession
from ms_preprocessing.utils.validators import DataValidator, ValidationResult


class TestValidationResult:
    def test_valid_result(self) -> None:
        result = ValidationResult(is_valid=True)

        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_invalid_result_with_errors(self) -> None:
        result = ValidationResult(is_valid=False, errors=["missing file"])

        assert result.is_valid is False
        assert "missing file" in result.errors

    def test_warning_does_not_affect_validity(self) -> None:
        result = ValidationResult(is_valid=True, warnings=["large file"])

        assert result.is_valid is True


class TestValidateStepPrerequisites:
    def test_data_organizer_has_no_prerequisites(self, tmp_path) -> None:
        session = PipelineSession(output_dir=tmp_path)
        validator = DataValidator()

        result = validator.validate_step_prerequisites("data_organizer", session)

        assert result.is_valid

    def test_istd_marker_has_no_prerequisites(self, tmp_path) -> None:
        session = PipelineSession(output_dir=tmp_path)
        validator = DataValidator()

        result = validator.validate_step_prerequisites("istd_marker", session)

        assert result.is_valid

    def test_duplicate_remover_requires_data_organizer(self, tmp_path) -> None:
        session = PipelineSession(output_dir=tmp_path)
        validator = DataValidator()

        result = validator.validate_step_prerequisites("duplicate_remover", session)

        assert result.is_valid is False
        assert any("data_organizer" in error for error in result.errors)

    def test_duplicate_remover_passes_when_prerequisite_met(self, tmp_path) -> None:
        session = PipelineSession(output_dir=tmp_path)
        session.completed_steps.add("data_organizer")
        validator = DataValidator()

        result = validator.validate_step_prerequisites("duplicate_remover", session)

        assert result.is_valid

    def test_feature_filter_requires_data_organizer(self, tmp_path) -> None:
        session = PipelineSession(output_dir=tmp_path)
        validator = DataValidator()

        result = validator.validate_step_prerequisites("feature_filter", session)

        assert result.is_valid is False
        assert any("data_organizer" in error for error in result.errors)


class TestValidateDataframeSampleTypeContract:
    def test_validate_dataframe_requires_sample_type_row_when_requested(self) -> None:
        validator = DataValidator()
        df = pd.DataFrame({"Mz/RT": ["100.0/1.0"], "S1": [123]})

        result = validator.validate_dataframe(df, require_sample_type=True)

        assert result is False
        assert "Sample_Type row not found" in validator.errors

    def test_validate_dataframe_accepts_sample_type_row_when_present(self) -> None:
        validator = DataValidator()
        df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 123]})

        result = validator.validate_dataframe(df, require_sample_type=True)

        assert result is True
        assert validator.errors == []
