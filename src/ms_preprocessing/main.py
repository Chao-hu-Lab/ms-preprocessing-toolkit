"""
Main entry point for MS Preprocessing Toolkit.

This module provides the main entry point for running the application
either as a GUI or from the command line.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime


def _resolve_cli_step_parameters(args):
    """Resolve CLI step parameters from the selected profile plus explicit overrides."""
    from ms_preprocessing.config import get_pipeline_profile

    profile = get_pipeline_profile(args.profile)
    step1 = dict(profile["step1"])
    step2 = dict(profile["step2"])
    step3 = dict(profile["step3"])
    step4 = dict(profile["step4"])

    return {
        "step1": {
            "method_file": args.method_file if args.method_file is not None else step1.get("method_file"),
        },
        "step2": {
            "istd_mz_list": (
                [float(x.strip()) for x in args.istd_mz.split(",") if x.strip()]
                if args.istd_mz
                else step2.get("istd_mz_list")
            ),
            "istd_record_file": (
                args.istd_record_file if args.istd_record_file is not None else step2.get("istd_record_file")
            ),
            "istd_record_date": (
                args.istd_record_date if args.istd_record_date is not None else step2.get("istd_record_date")
            ),
            "ppm_tolerance": args.mz_tol if args.mz_tol is not None else step2.get("ppm_tolerance"),
            "rt_tolerance": args.rt_tol if args.rt_tol is not None else step2.get("rt_tolerance"),
        },
        "step3": {
            "mz_tolerance_ppm": args.mz_tol if args.mz_tol is not None else step3.get("mz_tolerance_ppm"),
            "rt_tolerance": args.rt_tol if args.rt_tol is not None else step3.get("rt_tolerance"),
            "preserve_red_font": step3.get("preserve_red_font"),
            "top_n": step3.get("top_n"),
        },
        "step4": {
            "signal_threshold": step4.get("signal_threshold"),
            "background_threshold": (
                args.bg_threshold if args.bg_threshold is not None else step4.get("background_threshold")
            ),
            "high_det_thresh": (
                args.high_det_thresh if args.high_det_thresh is not None else step4.get("high_det_thresh")
            ),
            "low_det_thresh": (
                args.low_det_thresh if args.low_det_thresh is not None else step4.get("low_det_thresh")
            ),
            "intensity_fc_threshold": (
                args.intensity_fc_threshold
                if args.intensity_fc_threshold is not None
                else step4.get("intensity_fc_threshold")
            ),
            "qc_ratio_threshold": (
                args.qc_ratio_threshold if args.qc_ratio_threshold is not None else step4.get("qc_ratio_threshold")
            ),
            "enable_background_threshold": step4.get("enable_background_threshold", True),
            "enable_qc_ratio_threshold": step4.get("enable_qc_ratio_threshold", True),
            "enable_intensity_fc_threshold": step4.get("enable_intensity_fc_threshold", False),
        },
    }


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
        "--profile",
        type=str,
        choices=["loose", "default", "strict"],
        default="default",
        help="Integrated Step 1-4 parameter profile (default: default)",
    )

    parser.add_argument(
        "--mz-tol",
        type=float,
        default=None,
        help="m/z tolerance in ppm (overrides Step 2/3 profile values)",
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
        default=None,
        help="RT tolerance in minutes (overrides Step 2/3 profile values)",
    )

    parser.add_argument(
        "--bg-threshold",
        type=float,
        default=None,
        help="Background threshold for feature filtering (overrides profile value)",
    )

    parser.add_argument(
        "--intensity-fc-threshold",
        type=float,
        default=None,
        help="Intensity fold-change threshold for feature filtering (overrides profile value)",
    )

    parser.add_argument(
        "--high-det-thresh",
        type=float,
        default=None,
        help="MNAR high detection rate threshold (0-1, overrides profile value, default 0.8)",
    )

    parser.add_argument(
        "--low-det-thresh",
        type=float,
        default=None,
        help="MNAR low detection rate threshold (0-1, overrides profile value, default 0.2)",
    )

    parser.add_argument(
        "--qc-ratio-threshold",
        type=float,
        default=None,
        help="Minimum QC_ratio to keep a feature (overrides profile value)",
    )

    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run in command-line mode without GUI",
    )

    parser.add_argument(
        "--persist-intermediate",
        action="store_true",
        help="Persist step snapshots to machine-local cache during --step all",
    )

    parser.add_argument(
        "--export-deleted-feature",
        action="store_true",
        help="Include deleted_feature worksheet in final Excel export",
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
    from ms_preprocessing.adapters import (
        data_organizer as _adapter_do,
        duplicate_remover as _adapter_dr,
        feature_filter as _adapter_ff,
        istd_marker as _adapter_istd,
    )
    from ms_preprocessing.config.settings import Settings
    from ms_preprocessing.gui.pipeline_session import PipelineSession
    from ms_preprocessing.utils.file_handler import FileHandler
    from ms_preprocessing.utils.perf import take_snapshot, format_perf_delta

    def _compact_stats(stats: dict) -> dict:
        compact = {}
        for key, value in (stats or {}).items():
            if isinstance(value, list) and len(value) > 20:
                compact[key] = f"[{len(value)} items]"
            else:
                compact[key] = value
        return compact

    try:
        resolved = _resolve_cli_step_parameters(args)

        # Load data
        print(f"Loading: {input_path}")
        handler = FileHandler()
        df, metadata = handler.load_data(input_path)
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
        session = PipelineSession(
            output_dir=Settings.get_parquet_cache_root() / "cli",
            source_file=input_path,
        )
        session.update_context_from_metadata(
            {
                "red_font_rows": metadata.get("red_font_rows", []),
                "protected_rows": metadata.get("protected_rows") or metadata.get("red_font_rows") or [],
            }
        )
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
                    session.update_context_from_metadata({"sample_info": preserved_sheets.pop("SampleInfo")})
                if "deleted_feature" in preserved_sheets:
                    session.update_context_from_metadata(
                        {"deleted_feature_df": preserved_sheets.pop("deleted_feature")}
                    )
            except Exception:
                # Continue processing even if auxiliary-sheet preservation fails.
                preserved_sheets = {}

        # Run requested steps
        step = args.step
        project_root = Path(__file__).resolve().parents[2]
        intermediate_dir: Path | None = None
        if step == "all" and args.persist_intermediate:
            intermediate_dir = Settings.get_parquet_cache_root() / "cli-intermediate"
            intermediate_dir.mkdir(parents=True, exist_ok=True)

        def _persist_parquet_handoff(step_index: int) -> None:
            """Persist current state to parquet for optional diagnostics."""
            nonlocal df

            if step != "all" or not args.persist_intermediate or intermediate_dir is None:
                return

            stem = input_path.stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            handoff_path = intermediate_dir / f"_CLI_STEP{step_index}_{stem}_{timestamp}.parquet"

            handler.save_data(
                df,
                handoff_path,
                red_font_rows=session.metadata.red_font_rows,
                blue_font_cells=session.metadata.blue_font_cells,
                save_parquet_cache=False,
            )

        if step in ["organize", "all"]:
            print("Step 1: Data Organization...")
            perf_start = take_snapshot()
            session.record_step_parameters(0, dict(resolved["step1"]))
            result = _adapter_do.run_from_df(df, **resolved["step1"])
            if result.success:
                df = result.data
                session.update_from_result(result)
                perf_end = take_snapshot()
                print(f"  Perf: {format_perf_delta(perf_start, perf_end)}")
                print("  Done")
                _persist_parquet_handoff(1)
            else:
                print(f"  Error: {result.error or 'Processing failed'}")
                return 1

        if step in ["istd", "all"]:
            print("Step 2: ISTD Marking...")
            perf_start = take_snapshot()
            if args.istd_mz:
                try:
                    resolved["step2"]["istd_mz_list"] = [
                        float(x.strip()) for x in args.istd_mz.split(",") if x.strip()
                    ]
                except ValueError:
                    print("  Error: Invalid --istd-mz format")
                    return 1

            session.record_step_parameters(
                1,
                dict(resolved["step2"]),
            )
            step2_kwargs = dict(resolved["step2"])
            if step2_kwargs.get("istd_record_file"):
                step2_kwargs["istd_record_file"] = Path(step2_kwargs["istd_record_file"])
            result = _adapter_istd.run_from_df(df, **step2_kwargs)
            if result.success:
                df = result.data
                session.update_from_result(result)
                perf_end = take_snapshot()
                print(f"  Perf: {format_perf_delta(perf_start, perf_end)}")
                print("  Done")
                _persist_parquet_handoff(2)
            else:
                print(f"  Error: {result.error or 'Processing failed'}")
                return 1

        if step in ["duplicate-removal", "all"]:
            print("Step 3: Duplicate Removal...")
            perf_start = take_snapshot()
            step3_params = dict(resolved["step3"])
            step3_params["protected_rows"] = set(session.metadata.protected_rows)
            session.record_step_parameters(2, dict(step3_params))
            result = _adapter_dr.run_from_df(df, **step3_params)
            if result.success:
                df = result.data
                session.update_from_result(result)
                perf_end = take_snapshot()
                print(f"  Perf: {format_perf_delta(perf_start, perf_end)}")
                print("  Done")
                _persist_parquet_handoff(3)
            else:
                print(f"  Error: {result.error or 'Processing failed'}")
                return 1

        if step in ["filter", "all"]:
            print("Step 4: Feature Filtering...")
            perf_start = take_snapshot()
            step4_params = dict(resolved["step4"])
            step4_params["protected_rows"] = set(session.metadata.protected_rows)
            session.record_step_parameters(3, dict(step4_params))
            result = _adapter_ff.run_from_df(df, **step4_params)
            if result.success:
                df = result.data
                session.update_from_result(result)
                perf_end = take_snapshot()
                print(f"  Perf: {format_perf_delta(perf_start, perf_end)}")
                print("  Done")
                _persist_parquet_handoff(4)
            else:
                print(f"  Error: {result.error or 'Processing failed'}")
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

        extra_sheets = {}
        if preserved_sheets:
            extra_sheets.update(preserved_sheets)
        if session.metadata.sample_info is not None:
            extra_sheets["SampleInfo"] = session.metadata.sample_info
        if (
            args.export_deleted_feature
            and session.metadata.deleted_feature_df is not None
            and not session.metadata.deleted_feature_df.empty
        ):
            extra_sheets["deleted_feature"] = session.metadata.deleted_feature_df

        print(f"Saving to: {output_path}")
        handler.save_data(
            df,
            output_path,
            sheet_name="RawIntensity",
            red_font_rows=session.metadata.red_font_rows,
            blue_font_cells=session.metadata.blue_font_cells,
            extra_sheets=extra_sheets or None,
            save_parquet_cache=False,
        )
        print("Done!")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
