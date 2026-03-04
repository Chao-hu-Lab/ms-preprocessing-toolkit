"""Pipeline session state for GUI step chaining and exports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import re

import pandas as pd


class PipelineSession:
    """Tracks per-step outputs, parameters, and shared metadata context."""

    def __init__(self, output_dir: Path, source_file: Path | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.source_file = Path(source_file) if source_file else None
        self.step_output_paths: dict[int, Path] = {}
        self.step_parameters: dict[int, dict[str, Any]] = {}
        self.context: dict[str, Any] = {
            "red_font_rows": set(),
            "protected_rows": set(),
            "blue_font_cells": [],
            "highlight_rows": set(),
            "sample_info": None,
            "deleted_feature_df": None,
            "metadata_refs": {
                "sample_info_ref": None,
                "deleted_feature_ref": None,
            },
        }

    def set_source_file(self, source_file: Path | None) -> None:
        self.source_file = Path(source_file) if source_file else None

    def record_step_parameters(self, step_index: int, params: dict[str, Any]) -> None:
        self.step_parameters[step_index] = dict(params or {})

    def update_context_from_metadata(self, metadata: dict[str, Any] | None) -> None:
        if not metadata:
            return

        if "red_font_rows" in metadata:
            self.context["red_font_rows"] = set(metadata.get("red_font_rows") or [])
        if "protected_rows" in metadata:
            self.context["protected_rows"] = set(metadata.get("protected_rows") or [])
        elif "red_font_rows" in metadata:
            self.context["protected_rows"] = set(metadata.get("red_font_rows") or [])

        if "sample_info" in metadata:
            sample_info = metadata.get("sample_info")
            self.context["sample_info"] = sample_info
            self.context["metadata_refs"]["sample_info_ref"] = "SampleInfo" if sample_info is not None else None
        if "sample_info_ref" in metadata:
            self.context["metadata_refs"]["sample_info_ref"] = metadata.get("sample_info_ref")

        if "deleted_features" in metadata:
            deleted_df = None
            deleted_features = metadata.get("deleted_features") or []
            if deleted_features:
                try:
                    deleted_columns = list(deleted_features[0].index)
                    deleted_values = [row.tolist() for row in deleted_features]
                    deleted_df = pd.DataFrame(deleted_values, columns=deleted_columns)
                except Exception:
                    deleted_df = None
            self.context["deleted_feature_df"] = deleted_df
            self.context["metadata_refs"]["deleted_feature_ref"] = (
                "deleted_feature" if isinstance(deleted_df, pd.DataFrame) and not deleted_df.empty else None
            )
        if "deleted_feature_ref" in metadata:
            self.context["metadata_refs"]["deleted_feature_ref"] = metadata.get("deleted_feature_ref")

        if "blue_font_cells" in metadata:
            self.context["blue_font_cells"] = metadata.get("blue_font_cells") or []
        if "highlight_rows" in metadata:
            self.context["highlight_rows"] = set(metadata.get("highlight_rows") or [])

    def save_step_output(self, step_index: int, data: pd.DataFrame, file_handler) -> Path:
        """Persist step output as parquet intermediate for GUI chaining."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stem = self._get_base_stem(self.source_file) if self.source_file else "output"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        step_prefix = f"STEP{step_index + 1}"
        path = self.output_dir / f"{step_prefix}_{stem}_{timestamp}.parquet"

        file_handler.save_data(
            data,
            path,
            sheet_name="RawIntensity",
            highlight_rows=self.context.get("highlight_rows"),
            blue_font_cells=self.context.get("blue_font_cells"),
            red_font_rows=self.context.get("red_font_rows"),
            save_parquet_cache=False,
        )
        self.step_output_paths[step_index] = path
        return path

    def build_final_export_path(
        self,
        last_completed_step: int | None,
        last_run_all: bool,
        suffix: str = ".xlsx",
    ) -> Path:
        """Generate final materialized export path (xlsx by default)."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stem = self._get_base_stem(self.source_file) if self.source_file else "output"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if last_run_all:
            candidate = self.output_dir / f"ALL_{stem}{suffix}"
            if not candidate.exists():
                return candidate
            return self.output_dir / f"ALL_{stem}_{timestamp}{suffix}"

        step_idx = (last_completed_step + 1) if last_completed_step is not None else 1
        return self.output_dir / f"STEP{step_idx}_{stem}_{timestamp}{suffix}"

    def snapshot(self) -> dict[str, Any]:
        return {
            "step_parameters": {k: dict(v) for k, v in self.step_parameters.items()},
            "metadata_refs": dict(self.context.get("metadata_refs", {})),
            "step_output_paths": {k: str(v) for k, v in self.step_output_paths.items()},
        }

    @staticmethod
    def _get_base_stem(path: Path | None) -> str:
        if not path:
            return "output"
        stem = Path(path).stem
        for prefix in ["STEP1_", "STEP2_", "STEP3_", "STEP4_", "ALL_"]:
            if stem.startswith(prefix):
                stem = stem[len(prefix):]
                break
        return re.sub(r"_\d{8}_\d{6}$", "", stem)
