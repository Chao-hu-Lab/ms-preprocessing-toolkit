# Step2 XIC Input Provider Plan

Date: 2026-04-28
Branch: `feature/step2-xic-input-provider`
Status: Plan reviewed, not implemented

## Goal

Replace the current Step2 ISTD input model with XIC Extractor output workbooks as the only supported ISTD target source.

Step2 should read an XIC Extractor `.xlsx`, extract ISTD target definitions, mark matching ISTD rows in the feature matrix, and pass the same protected-row metadata to Step3. The old ISTD record/date workflow and manual ISTD m/z list workflow are not long-term supported and should be removed during this change.

## Context

The example source workbook is:

`C:\Users\user\Desktop\XIC_Extractor\output\xic_results_20260427_1425.xlsx`

Observed sheets:

| Sheet | Role For Step2 |
| --- | --- |
| `Targets` | Primary target registry. Contains `Label`, `Role`, `ISTD Pair`, `m/z`, `RT min`, `RT max`, `ppm tol`. |
| `Summary` | Optional observed target summary. Contains `Target`, `Role`, `Detected`, `Total`, `Detection %`, `Mean RT`, NL and confidence fields. |
| `XIC Results` | Sample-level extraction output. Not needed for Step2 matching in this pass. |
| `Diagnostics` | QA diagnostics. Not needed for Step2 matching in this pass. |

Useful ISTD rows from `Targets` are rows where `Role == "ISTD"`. The example contains 7 ISTD targets:

- `d3-5-hmdC`, m/z `261.127276`
- `d3-5-medC`, m/z `245.132362`
- `d4-N6-2HE-dA`, m/z `300.1605`
- `15N5-8-oxodG`, m/z `289.0841`
- `[13C,15N2]-8-oxo-Guo`, m/z `303.0913`
- `d3-N6-medA`, m/z `269.1436`
- `d3-dG-C8-MeIQx`, m/z `482.208679`

## Constraints

- Do not preserve the old ISTD record/date parser as a supported source.
- Do not preserve manual `istd_mz_list` as a GUI or CLI fallback.
- Do not parse XIC workbook internals in GUI widgets or event handlers.
- Keep Step2 output contract compatible with Step3:
  - `red_font_rows`
  - `protected_rows`
  - `istd_features`
- Do not let Step2 detect duplicate/protected neighbor rows. Step3 owns duplicate grouping.
- `ms-core` is a submodule. Any core parser or processor change must be committed and pushed inside `ms-core` before updating the top-level pointer.
- Use focused tests first, then broader top-level verification.

## Done When

- Step2 accepts an XIC Extractor workbook path.
- Step2 rejects missing or invalid XIC workbooks with clear errors.
- Step2 no longer exposes old ISTD record date or manual m/z list controls in GUI.
- CLI and local config use XIC-oriented names.
- Legacy ISTD record/date tests are deleted or rewritten.
- Existing Step2 row-marking and Step3 protected-row behavior still passes.
- The top-level repo points at a pushed `ms-core` commit.

## Target Architecture

```
XIC Extractor workbook
        |
        v
ms-core XIC target parser
        |
        v
Normalized ISTD target list
        |
        v
ISTDMarker target matching
        |
        +--> red/protected row metadata
        |
        v
Toolkit adapter result
        |
        +--> GUI Step2
        +--> CLI Step2
        +--> PipelineSession metadata
        |
        v
Step3 duplicate removal
```

## Normalized Target Contract

Add a small typed contract in `ms-core` for XIC-derived targets.

Required fields:

| Field | Source | Rule |
| --- | --- | --- |
| `label` | `Targets.Label` | Required. |
| `mz` | `Targets.m/z` | Required numeric. |
| `rt` | `Summary.Mean RT` or target window midpoint | Required numeric after fallback. |
| `rt_min` | `Targets.RT min` | Optional but should be kept for metadata. |
| `rt_max` | `Targets.RT max` | Optional but should be kept for metadata. |
| `ppm_tolerance` | `Targets.ppm tol` | Required numeric. Missing or non-numeric values make the target unusable. |
| `source` | constant | `xic_extractor`. |

RT selection:

1. Join `Targets.Label` to `Summary.Target` for rows where both sides have `Role == "ISTD"`.
2. Use `Summary.Mean RT` when it is numeric.
3. If `Mean RT` is missing or non-numeric, use `(RT min + RT max) / 2`.
4. If neither mean RT nor a valid RT window exists, skip that target and report it in metadata warnings.

Detection summary:

- Keep `Detected`, `Total`, and `Detection %` in metadata for logging and debugging.
- Do not fail solely because an ISTD has low detection in `Summary`.
- Fail only when no usable ISTD targets remain.

## Implementation Plan

### Phase 1: ms-core Parser And Contract

Create an XIC workbook target parser in `ms-core`, likely near `ms_core.preprocessing.istd_marker` or a small sibling module.

Responsibilities:

- Validate required sheets: `Targets` required, `Summary` optional.
- Validate required columns in `Targets`.
- Filter `Role == "ISTD"` case-insensitively.
- Parse numeric m/z, RT window, ppm tolerance.
- Join optional `Summary` by target label.
- Return normalized target objects plus parser metadata:
  - source path
  - target count
  - skipped target labels and reasons
  - targets using `Summary.Mean RT`
  - targets using RT midpoint fallback

Do not let this parser read feature matrix data. It should only describe target definitions.

### Phase 2: ISTDMarker Uses XIC Targets

Change `ISTDMarker.process()` so XIC targets are the official source.

Planned parameter shape:

```python
process(
    df,
    xic_results_file: Path | None = None,
    ...
)
```

Removal plan:

- Remove `istd_record_file`.
- Remove `istd_record_date`.
- Remove `istd_mz_list`.
- Remove `infer_istd_from_record()`.
- Remove `_load_istd_record_targets()`.
- Remove `find_potential_istd()` and rewrite tests that depended on manual m/z fallback.

Matching rule:

- For each normalized XIC target, find feature matrix rows whose m/z is within the target `ppm tol`.
- If the XIC target has `RT min` and `RT max`, require the feature RT to fall inside that window.
- If the RT window is missing, use the normalized target RT only for ranking candidates, not as a user-tunable Step2 tolerance.
- If multiple rows match one target, choose by occurrence count, then total intensity, then RT closeness. This preserves the current intent.
- If no XIC target matches any feature matrix row, fail Step2 with a clear message. This usually means the wrong XIC file, wrong batch, or incompatible feature matrix was selected.
- Produce the same `istd_features`, `istd_rows`, `red_font_rows`, and `protected_rows` metadata expected by the toolkit.
- Keep `duplicate_indices` empty and `duplicates_marked == 0`; duplicate decisions belong to Step3.

### Phase 3: Toolkit Adapter

Update `src/ms_preprocessing/adapters/istd_marker.py`.

Responsibilities:

- Rename adapter input to `xic_results_file`.
- Pass only `xic_results_file` to core.
- Remove `get_default_istd_mz()` if GUI no longer needs it.
- Preserve `ProcessingResult` metadata conversion.
- Surface parser warnings in `statistics` or metadata so GUI can log useful messages.

### Phase 4: GUI Step2

Update `src/ms_preprocessing/gui/widgets/istd_marker_widget.py`.

GUI shape:

- Remove `m/z 容差 (ppm)`.
- Remove `RT 容差 (min)`.
- Replace `預設 ISTD m/z` with nothing.
- Replace `ISTD 記錄檔 (.xlsx)` with `XIC 結果檔 (.xlsx)`.
- Remove `ISTD 日期 (YYYYMMDD)`.
- Browse dialog title: `選擇 XIC Extractor 結果檔`.
- Description should say Step2 uses XIC targets to identify ISTD rows.

Parameter output:

```python
{
    "xic_results_file": "...",
}
```

Validation:

- Missing XIC file is blocking for Step2.
- Non-existent XIC file is blocking.
- Invalid extension is blocking unless future XIC exports add non-xlsx formats.
- Do not validate internal workbook schema in the widget. Schema errors belong to core parser.

### Phase 5: CLI And Config

Update CLI:

- Add `--xic-results-file`.
- Remove `--istd-record-file`.
- Remove `--istd-record-date`.
- Remove `--istd-mz`.

Update config:

- Replace `DEFAULT_ISTD_RECORD_FILE` with `DEFAULT_XIC_RESULTS_FILE`.
- Replace env var `MSPTK_ISTD_RECORD_FILE` with `MSPTK_XIC_RESULTS_FILE`.
- Remove `MSPTK_ISTD_RECORD_DATE`.
- Replace local config key `istd_record_file` with `xic_results_file`.

Migration behavior:

- Do not silently read old keys as supported config.
- If old keys are present in local config or CLI use is attempted, fail with a direct message:
  - `Step2 now requires an XIC Extractor results workbook. Please set xic_results_file or pass --xic-results-file.`

This makes the breaking change visible instead of quietly running stale behavior.

### Phase 6: Docs And User-Facing Copy

Update:

- `README.md`
- `docs/plans/2026-04-27-gui-ux-hardening.md` references if they now describe future work that has become current work.
- CLI help text.
- GUI labels and validation warnings.
- Any `local_reference_paths.json` documentation.

Do not rewrite unrelated old historical plans unless they are active instructions or smoke guardrails assert against them.

## Test Plan

### ms-core Tests

Add a minimal XIC workbook fixture generated in test code.

Cover:

- Parser extracts only `Role == "ISTD"` rows from `Targets`.
- Parser prefers numeric `Summary.Mean RT`.
- Parser falls back to target RT midpoint.
- Parser reports skipped targets with missing m/z or unusable RT.
- Parser fails clearly when `Targets` sheet is missing.
- `ISTDMarker.process()` marks matching ISTD rows using XIC targets.
- `ISTDMarker.process()` fails clearly when XIC targets parse successfully but match zero feature rows.
- Multiple feature candidates choose occurrence count, then total intensity, then RT closeness.
- Step2 does not mark duplicate-of-ISTD rows; it only marks selected ISTD rows.
- Old record/date parser tests are removed or rewritten to assert the new XIC contract.

### Toolkit Tests

Update:

- `tests/adapters/test_adapter_istd_marker.py`
- `tests/adapters/test_adapter_runtime_contracts.py`
- `tests/test_istd_marker_widget.py`
- `tests/test_cli_parquet_chain.py`
- `tests/test_pipeline_baseline_contract.py`
- GUI validation and session summary tests.

Cover:

- Adapter passes `xic_results_file` to core.
- GUI returns `xic_results_file` and no longer returns Step2 PPM/RT, `istd_record_date`, or `istd_mz_list`.
- GUI validation blocks missing XIC source.
- CLI resolves `--xic-results-file`.
- Local config resolves `xic_results_file`.
- Run All profile applies Step2 defaults without old record/date keys.
- Session summary displays XIC file, not ISTD date.

### Verification Commands

Focused first:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest ms-core/tests/test_istd_marker.py tests/test_istd_marker_widget.py tests/adapters/test_adapter_istd_marker.py -v --tb=short
```

Then toolkit-relevant:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_cli_parquet_chain.py tests/test_pipeline_baseline_contract.py tests/test_gui_validation.py tests/test_gui_session_summary.py -v --tb=short
```

Before PR:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

## Failure Modes

| Failure | Expected Handling | Test |
| --- | --- | --- |
| XIC workbook missing `Targets` sheet | Blocking error with sheet name. | Parser test. |
| Required `Targets` columns missing | Blocking error listing missing columns. | Parser test. |
| `Summary.Mean RT` is `—` or empty | Fallback to RT midpoint. | Parser test. |
| Both `Mean RT` and RT window unusable | Skip target with warning; fail only if all targets skipped. | Parser test. |
| No feature matrix rows match XIC targets | Blocking error that suggests wrong XIC file or incompatible feature matrix. | Core processor test. |
| Multiple rows match one ISTD target | Deterministic best candidate selection. | Core processor test. |
| Old config keys still present | Clear breaking-change message. | Config test. |
| Step3 loses protected rows | Existing duplicate remover contract still passes. | Cross-project adapter test. |

## NOT In Scope

- Reading sample-level `XIC Results` for per-sample correction.
- Using `Diagnostics` to reject targets.
- Supporting old ISTD record/date files.
- Supporting manual ISTD m/z list entry.
- Adding a format selector in GUI.
- Changing downstream DNP or normalization behavior.
- Renaming the workflow step itself away from `ISTD 標記`.

## What Already Exists

- `ms-core/src/ms_core/preprocessing/istd_marker.py`
  - Already validates feature matrix shape, sorts by m/z, finds matching rows, and emits protected row metadata.
  - Reuse the row matching and metadata contract, but keep duplicate grouping in Step3.
- `src/ms_preprocessing/adapters/istd_marker.py`
  - Already isolates toolkit from core processing.
  - Reuse the adapter result wrapping, update parameter names.
- `src/ms_preprocessing/gui/widgets/istd_marker_widget.py`
  - Already owns Step2 parameter UI.
  - Reuse the widget shell and validation hook, replace legacy controls.
- `src/ms_preprocessing/gui/validation.py`
  - Already provides blocking/non-blocking validation.
  - Reuse it for XIC file path validation.
- `src/ms_preprocessing/config/pipeline_defaults.py`
  - Already resolves local config and env defaults.
  - Reuse the mechanism, replace old keys.
- `PipelineSession`
  - Already records step parameters and metadata.
  - Do not add XIC parser logic there.

## Worktree Strategy

Sequential implementation is recommended because the ms-core processor contract must land before toolkit adapter, GUI, CLI, and tests can compile cleanly.

Possible ordering:

| Step | Modules touched | Depends on |
| --- | --- | --- |
| Core parser and ISTDMarker contract | `ms-core/src/ms_core/preprocessing`, `ms-core/tests` | none |
| Toolkit adapter and config | `src/ms_preprocessing/adapters`, `src/ms_preprocessing/config`, `tests/adapters` | core parser |
| GUI and validation | `src/ms_preprocessing/gui`, GUI tests | adapter/config |
| CLI and docs | `src/ms_preprocessing/main.py`, `README.md`, docs/tests | adapter/config |

Parallel worktrees are not recommended for this PR. Too many changes share Step2 naming and test fixtures, and merge conflicts would waste more time than they save.

## Engineering Review

Verdict: plan is sound after review. The important decision is to treat old ISTD record/date and manual m/z list as removed surfaces, not deprecated surfaces.

### Scope Challenge

Accepted as-is. Supporting both XIC and legacy ISTD record would create a long-lived compatibility layer for a workflow the project owner has already decided to abandon.

### Architecture Review

No blocking issues.

Required guardrails:

- The XIC parser must live in `ms-core`, not in the GUI or toolkit event handlers.
- The normalized target contract must be small and typed.
- The old record/date parser must be removed rather than hidden behind a selector.
- Breaking config changes must fail clearly, not silently ignore old values.
- `ppm tol` should be strict, not inferred, because XIC is now the single supported source.
- Zero matched ISTD rows should be a blocking failure, not a warning.

### Code Quality Review

One non-blocking risk:

- `ISTDMarker.process()` can become too large if parser, matching, and metadata formatting all stay in the same method. Keep parser and candidate selection helpers separate.

Recommended implementation guard:

- Put XIC workbook parsing in a helper module or clearly bounded helper functions.
- Keep `process()` focused on orchestration.

### Test Review

Coverage requirements are clear. The biggest gap to avoid is testing only parser extraction but not end-to-end row marking.

Required minimum:

- Parser unit tests.
- Core Step2 row-marking test using XIC target source.
- Toolkit adapter parameter contract test.
- GUI parameter and validation tests.
- CLI/local config contract tests.

### Performance Review

No performance concern for this plan.

The XIC workbook is small relative to feature matrices, and Step2 already scans feature rows. The parser should read only `Targets` and `Summary`, not `XIC Results` or `Diagnostics`, to avoid accidental slowdowns.

### Resolved Review Findings

1. The first draft allowed `Targets.ppm tol` to fall back to a Step2 default. That was too permissive for a single official XIC schema, so the plan now treats missing or non-numeric `ppm tol` as an unusable target.
2. The first draft allowed zero matched ISTD rows as a warning. That would silently continue with no protected ISTD rows, so the plan now requires a blocking Step2 error.

### Final Review Notes

- This is a breaking change by design.
- The implementation should be one PR spanning `ms-core` and toolkit submodule pointer update.
- Manual verification should include one real run with `xic_results_20260427_1425.xlsx` after automated tests pass.
