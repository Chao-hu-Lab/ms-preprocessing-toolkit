"""
Pipeline Fixed Parameters — Steps 1–3

Steps 1–3 的參數在不同分析場景下不需要調整，統一集中於此。
Step 4 的可調參數請見 feature_filter_presets.py。

檔案路徑說明：
  DEFAULT_METHOD_FILE      — Step 1 上機方法 .docx（依上機順序排序用）
  DEFAULT_ISTD_RECORD_FILE — Step 2 ISTD 記錄表 .xlsx

使用方式：
    from ms_preprocessing.config.pipeline_defaults import (
        STEP1_PARAMS, STEP2_PARAMS, STEP3_PARAMS,
        DEFAULT_METHOD_FILE, DEFAULT_ISTD_RECORD_FILE,
    )

    result1 = data_organizer_adapter.run_from_df(df, **STEP1_PARAMS)
    result2 = istd_marker_adapter.run_from_df(df, **STEP2_PARAMS)
    result3 = duplicate_remover_adapter.run_from_df(df, **STEP3_PARAMS)
"""

from __future__ import annotations

import os
from pathlib import Path

# ── 預設檔案路徑（機器相依，換電腦時更新此處）─────────────────────────────
METHOD_FILE_ENV = "MSPTK_METHOD_FILE"
ISTD_RECORD_FILE_ENV = "MSPTK_ISTD_RECORD_FILE"

_DEFAULT_METHOD_FILE_FALLBACK = Path(
    r"C:\Users\user\Desktop\NTU cancer\2025台大乳癌組織數據for Jia"
    r"\20260105中研院台大Breast cancer tissue\20260105 中研院分析.docx"
)

_DEFAULT_ISTD_RECORD_FILE_FALLBACK = Path(
    r"C:\Users\user\Desktop\NTU cancer\2025台大乳癌組織數據for Jia"
    r"\20260105中研院台大Breast cancer tissue\20260106 ISDTs record.xlsx"
)


def _resolve_path(env_var: str, fallback: Path) -> Path:
    override = os.getenv(env_var)
    return Path(override) if override else fallback


DEFAULT_METHOD_FILE = _resolve_path(METHOD_FILE_ENV, _DEFAULT_METHOD_FILE_FALLBACK)
DEFAULT_ISTD_RECORD_FILE = _resolve_path(ISTD_RECORD_FILE_ENV, _DEFAULT_ISTD_RECORD_FILE_FALLBACK)

# ── Step 1：Data Organizer ────────────────────────────────────────────────────
STEP1_PARAMS: dict = {
    "mode":        "normalization",  # 另一選項: "statistics"
    "auto_detect": True,
    "method_file": str(DEFAULT_METHOD_FILE),
}

# ── Step 2：ISTD Marker ───────────────────────────────────────────────────────
STEP2_PARAMS: dict = {
    "ppm_tolerance":     20.0,
    "rt_tolerance":      1.5,
    "istd_mz_list":      [261.1273, 245.1324, 289.0841,
                          300.1605, 269.1436, 482.2087, 303.0913],
    "istd_record_file":  str(DEFAULT_ISTD_RECORD_FILE),
    "istd_record_date":  "20260106",
}

# ── Step 3：Duplicate Remover ─────────────────────────────────────────────────
STEP3_PARAMS: dict = {
    "mz_tolerance_ppm": 20.0,
    "rt_tolerance":     1.0,
    "preserve_red_font": True,   # 保護 ISTD 標記列（紅字）
    "top_n":            None,    # None = 保留全部；整數 = 只輸出前 N 個
}
