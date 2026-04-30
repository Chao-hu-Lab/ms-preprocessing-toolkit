"""Step 4 Feature Filter preset facade backed by YAML pipeline profiles."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from ms_preprocessing.config.profile_loader import (
    get_pipeline_profile,
    get_pipeline_profile_document,
)

PresetName = Literal["loose", "default", "strict"]
_BUILTIN_PRESET_NAMES: tuple[PresetName, ...] = ("loose", "default", "strict")


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
    enable_mnar_gate: bool
    enable_ratio_rescue: bool


def _coerce_step4_params(params: dict[str, Any]) -> Step4Params:
    return {
        "signal_threshold": float(params["signal_threshold"]),
        "background_threshold": float(params["background_threshold"]),
        "high_det_thresh": float(params["high_det_thresh"]),
        "low_det_thresh": float(params["low_det_thresh"]),
        "qc_ratio_threshold": float(params["qc_ratio_threshold"]),
        "intensity_fc_threshold": float(params["intensity_fc_threshold"]),
        "ratio_rescue_threshold": float(params["ratio_rescue_threshold"]),
        "enable_background_threshold": bool(params["enable_background_threshold"]),
        "enable_qc_ratio_threshold": bool(params["enable_qc_ratio_threshold"]),
        "enable_intensity_fc_threshold": bool(params["enable_intensity_fc_threshold"]),
        "enable_mnar_gate": bool(params["enable_mnar_gate"]),
        "enable_ratio_rescue": bool(params["enable_ratio_rescue"]),
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
    if name not in _BUILTIN_PRESET_NAMES:
        raise ValueError(
            f"Unknown preset: {name!r}. "
            f"Available presets: {list(_BUILTIN_PRESET_NAMES)}"
        )
    return _coerce_step4_params(get_pipeline_profile(name)["step4"])


STEP4_PRESETS: dict[PresetName, Step4Params] = {
    name: get_step4_preset(name) for name in _BUILTIN_PRESET_NAMES
}

PRESET_DESCRIPTIONS: dict[PresetName, str] = {
    name: get_pipeline_profile_document(name)["description"] for name in _BUILTIN_PRESET_NAMES
}
