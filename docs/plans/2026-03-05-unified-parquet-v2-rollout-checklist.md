# Unified Parquet V2 Rollout Checklist

Date: 2026-03-05
Status: Active rollout checklist

## 1. Release Scope

- Step1-4 intermediate format = parquet
- final export = xlsx; downstream handoff is manual
- Step4 zero-as-missing default behavior

## 2. Pre-Release Checks

- Confirm `pytest tests/test_integration_parquet_pipeline.py -v` passes.
- Confirm `pytest tests/test_final_export_handoff.py -v` passes.
- Confirm `pytest tests/test_feature_filter.py -k imputation -v` passes.
- Confirm benchmark warm path is faster than cold path on the full dataset.

## 3. Rollout Steps

- Deploy toolkit and core branches together (same unified-parquet-v2 change window).
- Run CLI end-to-end: `python main.py --no-gui --input <full.xlsx> --method-file <method.docx> --istd-record-file <istd.xlsx> --mz-tol 20 --rt-tol 1.5 --step all`.
- Verify output schema parity and confirm the exported xlsx is ready for manual downstream use.

## 4. Rollback Checklist

- Disable parquet intermediate chaining in runtime orchestration (CLI and GUI).
- Force intermediate handoff back to xlsx while preserving final export contract.
- Re-run full dataset verification and compare with last known stable release outputs.

## 5. Troubleshooting Checklist

- If downstream import fails: verify final xlsx materialization exists and is the file handed to the downstream tool.
- If metadata marks are missing after reload: inspect `.parquet.meta.json` sidecar presence and content.
- If warm run is not faster: verify cache hit path and compare `load_s` between cold/warm runs.
- If Step4 residual zero values appear: re-check imputation stats (`cells_imputed_from_zero`) and affected sample/QC columns.

## 6. Conservative I/O Go/No-Go Gate

- go/no-go baseline (legacy method total): `1497.067` seconds.
- Gate A (must pass): optimized total `<= 1497.067` seconds.
- Gate B (target): optimized total `<= 1420.0` seconds.
- If Gate A fails, stop rollout and execute rollback checklist.
