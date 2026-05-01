"""
Pipeline fixed parameters for Steps 1-3.

Step 4 named presets live in ``feature_filter_presets.py``.

Resolution order for reference files:
1. Environment variable override
2. Local config file (git-ignored)
3. Empty value in the open-source distribution
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from ms_preprocessing.config.path_resolver import user_config_dir

METHOD_FILE_ENV = "MSPTK_METHOD_FILE"
XIC_RESULTS_FILE_ENV = "MSPTK_XIC_RESULTS_FILE"
LOCAL_REFERENCE_CONFIG_ENV = "MSPTK_LOCAL_REFERENCE_CONFIG"
LEGACY_STEP2_ENV_VARS = ("MSPTK_ISTD_RECORD_FILE", "MSPTK_ISTD_RECORD_DATE")
LEGACY_STEP2_CONFIG_KEYS = frozenset({"istd_record_file", "istd_record_date", "istd_mz_list"})
STEP2_XIC_REQUIRED_MESSAGE = (
    "Step2 now requires an XIC Extractor results workbook. "
    "Please set xic_results_file or pass --xic-results-file."
)

def _local_reference_yaml_path() -> Path:
    return user_config_dir() / "local_reference.yml"


def _local_reference_json_path() -> Path:
    return user_config_dir() / "local_reference_paths.json"


LOCAL_REFERENCE_YAML_PATH = _local_reference_yaml_path()
LOCAL_REFERENCE_JSON_PATH = _local_reference_json_path()
LOCAL_CONFIG_PATH = LOCAL_REFERENCE_JSON_PATH


def _reference_config_path() -> Path | None:
    override = os.getenv(LOCAL_REFERENCE_CONFIG_ENV)
    if override:
        return Path(override)
    yaml_path = _local_reference_yaml_path()
    json_path = _local_reference_json_path()
    if yaml_path.exists():
        return yaml_path
    if json_path.exists():
        return json_path
    return None


def _extract_reference_config(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    references = data.get("references")
    if isinstance(references, dict):
        return references
    return data


def _load_local_reference_config() -> dict[str, Any]:
    config_path = _reference_config_path()
    if config_path is None or not config_path.exists():
        return {}

    try:
        text = config_path.read_text(encoding="utf-8")
        if config_path.suffix.lower() in {".yml", ".yaml"}:
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError):
        return {}

    return _extract_reference_config(data)


def _resolve_path(env_var: str, local_value: str | None) -> Path | None:
    override = os.getenv(env_var)
    if override:
        return Path(override)
    if local_value:
        return Path(local_value)
    return None


def _stringify_path(path_value: Path | None) -> str:
    return "" if path_value is None else str(path_value)


def resolve_reference_value(key: str) -> str:
    """Resolve a local reference value with env overrides where applicable."""
    config = _load_local_reference_config()
    if key == "method_file":
        return _stringify_path(_resolve_path(METHOD_FILE_ENV, config.get("method_file")))
    if key == "xic_results_file":
        return _stringify_path(
            _resolve_path(XIC_RESULTS_FILE_ENV, config.get("xic_results_file"))
        )
    value = config.get(key)
    return "" if value is None else str(value)


def get_legacy_step2_source_details() -> list[str]:
    """Return active legacy Step2 env/config sources without failing import."""
    config = _load_local_reference_config()
    legacy_env = [env_var for env_var in LEGACY_STEP2_ENV_VARS if os.getenv(env_var)]
    legacy_keys = sorted(LEGACY_STEP2_CONFIG_KEYS.intersection(config))
    if not legacy_env and not legacy_keys:
        return []

    details: list[str] = []
    if legacy_env:
        details.append(f"legacy env var(s): {', '.join(legacy_env)}")
    if legacy_keys:
        details.append(f"legacy local config key(s): {', '.join(legacy_keys)}")
    return details


_LOCAL_REFERENCE_CONFIG = _load_local_reference_config()

DEFAULT_METHOD_FILE = _resolve_path(
    METHOD_FILE_ENV,
    _LOCAL_REFERENCE_CONFIG.get("method_file"),
)
DEFAULT_XIC_RESULTS_FILE = _resolve_path(
    XIC_RESULTS_FILE_ENV,
    _LOCAL_REFERENCE_CONFIG.get("xic_results_file"),
)

STEP1_PARAMS: dict = {
    "mode": "normalization",
    "auto_detect": True,
    "method_file": _stringify_path(DEFAULT_METHOD_FILE),
}

STEP2_PARAMS: dict = {
    "xic_results_file": _stringify_path(DEFAULT_XIC_RESULTS_FILE),
}

STEP3_PARAMS: dict = {
    "mz_tolerance_ppm": 20.0,
    "rt_tolerance": 0.1,
    "merge_mode": "per_sample_max",
    "preserve_red_font": True,
    "top_n": None,
    "enable_degeneracy_annotation": False,
    "degeneracy_ppm_tolerance": 20.0,
    "degeneracy_rt_tolerance": 0.05,
    "degeneracy_correlation_threshold": 0.8,
    "degeneracy_min_correlation_points": 3,
    "degeneracy_adduct_table_file": "",
}
