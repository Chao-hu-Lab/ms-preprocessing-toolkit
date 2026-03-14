"""Runtime contract tests for adapter parameter forwarding and failures."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


def test_data_organizer_run_from_df_forwards_processing_arguments(monkeypatch) -> None:
    import ms_preprocessing.adapters.data_organizer as module

    df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 1]})
    calls: dict[str, object] = {}

    class FakeProcessor:
        def set_progress_callback(self, callback) -> None:
            calls["progress_callback"] = callback

        def process(self, input_df, **kwargs):
            calls["input_df"] = input_df.copy()
            calls["kwargs"] = kwargs
            return SimpleNamespace(success=True, data=input_df.copy(), metadata={}, statistics={})

    monkeypatch.setattr(module, "_DataOrganizer", FakeProcessor)
    monkeypatch.setattr(module, "_save_output", lambda _df: "organizer.parquet")

    result = module.run_from_df(
        df,
        method_file="method.xlsx",
        mz_decimals=5,
        rt_decimals=3,
        sample_type_mapping={"S1": "case"},
        mode="statistics",
    )

    assert result.success is True
    assert result.output_path == "organizer.parquet"
    assert calls["kwargs"] == {
        "method_file": "method.xlsx",
        "mz_decimals": 5,
        "rt_decimals": 3,
        "sample_type_mapping": {"S1": "case"},
        "mode": "statistics",
    }


def test_istd_marker_run_from_df_applies_tolerances_and_path_inputs(monkeypatch) -> None:
    import ms_preprocessing.adapters.istd_marker as module

    df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 1]})
    calls: dict[str, object] = {}

    class FakeProcessor:
        def __init__(self) -> None:
            self.config = SimpleNamespace(default_ppm_tolerance=20.0, default_rt_tolerance=1.0)

        def set_progress_callback(self, callback) -> None:
            calls["progress_callback"] = callback

        def process(self, input_df, **kwargs):
            calls["processor"] = self
            calls["kwargs"] = kwargs
            return SimpleNamespace(success=True, data=input_df.copy(), metadata={}, statistics={})

    monkeypatch.setattr(module, "_ISTDMarker", FakeProcessor)
    monkeypatch.setattr(module, "_save_output", lambda _df: "istd.parquet")

    result = module.run_from_df(
        df,
        istd_mz_list=[261.1273],
        istd_record_file="record.csv",
        keep_istd_rows=False,
        ppm_tolerance=5.0,
        rt_tolerance=0.2,
    )

    assert result.success is True
    assert result.output_path == "istd.parquet"
    processor = calls["processor"]
    assert processor.config.default_ppm_tolerance == 5.0
    assert processor.config.default_rt_tolerance == 0.2
    assert calls["kwargs"]["istd_mz_list"] == [261.1273]
    assert calls["kwargs"]["istd_record_file"] == Path("record.csv")
    assert calls["kwargs"]["keep_istd_rows"] is False


def test_duplicate_remover_run_from_df_forwards_protected_rows(monkeypatch) -> None:
    import ms_preprocessing.adapters.duplicate_remover as module

    df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 1]})
    calls: dict[str, object] = {}

    class FakeProcessor:
        def set_progress_callback(self, callback) -> None:
            calls["progress_callback"] = callback

        def process(self, input_df, **kwargs):
            calls["kwargs"] = kwargs
            return SimpleNamespace(success=True, data=input_df.copy(), metadata={}, statistics={})

    monkeypatch.setattr(module, "_DuplicateRemover", FakeProcessor)
    monkeypatch.setattr(module, "_save_output", lambda _df: "duplicate.parquet")

    result = module.run_from_df(
        df,
        mz_tolerance_ppm=10.0,
        rt_tolerance=0.4,
        top_n=2,
        protected_rows={1, 2},
    )

    assert result.success is True
    assert result.output_path == "duplicate.parquet"
    assert calls["kwargs"] == {
        "mz_tolerance_ppm": 10.0,
        "rt_tolerance": 0.4,
        "top_n": 2,
        "protected_rows": {1, 2},
    }


def test_feature_filter_run_from_df_applies_signal_threshold_and_flags(monkeypatch) -> None:
    import ms_preprocessing.adapters.feature_filter as module

    df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 1]})
    calls: dict[str, object] = {}

    class FakeProcessor:
        def __init__(self) -> None:
            self.config = SimpleNamespace(signal_threshold=5000.0)

        def set_progress_callback(self, callback) -> None:
            calls["progress_callback"] = callback

        def process(self, input_df, **kwargs):
            calls["processor"] = self
            calls["kwargs"] = kwargs
            return SimpleNamespace(success=True, data=input_df.copy(), metadata={}, statistics={})

    monkeypatch.setattr(module, "_FeatureFilter", FakeProcessor)
    monkeypatch.setattr(module, "_save_output", lambda _df: "filter.parquet")

    result = module.run_from_df(
        df,
        background_threshold=0.1,
        skew_threshold=0.2,
        diff_threshold=0.3,
        qc_ratio_threshold=0.4,
        enable_background_threshold=False,
        enable_skew_threshold=True,
        enable_diff_threshold=False,
        enable_qc_ratio_threshold=True,
        signal_threshold=123.0,
        protected_rows={9},
    )

    assert result.success is True
    assert result.output_path == "filter.parquet"
    processor = calls["processor"]
    assert processor.config.signal_threshold == 123.0
    assert calls["kwargs"] == {
        "background_threshold": 0.1,
        "skew_threshold": 0.2,
        "diff_threshold": 0.3,
        "qc_ratio_threshold": 0.4,
        "enable_background_threshold": False,
        "enable_skew_threshold": True,
        "enable_diff_threshold": False,
        "enable_qc_ratio_threshold": True,
        "protected_rows": {9},
    }


@pytest.mark.parametrize(
    ("module_name", "processor_attr", "step"),
    [
        ("ms_preprocessing.adapters.data_organizer", "_DataOrganizer", "data_organizer"),
        ("ms_preprocessing.adapters.istd_marker", "_ISTDMarker", "istd_marker"),
        ("ms_preprocessing.adapters.duplicate_remover", "_DuplicateRemover", "duplicate_remover"),
        ("ms_preprocessing.adapters.feature_filter", "_FeatureFilter", "feature_filter"),
    ],
)
def test_adapter_run_from_df_returns_failure_when_processor_raises(
    monkeypatch,
    module_name: str,
    processor_attr: str,
    step: str,
) -> None:
    module = importlib.import_module(module_name)
    df = pd.DataFrame({"Mz/RT": ["Sample_Type", "100.0/1.0"], "S1": ["case", 1]})

    class RaisingProcessor:
        def __init__(self) -> None:
            self.config = SimpleNamespace(
                default_ppm_tolerance=20.0,
                default_rt_tolerance=1.0,
                signal_threshold=5000.0,
            )

        def set_progress_callback(self, callback) -> None:
            _ = callback

        def process(self, input_df, **kwargs):
            _ = (input_df, kwargs)
            raise RuntimeError("boom")

    monkeypatch.setattr(module, processor_attr, RaisingProcessor)

    result = module.run_from_df(df)

    assert result.success is False
    assert result.step == step
    assert result.error == "boom"
