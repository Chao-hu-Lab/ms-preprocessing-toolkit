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
ISTD_RECORD_FILE_ENV = "MSPTK_ISTD_RECORD_FILE"
LOCAL_REFERENCE_CONFIG_ENV = "MSPTK_LOCAL_REFERENCE_CONFIG"

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


_LOCAL_REFERENCE_CONFIG = _load_local_reference_config()

DEFAULT_METHOD_FILE = _resolve_path(
    METHOD_FILE_ENV,
    _LOCAL_REFERENCE_CONFIG.get("method_file"),
)
DEFAULT_ISTD_RECORD_FILE = _resolve_path(
    ISTD_RECORD_FILE_ENV,
    _LOCAL_REFERENCE_CONFIG.get("istd_record_file"),
)

STEP1_PARAMS: dict = {
    "mode": "normalization",
    "auto_detect": True,
    "method_file": _stringify_path(DEFAULT_METHOD_FILE),
}

STEP2_PARAMS: dict = {
    "ppm_tolerance": 20.0,
    "rt_tolerance": 1.5,
    "istd_mz_list": [261.1273, 245.1324, 289.0841, 300.1605, 269.1436, 482.2087, 303.0913],
    "istd_record_file": _stringify_path(DEFAULT_ISTD_RECORD_FILE),
    "istd_record_date": "20260106",
}

STEP3_PARAMS: dict = {
    "mz_tolerance_ppm": 20.0,
    "rt_tolerance": 1.0,
    "preserve_red_font": True,
    "top_n": None,
    "enable_degeneracy_annotation": False,
    "degeneracy_ppm_tolerance": 20.0,
    "degeneracy_rt_tolerance": 0.05,
    "degeneracy_correlation_threshold": 0.8,
    "degeneracy_min_correlation_points": 3,
    "degeneracy_adduct_table_file": "",
}
