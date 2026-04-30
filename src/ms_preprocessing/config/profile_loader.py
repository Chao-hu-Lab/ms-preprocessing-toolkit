"""YAML-backed pipeline profile loading."""

from __future__ import annotations

import copy
import re
from importlib import resources
from pathlib import Path
from typing import Any, TypedDict

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_PROFILE_DIR = PROJECT_ROOT / "config" / "presets"
_BUILTIN_PROFILE_PACKAGE = "ms_preprocessing.config.presets"
_PLACEHOLDER_RE = re.compile(r"^\$\{local\.([A-Za-z_][A-Za-z0-9_]*)\}$")
_RUNTIME_FILE_KEYS = {"input", "input_file", "output", "output_file"}
_BUILTIN_PROFILE_ORDER = ("loose", "default", "strict")

_STEP_ALLOWED_KEYS: dict[str, set[str]] = {
    "step1": {"mode", "auto_detect", "method_file"},
    "step2": {"xic_results_file"},
    "step3": {
        "mz_tolerance_ppm",
        "rt_tolerance",
        "merge_mode",
        "preserve_red_font",
        "top_n",
        "enable_degeneracy_annotation",
        "degeneracy_ppm_tolerance",
        "degeneracy_rt_tolerance",
        "degeneracy_correlation_threshold",
        "degeneracy_min_correlation_points",
        "degeneracy_adduct_table_file",
    },
    "step4": {
        "signal_threshold",
        "background_threshold",
        "high_det_thresh",
        "low_det_thresh",
        "qc_ratio_threshold",
        "intensity_fc_threshold",
        "ratio_rescue_threshold",
        "enable_background_threshold",
        "enable_qc_ratio_threshold",
        "enable_intensity_fc_threshold",
        "enable_mnar_gate",
        "enable_ratio_rescue",
    },
}


class PipelineProfile(TypedDict):
    """Complete parameter bundle for a Step 1-4 preprocessing run."""

    step1: dict[str, Any]
    step2: dict[str, Any]
    step3: dict[str, Any]
    step4: dict[str, Any]


class ProfileDocument(TypedDict):
    version: int
    name: str
    description: str
    steps: PipelineProfile


def list_pipeline_profiles() -> list[str]:
    """Return built-in and local YAML profile names."""

    names: list[str] = [name for name in _BUILTIN_PROFILE_ORDER if _read_builtin_profile_text(name)]
    for name in sorted(_local_profile_paths()):
        if name not in names:
            names.append(name)
    return names


def get_pipeline_profile(name: str = "default") -> PipelineProfile:
    """Load a named built-in or local profile."""

    path = _local_profile_paths().get(name)
    if path is not None:
        return load_pipeline_profile_file(path)

    text = _read_builtin_profile_text(name)
    if text is None:
        raise ValueError(f"Unknown pipeline profile: {name!r}")
    return _profile_from_text(text, source=f"built-in profile {name!r}")["steps"]


def get_pipeline_profile_document(name: str = "default") -> ProfileDocument:
    """Load a named profile including its metadata."""

    path = _local_profile_paths().get(name)
    if path is not None:
        return _profile_from_text(path.read_text(encoding="utf-8"), source=str(path))

    text = _read_builtin_profile_text(name)
    if text is None:
        raise ValueError(f"Unknown pipeline profile: {name!r}")
    return _profile_from_text(text, source=f"built-in profile {name!r}")


def load_pipeline_profile_file(path: str | Path) -> PipelineProfile:
    """Load an explicit profile file path."""

    profile_path = Path(path)
    return _profile_from_text(profile_path.read_text(encoding="utf-8"), source=str(profile_path))[
        "steps"
    ]


def format_pipeline_profile_preview(name: str = "default") -> str:
    """Return the compact sidebar preview for a Run All pipeline profile."""

    document = get_pipeline_profile_document(name)
    profile = document["steps"]
    step4 = profile["step4"]
    intensity_fc = (
        f"{_format_number(step4['intensity_fc_threshold'])}x"
        if step4.get("enable_intensity_fc_threshold")
        else "off"
    )
    ratio_rescue = (
        f"{_format_number(step4['ratio_rescue_threshold'])}x"
        if step4.get("enable_ratio_rescue")
        else "off"
    )
    return "\n".join(
        [
            document.get("description") or f"Profile: {document['name']}",
            "Step 1-3: YAML profile",
            (
                f"訊號: {_format_number(step4['signal_threshold'])} | "
                f"穩定檢出: {_format_number(step4['background_threshold'])}"
            ),
            (
                f"MNAR 出現/缺失: {float(step4['high_det_thresh']):.2f} / "
                f"{float(step4['low_det_thresh']):.2f} | "
                f"QC檢出: {float(step4['qc_ratio_threshold']):.2f}"
            ),
            f"檢出率救援: {ratio_rescue} | 強度倍率: {intensity_fc}",
        ]
    )


def _profile_from_text(text: str, *, source: str) -> ProfileDocument:
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML profile {source}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid profile {source}: top-level YAML must be a mapping")

    _reject_runtime_keys(raw, source=source)
    for key in ("version", "name", "steps"):
        if key not in raw:
            raise ValueError(f"Invalid profile {source}: missing required key {key!r}")
    if raw["version"] != 1:
        raise ValueError(f"Invalid profile {source}: unsupported version {raw['version']!r}")
    if not isinstance(raw["name"], str) or not raw["name"].strip():
        raise ValueError(f"Invalid profile {source}: name must be a non-empty string")
    if not isinstance(raw["steps"], dict):
        raise ValueError(f"Invalid profile {source}: steps must be a mapping")

    steps = _validate_steps(raw["steps"], source=source)
    resolved = _resolve_placeholders(steps)
    return {
        "version": int(raw["version"]),
        "name": raw["name"],
        "description": str(raw.get("description") or ""),
        "steps": resolved,
    }


def _validate_steps(raw_steps: dict[str, object], *, source: str) -> PipelineProfile:
    for step_name in _STEP_ALLOWED_KEYS:
        if step_name not in raw_steps:
            raise ValueError(f"Invalid profile {source}: missing required step {step_name!r}")

    steps: dict[str, dict[str, Any]] = {}
    for step_name, allowed_keys in _STEP_ALLOWED_KEYS.items():
        raw_step = raw_steps[step_name]
        if not isinstance(raw_step, dict):
            raise ValueError(f"Invalid profile {source}: {step_name} must be a mapping")
        unknown_keys = set(raw_step) - allowed_keys
        if unknown_keys:
            unknown = ", ".join(sorted(unknown_keys))
            raise ValueError(f"Invalid profile {source}: unknown {step_name} key(s): {unknown}")
        missing_keys = allowed_keys - set(raw_step)
        if missing_keys:
            missing = ", ".join(sorted(missing_keys))
            raise ValueError(f"Invalid profile {source}: missing {step_name} key(s): {missing}")
        steps[step_name] = dict(raw_step)
    return copy.deepcopy(steps)  # type: ignore[return-value]


def _resolve_placeholders(steps: PipelineProfile) -> PipelineProfile:
    from ms_preprocessing.config import pipeline_defaults

    local_values = pipeline_defaults._load_local_reference_config()

    def resolve(value: object) -> object:
        if not isinstance(value, str):
            return value
        match = _PLACEHOLDER_RE.match(value)
        if match is None:
            return value
        return str(local_values.get(match.group(1), ""))

    return {
        step_name: {key: resolve(value) for key, value in params.items()}
        for step_name, params in steps.items()
    }  # type: ignore[return-value]


def _reject_runtime_keys(value: object, *, source: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in _RUNTIME_FILE_KEYS:
                raise ValueError(f"Invalid profile {source}: runtime file key {key!r} is not allowed")
            _reject_runtime_keys(child, source=source)
    elif isinstance(value, list):
        for child in value:
            _reject_runtime_keys(child, source=source)


def _builtin_profile_names() -> list[str]:
    return [
        path.stem
        for path in resources.files(_BUILTIN_PROFILE_PACKAGE).iterdir()
        if path.name.endswith(".yml")
    ]


def _read_builtin_profile_text(name: str) -> str | None:
    resource = resources.files(_BUILTIN_PROFILE_PACKAGE).joinpath(f"{name}.yml")
    if not resource.is_file():
        return None
    return resource.read_text(encoding="utf-8")


def _local_profile_paths() -> dict[str, Path]:
    if not LOCAL_PROFILE_DIR.exists():
        return {}
    paths: dict[str, Path] = {}
    for path in sorted(LOCAL_PROFILE_DIR.glob("*.yml")) + sorted(LOCAL_PROFILE_DIR.glob("*.yaml")):
        if path.is_file() and ".example." not in path.name:
            paths[path.stem] = path
    return paths


def _format_number(value: float) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}"
