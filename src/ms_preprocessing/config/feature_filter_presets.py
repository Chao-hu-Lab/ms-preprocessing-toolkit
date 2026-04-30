"""
Step 4 Feature Filter — Parameter Presets

設計依據：
  - 主場景：2 組（exposure vs control）+ QC，總樣本 85–148，每組約 20–46 人
  - QC 樣本數量少（7–10 個），因此 preset 採固定通用值：loose=0.00、default=0.25、strict=0.50
  - high_det_thresh / low_det_thresh 為 MNAR 存在/缺失規則：出現組 ≥ high_det_thresh 且缺失組 ≤ low_det_thresh
  - intensity_fc_threshold 代表「各組平均強度 fold-change」，抓偵測率相似但強度差異大的特徵

使用方式：
    from ms_preprocessing.config.feature_filter_presets import get_step4_preset

    params = get_step4_preset("default")
    result = feature_filter_adapter.run_from_df(df, **params)
"""

from __future__ import annotations

from typing import Literal, TypedDict

PresetName = Literal["loose", "default", "strict"]


class Step4Params(TypedDict):
    """完整的 Step 4 參數型別定義。"""
    signal_threshold: float
    background_threshold: float
    high_det_thresh: float
    low_det_thresh: float
    qc_ratio_threshold: float
    intensity_fc_threshold: float
    ratio_rescue_threshold: float
    enable_background_threshold: bool
    enable_qc_ratio_threshold: bool
    enable_intensity_fc_threshold: bool
    enable_ratio_rescue: bool


# ── 寬鬆 ──────────────────────────────────────────────────────────────────────
# 適用：探索性分析、樣本品質不確定、不想遺漏候選特徵
# intensity_fc=1.5 → 1.5 倍強度差異即保留
_LOOSE: Step4Params = {
    "signal_threshold":                5000.0,
    "background_threshold":            0.20,
    "high_det_thresh":                 0.8,
    "low_det_thresh":                  0.2,
    "qc_ratio_threshold":              0.00,
    "intensity_fc_threshold":          1.5,
    "ratio_rescue_threshold":          1.5,
    "enable_background_threshold":     True,
    "enable_qc_ratio_threshold":       True,
    "enable_intensity_fc_threshold":   False,
    "enable_ratio_rescue":             True,
}

# ── 預設 ──────────────────────────────────────────────────────────────────────
# 適用：主力用途，針對 2–4 組、每組 20–46 人的實驗校準
# intensity_fc=2.0 → 對應 log2FC=1，metabolomics 常用閾值
_DEFAULT: Step4Params = {
    "signal_threshold":                5000.0,
    "background_threshold":            0.33,
    "high_det_thresh":                 0.8,
    "low_det_thresh":                  0.2,
    "qc_ratio_threshold":              0.25,
    "intensity_fc_threshold":          2.0,
    "ratio_rescue_threshold":          2.0,
    "enable_background_threshold":     True,
    "enable_qc_ratio_threshold":       True,
    "enable_intensity_fc_threshold":   False,
    "enable_ratio_rescue":             True,
}

# ── 嚴謹 ──────────────────────────────────────────────────────────────────────
# 適用：發表導向、高確信度分析，只保留偵測率差異顯著或強度差異大的特徵
# intensity_fc=3.0 → 3 倍以上才保留
_STRICT: Step4Params = {
    "signal_threshold":                5000.0,
    "background_threshold":            0.50,
    "high_det_thresh":                 0.8,
    "low_det_thresh":                  0.2,
    "qc_ratio_threshold":              0.50,
    "intensity_fc_threshold":          3.0,
    "ratio_rescue_threshold":          3.0,
    "enable_background_threshold":     True,
    "enable_qc_ratio_threshold":       True,
    "enable_intensity_fc_threshold":   False,
    "enable_ratio_rescue":             True,
}


STEP4_PRESETS: dict[PresetName, Step4Params] = {
    "loose":   _LOOSE,
    "default": _DEFAULT,
    "strict":  _STRICT,
}

# 各 preset 的人類可讀說明，可用於 GUI tooltip 或測試報告
PRESET_DESCRIPTIONS: dict[PresetName, str] = {
    "loose":   "寬鬆：探索型分析，保留較多候選特徵（MNAR 存在/缺失，穩定檢出≥0.20，fc≥1.5x，QC 僅移除零檢出）",
    "default": "預設：主力用途，平衡保留與 QC 穩定性（MNAR 存在/缺失，穩定檢出≥0.33，fc≥2.0x，QC檢出≥0.25）",
    "strict":  "嚴謹：發表品質，強調高確信與 QC 穩定（MNAR 存在/缺失，穩定檢出≥0.50，fc≥3.0x，QC檢出≥0.50）",
}


def get_step4_preset(name: PresetName = "default") -> Step4Params:
    """
    取得指定名稱的 Step 4 參數 preset。

    Args:
        name: "loose"、"default" 或 "strict"

    Returns:
        可直接 **unpack 到 feature_filter_adapter.run_from_df() 的參數 dict

    Example:
        params = get_step4_preset("strict")
        result = feature_filter_adapter.run_from_df(df, **params)
    """
    if name not in STEP4_PRESETS:
        raise ValueError(
            f"Unknown preset: {name!r}. "
            f"Available presets: {list(STEP4_PRESETS)}"
        )
    return dict(STEP4_PRESETS[name])  # type: ignore[return-value]
