"""YAML-backed pipeline profile loading."""

from __future__ import annotations

import copy
import re
from importlib import resources
from pathlib import Path
from typing import Any, TypedDict

import yaml

from ms_preprocessing.config.path_resolver import user_config_dir

LOCAL_PROFILE_DIR: Path | None = None
_BUILTIN_PROFILE_PACKAGE = "ms_preprocessing.resources.builtin_profiles"
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

_STRING_KEYS: dict[str, set[str]] = {
    "step1": {"mode", "method_file"},
    "step2": {"xic_results_file"},
    "step3": {"merge_mode", "degeneracy_adduct_table_file"},
    "step4": set(),
}
_BOOL_KEYS: dict[str, set[str]] = {
    "step1": {"auto_detect"},
    "step2": set(),
    "step3": {"preserve_red_font", "enable_degeneracy_annotation"},
    "step4": {
        "enable_background_threshold",
        "enable_qc_ratio_threshold",
        "enable_intensity_fc_threshold",
        "enable_mnar_gate",
        "enable_ratio_rescue",
    },
}
_NUMERIC_RANGES: dict[str, dict[str, tuple[float | None, float | None]]] = {
    "step1": {},
    "step2": {},
    "step3": {
        "mz_tolerance_ppm": (0.0, None),
        "rt_tolerance": (0.0, None),
        "degeneracy_ppm_tolerance": (0.0, None),
        "degeneracy_rt_tolerance": (0.0, None),
        "degeneracy_correlation_threshold": (0.0, 1.0),
    },
    "step4": {
        "signal_threshold": (0.0, None),
        "background_threshold": (0.0, 1.0),
        "high_det_thresh": (0.0, 1.0),
        "low_det_thresh": (0.0, 1.0),
        "qc_ratio_threshold": (0.0, 1.0),
        "intensity_fc_threshold": (1.0, None),
        "ratio_rescue_threshold": (1.0, None),
    },
}
_INT_RANGES: dict[str, dict[str, tuple[int, int | None]]] = {
    "step1": {},
    "step2": {},
    "step3": {"degeneracy_min_correlation_points": (1, None)},
    "step4": {},
}
_NULLABLE_INT_RANGES: dict[str, dict[str, tuple[int, int | None]]] = {
    "step1": {},
    "step2": {},
    "step3": {"top_n": (1, None)},
    "step4": {},
}
_ENUM_VALUES: dict[str, dict[str, set[str]]] = {
    "step1": {},
    "step2": {},
    "step3": {"merge_mode": {"per_sample_max", "fill_gaps"}},
    "step4": {},
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
        _validate_step_values(step_name, raw_step, source=source)
        steps[step_name] = dict(raw_step)
    return copy.deepcopy(steps)  # type: ignore[return-value]


def _validate_step_values(step_name: str, raw_step: dict[object, object], *, source: str) -> None:
    for key in _STRING_KEYS[step_name]:
        value = raw_step[key]
        if not isinstance(value, str):
            raise ValueError(f"Invalid profile {source}: {step_name}.{key} must be a string")

    for key in _BOOL_KEYS[step_name]:
        value = raw_step[key]
        if not isinstance(value, bool):
            raise ValueError(f"Invalid profile {source}: {step_name}.{key} must be true/false")

    for key, (minimum, maximum) in _NUMERIC_RANGES[step_name].items():
        _validate_numeric_value(step_name, key, raw_step[key], minimum, maximum, source=source)

    for key, (minimum, maximum) in _INT_RANGES[step_name].items():
        _validate_int_value(step_name, key, raw_step[key], minimum, maximum, source=source)

    for key, (minimum, maximum) in _NULLABLE_INT_RANGES[step_name].items():
        value = raw_step[key]
        if value is not None:
            _validate_int_value(step_name, key, value, minimum, maximum, source=source)

    for key, choices in _ENUM_VALUES[step_name].items():
        value = raw_step[key]
        if value not in choices:
            allowed = ", ".join(sorted(choices))
            raise ValueError(
                f"Invalid profile {source}: {step_name}.{key} must be one of: {allowed}"
            )


def _validate_numeric_value(
    step_name: str,
    key: str,
    value: object,
    minimum: float | None,
    maximum: float | None,
    *,
    source: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid profile {source}: {step_name}.{key} must be a number")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise ValueError(f"Invalid profile {source}: {step_name}.{key} must be >= {minimum}")
    if maximum is not None and numeric > maximum:
        raise ValueError(f"Invalid profile {source}: {step_name}.{key} must be <= {maximum}")


def _validate_int_value(
    step_name: str,
    key: str,
    value: object,
    minimum: int,
    maximum: int | None,
    *,
    source: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid profile {source}: {step_name}.{key} must be an integer")
    if value < minimum:
        raise ValueError(f"Invalid profile {source}: {step_name}.{key} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"Invalid profile {source}: {step_name}.{key} must be <= {maximum}")


def _resolve_placeholders(steps: PipelineProfile) -> PipelineProfile:
    from ms_preprocessing.config import pipeline_defaults

    def resolve(value: object) -> object:
        if not isinstance(value, str):
            return value
        match = _PLACEHOLDER_RE.match(value)
        if match is None:
            return value
        return pipeline_defaults.resolve_reference_value(match.group(1))

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
    local_profile_dir = _local_profile_dir()
    if not local_profile_dir.exists():
        return {}
    paths: dict[str, Path] = {}
    for path in sorted(local_profile_dir.glob("*.yml")) + sorted(
        local_profile_dir.glob("*.yaml")
    ):
        if path.is_file() and ".example." not in path.name:
            paths[path.stem] = path
    return paths


def _local_profile_dir() -> Path:
    return LOCAL_PROFILE_DIR if LOCAL_PROFILE_DIR is not None else user_config_dir() / "presets"


def _format_number(value: float) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}"
