"""Compatibility facade for YAML-backed Step 1-4 pipeline profiles."""

from __future__ import annotations

from typing import Literal

from ms_preprocessing.config.profile_loader import (
    PipelineProfile,
    format_pipeline_profile_preview,
    get_pipeline_profile,
    list_pipeline_profiles,
    load_pipeline_profile_file,
)

PipelineProfileName = Literal["loose", "default", "strict"]

__all__ = [
    "PipelineProfile",
    "PipelineProfileName",
    "format_pipeline_profile_preview",
    "get_pipeline_profile",
    "list_pipeline_profiles",
    "load_pipeline_profile_file",
]
