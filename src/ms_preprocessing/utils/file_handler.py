"""
File handling utilities for MS Preprocessing Toolkit.

This module provides functions for reading and writing various file formats
commonly used in mass spectrometry data processing.
"""

import importlib.util
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from ms_preprocessing.config.settings import Settings
from ms_preprocessing.utils.excel_formatting_writer import ExcelFormattingWriter
from ms_preprocessing.utils.intermediate_store import IntermediateStore
from ms_preprocessing.utils.input_reader import InputReader
from ms_preprocessing.utils.output_writer import OutputWriter
from ms_preprocessing.utils.parquet_cache_store import ParquetCacheStore
from ms_preprocessing.utils.parquet_compat import (
    normalize_dataframe_for_parquet,
)

logger = logging.getLogger(__name__)


class FileHandler:
    """
    Handles file I/O operations for mass spectrometry data files.

    Supports Excel (.xlsx, .xls), CSV, and TSV formats with
    preservation of formatting information where applicable.
    """

    SUPPORTED_FORMATS = Settings.SUPPORTED_FORMATS

    def __init__(self):
        """Initialize the FileHandler."""
        self._last_loaded_path: Path | None = None
        self._input_reader = InputReader()
        self._excel_writer = ExcelFormattingWriter()
        self._output_writer = OutputWriter()
        self._parquet_cache_store = ParquetCacheStore()

    @staticmethod
    def is_supported_format(file_path: str | Path) -> bool:
        """Check if the file format is supported."""
        path = Path(file_path)
        return path.suffix.lower() in FileHandler.SUPPORTED_FORMATS

    def load_data(
        self,
        file_path: str | Path,
        sheet_name: str | int | None = 0,
        header_row: int = 0,
    ) -> tuple[pd.DataFrame, dict]:
        """
        Load data from a file.

        Args:
            file_path: Path to the input file
            sheet_name: Sheet name or index for Excel files
            header_row: Row index to use as header

        Returns:
            Tuple of (DataFrame, metadata dict)
        """
        path = Path(file_path)
        # Prefer parquet cache only when cache feature is enabled.
        if Settings.SAVE_PARQUET_CACHE and path.suffix.lower() == ".xlsx":
            cached = self._resolve_parquet_cache(path)
            if cached:
                path = cached
        self._last_loaded_path = path
        red_font_rows: set = set()
        metadata = {"source_file": str(path), "load_time": datetime.now().isoformat()}

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not self.is_supported_format(path):
            raise ValueError(f"Unsupported file format: {path.suffix}")

        suffix = path.suffix.lower()

        if suffix in {".xlsx", ".xls"}:
            df, red_font_rows = self._load_excel(path, sheet_name, header_row)
            metadata["format"] = "excel"
            metadata["sheet_name"] = sheet_name
        elif suffix == ".csv":
            df = self._load_delimited(path, header_row, sep=",")
            metadata["format"] = "csv"
        elif suffix in {".tsv", ".txt"}:
            df = self._load_delimited(path, header_row, sep="\t")
            metadata["format"] = "tsv"
        elif suffix == ".parquet":
            metadata["format"] = "parquet"
            try:
                df, store_meta = IntermediateStore.load(path)
                metadata.update(store_meta)
                red_font_rows = set(store_meta.get("red_font_rows", []))
            except Exception as exc:
                logger.warning("Intermediate store load failed, falling back to legacy parquet loader: %s", exc)
                df = pd.read_parquet(path)
                meta = self._load_parquet_meta(path)
                if meta:
                    metadata.update(meta)
                    red_font_rows = set(meta.get("red_font_rows", []))
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        metadata["shape"] = df.shape
        metadata["columns"] = list(df.columns)
        if "red_font_rows" not in metadata:
            metadata["red_font_rows"] = sorted(red_font_rows)
        else:
            metadata["red_font_rows"] = sorted(set(metadata.get("red_font_rows", [])))

        return df, metadata

    @staticmethod
    def _load_excel(
        file_path: Path,
        sheet_name: str | int | None = 0,
        header_row: int = 0,
    ) -> tuple[pd.DataFrame, set]:
        """Load data from Excel file with formatting extraction.

        Returns:
            Tuple of (DataFrame, set of red-font row indices).
        """
        return InputReader.load_excel(file_path, sheet_name=sheet_name, header_row=header_row)

    def save_data(
        self,
        df: pd.DataFrame,
        file_path: str | Path,
        sheet_name: str = "Sheet1",
        index: bool = False,
        highlight_rows: set | None = None,
        blue_font_cells: list | None = None,
        red_font_rows: set | None = None,
        extra_sheets: dict | None = None,
        save_parquet_cache: bool = False,
    ) -> Path:
        """
        Save data to a file.

        Args:
            df: DataFrame to save
            file_path: Output file path
            sheet_name: Sheet name for Excel files
            index: Whether to include DataFrame index
            highlight_rows: Set of row indices to highlight with yellow
            blue_font_cells: List of (row, col) tuples for blue font cells

        Returns:
            Path to the saved file
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix in {".xlsx", ".xls"}:
            self._save_excel(
                df,
                path,
                sheet_name,
                index,
                highlight_rows,
                blue_font_cells,
                red_font_rows,
                extra_sheets=extra_sheets,
            )
            if save_parquet_cache:
                try:
                    self._save_parquet_cache(
                        df,
                        path.with_suffix(".parquet"),
                        highlight_rows=highlight_rows,
                        blue_font_cells=blue_font_cells,
                        red_font_rows=red_font_rows,
                    )
                except Exception as exc:
                    logger.warning("Parquet cache save failed (non-fatal): %s", exc)
        elif suffix == ".csv":
            self._output_writer.save_delimited(df, path, index=index, sep=",")
        elif suffix in {".tsv", ".txt"}:
            self._output_writer.save_delimited(df, path, index=index, sep="\t")
        elif suffix == ".parquet":
            self._output_writer.save_parquet(
                df,
                path,
                index=index,
                highlight_rows=highlight_rows,
                blue_font_cells=blue_font_cells,
                red_font_rows=red_font_rows,
            )
        else:
            # Default to Excel format
            path = path.with_suffix(".xlsx")
            self._save_excel(df, path, sheet_name, index, highlight_rows, blue_font_cells, red_font_rows)

        return path

    def _save_excel(
        self,
        df: pd.DataFrame,
        file_path: Path,
        sheet_name: str = "Sheet1",
        index: bool = False,
        highlight_rows: set | None = None,
        blue_font_cells: list | None = None,
        red_font_rows: set | None = None,
        extra_sheets: dict | None = None,
    ) -> None:
        """Save DataFrame to Excel with optional formatting."""
        self._excel_writer.save(
            df,
            file_path,
            sheet_name=sheet_name,
            index=index,
            highlight_rows=highlight_rows,
            blue_font_cells=blue_font_cells,
            red_font_rows=red_font_rows,
            extra_sheets=extra_sheets,
        )

    @staticmethod
    def generate_output_path(
        input_path: str | Path,
        suffix: str = "_processed",
        output_dir: str | Path | None = None,
        add_timestamp: bool = True,
    ) -> Path:
        """
        Generate an output file path based on input path.

        Args:
            input_path: Original input file path
            suffix: Suffix to add before file extension
            output_dir: Output directory (defaults to input file directory)
            add_timestamp: Whether to add timestamp to filename

        Returns:
            Generated output path
        """
        input_path = Path(input_path)
        stem = input_path.stem

        if add_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{stem}{suffix}_{timestamp}{input_path.suffix}"
        else:
            new_name = f"{stem}{suffix}{input_path.suffix}"

        if output_dir:
            output_path = Path(output_dir) / new_name
        else:
            output_path = input_path.parent / new_name

        return output_path

    @staticmethod
    def _parquet_meta_path(parquet_path: Path) -> Path:
        return ParquetCacheStore.meta_path(parquet_path)

    def _save_parquet_cache(
        self,
        df: pd.DataFrame,
        parquet_path: Path,
        highlight_rows: set | None = None,
        blue_font_cells: list | None = None,
        red_font_rows: set | None = None,
    ) -> None:
        """Save a parquet cache with metadata sidecar for formatting."""
        self._parquet_cache_store.save_cache(
            df,
            parquet_path,
            highlight_rows=highlight_rows,
            blue_font_cells=blue_font_cells,
            red_font_rows=red_font_rows,
        )

    def _load_parquet_meta(self, parquet_path: Path) -> dict | None:
        """Load parquet metadata sidecar if it exists."""
        return self._parquet_cache_store.load_meta(parquet_path)

    def _resolve_parquet_cache(self, excel_path: Path) -> Path | None:
        """Return parquet cache if it exists and is newer than Excel."""
        return self._parquet_cache_store.resolve_cache(excel_path)

    @staticmethod
    def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
        """Backward-compatible wrapper around the shared parquet normalizer."""
        return normalize_dataframe_for_parquet(df)

    @staticmethod
    def _load_delimited(path: Path, header_row: int, sep: str) -> pd.DataFrame:
        """Load CSV/TSV using pyarrow engine if available."""
        engine = "pyarrow" if importlib.util.find_spec("pyarrow") is not None else None

        if engine:
            try:
                return pd.read_csv(path, header=header_row, sep=sep, engine=engine)
            except Exception as exc:
                logger.debug(
                    "pyarrow delimited parse failed for %s; falling back to default parser: %s",
                    path,
                    exc,
                )
        return pd.read_csv(path, header=header_row, sep=sep)


def parse_mz_rt_string(value: str) -> tuple[float | None, float | None]:
    """
    Parse a combined m/z and RT string (e.g., "123.456/1.23").

    Args:
        value: String in format "mz/rt"

    Returns:
        Tuple of (mz, rt) as floats, or (None, None) if parsing fails
    """
    try:
        parts = str(value).split("/")
        if len(parts) == 2:
            mz = float(parts[0].strip())
            rt = float(parts[1].strip())
            return mz, rt
    except (ValueError, AttributeError):
        pass
    return None, None


def format_mz_rt_string(mz: float, rt: float, mz_decimals: int = 4, rt_decimals: int = 2) -> str:
    """
    Format m/z and RT values as a combined string.

    Args:
        mz: m/z value
        rt: RT value
        mz_decimals: Decimal places for m/z
        rt_decimals: Decimal places for RT

    Returns:
        Formatted string in "mz/rt" format
    """
    return f"{mz:.{mz_decimals}f}/{rt:.{rt_decimals}f}"
