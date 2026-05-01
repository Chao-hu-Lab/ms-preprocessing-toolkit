"""
Main entry point for MS Preprocessing Toolkit.

This module provides the main entry point for running the application
either as a GUI or from the command line.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ms_preprocessing.config import list_pipeline_profiles
from ms_preprocessing.workflow.parameter_resolver import (
    STEP2_XIC_REQUIRED_MESSAGE,
    ParameterResolver,
    WorkflowValidationService,
    legacy_step2_cli_flags,
)


def _legacy_step2_cli_flags(args) -> list[str]:
    return legacy_step2_cli_flags(args)


def _collect_cli_validation_warnings(step: str, resolved: dict) -> list:
    return WorkflowValidationService().collect(step, resolved)


def _resolve_cli_step_parameters(args):
    """Resolve CLI step parameters from the selected profile plus explicit overrides."""
    return ParameterResolver.from_cli_args(args)


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
        choices=list_pipeline_profiles(),
        default="default",
        help="Integrated Step 1-4 parameter profile (default: default)",
    )

    parser.add_argument(
        "--profile-file",
        type=str,
        default=None,
        help="Explicit YAML Step 1-4 profile file path (overrides --profile)",
    )

    parser.add_argument(
        "--mz-tol",
        type=float,
        default=None,
        help="Step 3 m/z tolerance in ppm (overrides profile value)",
    )

    parser.add_argument(
        "--xic-results-file",
        type=str,
        help="XIC Extractor results workbook for Step 2 (.xlsx)",
    )

    parser.add_argument(
        "--istd-mz",
        type=str,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--istd-record-file",
        type=str,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--istd-record-date",
        type=str,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--rt-tol",
        type=float,
        default=None,
        help="Step 3 RT tolerance in minutes (overrides profile value)",
    )

    parser.add_argument(
        "--merge-mode",
        type=str,
        choices=["per_sample_max", "fill_gaps"],
        default=None,
        help="Step 3 duplicate merge policy (overrides profile value)",
    )

    parser.add_argument(
        "--enable-degeneracy-annotation",
        action="store_true",
        help="Enable Step 3 degeneracy/adduct annotation without removing matched features",
    )

    parser.add_argument(
        "--degeneracy-ppm-tol",
        type=float,
        default=None,
        help="m/z tolerance in ppm for Step 3 degeneracy annotation",
    )

    parser.add_argument(
        "--degeneracy-rt-tol",
        type=float,
        default=None,
        help="RT tolerance in minutes for Step 3 degeneracy annotation",
    )

    parser.add_argument(
        "--degeneracy-corr-threshold",
        type=float,
        default=None,
        help="Minimum Pearson correlation for Step 3 degeneracy annotation",
    )

    parser.add_argument(
        "--degeneracy-min-corr-points",
        type=int,
        default=None,
        help="Minimum shared positive samples required to compute Step 3 degeneracy correlation",
    )

    parser.add_argument(
        "--degeneracy-adduct-table-file",
        type=str,
        default=None,
        help="Optional custom adduct table file for Step 3 degeneracy annotation",
    )

    parser.add_argument(
        "--bg-threshold",
        type=float,
        default=None,
        help="Stable detection-rate threshold for feature filtering (overrides profile value)",
    )

    parser.add_argument(
        "--intensity-fc-threshold",
        type=float,
        default=None,
        help="Intensity fold-change threshold for feature filtering (overrides profile value)",
    )

    parser.add_argument(
        "--ratio-rescue-threshold",
        type=float,
        default=None,
        help="Detection-rate max/min ratio rescue threshold for feature filtering (overrides profile value)",
    )

    parser.add_argument(
        "--disable-ratio-rescue",
        action="store_true",
        help="Disable Step 4 detection-rate ratio rescue",
    )

    parser.add_argument(
        "--high-det-thresh",
        type=float,
        default=None,
        help="MNAR present-group detection-rate lower bound (0-1, overrides profile value, default 0.8)",
    )

    parser.add_argument(
        "--low-det-thresh",
        type=float,
        default=None,
        help="MNAR absent-group detection-rate upper bound (0-1, overrides profile value, default 0.2)",
    )

    parser.add_argument(
        "--qc-ratio-threshold",
        type=float,
        default=None,
        help="Minimum QC detection rate to keep a feature (overrides profile value)",
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

    legacy_flags = _legacy_step2_cli_flags(args)
    if legacy_flags:
        print(
            f"Error: {STEP2_XIC_REQUIRED_MESSAGE} "
            f"Unsupported legacy option(s): {', '.join(legacy_flags)}."
        )
        return 2

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

    from ms_preprocessing.config.settings import Settings
    from ms_preprocessing.pipeline_validation import (
        format_validation_warnings,
        has_blocking_warnings,
    )
    import ms_preprocessing.utils.file_handler as file_handler_module
    from ms_preprocessing.workflow.export_service import ExportService
    from ms_preprocessing.workflow.input_loader import InputLoader
    from ms_preprocessing.workflow.pipeline_session import PipelineSession
    from ms_preprocessing.workflow.workflow_runner import WorkflowRunner

    try:
        step = args.step
        resolved = _resolve_cli_step_parameters(args)
        validation_warnings = _collect_cli_validation_warnings(step, resolved)
        if validation_warnings:
            validation_message = format_validation_warnings(validation_warnings)
            if has_blocking_warnings(validation_warnings):
                print(f"Validation blocked CLI run:\n{validation_message}")
                return 1
            print(f"Validation warning before CLI run:\n{validation_message}")

        print(f"Loading: {input_path}")
        project_root = Path(__file__).resolve().parents[2]
        handler = file_handler_module.FileHandler()
        session = PipelineSession(
            output_dir=project_root / "OUTPUT",
            source_file=input_path,
            intermediate_dir=Settings.get_parquet_cache_root() / "cli-intermediate",
        )
        loaded = InputLoader(file_handler=handler).load(input_path, session=session)
        df = loaded.data
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

        result = WorkflowRunner(file_handler=handler).run(
            df,
            step=step,
            resolved_parameters=resolved,
            session=session,
            persist_intermediate=bool(step == "all" and args.persist_intermediate),
            log_callback=print,
        )
        if not result.success or result.data is None:
            print(f"Error: {result.message or 'Processing failed'}")
            return 1

        output_path = Path(args.output) if args.output else None
        target_path = ExportService(file_handler=handler).export_final(
            result.data,
            output_path=output_path,
            input_path=input_path,
            step=step,
            session=session,
            export_deleted_feature=bool(args.export_deleted_feature),
        )
        print(f"Saving to: {target_path}")
        print("Done!")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
