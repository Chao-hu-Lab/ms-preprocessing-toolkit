"""
Feature Filter Module - Step 4 of the preprocessing pipeline.

This module handles feature filtering and missing value imputation:
- Dynamic sample type detection
- Ratio calculation for each group
- Multi-criteria feature filtering
- Intelligent missing value imputation

Based on: Feature_barrier_V3.bas
"""

from typing import Optional, Dict, Any, List, Set, Tuple
import pandas as pd
import numpy as np

from ms_preprocessing.core.base import BaseProcessor, ProcessingResult
from ms_preprocessing.config.settings import FeatureFilterConfig


class FeatureFilter(BaseProcessor):
    """
    Filters features and imputes missing values.

    This processor:
    1. Automatically detects sample types from row 2
    2. Calculates signal ratio for each group
    3. Filters features based on multiple criteria:
       - Stable: >=2 groups with ratio >= background threshold
       - Skewed: Any group with ratio >= skew threshold
       - Different: Any two groups with ratio difference >= diff threshold
    4. Removes features with QC_ratio = 0
    5. Imputes missing values using group-specific minimum/2
    """

    def __init__(self, config: Optional[FeatureFilterConfig] = None):
        """
        Initialize the Feature Filter.

        Args:
            config: Configuration options for feature filtering
        """
        super().__init__("Feature Filter")
        self.config = config or FeatureFilterConfig()

    def validate_input(self, df: pd.DataFrame) -> tuple:
        """
        Validate input data for feature filtering.

        Args:
            df: Input DataFrame

        Returns:
            Tuple of (is_valid, error_message)
        """
        if df is None or df.empty:
            return False, "Input data is empty"

        if len(df) < 2:
            return False, "Data must have at least 2 rows (Sample_Type + data)"

        if len(df.columns) < 3:
            return False, "Data must have at least 3 columns (feature + samples)"

        return True, ""

    def process(
        self,
        df: pd.DataFrame,
        background_threshold: Optional[float] = None,
        skew_threshold: Optional[float] = None,
        diff_threshold: Optional[float] = None,
        protected_rows: Optional[Set[int]] = None,
        **kwargs,
    ) -> ProcessingResult:
        """
        Process data for feature filtering and missing value imputation.

        Args:
            df: Input DataFrame
            background_threshold: Threshold for stable features (0-1)
            skew_threshold: Threshold for skewed features (0-1)
            diff_threshold: Threshold for differential features (0-1)
            protected_rows: Set of row indices (red font) to protect from removal
            **kwargs: Additional parameters

        Returns:
            ProcessingResult with filtered data and imputed values
        """
        self.reset()

        # Use config defaults if not specified
        bg_thresh = background_threshold if background_threshold is not None else self.config.default_background_threshold
        skew_thresh = skew_threshold if skew_threshold is not None else self.config.default_skew_threshold
        diff_thresh = diff_threshold if diff_threshold is not None else self.config.default_diff_threshold

        # Validate input
        is_valid, error_msg = self.validate_input(df)
        if not is_valid:
            return ProcessingResult(
                success=False,
                errors=[error_msg],
                message=f"Validation failed: {error_msg}",
            )

        self.update_progress(5, "Starting feature filtering...")

        try:
            # Create a copy
            result_df = df.copy()
            deleted_features = []

            # Step 1: Detect sample types
            self.update_progress(10, "Detecting sample types...")
            group_info = self._detect_sample_types(result_df)

            if self._cancelled:
                return ProcessingResult(success=False, message="Processing cancelled")

            # Step 2: Calculate ratios for each group
            self.update_progress(25, "Calculating group ratios...")
            result_df, ratio_cols = self._calculate_ratios(result_df, group_info)

            if self._cancelled:
                return ProcessingResult(success=False, message="Processing cancelled")

            # Step 3: Filter features
            self.update_progress(50, "Filtering features...")
            result_df, deleted_features, filter_stats = self._filter_features(
                result_df,
                group_info,
                ratio_cols,
                bg_thresh,
                skew_thresh,
                diff_thresh,
                protected_rows or set(),
            )

            if self._cancelled:
                return ProcessingResult(success=False, message="Processing cancelled")

            # Step 4: Impute missing values
            self.update_progress(75, "Imputing missing values...")
            result_df, impute_stats = self._impute_missing_values(
                result_df,
                group_info,
                ratio_cols,
            )

            self.update_progress(100, "Feature filtering complete")

            # Compile statistics
            stats = {
                **filter_stats,
                **impute_stats,
                "final_features": len(result_df) - 1,
                "groups_detected": len(group_info["groups"]),
                "has_qc": group_info["has_qc"],
            }

            # Create deleted features DataFrame
            deleted_df = None
            if deleted_features:
                # Reconstruct deleted rows
                pass  # Handled in metadata

            return ProcessingResult(
                success=True,
                data=result_df,
                message=f"Feature filtering completed. Kept {filter_stats.get('kept_count', 0)}, "
                        f"removed {filter_stats.get('deleted_count', 0)} features.",
                statistics=stats,
                metadata={
                    "group_info": group_info,
                    "ratio_columns": ratio_cols,
                    "thresholds": {
                        "background": bg_thresh,
                        "skew": skew_thresh,
                        "diff": diff_thresh,
                    },
                    "deleted_features": deleted_features,
                    "blue_font_cells": impute_stats.get("imputed_cells", []),
                    "red_font_rows": filter_stats.get("red_font_rows", []),
                    "protected_rows": filter_stats.get("red_font_rows", []),
                },
            )

        except Exception as e:
            return ProcessingResult(
                success=False,
                errors=[str(e)],
                message=f"Error during feature filtering: {str(e)}",
            )

    def _detect_sample_types(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect sample types from row index 1 (Sample_Type row).

        Returns dict with group information.
        """
        info = {
            "groups": {},  # group_name -> list of column indices
            "qc_cols": [],
            "excluded_cols": [],
            "unknown_types": set(),
            "has_qc": False,
        }

        excluded_types = set(t.lower() for t in self.config.excluded_types)

        # Row 0 contains sample types (Sample_Type row)
        sample_type_row = 0

        fixed_cols = []
        for col in df.columns:
            col_lower = str(col).lower()
            if col in ["Mz/RT", "FeatureID"] or "tolerance" in col_lower:
                fixed_cols.append(col)
            else:
                break
        start_idx = len(fixed_cols) if fixed_cols else 1

        for col_idx in range(start_idx, len(df.columns)):
            col_name = df.columns[col_idx]
            sample_type = str(df.iat[sample_type_row, col_idx]).lower().strip()

            if sample_type in ['', 'nan', 'na', 'none']:
                continue

            if sample_type == 'qc':
                info["qc_cols"].append(col_idx)
                info["has_qc"] = True
            elif sample_type in excluded_types:
                info["excluded_cols"].append(col_idx)
            else:
                # Analysis group
                if sample_type not in info["groups"]:
                    info["groups"][sample_type] = []
                info["groups"][sample_type].append(col_idx)

        return info

    def _calculate_ratios(
        self,
        df: pd.DataFrame,
        group_info: Dict[str, Any],
    ) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """
        Calculate signal ratio for each group.

        Returns DataFrame with ratio columns and dict mapping group to ratio column name.
        """
        ratio_cols = {}
        signal_threshold = self.config.signal_threshold

        # Add ratio columns for each group
        for group_name, col_indices in group_info["groups"].items():
            ratio_col = f"{group_name}_ratio"
            ratio_cols[group_name] = ratio_col

            ratios = ["na"]  # Sample_Type row value

            for row_idx in range(1, len(df)):
                signal_count = 0
                total_count = len(col_indices)

                for col_idx in col_indices:
                    try:
                        val = pd.to_numeric(df.iat[row_idx, col_idx], errors='coerce')
                        if pd.notna(val) and val >= signal_threshold:
                            signal_count += 1
                    except Exception:
                        pass

                ratio = signal_count / total_count if total_count > 0 else 0
                ratios.append(ratio)

            df[ratio_col] = ratios

        # Add QC ratio if QC samples exist
        if group_info["has_qc"]:
            qc_ratio_col = "QC_ratio"
            ratio_cols["QC"] = qc_ratio_col

            qc_ratios = ["na"]

            for row_idx in range(1, len(df)):
                signal_count = 0
                total_count = len(group_info["qc_cols"])

                for col_idx in group_info["qc_cols"]:
                    try:
                        val = pd.to_numeric(df.iat[row_idx, col_idx], errors='coerce')
                        if pd.notna(val) and val >= signal_threshold:
                            signal_count += 1
                    except Exception:
                        pass

                ratio = signal_count / total_count if total_count > 0 else 0
                qc_ratios.append(ratio)

            df[qc_ratio_col] = qc_ratios

        return df, ratio_cols

    def _filter_features(
        self,
        df: pd.DataFrame,
        group_info: Dict[str, Any],
        ratio_cols: Dict[str, str],
        bg_threshold: float,
        skew_threshold: float,
        diff_threshold: float,
        protected_rows: Set[int],
    ) -> Tuple[pd.DataFrame, List[pd.Series], Dict[str, Any]]:
        """
        Filter features based on ratio criteria.

        Returns filtered DataFrame, deleted rows, and statistics.
        """
        stats = {
            "kept_count": 0,
            "deleted_count": 0,
            "skew_kept": 0,
            "stable_kept": 0,
            "diff_kept": 0,
            "qc_zero_deleted": 0,
            "protected_kept": 0,
        }

        deleted_features = []
        rows_to_keep = [0]  # Always keep Sample_Type row

        group_names = list(group_info["groups"].keys())
        has_qc = group_info["has_qc"]
        qc_ratio_col = ratio_cols.get("QC")

        for row_idx in range(1, len(df)):
            # Check if protected (red font)
            is_protected = row_idx in protected_rows

            # Get QC ratio
            qc_ratio = 1.0  # Default if no QC
            if has_qc and qc_ratio_col:
                try:
                    qc_ratio = float(df.at[row_idx, qc_ratio_col])
                except (ValueError, TypeError):
                    qc_ratio = 0

            # Rule 1: QC_ratio = 0 -> delete (unless protected)
            if has_qc and qc_ratio == 0 and not is_protected:
                deleted_features.append(df.iloc[row_idx].copy())
                stats["deleted_count"] += 1
                stats["qc_zero_deleted"] += 1
                continue

            # Get group ratios
            group_ratios = []
            for group_name in group_names:
                ratio_col = ratio_cols[group_name]
                try:
                    ratio = float(df.at[row_idx, ratio_col])
                except (ValueError, TypeError):
                    ratio = 0
                group_ratios.append(ratio)

            keep_feature = False
            keep_reason = None

            if is_protected:
                keep_feature = True
                keep_reason = "protected"
                stats["protected_kept"] += 1
            else:
                # Condition 1: Skew - any group ratio >= skew_threshold
                if any(r >= skew_threshold for r in group_ratios):
                    keep_feature = True
                    keep_reason = "skew"
                    stats["skew_kept"] += 1

                # Condition 2: Diff - any two groups differ by >= diff_threshold
                if not keep_feature and len(group_ratios) >= 2:
                    max_diff = self._get_max_ratio_diff(group_ratios)
                    if max_diff >= diff_threshold:
                        keep_feature = True
                        keep_reason = "diff"
                        stats["diff_kept"] += 1

                # Condition 3: Stable - >= 2 groups with ratio >= bg_threshold
                if not keep_feature:
                    groups_above = sum(1 for r in group_ratios if r >= bg_threshold)
                    if groups_above >= 2:
                        keep_feature = True
                        keep_reason = "stable"
                        stats["stable_kept"] += 1

            if keep_feature:
                rows_to_keep.append(row_idx)
                stats["kept_count"] += 1
            else:
                deleted_features.append(df.iloc[row_idx].copy())
                stats["deleted_count"] += 1

        # Build mapping for kept rows (for protected row updates)
        row_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(rows_to_keep)}
        stats["red_font_rows"] = sorted(
            row_mapping[idx] for idx in protected_rows if idx in row_mapping
        )

        # Filter DataFrame
        result_df = df.iloc[rows_to_keep].reset_index(drop=True)

        return result_df, deleted_features, stats

    def _get_max_ratio_diff(self, ratios: List[float]) -> float:
        """Calculate maximum difference between any two ratios."""
        max_diff = 0
        for i in range(len(ratios)):
            for j in range(i + 1, len(ratios)):
                diff = abs(ratios[i] - ratios[j])
                if diff > max_diff:
                    max_diff = diff
        return max_diff

    def _impute_missing_values(
        self,
        df: pd.DataFrame,
        group_info: Dict[str, Any],
        ratio_cols: Dict[str, str],
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Impute missing values using group-specific minimum/2.

        Returns DataFrame with imputed values and statistics.
        """
        stats = {
            "cells_imputed": 0,
            "imputation_method": "group_min_half",
        }

        # Track imputed cells for blue font marking
        imputed_cells = []

        signal_threshold = self.config.signal_threshold

        for row_idx in range(1, len(df)):
            # Calculate group minimums for this row
            group_mins = {}

            # Get ratios for special case detection
            group_ratios = {}
            for group_name in group_info["groups"].keys():
                ratio_col = ratio_cols.get(group_name)
                if ratio_col:
                    try:
                        group_ratios[group_name] = float(df.at[row_idx, ratio_col])
                    except (ValueError, TypeError):
                        group_ratios[group_name] = 0

            # Find min value for each group
            for group_name, col_indices in group_info["groups"].items():
                min_val = None
                for col_idx in col_indices:
                    try:
                        val = pd.to_numeric(df.iat[row_idx, col_idx], errors='coerce')
                        if pd.notna(val) and val > 0:
                            if min_val is None or val < min_val:
                                min_val = val
                    except Exception:
                        pass
                group_mins[group_name] = min_val if min_val is not None else 0

            # QC minimum
            qc_min = None
            for col_idx in group_info.get("qc_cols", []):
                try:
                    val = pd.to_numeric(df.iat[row_idx, col_idx], errors='coerce')
                    if pd.notna(val) and val > 0:
                        if qc_min is None or val < qc_min:
                            qc_min = val
                except Exception:
                    pass
            qc_min = qc_min if qc_min is not None else 0

            # Impute missing values
            for group_name, col_indices in group_info["groups"].items():
                group_ratio = group_ratios.get(group_name, 0)

                # Special case: this group has ratio=0 but others have ratio=1
                is_special_case = False
                if group_ratio == 0:
                    other_all_one = all(
                        group_ratios.get(g, 0) == 1.0
                        for g in group_info["groups"].keys()
                        if g != group_name
                    )
                    if other_all_one and len(group_info["groups"]) > 1:
                        is_special_case = True

                for col_idx in col_indices:
                    val = df.iat[row_idx, col_idx]
                    is_missing = pd.isna(val) or val == '' or val is None

                    if not is_missing:
                        try:
                            numeric_val = pd.to_numeric(val, errors='coerce')
                            is_missing = pd.isna(numeric_val)
                        except Exception:
                            is_missing = True

                    if is_missing:
                        if is_special_case:
                            fill_value = signal_threshold
                        else:
                            fill_value = group_mins[group_name] / 2 if group_mins[group_name] > 0 else 0

                        df.iat[row_idx, col_idx] = fill_value
                        imputed_cells.append((row_idx, col_idx))
                        stats["cells_imputed"] += 1

            # Impute QC values
            for col_idx in group_info.get("qc_cols", []):
                val = df.iat[row_idx, col_idx]
                is_missing = pd.isna(val) or val == '' or val is None

                if not is_missing:
                    try:
                        numeric_val = pd.to_numeric(val, errors='coerce')
                        is_missing = pd.isna(numeric_val)
                    except Exception:
                        is_missing = True

                if is_missing:
                    fill_value = qc_min / 2 if qc_min > 0 else 0
                    df.iat[row_idx, col_idx] = fill_value
                    imputed_cells.append((row_idx, col_idx))
                    stats["cells_imputed"] += 1

        stats["imputed_cells"] = imputed_cells

        return df, stats

    def get_group_summary(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Get a summary of detected groups and their statistics.

        Args:
            df: Input DataFrame

        Returns:
            Dictionary with group summary information
        """
        group_info = self._detect_sample_types(df)

        summary = {
            "groups": {},
            "qc_count": len(group_info["qc_cols"]),
            "has_qc": group_info["has_qc"],
            "excluded_count": len(group_info["excluded_cols"]),
            "unknown_types": list(group_info["unknown_types"]),
        }

        for group_name, col_indices in group_info["groups"].items():
            summary["groups"][group_name] = {
                "sample_count": len(col_indices),
                "columns": [df.columns[i] for i in col_indices],
            }

        return summary
