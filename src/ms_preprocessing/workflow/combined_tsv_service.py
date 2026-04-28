"""Combined TSV preprocessing service for GUI Step 1 handoff."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ms_preprocessing.adapters import data_organizer as data_organizer_adapter
from ms_preprocessing.utils.file_handler import FileHandler


class CombinedTsvService:
    """Create a Step 1-loadable combined_fix workbook from a combined TSV."""

    def __init__(self, file_handler: FileHandler | None = None) -> None:
        self._file_handler = file_handler or FileHandler()
        self.last_statistics: dict[str, object] = {}
        self.last_output_features: int | None = None

    def create_combined_fix(
        self,
        *,
        raw_path: Path,
        method_file: Path | None,
        output_dir: Path,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> Path:
        output_path = self.build_output_path(raw_path=raw_path, output_dir=output_dir)
        result = data_organizer_adapter.run_combined_fix(
            str(raw_path),
            method_file=str(method_file) if method_file else None,
            progress_callback=progress_callback,
        )
        if not result.success or result.data is None:
            raise RuntimeError(result.error or "Combined TSV preprocessing failed.")

        self.last_statistics = dict(result.statistics or {})
        self.last_output_features = len(result.data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        saved_path = self._file_handler.save_data(
            result.data,
            output_path,
            save_parquet_cache=False,
        )
        return Path(saved_path)

    @staticmethod
    def build_output_path(*, raw_path: Path, output_dir: Path) -> Path:
        combined_dir = Path(output_dir) / "combined_fix"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = combined_dir / f"{Path(raw_path).stem}_combined_fix_{timestamp}.xlsx"
        if not base.exists():
            return base

        counter = 2
        while True:
            candidate = combined_dir / f"{Path(raw_path).stem}_combined_fix_{timestamp}_{counter}.xlsx"
            if not candidate.exists():
                return candidate
            counter += 1
