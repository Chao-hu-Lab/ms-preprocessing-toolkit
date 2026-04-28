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

METHOD_FILE_ENV = "MSPTK_METHOD_FILE"
XIC_RESULTS_FILE_ENV = "MSPTK_XIC_RESULTS_FILE"
LOCAL_REFERENCE_CONFIG_ENV = "MSPTK_LOCAL_REFERENCE_CONFIG"
LEGACY_STEP2_ENV_VARS = ("MSPTK_ISTD_RECORD_FILE", "MSPTK_ISTD_RECORD_DATE")
LEGACY_STEP2_CONFIG_KEYS = frozenset({"istd_record_file", "istd_record_date", "istd_mz_list"})
STEP2_XIC_REQUIRED_MESSAGE = (
    "Step2 now requires an XIC Extractor results workbook. "
    "Please set xic_results_file or pass --xic-results-file."
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_CONFIG_PATH = PROJECT_ROOT / "config" / "local_reference_paths.json"


def _load_local_reference_config() -> dict[str, Any]:
    config_path = Path(os.getenv(LOCAL_REFERENCE_CONFIG_ENV, str(LOCAL_CONFIG_PATH)))
    if not config_path.exists():
        return {}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def _resolve_path(env_var: str, local_value: str | None) -> Path | None:
    override = os.getenv(env_var)
    if override:
        return Path(override)
    if local_value:
        return Path(local_value)
    return None


def _stringify_path(path_value: Path | None) -> str:
    return "" if path_value is None else str(path_value)


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
