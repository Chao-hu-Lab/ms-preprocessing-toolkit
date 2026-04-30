"""Pipeline session state for workflow step chaining and exports."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ms_preprocessing.config.settings import Settings
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


class PipelineSession:
    """Tracks per-step outputs, parameters, and shared metadata context."""

    def __init__(
        self,
        output_dir: Path,
        source_file: Path | None = None,
        intermediate_dir: Path | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.source_file = Path(source_file) if source_file else None
        self.intermediate_dir = (
            Path(intermediate_dir)
            if intermediate_dir is not None
            else Settings.get_parquet_cache_root() / "gui-intermediate"
        )
        self.step_output_paths: dict[int, Path] = {}
        self.step_outputs: dict[str, str] = {}
        self.step_parameters: dict[int, dict[str, Any]] = {}
        self.completed_steps: set[str] = set()
        self.metadata: ProcessingMetadata = ProcessingMetadata()
        self._metadata_refs: dict[str, str | None] = {
            "sample_info_ref": None,
            "deleted_feature_ref": None,
        }
        # TODO(arch-refactor): retire this legacy dict once GUI consumers read ProcessingMetadata directly.
        self.context: dict[str, Any] = {}
        self._sync_context_from_metadata()

    def set_source_file(self, source_file: Path | None) -> None:
        self.source_file = Path(source_file) if source_file else None

    def record_step_parameters(self, step_index: int, params: dict[str, Any]) -> None:
        self.step_parameters[step_index] = dict(params or {})

    def update_context_from_metadata(
        self,
        metadata: ProcessingMetadata | dict[str, Any] | None,
    ) -> None:
        """Backward-compatible metadata merge for dict-based callers."""
        if not metadata:
            return

        if isinstance(metadata, ProcessingMetadata):
            metadata = metadata.as_context_dict()

        self._merge_formatting_metadata(
            red_font_rows=set(metadata.get("red_font_rows") or []) if "red_font_rows" in metadata else None,
            protected_rows=set(metadata.get("protected_rows") or []) if "protected_rows" in metadata else None,
            blue_font_cells=list(metadata.get("blue_font_cells") or []) if "blue_font_cells" in metadata else None,
            highlight_rows=set(metadata.get("highlight_rows") or []) if "highlight_rows" in metadata else None,
        )

        if "sample_info" in metadata:
            sample_info = metadata.get("sample_info")
            self.metadata.sample_info = sample_info if isinstance(sample_info, pd.DataFrame) else None
            self._metadata_refs["sample_info_ref"] = "SampleInfo" if sample_info is not None else None
        if "sample_info_ref" in metadata:
            self._metadata_refs["sample_info_ref"] = metadata.get("sample_info_ref")

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
            self.metadata.deleted_feature_df = deleted_df
            self._metadata_refs["deleted_feature_ref"] = (
                "deleted_feature" if isinstance(deleted_df, pd.DataFrame) and not deleted_df.empty else None
            )
        if "deleted_feature_df" in metadata:
            deleted_feature_df = metadata.get("deleted_feature_df")
            self.metadata.deleted_feature_df = (
                deleted_feature_df if isinstance(deleted_feature_df, pd.DataFrame) else None
            )
            self._metadata_refs["deleted_feature_ref"] = (
                "deleted_feature"
                if isinstance(self.metadata.deleted_feature_df, pd.DataFrame)
                and not self.metadata.deleted_feature_df.empty
                else None
            )
        if "deleted_feature_ref" in metadata:
            self._metadata_refs["deleted_feature_ref"] = metadata.get("deleted_feature_ref")

        self._sync_context_from_metadata()

    def can_run_step(self, step: str) -> bool:
        """Return whether GUI prerequisites for a step are satisfied."""
        prerequisites: dict[str, set[str]] = {
            "data_organizer": set(),
            "istd_marker": set(),
            "duplicate_remover": {"data_organizer"},
            "feature_filter": {"data_organizer"},
        }
        return prerequisites.get(step, set()).issubset(self.completed_steps)

    def update_from_result(self, result: ProcessingResult) -> None:
        """Merge a typed processing result into session state."""
        if not result.success:
            return

        new_metadata = result.metadata
        self._replace_formatting_metadata(
            red_font_rows=set(new_metadata.red_font_rows),
            protected_rows=set(new_metadata.protected_rows),
            blue_font_cells=list(new_metadata.blue_font_cells),
            highlight_rows=set(new_metadata.highlight_rows),
        )
        if new_metadata.sample_info is not None:
            self.metadata.sample_info = new_metadata.sample_info
            self._metadata_refs["sample_info_ref"] = "SampleInfo"
        if new_metadata.deleted_feature_df is not None or result.step == "feature_filter":
            self.metadata.deleted_feature_df = new_metadata.deleted_feature_df
            self._metadata_refs["deleted_feature_ref"] = (
                "deleted_feature"
                if isinstance(self.metadata.deleted_feature_df, pd.DataFrame)
                and not self.metadata.deleted_feature_df.empty
                else None
            )

        self.completed_steps.add(result.step)
        if result.output_path:
            self.step_outputs[result.step] = result.output_path

        self._sync_context_from_metadata()

    def save_step_output(self, step_index: int, data: pd.DataFrame, file_handler) -> Path:
        """Persist step output as parquet intermediate for workflow chaining."""
        path = self.build_step_output_path(step_index)

        file_handler.save_data(
            data,
            path,
            sheet_name="RawIntensity",
            highlight_rows=self.metadata.highlight_rows,
            blue_font_cells=self.metadata.blue_font_cells,
            red_font_rows=self.metadata.red_font_rows,
            save_parquet_cache=False,
        )
        self.step_output_paths[step_index] = path
        return path

    def build_step_output_path(self, step_index: int) -> Path:
        """Build an intermediate path without registering it as a completed output."""
        self.intermediate_dir.mkdir(parents=True, exist_ok=True)
        stem = self._get_base_stem(self.source_file) if self.source_file else "output"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        step_prefix = f"STEP{step_index + 1}"
        base_name = f"{step_prefix}_{stem}_{timestamp}"
        candidate = self.intermediate_dir / f"{base_name}.parquet"
        counter = 1
        while candidate.exists():
            candidate = self.intermediate_dir / f"{base_name}_{counter}.parquet"
            counter += 1
        return candidate

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
            "metadata_refs": dict(self._metadata_refs),
            "step_output_paths": {k: str(v) for k, v in self.step_output_paths.items()},
        }

    def _sync_context_from_metadata(self) -> None:
        next_context = {
            "red_font_rows": set(self.metadata.red_font_rows),
            "protected_rows": set(self.metadata.protected_rows),
            "blue_font_cells": list(self.metadata.blue_font_cells),
            "highlight_rows": set(self.metadata.highlight_rows),
            "sample_info": self.metadata.sample_info,
            "deleted_feature_df": self.metadata.deleted_feature_df,
            "metadata_refs": dict(self._metadata_refs),
        }
        self.context.clear()
        self.context.update(next_context)


    def _merge_formatting_metadata(
        self,
        *,
        red_font_rows: set[Any] | None = None,
        protected_rows: set[Any] | None = None,
        blue_font_cells: list[Any] | None = None,
        highlight_rows: set[Any] | None = None,
    ) -> None:
        if red_font_rows is not None:
            self.metadata.red_font_rows |= set(red_font_rows)
        if protected_rows is not None:
            self.metadata.protected_rows |= set(protected_rows)
        elif red_font_rows is not None:
            self.metadata.protected_rows |= set(red_font_rows)
        if blue_font_cells is not None:
            self.metadata.blue_font_cells = self._merge_sequence(
                self.metadata.blue_font_cells,
                blue_font_cells,
            )
        if highlight_rows is not None:
            self.metadata.highlight_rows |= set(highlight_rows)

    def _replace_formatting_metadata(
        self,
        *,
        red_font_rows: set[Any] | None = None,
        protected_rows: set[Any] | None = None,
        blue_font_cells: list[Any] | None = None,
        highlight_rows: set[Any] | None = None,
    ) -> None:
        """Replace row/cell-indexed formatting metadata with the latest step output."""
        if red_font_rows is not None:
            self.metadata.red_font_rows = set(red_font_rows)
        if protected_rows is not None:
            self.metadata.protected_rows = set(protected_rows)
        elif red_font_rows is not None:
            self.metadata.protected_rows = set(red_font_rows)
        if blue_font_cells is not None:
            self.metadata.blue_font_cells = list(blue_font_cells)
        if highlight_rows is not None:
            self.metadata.highlight_rows = set(highlight_rows)

    @staticmethod
    def _merge_sequence(existing: list[Any], incoming: list[Any]) -> list[Any]:
        merged = list(existing)
        for value in incoming:
            if value not in merged:
                merged.append(value)
        return merged

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
