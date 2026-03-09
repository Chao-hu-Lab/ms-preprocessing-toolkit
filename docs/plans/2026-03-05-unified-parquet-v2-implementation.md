# Unified Parquet Intermediate Pipeline (Step1-4) V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify Step1-4 intermediate artifacts to parquet (with metadata sidecar), keep final output as xlsx for compatibility, and implement Step4 zero-as-missing imputation (including QC) by default.

**Architecture:** Build a single intermediate storage contract first (`data + metadata`) in `ms-core`, then migrate CLI and GUI to consume that contract so Step chaining no longer depends on xlsx. Keep final export and DNP bridge on xlsx only. Execute tasks in batches with controlled parallelism after shared contract tasks are complete.

**Tech Stack:** Python 3.14, pandas, numpy, openpyxl, pyarrow parquet, pytest, customtkinter, ms-core + ms-preprocessing-toolkit.

---

## Repository Roots

- Toolkit root: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit`
- Core root: `C:/Users/user/Desktop/質譜數據工具箱/ms-core`

## Required Workflow Skills

- `@superpowers:executing-plans` (driver)
- `@superpowers:test-driven-development` (every behavior change)
- `@superpowers:dispatching-parallel-agents` (parallel batch only)
- `@superpowers:requesting-code-review` (batch gates)
- `@superpowers:verification-before-completion` (before any completion claim)
- `@superpowers:finishing-a-development-branch` (endgame)

## Parallelization Map

Sequential-only tasks:
- Task 1, Task 2, Task 3

Parallel-eligible batch (after Task 3):
- Task 4 (CLI parquet chain)
- Task 5 (GUI pipeline + parameter integration)
- Task 6 (Step4 zero-as-missing behavior)

Sequential again:
- Task 7 (DNP bridge/final export integration)
- Task 8 (performance benchmark + regression matrix)
- Task 9 (docs + release notes)

## Branching Rules

- Implement on feature branch only (never `master`/`main` directly).
- Commit at end of each task.
- Run specified verification before each commit.

---

### Task 1: Establish Baseline Performance and Behavioral Fixture

**Files:**
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/scripts/benchmark_pipeline_io.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_pipeline_baseline_contract.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/conftest.py`

**Step 1: Write the failing test**

```python
def test_baseline_contract_records_load_process_save_sections():
    from scripts.benchmark_pipeline_io import run_benchmark
    result = run_benchmark(input_path="dummy.xlsx", dry_run=True)
    assert {"load_s", "step_times", "save_s", "total_s"} <= set(result.keys())
```

**Step 2: Run test to verify it fails**

Run:
`pytest tests/test_pipeline_baseline_contract.py::test_baseline_contract_records_load_process_save_sections -v`

Expected:
- FAIL because benchmark script/function does not exist yet.

**Step 3: Write minimal implementation**

- Implement `run_benchmark(...)` with dry-run structure and explicit timing keys.
- Ensure output schema is stable JSON-serializable dict.

**Step 4: Run test to verify it passes**

Run:
`pytest tests/test_pipeline_baseline_contract.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git add scripts/benchmark_pipeline_io.py tests/test_pipeline_baseline_contract.py tests/conftest.py
git commit -m "test: add baseline pipeline benchmark contract"
```

---

### Task 2: Define Unified Intermediate Storage Contract in ms-core

**Files:**
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-core/src/ms_core/utils/intermediate_store.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-core/src/ms_core/utils/file_handler.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-core/src/ms_core/preprocessing/settings.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests/test_intermediate_store.py`

**Step 1: Write failing tests**

```python
def test_intermediate_store_roundtrip_preserves_metadata():
    # metadata keys must survive save/load:
    # red_font_rows, blue_font_cells, protected_rows, sample_info_ref, deleted_feature_ref
    ...
```

```python
def test_save_parquet_cache_default_enabled():
    from ms_core.preprocessing.settings import Settings
    assert Settings.SAVE_PARQUET_CACHE is True
```

**Step 2: Run tests to verify they fail**

Run:
`pytest C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests/test_intermediate_store.py -v`

Expected:
- FAIL (contract/storage module not implemented yet; default still false).

**Step 3: Write minimal implementation**

- Add `IntermediateStore.save(...)` and `IntermediateStore.load(...)`.
- Store primary data as `.parquet`.
- Store metadata sidecar as `.parquet.meta.json`.
- Set `Settings.SAVE_PARQUET_CACHE = True`.
- Keep legacy fallbacks in `FileHandler`.

**Step 4: Run tests to verify they pass**

Run:
`pytest C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests/test_intermediate_store.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-core add src/ms_core/utils/intermediate_store.py src/ms_core/utils/file_handler.py src/ms_core/preprocessing/settings.py tests/test_intermediate_store.py
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-core commit -m "feat: add unified parquet intermediate store contract"
```

---

### Task 3: Bridge Toolkit to New Intermediate Store API

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/utils/file_handler.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/config/settings.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_intermediate_store_bridge.py`

**Step 1: Write failing test**

```python
def test_toolkit_file_handler_uses_intermediate_store_for_parquet_paths():
    ...
```

**Step 2: Run test to verify it fails**

Run:
`pytest tests/test_intermediate_store_bridge.py -v`

Expected:
- FAIL.

**Step 3: Write minimal implementation**

- Route toolkit file handling to the new ms-core intermediate contract for parquet paths.
- Keep xlsx/csv/tsv behavior intact.

**Step 4: Run test to verify it passes**

Run:
`pytest tests/test_intermediate_store_bridge.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git add src/ms_preprocessing/utils/file_handler.py src/ms_preprocessing/config/settings.py tests/test_intermediate_store_bridge.py
git commit -m "feat: bridge toolkit file handler to unified parquet store"
```

---

### Task 4: Migrate CLI Step Chain to Parquet Intermediates (Parallel Batch A)

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/main.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_cli_parquet_chain.py`

**Step 1: Write failing tests**

```python
def test_cli_step_all_uses_parquet_intermediates_and_final_xlsx():
    ...
```

```python
def test_cli_single_step_filter_accepts_parquet_input():
    ...
```

**Step 2: Run tests to verify they fail**

Run:
`pytest tests/test_cli_parquet_chain.py -v`

Expected:
- FAIL.

**Step 3: Write minimal implementation**

- Step1-4 internal handoff persists/reads parquet.
- Final explicit output remains xlsx unless user requests parquet.

**Step 4: Run tests to verify they pass**

Run:
`pytest tests/test_cli_parquet_chain.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git add src/ms_preprocessing/main.py tests/test_cli_parquet_chain.py
git commit -m "feat: migrate CLI step chaining to parquet intermediates"
```

---

### Task 5: Migrate GUI Pipeline + Parameter Integration (Parallel Batch B)

**Files:**
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/gui/pipeline_session.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/gui/main_window.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/gui/widgets/base_widget.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/gui/widgets/feature_filter_widget.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_gui_pipeline_session.py`

**Step 1: Write failing tests**

```python
def test_gui_pipeline_session_stores_step_outputs_as_parquet_until_final_export():
    ...
```

```python
def test_gui_parameters_are_collected_in_single_pipeline_session_context():
    ...
```

**Step 2: Run tests to verify they fail**

Run:
`pytest tests/test_gui_pipeline_session.py -v`

Expected:
- FAIL.

**Step 3: Write minimal implementation**

- Add `PipelineSession` abstraction for:
  - per-step input/output paths
  - shared parameters/context
  - metadata refs (sample_info/deleted_feature/format marks)
- Route GUI run-all and step-run through this session.

**Step 4: Run tests to verify they pass**

Run:
`pytest tests/test_gui_pipeline_session.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git add src/ms_preprocessing/gui/pipeline_session.py src/ms_preprocessing/gui/main_window.py src/ms_preprocessing/gui/widgets/base_widget.py src/ms_preprocessing/gui/widgets/feature_filter_widget.py tests/test_gui_pipeline_session.py
git commit -m "feat: unify GUI pipeline session and parquet intermediate chain"
```

---

### Task 6: Implement Step4 Zero-As-Missing Imputation (Parallel Batch C)

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-core/src/ms_core/preprocessing/ms_quality_filter.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_feature_filter.py`
- Optional sync mirror: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/core/feature_filter.py`

**Step 1: Write failing tests**

```python
def test_imputation_treats_zero_as_missing_for_group_and_qc_columns():
    ...
```

```python
def test_imputation_stats_split_nan_and_zero_counts():
    ...
```

**Step 2: Run tests to verify they fail**

Run:
`pytest tests/test_feature_filter.py -k "zero_as_missing or imputation_stats_split" -v`

Expected:
- FAIL.

**Step 3: Write minimal implementation**

- Update missing mask to `isna OR (value == 0)` in group and QC blocks.
- Add stats:
  - `cells_imputed_from_nan`
  - `cells_imputed_from_zero`
  - `cells_imputed` remains total.

**Step 4: Run tests to verify they pass**

Run:
`pytest tests/test_feature_filter.py -k "imputation" -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-core add src/ms_core/preprocessing/ms_quality_filter.py
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-core commit -m "feat: treat zero as missing in Step4 imputation"
git add tests/test_feature_filter.py src/ms_preprocessing/core/feature_filter.py
git commit -m "test: cover zero-as-missing Step4 behavior and stats"
```

---

### Task 7: Integrate Final Export and DNP Bridge on xlsx Only

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/gui/main_window.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/main.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_export_dnp_bridge.py`

**Step 1: Write failing tests**

```python
def test_dnp_bridge_always_receives_xlsx_even_when_intermediates_are_parquet():
    ...
```

```python
def test_final_export_materializes_xlsx_from_parquet_intermediate():
    ...
```

**Step 2: Run tests to verify they fail**

Run:
`pytest tests/test_export_dnp_bridge.py -v`

Expected:
- FAIL.

**Step 3: Write minimal implementation**

- Add explicit "materialize final xlsx from last parquet state" operation.
- Ensure DNP export path references only materialized xlsx file.

**Step 4: Run tests to verify they pass**

Run:
`pytest tests/test_export_dnp_bridge.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git add src/ms_preprocessing/gui/main_window.py src/ms_preprocessing/main.py tests/test_export_dnp_bridge.py
git commit -m "feat: lock final export and DNP bridge to xlsx materialization"
```

---

### Task 8: Performance and Regression Matrix Verification

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/scripts/benchmark_pipeline_io.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_integration_parquet_pipeline.py`

**Step 1: Write failing integration test**

```python
def test_parquet_pipeline_preserves_output_schema_and_key_metadata():
    ...
```

**Step 2: Run test to verify it fails**

Run:
`pytest tests/test_integration_parquet_pipeline.py -v`

Expected:
- FAIL.

**Step 3: Write minimal implementation**

- Expand benchmark script for cold/warm runs.
- Add schema+metadata invariants.

**Step 4: Run verification matrix**

Run:
`pytest tests/test_integration_parquet_pipeline.py -v`

Run:
`pytest tests/test_feature_filter.py tests/test_regressions.py tests/test_smoke_guardrails.py -v`

Run:
`python scripts/benchmark_pipeline_io.py --input "C:/Users/user/Desktop/廖老師樣本/drLiao_HNC_Urine.xlsx" --method-file "C:/Users/user/Desktop/廖老師樣本/20250804 廖老師食道癌樣本_中研院分析.docx" --istd-record-file "C:/Users/user/Desktop/NTU cancer/2025台大乳癌組織數據for Jia/20260105中研院台大Breast cancer tissue/20260106 ISDTs record.xlsx" --mz-tol 20 --rt-tol 1.5`

Expected:
- Tests PASS.
- Warm run faster than cold run.

**Step 5: Commit**

```bash
git add scripts/benchmark_pipeline_io.py tests/test_integration_parquet_pipeline.py
git commit -m "test: add integration and benchmark verification for unified parquet pipeline"
```

---

### Task 9: Documentation and Rollout Notes

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/README.md`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/docs/plans/2026-03-04-step4-zero-impute-and-performance-design.md`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/docs/plans/2026-03-05-unified-parquet-v2-rollout-checklist.md`

**Step 1: Write failing documentation check**

```python
def test_docs_reference_unified_parquet_pipeline_and_zero_missing_behavior():
    ...
```

**Step 2: Run test to verify it fails**

Run:
`pytest tests/test_smoke_guardrails.py -k docs -v`

Expected:
- FAIL until docs updated.

**Step 3: Update docs**

- Document:
  - Step1-4 intermediate format = parquet
  - final export/DNP = xlsx
  - Step4 zero-as-missing default behavior
  - rollback and troubleshooting checklist

**Step 4: Run docs check**

Run:
`pytest tests/test_smoke_guardrails.py -k docs -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git add README.md docs/plans/2026-03-04-step4-zero-impute-and-performance-design.md docs/plans/2026-03-05-unified-parquet-v2-rollout-checklist.md
git commit -m "docs: publish unified parquet v2 behavior and rollout checklist"
```

---

## Batch Execution and Review Gates

Batch 1:
- Task 1-3 (sequential)
- Then run `@superpowers:requesting-code-review`

Batch 2:
- Task 4-6 (parallel via `@superpowers:dispatching-parallel-agents`)
- Merge/reconcile conflicts
- Then run `@superpowers:requesting-code-review`

Batch 3:
- Task 7-9 (sequential)
- Final full verification
- Then run `@superpowers:requesting-code-review`

## Final Verification Commands (Must Run Fresh)

Toolkit:
- `pytest tests -v`

Core:
- `pytest C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests -v`

End-to-end sample:
- `python main.py --no-gui --input "C:/Users/user/Desktop/廖老師樣本/drLiao_HNC_Urine.xlsx" --method-file "C:/Users/user/Desktop/廖老師樣本/20250804 廖老師食道癌樣本_中研院分析.docx" --istd-record-file "C:/Users/user/Desktop/NTU cancer/2025台大乳癌組織數據for Jia/20260105中研院台大Breast cancer tissue/20260106 ISDTs record.xlsx" --mz-tol 20 --rt-tol 1.5 --step all`

Required acceptance:
- No regression in output schema and downstream DNP path.
- Step4 confirms zero-as-missing behavior via stats.
- Total runtime improves meaningfully with warm intermediate path.

