"""Combined TSV preprocessing orchestration for the GUI pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class CombinedTsvController:
    """Coordinate Step 1 combined TSV preprocessing UI flow."""

    def __init__(self, host: Any, *, combined_tsv_service: Any) -> None:
        self._host = host
        self._combined_tsv_service = combined_tsv_service

    def run_combined_tsv_preprocessor(self) -> None:
        host = self._host
        if host._has_active_processing():
            host._log("Busy: wait for the current task to finish before creating combined_fix.")
            return

        if not host.__dict__.get("step_widgets"):
            host._show_error("Step 1 widget is not available.")
            return

        widget = host.step_widgets[0]
        path_getter = getattr(widget, "get_combined_preprocessor_paths", None)
        if not callable(path_getter):
            host._show_error("Combined TSV controls are not available.")
            return

        paths = path_getter()
        raw_text = str(paths.get("combined_tsv") or "").strip()
        method_text = str(paths.get("method_file") or "").strip()
        if not raw_text:
            host._show_error("Please select a combined TSV file first.")
            return

        raw_path = Path(raw_text)
        if not raw_path.exists():
            host._show_error(f"Combined TSV file not found:\n{raw_path}")
            return

        host._set_pipeline_busy_state(True)
        try:
            host._log(f"Creating combined_fix file from: {raw_path}")
            loaded_path = self._combined_tsv_service.create_combined_fix(
                raw_path=raw_path,
                method_file=Path(method_text) if method_text else None,
                output_dir=host._output_dir,
                progress_callback=host._safe_update_action_bar_progress,
            )
            stats = getattr(self._combined_tsv_service, "last_statistics", {}) or {}
            removed = stats.get("removed_features", "unknown")
            output_features = stats.get(
                "output_features",
                getattr(self._combined_tsv_service, "last_output_features", "unknown"),
            )
            host._log(
                f"Combined TSV preprocessing complete: {output_features} features kept, "
                f"{removed} removed. Output: {loaded_path}"
            )
        except Exception as exc:
            host._show_error(f"Combined TSV preprocessing failed:\n{exc}")
            return
        finally:
            host._set_pipeline_busy_state(False)

        host._load_file_for_step(0, path=loaded_path)
        prefill = getattr(host.step_widgets[0], "prefill_normal_method_from_combined", None)
        if callable(prefill):
            prefill()
        host._last_materialized_export_path = loaded_path
        self._update_run_context_summary()
        host._log("Ready: review Step 1 settings, then run Step 1 or Run All.")

    def _update_run_context_summary(self) -> None:
        updater = getattr(self._host, "_update_run_context_summary", None)
        if callable(updater):
            updater()
