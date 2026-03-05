"""
Main entry point for MS Preprocessing Toolkit.

This module provides the main entry point for running the application
either as a GUI or from the command line.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MS Preprocessing Toolkit - Mass Spectrometry Data Preprocessing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run GUI
  ms-preprocessing

  # Process file from command line
  ms-preprocessing --input data.xlsx --output processed.xlsx

  # Run specific step only
  ms-preprocessing --input data.xlsx --step duplicate-removal --mz-tol 20 --rt-tol 1.0
        """,
    )

    parser.add_argument(
        "--input", "-i",
        type=str,
        help="Input file path (Excel, CSV, or TSV)",
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path",
    )

    parser.add_argument(
        "--method-file",
        type=str,
        help="Method/injection sequence file path (.docx)",
    )

    parser.add_argument(
        "--step",
        type=str,
        choices=["organize", "istd", "duplicate-removal", "filter", "all"],
        default="all",
        help="Processing step to run (default: all)",
    )

    parser.add_argument(
        "--mz-tol",
        type=float,
        default=20.0,
        help="m/z tolerance in ppm (default: 20)",
    )

    parser.add_argument(
        "--istd-mz",
        type=str,
        help="Comma-separated ISTD m/z list (e.g., 261.1273,245.1324)",
    )

    parser.add_argument(
        "--istd-record-file",
        type=str,
        help="ISTD record Excel file path",
    )

    parser.add_argument(
        "--istd-record-date",
        type=str,
        help="ISTD record target date (YYYYMMDD)",
    )

    parser.add_argument(
        "--rt-tol",
        type=float,
        default=1.0,
        help="RT tolerance in minutes (default: 1.0)",
    )

    parser.add_argument(
        "--bg-threshold",
        type=float,
        default=0.33,
        help="Background threshold for feature filtering (default: 0.33)",
    )

    parser.add_argument(
        "--skew-threshold",
        type=float,
        default=0.66,
        help="Skew threshold for feature filtering (default: 0.66)",
    )

    parser.add_argument(
        "--diff-threshold",
        type=float,
        default=0.30,
        help="Difference threshold for feature filtering (default: 0.30)",
    )

    parser.add_argument(
        "--qc-ratio-threshold",
        type=float,
        default=0.0,
        help="Minimum QC_ratio to keep a feature (default: 0.0, legacy mode)",
    )

    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run in command-line mode without GUI",
    )

    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version information",
    )

    args = parser.parse_args()

    # Show version
    if args.version:
        from ms_preprocessing import __version__
        print(f"MS Preprocessing Toolkit v{__version__}")
        return 0

    # Command-line mode
    if args.no_gui or args.input:
        return run_cli(args)

    # GUI mode
    return run_gui()


def run_gui():
    """Run the GUI application."""
    try:
        from ms_preprocessing.gui.main_window import MainWindow

        app = MainWindow()
        app.mainloop()
        return 0

    except ImportError as e:
        print(f"Error: Could not import GUI components: {e}")
        print("Make sure customtkinter is installed: pip install customtkinter")
        return 1


def run_cli(args):
    """Run in command-line mode."""
    if not args.input:
        print("Error: --input is required in command-line mode")
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    # Import processing modules
    from ms_core.utils.file_handler import FileHandler
    from ms_core.preprocessing.data_organizer import DataOrganizer
    from ms_core.preprocessing.istd_marker import ISTDMarker
    from ms_core.preprocessing.duplicate_remover import DuplicateRemover
    from ms_core.preprocessing.ms_quality_filter import FeatureFilter
    from ms_preprocessing.utils.perf import take_snapshot, format_perf_delta
    from ms_core.preprocessing.settings import Settings

    def _compact_stats(stats: dict) -> dict:
        compact = {}
        for key, value in (stats or {}).items():
            if isinstance(value, list) and len(value) > 20:
                compact[key] = f"[{len(value)} items]"
            else:
                compact[key] = value
        return compact

    try:
        # Load data
        print(f"Loading: {input_path}")
        handler = FileHandler()
        df, metadata = handler.load_data(input_path)
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
        red_font_rows = set(metadata.get("red_font_rows", []))
        protected_rows = set(metadata.get("protected_rows") or metadata.get("red_font_rows") or [])
        blue_font_cells = []
        sample_info_df = None
        deleted_feature_df = None
        preserved_sheets = {}

        # Preserve auxiliary sheets (e.g., SampleInfo) when running Step2+ on prior outputs.
        if input_path.suffix.lower() in {".xlsx", ".xls"}:
            try:
                import pandas as pd

                xls = pd.ExcelFile(input_path, engine="openpyxl")
                sheet_names = list(xls.sheet_names)
                raw_sheet_name = "RawIntensity" if "RawIntensity" in sheet_names else None
                if raw_sheet_name is None:
                    sheet_ref = metadata.get("sheet_name")
                    if isinstance(sheet_ref, str) and sheet_ref in sheet_names:
                        raw_sheet_name = sheet_ref
                    elif isinstance(sheet_ref, int) and 0 <= sheet_ref < len(sheet_names):
                        raw_sheet_name = sheet_names[sheet_ref]
                    elif sheet_names:
                        raw_sheet_name = sheet_names[0]

                for sheet in sheet_names:
                    if sheet == raw_sheet_name:
                        continue
                    preserved_sheets[sheet] = pd.read_excel(input_path, sheet_name=sheet, engine="openpyxl")

                if "SampleInfo" in preserved_sheets:
                    sample_info_df = preserved_sheets.pop("SampleInfo")
                if "deleted_feature" in preserved_sheets:
                    deleted_feature_df = preserved_sheets.pop("deleted_feature")
            except Exception:
                # Continue processing even if auxiliary-sheet preservation fails.
                preserved_sheets = {}

        # Run requested steps
        step = args.step
        project_root = Path(__file__).resolve().parents[2]
        intermediate_dir = project_root / "OUTPUT" / ".cli_intermediate"
        last_parquet_handoff: Path | None = None
        if step == "all":
            intermediate_dir.mkdir(parents=True, exist_ok=True)

        def _persist_parquet_handoff(step_index: int) -> None:
            """Persist current state to parquet and reload for next step handoff."""
            nonlocal df, red_font_rows, protected_rows, blue_font_cells, last_parquet_handoff

            if step != "all":
                return

            stem = input_path.stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            handoff_path = intermediate_dir / f"_CLI_STEP{step_index}_{stem}_{timestamp}.parquet"

            handler.save_data(
                df,
                handoff_path,
                red_font_rows=red_font_rows,
                blue_font_cells=blue_font_cells,
                save_parquet_cache=False,
            )
            last_parquet_handoff = handoff_path
            df, handoff_meta = handler.load_data(handoff_path)
            red_font_rows = set(handoff_meta.get("red_font_rows", red_font_rows))
            protected_rows = set(
                handoff_meta.get("protected_rows") or handoff_meta.get("red_font_rows") or protected_rows
            )
            blue_font_cells = handoff_meta.get("blue_font_cells", blue_font_cells)

        if step in ["organize", "all"]:
            print("Step 1: Data Organization...")
            perf_start = take_snapshot()
            organizer = DataOrganizer()
            result = organizer.process(df, method_file=args.method_file)
            if result.success:
                df = result.data
                sample_info_df = result.metadata.get("sample_info")
                perf_end = take_snapshot()
                print(f"  Perf: {format_perf_delta(perf_start, perf_end)}")
                print(f"  Done: {_compact_stats(result.statistics)}")
                _persist_parquet_handoff(1)
            else:
                print(f"  Error: {result.message}")
                return 1

        if step in ["istd", "all"]:
            print("Step 2: ISTD Marking...")
            perf_start = take_snapshot()
            marker = ISTDMarker()
            marker.config.default_ppm_tolerance = args.mz_tol
            marker.config.default_rt_tolerance = args.rt_tol
            istd_mz_list = None
            if args.istd_mz:
                try:
                    istd_mz_list = [float(x.strip()) for x in args.istd_mz.split(",") if x.strip()]
                except ValueError:
                    print("  Error: Invalid --istd-mz format")
                    return 1

            result = marker.process(
                df,
                istd_mz_list=istd_mz_list,
                istd_record_file=Path(args.istd_record_file) if args.istd_record_file else None,
                istd_record_date=args.istd_record_date,
            )
            if result.success:
                df = result.data
                red_font_rows = set(result.metadata.get("red_font_rows", []))
                protected_rows = set(
                    result.metadata.get("protected_rows") or result.metadata.get("istd_rows") or red_font_rows
                )
                perf_end = take_snapshot()
                print(f"  Perf: {format_perf_delta(perf_start, perf_end)}")
                if result.metadata.get("warning"):
                    print(f"  Warning: {result.metadata.get('warning')}")
                print(f"  Done: {_compact_stats(result.statistics)}")
                _persist_parquet_handoff(2)
            else:
                print(f"  Error: {result.message}")
                return 1

        if step in ["duplicate-removal", "all"]:
            print("Step 3: Duplicate Removal...")
            perf_start = take_snapshot()
            remover = DuplicateRemover()
            result = remover.process(
                df,
                mz_tolerance_ppm=args.mz_tol,
                rt_tolerance=args.rt_tol,
                protected_rows=protected_rows,
            )
            if result.success:
                df = result.data
                red_font_rows = set(result.metadata.get("red_font_rows", red_font_rows))
                protected_rows = set(result.metadata.get("protected_rows") or red_font_rows)
                perf_end = take_snapshot()
                print(f"  Perf: {format_perf_delta(perf_start, perf_end)}")
                print(f"  Done: {_compact_stats(result.statistics)}")
                _persist_parquet_handoff(3)
            else:
                print(f"  Error: {result.message}")
                return 1

        if step in ["filter", "all"]:
            print("Step 4: Feature Filtering...")
            perf_start = take_snapshot()
            filter_proc = FeatureFilter()
            result = filter_proc.process(
                df,
                background_threshold=args.bg_threshold,
                skew_threshold=args.skew_threshold,
                diff_threshold=args.diff_threshold,
                qc_ratio_threshold=args.qc_ratio_threshold,
                protected_rows=protected_rows,
            )
            if result.success:
                df = result.data
                red_font_rows = set(result.metadata.get("red_font_rows", red_font_rows))
                protected_rows = set(result.metadata.get("protected_rows") or red_font_rows)
                blue_font_cells = result.metadata.get("blue_font_cells", blue_font_cells)
                deleted_features = result.metadata.get("deleted_features", [])
                if deleted_features:
                    try:
                        import pandas as pd
                        # Support duplicate column labels by building from row values.
                        deleted_columns = list(deleted_features[0].index)
                        deleted_values = [row.tolist() for row in deleted_features]
                        deleted_feature_df = pd.DataFrame(deleted_values, columns=deleted_columns)
                    except Exception:
                        deleted_feature_df = None
                perf_end = take_snapshot()
                print(f"  Perf: {format_perf_delta(perf_start, perf_end)}")
                print(f"  Done: {_compact_stats(result.statistics)}")
                _persist_parquet_handoff(4)
            else:
                print(f"  Error: {result.message}")
                return 1

        # Save output
        if args.output:
            output_path = Path(args.output)
            suffix = output_path.suffix.lower()
            if suffix == "":
                output_path = output_path.with_suffix(".xlsx")
            elif suffix not in {".xlsx", ".parquet"}:
                output_path = output_path.with_suffix(".xlsx")
        else:
            output_dir = project_root / "OUTPUT"
            output_dir.mkdir(parents=True, exist_ok=True)
            stem = input_path.stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_suffix = ".xlsx"

            step_prefix_map = {
                "organize": "STEP1",
                "istd": "STEP2",
                "duplicate-removal": "STEP3",
                "filter": "STEP4",
                "all": "ALL",
            }
            step_prefix = step_prefix_map.get(step, "STEP1")

            if step_prefix == "ALL":
                filename = f"{step_prefix}_{stem}{output_suffix}"
                output_path = output_dir / filename
                if output_path.exists():
                    filename = f"{step_prefix}_{stem}_{timestamp}{output_suffix}"
                    output_path = output_dir / filename
            else:
                filename = f"{step_prefix}_{stem}_{timestamp}{output_suffix}"
                output_path = output_dir / filename

        # Explicitly materialize final xlsx from the latest parquet intermediate state.
        if (
            step == "all"
            and output_path.suffix.lower() == ".xlsx"
            and last_parquet_handoff is not None
        ):
            df, materialized_meta = handler.load_data(last_parquet_handoff)
            red_font_rows = set(materialized_meta.get("red_font_rows", red_font_rows))
            protected_rows = set(
                materialized_meta.get("protected_rows") or materialized_meta.get("red_font_rows") or protected_rows
            )
            blue_font_cells = materialized_meta.get("blue_font_cells", blue_font_cells)

        extra_sheets = {}
        if preserved_sheets:
            extra_sheets.update(preserved_sheets)
        if sample_info_df is not None:
            extra_sheets["SampleInfo"] = sample_info_df
        if deleted_feature_df is not None and not deleted_feature_df.empty:
            extra_sheets["deleted_feature"] = deleted_feature_df

        print(f"Saving to: {output_path}")
        handler.save_data(
            df,
            output_path,
            sheet_name="RawIntensity",
            red_font_rows=red_font_rows,
            blue_font_cells=blue_font_cells,
            extra_sheets=extra_sheets or None,
            save_parquet_cache=Settings.SAVE_PARQUET_CACHE,
        )
        print("Done!")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
