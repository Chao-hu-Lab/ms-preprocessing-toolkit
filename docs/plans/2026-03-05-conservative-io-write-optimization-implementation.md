# Conservative I/O Write Optimization (1+2+3+4) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce full `--step all` wall-clock time without risking core pipeline availability by making parquet intermediates/caches optional, fail-open, and hidden from `OUTPUT`.

**Architecture:** Keep core processing chain in memory by default; persist only final `.xlsx` deliverable. Move parquet intermediate/cache artifacts to an internal machine-only cache root. Keep parquet as acceleration/fallback mechanism, never as a hard dependency for successful end-to-end execution.

**Tech Stack:** Python 3.14, pandas/openpyxl/pyarrow, pytest, ms-core + ms-preprocessing-toolkit CLI/GUI.

---

## Repository Roots

- Toolkit root: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit`
- Core root: `C:/Users/user/Desktop/質譜數據工具箱/ms-core`

## Data and Verification Policy

- Fast iteration dataset (subset): `C:/path/to/validation-subset.xlsx`
- Batch-end critical validation dataset (full): `C:/path/to/validation-full.xlsx`
- Performance go/no-go:
  - Baseline old method: `1497.067s` (~24m57s)
  - Current unified-parquet-v2 run: `1763.8s` (~29m24s)
  - **Gate A (must meet):** optimized run `<= 1497.067s`; if not met, keep current behavior.
  - **Gate B (target):** `<= 1420s` (optional stretch).

## Required Workflow Skills

- `@superpowers:executing-plans`
- `@superpowers:test-driven-development`
- `@superpowers:dispatching-parallel-agents` (Batch 2 only)
- `@superpowers:requesting-code-review` (after every batch)
- `@superpowers:verification-before-completion`
- `@superpowers:finishing-a-development-branch`

## Branch / Worktree Rules

- Never implement on `main/master`.
- Use dedicated feature branches:
  - Toolkit: `feature/io-perf-conservative-toolkit` (from current toolkit feature branch)
  - Core: `feature/io-perf-conservative-core` (from current core feature branch)
- Every task must end with a commit hash.
- Batch 2 parallel execution must use isolated worktrees (subagent-safe), example:
  - `.../ms-preprocessing-toolkit/.worktrees/agent-cli-io`
  - `.../ms-preprocessing-toolkit/.worktrees/agent-gui-cache`

---

### Task 1: Add Perf Guardrails and Baseline Contract

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/scripts/benchmark_pipeline_io.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_perf_guardrails.py`

**Step 1: Write failing tests**

```python
def test_perf_contract_contains_io_breakdown_and_gate_fields():
    from scripts.benchmark_pipeline_io import run_benchmark
    result = run_benchmark(input_path="dummy.xlsx", dry_run=True)
    assert {"load_s", "save_s", "total_s", "warm_faster_than_cold"} <= set(result.keys())
    assert "gate_a_seconds" in result
```

**Step 2: Run test to verify it fails**

Run:
`pytest tests/test_perf_guardrails.py -v`

Expected:
- FAIL because new gate fields do not exist yet.

**Step 3: Write minimal implementation**

- Extend benchmark contract with:
  - `gate_a_seconds` (1497.067)
  - `gate_b_seconds` (1420.0)
  - `meets_gate_a` / `meets_gate_b` (for non-dry runs)
- Keep existing keys backward compatible.

**Step 4: Run tests to verify pass**

Run:
`pytest tests/test_perf_guardrails.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit add scripts/benchmark_pipeline_io.py tests/test_perf_guardrails.py
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit commit -m "test: add conservative perf guardrail contract"
```

---

### Task 2: Move Parquet Cache Paths Out of OUTPUT (Core, Fail-Open)

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-core/src/ms_core/utils/file_handler.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-core/src/ms_core/preprocessing/settings.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests/test_cache_path_policy.py`

**Step 1: Write failing tests**

```python
def test_excel_cache_path_not_co_located_in_output_directory(tmp_path):
    # save xlsx under OUTPUT; resolve parquet cache; assert cache path not under OUTPUT
    ...
```

```python
def test_cache_failures_do_not_block_excel_save(tmp_path):
    # force parquet cache write failure; save_data still succeeds for xlsx
    ...
```

**Step 2: Run tests to verify fail**

Run:
`pytest C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests/test_cache_path_policy.py -v`

Expected:
- FAIL (current cache path is `xlsx.with_suffix(".parquet")`).

**Step 3: Write minimal implementation**

- Add internal cache root setting, default hidden machine path:
  - Windows: `%LOCALAPPDATA%/ms-preprocessing-toolkit/cache`
  - fallback: `tempfile.gettempdir()/ms-preprocessing-toolkit/cache`
- Add deterministic cache mapping for xlsx path (hash-based).
- `_save_parquet_cache` and `_resolve_parquet_cache` use internal cache root.
- Any cache read/write exceptions remain non-fatal (warning/log + continue).

**Step 4: Run tests to verify pass**

Run:
`pytest C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests/test_cache_path_policy.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-core add src/ms_core/utils/file_handler.py src/ms_core/preprocessing/settings.py tests/test_cache_path_policy.py
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-core commit -m "feat: move parquet cache to hidden internal root with fail-open policy"
```

---

## Batch 1 Review Gate

- Execute `@superpowers:requesting-code-review` for Task 1-2 range.
- Fix Critical/Important findings before Batch 2.

---

### Task 3: CLI Default Memory Chain (No Step Roundtrip), Optional Persist Flag

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/main.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_cli_parquet_chain.py`

**Step 1: Write failing tests**

```python
def test_cli_step_all_default_does_not_write_step_parquet_intermediates():
    ...
```

```python
def test_cli_persist_intermediate_writes_parquet_to_internal_cache_not_output():
    ...
```

**Step 2: Run tests to verify fail**

Run:
`pytest tests/test_cli_parquet_chain.py -v`

Expected:
- FAIL (current behavior writes/reads step parquet roundtrip in `OUTPUT/.cli_intermediate`).

**Step 3: Write minimal implementation**

- Add CLI flag: `--persist-intermediate` (default `False`).
- For `--step all` default path:
  - No per-step parquet save/load roundtrip.
  - Keep in-memory `df/metadata` chaining.
- If `--persist-intermediate` enabled:
  - Persist parquet snapshots to internal cache root only (not `OUTPUT`).
- Preserve final output contract (`.xlsx` default).

**Step 4: Run tests to verify pass**

Run:
`pytest tests/test_cli_parquet_chain.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit add src/ms_preprocessing/main.py tests/test_cli_parquet_chain.py
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit commit -m "feat: default CLI step-all to memory chain with optional hidden intermediate persist"
```

---

### Task 4: GUI Intermediates Stored in Internal Cache (Not OUTPUT)

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/gui/pipeline_session.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/gui/main_window.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_gui_pipeline_session.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_regressions.py`

**Step 1: Write failing tests**

```python
def test_gui_step_intermediate_paths_use_internal_cache_not_output():
    ...
```

```python
def test_output_directory_contains_only_user_deliverables_after_run_all():
    ...
```

**Step 2: Run tests to verify fail**

Run:
`pytest tests/test_gui_pipeline_session.py tests/test_regressions.py -k "intermediate or autosave" -v`

Expected:
- FAIL (current step outputs are parquet under `OUTPUT`).

**Step 3: Write minimal implementation**

- Introduce internal intermediate directory provider (shared with core cache policy).
- `PipelineSession.save_step_output(...)` writes parquet intermediates to internal cache root.
- GUI `OUTPUT` folder keeps only final user-visible deliverables.

**Step 4: Run tests to verify pass**

Run:
`pytest tests/test_gui_pipeline_session.py tests/test_regressions.py -k "intermediate or autosave" -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit add src/ms_preprocessing/gui/pipeline_session.py src/ms_preprocessing/gui/main_window.py tests/test_gui_pipeline_session.py tests/test_regressions.py
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit commit -m "feat: move GUI parquet intermediates to hidden internal cache"
```

---

### Task 5: Disable Final Excel-Adjacent Parquet Cache by Default

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/main.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/src/ms_preprocessing/gui/main_window.py`
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_final_export_handoff.py`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/tests/test_final_export_cache_policy.py`

**Step 1: Write failing tests**

```python
def test_cli_final_xlsx_save_does_not_request_parquet_cache_by_default():
    ...
```

```python
def test_gui_final_export_does_not_request_parquet_cache_by_default():
    ...
```

**Step 2: Run tests to verify fail**

Run:
`pytest tests/test_final_export_cache_policy.py tests/test_final_export_handoff.py -v`

Expected:
- FAIL (currently final save path uses `save_parquet_cache=Settings.SAVE_PARQUET_CACHE`).

**Step 3: Write minimal implementation**

- Final `.xlsx` export in CLI/GUI uses `save_parquet_cache=False` by default.
- Keep explicit opt-in ability for future tuning (flag/config), but default must be off.
- Downstream handoff remains xlsx-only; no DNP bridge file is generated by the toolkit.

**Step 4: Run tests to verify pass**

Run:
`pytest tests/test_final_export_cache_policy.py tests/test_final_export_handoff.py -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit add src/ms_preprocessing/main.py src/ms_preprocessing/gui/main_window.py tests/test_final_export_handoff.py tests/test_final_export_cache_policy.py
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit commit -m "feat: disable final xlsx parquet cache by default"
```

---

## Batch 2 Parallel Execution (Required)

- Run **Task 3-5 in parallel** using `@superpowers:dispatching-parallel-agents`.
- Each parallel task must run in its own worktree/branch to avoid collisions.
- Reconcile and re-run combined tests after merge/cherry-pick.
- Execute `@superpowers:requesting-code-review` after reconciliation.

---

### Task 6: End-to-End Verification, Go/No-Go Decision, and Rollback Safety

**Files:**
- Modify: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/docs/plans/2026-03-05-unified-parquet-v2-rollout-checklist.md`
- Create: `C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit/docs/plans/2026-03-05-conservative-io-write-optimization-notes.md`

**Step 1: Write failing docs/contract test**

```python
def test_docs_include_conservative_io_go_no_go_and_rollback_criteria():
    ...
```

**Step 2: Run test to verify fail**

Run:
`pytest tests/test_smoke_guardrails.py -k docs -v`

Expected:
- FAIL until docs updated.

**Step 3: Update docs and run full verification matrix**

Run:
`pytest tests -v`

Run:
`pytest C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests -v`

Run (subset):
`python main.py --no-gui --input "C:/path/to/validation-subset.xlsx" --method-file "<method.docx>" --istd-record-file "<record.xlsx>" --mz-tol 20 --rt-tol 1.5 --step all`

Run (full):
`python main.py --no-gui --input "C:/path/to/validation-full.xlsx" --method-file "<method.docx>" --istd-record-file "<record.xlsx>" --mz-tol 20 --rt-tol 1.5 --step all`

Expected:
- All tests PASS.
- Full-run total time meets Gate A (`<=1497.067s`) to proceed.
- If Gate A fails: document “revert to previous behavior / keep original.”

**Step 4: Re-run docs test**

Run:
`pytest tests/test_smoke_guardrails.py -k docs -v`

Expected:
- PASS.

**Step 5: Commit**

```bash
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit add docs/plans/2026-03-05-unified-parquet-v2-rollout-checklist.md docs/plans/2026-03-05-conservative-io-write-optimization-notes.md tests/test_smoke_guardrails.py
git -C C:/Users/user/Desktop/質譜數據工具箱/ms-preprocessing-toolkit commit -m "docs: add conservative io optimization go-no-go and rollback notes"
```

---

## Batch 3 Review Gate

- Run `@superpowers:requesting-code-review` on final combined range.
- Address Critical/Important findings.

## Final Verification Before Completion (Must Run Fresh)

Toolkit:
- `pytest tests -v`

Core:
- `pytest C:/Users/user/Desktop/質譜數據工具箱/ms-core/tests -v`

Full E2E:
- `python main.py --no-gui --input "C:/path/to/validation-full.xlsx" --method-file "<method.docx>" --istd-record-file "<record.xlsx>" --mz-tol 20 --rt-tol 1.5 --step all`

Acceptance:
- Core functionality works without requiring parquet intermediates/caches.
- `OUTPUT` no longer contains machine-only parquet intermediate/cache artifacts.
- Gate A achieved; otherwise stop rollout and keep previous behavior.
