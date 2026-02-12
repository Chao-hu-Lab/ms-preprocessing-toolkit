"""Unit tests for ISTD Marker (Step 2)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ms_preprocessing.core.istd_marker import ISTDMarker
from ms_preprocessing.config.settings import ISTDConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(feature_ids: list[str], sample_values: dict[str, list]) -> pd.DataFrame:
    """Build a DataFrame with Sample_Type header row."""
    data = {"FeatureID": ["Sample_Type"] + feature_ids}
    for col, vals in sample_values.items():
        data[col] = [col.split("_")[0]] + vals  # e.g. "case_S1" -> type "case"
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

class TestSortByMz:
    def test_sorts_ascending(self):
        df = _make_df(
            ["300.0000/1.0", "100.0000/2.0", "200.0000/3.0"],
            {"case_S1": [10, 20, 30]},
        )
        marker = ISTDMarker()
        result = marker.process(df, istd_mz_list=[])
        assert result.success
        mz_values = [
            float(str(result.data.iat[i, 0]).split("/")[0])
            for i in range(1, len(result.data))
        ]
        assert mz_values == sorted(mz_values)

    def test_preserves_sample_type_row(self):
        df = _make_df(["100.0000/1.0"], {"case_S1": [10]})
        marker = ISTDMarker()
        result = marker.process(df)
        assert result.success
        assert str(result.data.iat[0, 0]).lower() == "sample_type"


# ---------------------------------------------------------------------------
# ISTD detection via m/z list
# ---------------------------------------------------------------------------

class TestISTDDetection:
    def test_marks_matching_mz(self):
        """Features matching known ISTD m/z should be identified."""
        df = _make_df(
            ["261.1273/5.0", "500.0000/3.0"],
            {"case_S1": [1000, 2000], "case_S2": [1100, 2100]},
        )
        marker = ISTDMarker()
        result = marker.process(df, istd_mz_list=[261.1273])
        assert result.success
        assert "261.1273/5.0" in result.metadata.get("istd_features", [])

    def test_no_match_outside_tolerance(self):
        """Features far from known ISTD m/z should NOT be marked."""
        df = _make_df(
            ["999.9999/1.0"],
            {"case_S1": [1000]},
        )
        marker = ISTDMarker()
        result = marker.process(df, istd_mz_list=[261.1273])
        assert result.success
        assert result.metadata.get("istd_features", []) == []


# ---------------------------------------------------------------------------
# Duplicate detection (relative to ISTD)
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    def test_detects_duplicate_of_istd(self):
        """A non-ISTD feature within ppm + RT tolerance of an ISTD should be marked as duplicate."""
        istd_mz = 261.1273
        # Create a feature that is within ppm+RT tolerance of the ISTD but
        # does NOT itself match the ISTD m/z list (use a single known m/z).
        # We explicitly provide the ISTD feature set so only one row is ISTD.
        close_mz = istd_mz + istd_mz * 5e-6  # 5 ppm away
        df = _make_df(
            [f"{istd_mz:.4f}/5.00", f"{close_mz:.4f}/5.10"],
            {"case_S1": [1000, 900], "case_S2": [1100, 800]},
        )
        marker = ISTDMarker()
        # Pass explicit istd_features so only the first row is treated as ISTD
        result = marker.process(df, istd_features={f"{istd_mz:.4f}/5.00"})
        assert result.success
        assert result.statistics.get("duplicates_marked", 0) >= 1

    def test_no_duplicate_outside_tolerance(self):
        """A feature far from all ISTDs should NOT be marked duplicate."""
        df = _make_df(
            ["261.1273/5.00", "999.0000/20.00"],
            {"case_S1": [1000, 500]},
        )
        marker = ISTDMarker()
        result = marker.process(df, istd_mz_list=[261.1273])
        assert result.success
        # Only ISTD duplicate detection (not the ISTD itself)
        assert result.statistics.get("duplicates_marked", 0) == 0


# ---------------------------------------------------------------------------
# Red font / protected rows metadata
# ---------------------------------------------------------------------------

class TestMetadataOutput:
    def test_red_font_rows_populated_for_istd(self):
        df = _make_df(
            ["261.1273/5.00", "500.0000/3.00"],
            {"case_S1": [1000, 2000]},
        )
        marker = ISTDMarker()
        result = marker.process(df, istd_mz_list=[261.1273])
        assert result.success
        assert len(result.metadata.get("red_font_rows", [])) >= 1

    def test_keep_istd_rows_default(self):
        """By default ISTD rows are kept (not removed)."""
        df = _make_df(
            ["261.1273/5.00", "500.0000/3.00"],
            {"case_S1": [1000, 2000]},
        )
        marker = ISTDMarker()
        result = marker.process(df, istd_mz_list=[261.1273], keep_istd_rows=True)
        assert result.success
        assert result.statistics.get("rows_removed", 0) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_df_fails_validation(self):
        df = pd.DataFrame()
        marker = ISTDMarker()
        result = marker.process(df)
        assert not result.success

    def test_single_data_row(self):
        df = _make_df(["100.0000/1.0"], {"case_S1": [10]})
        marker = ISTDMarker()
        result = marker.process(df)
        assert result.success

    def test_no_slash_in_feature_id(self):
        """FeatureID without '/' should not crash _extract_mz_rt_arrays."""
        df = pd.DataFrame({
            "FeatureID": ["Sample_Type", "no_slash_here", "also_no_slash"],
            "S1": ["case", 10, 20],
        })
        marker = ISTDMarker()
        result = marker.process(df)
        # Validation should reject (< 50% valid format)
        assert not result.success

    def test_cancellation(self):
        """Cancellation mid-process should return failure."""
        df = _make_df(
            [f"{100 + i:.4f}/1.0" for i in range(20)],
            {"case_S1": list(range(20))},
        )
        marker = ISTDMarker()
        # Cancel during progress callback (after process starts and calls reset)
        def cancel_on_progress(percent, msg):
            if percent >= 20:
                marker.cancel()
        marker.set_progress_callback(cancel_on_progress)
        result = marker.process(df)
        assert not result.success
        assert "cancelled" in result.message.lower()
