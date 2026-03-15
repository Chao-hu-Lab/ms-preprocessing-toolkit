"""
Step 4 Feature Filter — Parameter Presets

設計依據：
  - 主場景：2 組（exposure vs control）+ QC，總樣本 85–148，每組約 20–46 人
  - QC 樣本數量少（7–10 個），統計力不足，qc_ratio_threshold 統一維持 0.00
  - diff_threshold 代表「最大偵測率組 - 最小偵測率組」，2 組情境下等同直接的組間差異

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
    skew_threshold: float
    diff_threshold: float
    qc_ratio_threshold: float
    enable_background_threshold: bool
    enable_skew_threshold: bool
    enable_diff_threshold: bool
    enable_qc_ratio_threshold: bool


# ── 寬鬆 ──────────────────────────────────────────────────────────────────────
# 適用：探索性分析、樣本品質不確定、不想遺漏候選特徵
# diff=0.20 對應 N=23 約 5 人差、N=35 約 7 人差
_LOOSE: Step4Params = {
    "signal_threshold":             5000.0,
    "background_threshold":         0.20,
    "skew_threshold":               0.50,
    "diff_threshold":               0.20,
    "qc_ratio_threshold":           0.00,
    "enable_background_threshold":  True,
    "enable_skew_threshold":        True,
    "enable_diff_threshold":        True,
    "enable_qc_ratio_threshold":    True,
}

# ── 預設 ──────────────────────────────────────────────────────────────────────
# 適用：主力用途，針對 2–4 組、每組 20–46 人的實驗校準
# diff=0.25 對應 N=23 約 6 人差、N=35 約 9 人差（約 p<0.05 邊界）
_DEFAULT: Step4Params = {
    "signal_threshold":             5000.0,
    "background_threshold":         0.33,
    "skew_threshold":               0.66,
    "diff_threshold":               0.25,
    "qc_ratio_threshold":           0.00,
    "enable_background_threshold":  True,
    "enable_skew_threshold":        True,
    "enable_diff_threshold":        True,
    "enable_qc_ratio_threshold":    True,
}

# ── 嚴謹 ──────────────────────────────────────────────────────────────────────
# 適用：發表導向、高確信度分析、只保留偵測率差異顯著的特徵
# diff=0.35 對應 N=23 約 8 人差、N=35 約 12 人差
_STRICT: Step4Params = {
    "signal_threshold":             5000.0,
    "background_threshold":         0.50,
    "skew_threshold":               0.80,
    "diff_threshold":               0.35,
    "qc_ratio_threshold":           0.00,
    "enable_background_threshold":  True,
    "enable_skew_threshold":        True,
    "enable_diff_threshold":        True,
    "enable_qc_ratio_threshold":    True,
}


STEP4_PRESETS: dict[PresetName, Step4Params] = {
    "loose":   _LOOSE,
    "default": _DEFAULT,
    "strict":  _STRICT,
}

# 各 preset 的人類可讀說明，可用於 GUI tooltip 或測試報告
PRESET_DESCRIPTIONS: dict[PresetName, str] = {
    "loose":   "寬鬆：探索型分析，保留較多候選特徵（diff≥0.20，bg≥0.20，skew≥0.50）",
    "default": "預設：主力用途，組間 6–9 人偵測率差即保留（diff≥0.25，bg≥0.33，skew≥0.66）",
    "strict":  "嚴謹：發表品質，組間 8–12 人偵測率差才保留（diff≥0.35，bg≥0.50，skew≥0.80）",
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
