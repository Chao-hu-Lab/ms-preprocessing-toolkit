"""
Data validation utilities for MS Preprocessing Toolkit.

This module provides validation functions for mass spectrometry data
to ensure data quality before processing.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from ms_preprocessing.gui.pipeline_session import PipelineSession


class ValidationError(Exception):
    """Exception raised for validation errors."""

    pass


class ValidationWarning:
    """Represents a non-critical validation warning."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}


@dataclass
class ValidationResult:
    """Structured validation response for new step-order checks."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DataValidator:
    """
    Validates mass spectrometry data for the preprocessing pipeline.

    Provides methods to check data structure, identify missing values,
    and validate column formats.
    """

    # Common column name patterns
    FEATURE_ID_PATTERNS = ["featureid", "feature_id", "feature", "id", "name"]
    SAMPLE_TYPE_PATTERNS = ["sample_type", "sampletype", "type", "class", "group"]
    MZ_PATTERNS = ["mz", "m/z", "mass", "mz_value"]
    RT_PATTERNS = ["rt", "retention", "time", "rt_value", "retentiontime"]
    INTENSITY_PATTERNS = ["intensity", "area", "height", "abundance", "signal"]

    def __init__(self):
        """Initialize the DataValidator."""
        self.warnings: list[ValidationWarning] = []
        self.errors: list[str] = []

    def clear(self):
        """Clear all warnings and errors."""
        self.warnings = []
        self.errors = []

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        require_feature_id: bool = True,
        require_sample_type: bool = True,
        min_rows: int = 1,
        min_cols: int = 2,
    ) -> bool:
        """
        Validate a DataFrame for basic structure requirements.

        Args:
            df: DataFrame to validate
            require_feature_id: Whether to require a Mz/RT (or legacy FeatureID) column
            require_sample_type: Whether to require a Sample_Type row
            min_rows: Minimum number of data rows
            min_cols: Minimum number of columns

        Returns:
            True if validation passes, False otherwise
        """
        self.clear()

        # Check basic structure
        if df.empty:
            self.errors.append("DataFrame is empty")
            return False

        if len(df) < min_rows:
            self.errors.append(f"DataFrame has fewer than {min_rows} rows")
            return False

        if len(df.columns) < min_cols:
            self.errors.append(f"DataFrame has fewer than {min_cols} columns")
            return False

        # Check for Mz/RT (or legacy FeatureID) column
        if require_feature_id:
            feature_col = self._find_column(df, self.FEATURE_ID_PATTERNS)
            if feature_col is None:
                self.warnings.append(
                    ValidationWarning(
                        "No Mz/RT column found",
                        {"expected_patterns": self.FEATURE_ID_PATTERNS},
                    )
                )

        if require_sample_type and not self._has_sample_type_row(df):
            self.errors.append("Sample_Type row not found")

        return len(self.errors) == 0

    def validate_mz_rt_format(self, df: pd.DataFrame, column: str = "Mz/RT") -> bool:
        """
        Validate that a column contains valid m/z/RT format strings.

        Args:
            df: DataFrame to validate
            column: Column name to check

        Returns:
            True if format is valid, False otherwise
        """
        if column not in df.columns:
            self.errors.append(f"Column '{column}' not found")
            return False

        # Skip the Sample_Type marker row if present (case/whitespace insensitive).
        first_val = str(df[column].iloc[0]).strip().lower().replace(" ", "").replace("_", "") if len(df) > 0 else ""
        start_idx = 1 if first_val == "sampletype" else 0

        invalid_count = 0
        for _, value in df[column].iloc[start_idx:].items():
            if not self._is_valid_mz_rt(value):
                invalid_count += 1

        if invalid_count > 0:
            self.warnings.append(
                ValidationWarning(
                    f"Found {invalid_count} rows with invalid m/z/RT format",
                    {"column": column, "invalid_count": invalid_count},
                )
            )

        return invalid_count == 0

    def validate_numeric_columns(
        self,
        df: pd.DataFrame,
        start_col: int = 2,
        allow_missing: bool = True,
    ) -> tuple[bool, dict[str, int]]:
        """
        Validate that data columns contain numeric values.

        Args:
            df: DataFrame to validate
            start_col: Starting column index for data columns
            allow_missing: Whether to allow missing/NaN values

        Returns:
            Tuple of (is_valid, missing_value_counts_by_column)
        """
        missing_counts = {}
        non_numeric_counts = {}

        for col_idx in range(start_col, len(df.columns)):
            col = df.columns[col_idx]
            col_data = df[col]

            # Count missing values
            missing = col_data.isna().sum()
            if missing > 0:
                missing_counts[col] = int(missing)

            # Check for non-numeric values (excluding NaN)
            non_missing = col_data.dropna()
            if len(non_missing) > 0:
                non_numeric = (~pd.to_numeric(non_missing, errors="coerce").notna()).sum()
                if non_numeric > 0:
                    non_numeric_counts[col] = int(non_numeric)

        if non_numeric_counts:
            self.errors.append(f"Found non-numeric values in columns: {list(non_numeric_counts.keys())}")
            return False, missing_counts

        if missing_counts and not allow_missing:
            self.warnings.append(
                ValidationWarning(
                    f"Found missing values in {len(missing_counts)} columns",
                    {"missing_counts": missing_counts},
                )
            )

        return True, missing_counts

    def validate_sample_types(
        self,
        df: pd.DataFrame,
        sample_type_row: int = 0,
        expected_types: list[str] | None = None,
    ) -> tuple[bool, dict[str, int]]:
        """
        Validate sample type row and count each type.

        Args:
            df: DataFrame to validate
            sample_type_row: Row index containing sample types
            expected_types: List of expected sample type values

        Returns:
            Tuple of (is_valid, type_counts)
        """
        if sample_type_row >= len(df):
            self.errors.append(f"Sample type row {sample_type_row} is out of range")
            return False, {}

        type_counts = {}
        unknown_types = set()

        for col_idx in range(1, len(df.columns)):
            sample_type = str(df.iloc[sample_type_row, col_idx]).lower().strip()
            if sample_type and sample_type != "nan" and sample_type != "na":
                type_counts[sample_type] = type_counts.get(sample_type, 0) + 1

                if expected_types and sample_type not in expected_types:
                    unknown_types.add(sample_type)

        if unknown_types:
            self.warnings.append(
                ValidationWarning(
                    f"Found unknown sample types: {unknown_types}",
                    {"unknown_types": list(unknown_types)},
                )
            )

        return True, type_counts

    def _find_column(self, df: pd.DataFrame, patterns: list[str]) -> str | None:
        """Find a column matching any of the given patterns."""
        for col in df.columns:
            col_lower = str(col).lower().replace(" ", "").replace("_", "")
            for pattern in patterns:
                if pattern.replace("_", "") in col_lower:
                    return col
        return None

    @staticmethod
    def _has_sample_type_row(df: pd.DataFrame) -> bool:
        """Return whether the first column contains the Sample_Type marker row."""
        if df.empty or len(df.columns) == 0:
            return False

        first_col = df.iloc[:, 0]
        normalized = (
            first_col.fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(" ", "", regex=False)
            .str.replace("_", "", regex=False)
        )
        return bool(normalized.eq("sampletype").any())

    @staticmethod
    def _is_valid_mz_rt(value: Any) -> bool:
        """Check if a value is a valid m/z/RT format string."""
        try:
            value_str = str(value)
            if "/" not in value_str:
                return False
            parts = value_str.split("/")
            if len(parts) != 2:
                return False
            mz = float(parts[0].strip())
            rt = float(parts[1].strip())
            return mz > 0 and rt >= 0
        except (ValueError, TypeError):
            return False

    def get_validation_report(self) -> str:
        """Generate a human-readable validation report."""
        lines = ["=== Validation Report ===", ""]

        if self.errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
            lines.append("")

        if self.warnings:
            lines.append("WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  - {warning.message}")
                if warning.details:
                    for key, value in warning.details.items():
                        lines.append(f"      {key}: {value}")
            lines.append("")

        if not self.errors and not self.warnings:
            lines.append("No issues found.")

        return "\n".join(lines)

    def validate_step_prerequisites(
        self,
        step: str,
        session: "PipelineSession",
    ) -> ValidationResult:
        """Check GUI step-order prerequisites against a pipeline session."""
        prerequisites: dict[str, set[str]] = {
            "data_organizer": set(),
            "istd_marker": set(),
            "duplicate_remover": {"data_organizer"},
            "feature_filter": {"data_organizer"},
        }
        required = prerequisites.get(step, set())
        missing = required - session.completed_steps

        if missing:
            return ValidationResult(
                is_valid=False,
                errors=[f"Step '{step}' requires completed steps: {sorted(missing)}"],
            )

        return ValidationResult(is_valid=True)


# Fixed column names that precede sample data columns.
_FIXED_COLUMN_NAMES = {"Mz/RT", "FeatureID", "m/z Tolerance( ppm)/RT Tolerance"}


def detect_fixed_columns(df: pd.DataFrame) -> tuple[list[str], int]:
    """
    Detect leading fixed (non-sample) columns in a DataFrame.

    Fixed columns are metadata columns such as Mz/RT / Tolerance
    that appear before the sample intensity columns.  Detection stops at the
    first column whose name is NOT in the known fixed-column set.

    Args:
        df: DataFrame to inspect.

    Returns:
        Tuple of (list of fixed column names, count of fixed columns).
    """
    fixed: list[str] = []
    for col in df.columns:
        if col in _FIXED_COLUMN_NAMES:
            fixed.append(col)
        else:
            break
    return fixed, len(fixed)
