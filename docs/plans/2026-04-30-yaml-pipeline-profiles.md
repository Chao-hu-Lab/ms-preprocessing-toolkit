# YAML Pipeline Profiles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move workflow presets from Python literals into YAML-backed Step1-4 pipeline profiles shared by GUI and CLI, while keeping runtime input files out of profiles.

**Architecture:** `ms-core` owns algorithm invariants such as the Step4 ratio-rescue 10% floor. `ms_preprocessing` owns workflow policy through validated YAML profiles and local references. Existing public APIs such as `get_pipeline_profile()` and `get_step4_preset()` remain as facades so GUI, CLI, and tests keep one profile resolution path.

**Tech Stack:** Python 3.10+, PyYAML, pytest, packaged resources via `importlib.resources`, existing `ProcessingResult`/`ProcessingMetadata` contracts.

---

## Decisions

- Built-in profiles are packaged YAML resources under `src/ms_preprocessing/resources/builtin_profiles/`, separate from user-facing local config.
- User/local profiles are discovered from `config/presets/*.yml` and `config/presets/*.yaml`.
- CLI additionally accepts `--profile-file <path>` for one-off batch runs.
- GUI profile dropdown lists built-in profiles plus discovered local profile names, not arbitrary `--profile-file` paths.
- Local references use `${local.method_file}` and `${local.xic_results_file}` placeholders.
- `input` / `input_file` / `output` / `output_file` are invalid profile keys. Input remains a runtime CLI/GUI selection.
- YAML local references are the primary path. Existing JSON local reference files remain as a temporary fallback until YAML is verified in a follow-up cleanup PR.
- PyYAML is allowed as a dependency.

## Current State To Preserve Or Correct

- Preserve the `ms-core` ratio-rescue rule change: a feature is eligible only when every analysis group has detection ratio at least 10%.
- Revert any accidental `ms-core` direct default threshold changes. Toolkit presets may set default/strict `ratio_rescue_threshold` to `3.0`, but core direct defaults should not become the profile source of truth.
- Revert any bare widget default changes that tried to encode profile policy directly in `FeatureFilterWidget`; profile values should enter widgets through `apply_parameters()`.

---

## Task 1: Add YAML Dependency And Packaged Profile Fixtures

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ms_preprocessing/resources/builtin_profiles/loose.yml`
- Create: `src/ms_preprocessing/resources/builtin_profiles/default.yml`
- Create: `src/ms_preprocessing/resources/builtin_profiles/strict.yml`

**Step 1: Add PyYAML dependency**

Add `PyYAML` to `[project].dependencies`.

**Step 2: Create built-in YAML profiles**

Each profile must include:

```yaml
version: 1
name: default
description: "預設：主力用途，平衡保留與 QC 穩定性"
steps:
  step1:
    mode: normalization
    auto_detect: true
    method_file: "${local.method_file}"
  step2:
    xic_results_file: "${local.xic_results_file}"
  step3:
    mz_tolerance_ppm: 20.0
    rt_tolerance: 0.1
    merge_mode: per_sample_max
    preserve_red_font: true
    top_n: null
    enable_degeneracy_annotation: false
    degeneracy_ppm_tolerance: 20.0
    degeneracy_rt_tolerance: 0.05
    degeneracy_correlation_threshold: 0.8
    degeneracy_min_correlation_points: 3
    degeneracy_adduct_table_file: ""
  step4:
    signal_threshold: 5000.0
    background_threshold: 0.33
    high_det_thresh: 0.8
    low_det_thresh: 0.2
    qc_ratio_threshold: 0.25
    intensity_fc_threshold: 2.0
    ratio_rescue_threshold: 3.0
    enable_background_threshold: true
    enable_qc_ratio_threshold: true
    enable_intensity_fc_threshold: false
    enable_mnar_gate: true
    enable_ratio_rescue: true
```

Use these Step4 values:

- `loose`: `background_threshold=0.20`, `high_det_thresh=0.30`, `low_det_thresh=0.10`, `qc_ratio_threshold=0.00`, `intensity_fc_threshold=1.5`, `ratio_rescue_threshold=2.0`.
- `default`: keep existing non-ratio values, set `ratio_rescue_threshold=3.0`.
- `strict`: keep existing non-ratio values, set `ratio_rescue_threshold=3.0`.

**Step 3: Verify no tests yet**

No verification expected yet. YAML files are not loaded until Task 2.

---

## Task 2: Implement Local Reference YAML Loader

**Files:**
- Modify: `src/ms_preprocessing/config/pipeline_defaults.py`
- Test: `tests/test_pipeline_baseline_contract.py`

**Step 1: Write failing tests**

Add tests that assert:

- `MSPTK_LOCAL_REFERENCE_CONFIG` pointing at `.yml` resolves `method_file` and `xic_results_file`.
- Default local reference path prefers `config/local_reference.yml`.
- Existing `.json` local reference remains supported as fallback.
- Legacy Step2 keys in YAML still trigger the existing legacy-source warning.

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_pipeline_baseline_contract.py -q --tb=short
```

Expected: new YAML tests fail because only JSON is currently parsed.

**Step 2: Implement YAML local reference parsing**

Update `_load_local_reference_config()` to:

- Resolve path from `MSPTK_LOCAL_REFERENCE_CONFIG`, else `config/local_reference.yml`, else `config/local_reference_paths.json`.
- Parse `.yml` / `.yaml` with `yaml.safe_load()`.
- Parse `.json` with `json.loads()` during transition.
- Accept both top-level legacy shape:

```yaml
method_file: "..."
xic_results_file: "..."
```

and new shape:

```yaml
version: 1
references:
  method_file: "..."
  xic_results_file: "..."
```

**Step 3: Run tests**

Run the same file-level command. Expected: PASS.

---

## Task 3: Build Validated Profile Loader

**Files:**
- Create: `src/ms_preprocessing/config/profile_loader.py`
- Modify: `src/ms_preprocessing/config/__init__.py`
- Test: `tests/test_pipeline_profiles.py`

**Step 1: Write failing tests**

Add tests for:

- Built-in `default` profile loads from packaged YAML.
- Local references substitute `${local.method_file}` and `${local.xic_results_file}`.
- Unknown profile name raises a clear `ValueError`.
- Missing required step key raises a clear `ValueError`.
- Unknown keys under `steps.step4` raise a clear `ValueError`.
- `input`, `input_file`, `output`, and `output_file` are rejected anywhere under `steps`.
- Local `config/presets/*.yml` profile overrides or extends built-in names deterministically.
- `load_pipeline_profile_file(path)` loads an explicit path for CLI `--profile-file`.

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_pipeline_profiles.py -q --tb=short
```

Expected: FAIL because `profile_loader.py` does not exist.

**Step 2: Implement `ProfileLoader` functions**

Implement small functions, not a large framework:

- `list_pipeline_profiles() -> list[str]`
- `get_pipeline_profile(name: str = "default") -> PipelineProfile`
- `load_pipeline_profile_file(path: Path | str) -> PipelineProfile`
- `format_pipeline_profile_preview(name: str = "default") -> str`

Validation rules:

- Top-level required keys: `version`, `name`, `steps`.
- Required step keys: `step1`, `step2`, `step3`, `step4`.
- Reject runtime file keys: `input`, `input_file`, `output`, `output_file`.
- Reject unknown parameter keys under each step unless already accepted by current code.
- Preserve copies so callers cannot mutate cached profile data.

**Step 3: Run tests**

Run the same file-level command. Expected: PASS.

---

## Task 4: Replace Python Step4 Preset Literals With Facade

**Files:**
- Modify: `src/ms_preprocessing/config/feature_filter_presets.py`
- Modify: `src/ms_preprocessing/config/pipeline_profiles.py`
- Test: `tests/test_feature_filter_presets.py`
- Test: `tests/test_pipeline_profiles.py`

**Step 1: Write failing facade tests**

Ensure `get_step4_preset("loose")` reads the YAML-backed `steps.step4` values:

- `loose` MNAR is `0.30 / 0.10`.
- `loose` ratio rescue is `2.0`.
- `default` and `strict` ratio rescue are `3.0`.

**Step 2: Implement facade**

Make `feature_filter_presets.py` delegate to `profile_loader.get_pipeline_profile(name)["step4"]`.

Keep these public names if still imported:

- `PresetName`
- `Step4Params`
- `STEP4_PRESETS`, if tests/imports require it, as a lazy or generated mapping.
- `get_step4_preset()`

**Step 3: Run tests**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_feature_filter_presets.py tests/test_pipeline_profiles.py -q --tb=short
```

Expected: PASS.

---

## Task 5: Wire CLI Profile File And Keep Explicit Overrides

**Files:**
- Modify: `src/ms_preprocessing/main.py`
- Modify: `src/ms_preprocessing/workflow/parameter_resolver.py`
- Test: `tests/test_parameter_resolver.py`
- Test: `tests/test_cli_parquet_chain.py`

**Step 1: Write failing tests**

Add tests for:

- `--profile-file path.yml` resolves Step1-4 params from that file.
- `--profile-file` does not require the profile name to be in discovered profiles.
- Explicit CLI overrides still win over profile YAML values.
- `--ratio-rescue-threshold` and `--disable-ratio-rescue` remain supported.
- A profile file containing `input_file` is rejected before running adapters.

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_parameter_resolver.py tests/test_cli_parquet_chain.py -q --tb=short
```

Expected: FAIL for `--profile-file`.

**Step 2: Implement CLI path**

- Add `--profile-file`.
- `ParameterResolver.from_cli_args()` should use `load_pipeline_profile_file()` when provided, else `get_pipeline_profile(args.profile)`.
- Keep runtime `--input` and `--output` outside profile resolution.

**Step 3: Run tests**

Run the same command. Expected: PASS.

---

## Task 6: Wire GUI Profile Discovery

**Files:**
- Modify: `src/ms_preprocessing/gui/main_window.py`
- Modify: `src/ms_preprocessing/gui/event_handlers.py`
- Test: `tests/test_gui_main_window_sidebar_labels.py`
- Test: `tests/test_gui_event_handlers.py`

**Step 1: Write failing tests**

Assert:

- GUI profile selector values come from `list_pipeline_profiles()`.
- Selecting a local YAML profile applies Step1-4 params.
- Preview text comes from the resolved YAML profile.

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_gui_main_window_sidebar_labels.py tests/test_gui_event_handlers.py -q --tb=short
```

Expected: FAIL if GUI still hardcodes `["loose", "default", "strict"]`.

**Step 2: Implement GUI discovery**

- Replace hardcoded selector values with `list_pipeline_profiles()`.
- Keep default selection as `"default"` when available.
- If profile loading fails, log a clear message and do not start Run All.

**Step 3: Run tests**

Run the same command. Expected: PASS.

---

## Task 7: Preserve Correct `ms-core` Boundary

**Files:**
- Modify: `ms-core/src/ms_core/preprocessing/feature_filter_decisions.py`
- Modify: `ms-core/src/ms_core/preprocessing/ms_quality_filter.py`
- Revert if needed: `ms-core/src/ms_core/preprocessing/settings.py`
- Test: `ms-core/tests/test_feature_filter_decisions.py`
- Test: `ms-core/tests/test_feature_filter.py`

**Step 1: Keep algorithm tests**

Required tests:

- `32% / 16%` can be rescued when `ratio_rescue_threshold=2.0`.
- Any analysis group `<10%` cannot be rescued even if ratio is high.
- The 10% floor does not use `low_det_thresh`.

**Step 2: Correct boundary**

- Keep `_RATIO_RESCUE_MIN_DETECTION = 0.10` in `feature_filter_decisions.py`.
- Do not encode toolkit loose/default/strict values into `ms-core` settings.
- If `default_ratio_rescue_threshold` was changed only for toolkit profile reasons, revert it.

**Step 3: Run core tests**

Run:

```powershell
Push-Location ms-core
python -m pytest tests/test_feature_filter_decisions.py tests/test_feature_filter.py tests/test_feature_filter_output.py -q --tb=short
Pop-Location
```

Expected: PASS.

---

## Task 8: Update Documentation And Regression Coverage

**Files:**
- Modify: `docs/TESTING.md` only if test ownership changes.
- Create or modify: `tests/test_profile_loader.py` if profile tests grow too large for `tests/test_pipeline_profiles.py`.

**Step 1: Add docs if needed**

Document:

- Built-in profile location.
- Local profile location.
- Local reference YAML shape.
- JSON fallback is transitional.
- Input files are runtime-only.

**Step 2: Run relevant checks**

Run:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m smoke -q --tb=short
python -m pytest -m adapter -q --tb=short
python -m pytest tests/test_pipeline_profiles.py tests/test_parameter_resolver.py tests/test_cli_parquet_chain.py tests/test_gui_main_window_sidebar_labels.py tests/test_gui_event_handlers.py -q --tb=short
```

For `ms-core` changes:

```powershell
Push-Location ms-core
python -m pytest tests/ -q --tb=short -x
Pop-Location
```

Expected: PASS.

---

## Task 9: Review, Commit, And Push In Submodule Order

**Files:**
- All changed files.

**Step 1: Inspect diff**

Run:

```powershell
git diff --check
git -C ms-core diff --check
git status --short
git -C ms-core status --short
```

Expected: only intentional changes, no whitespace errors. CRLF warnings are acceptable on Windows.

**Step 2: Commit `ms-core` first**

Only if `ms-core` changed:

```powershell
Push-Location ms-core
git add src/ms_core/preprocessing/feature_filter_decisions.py src/ms_core/preprocessing/ms_quality_filter.py tests/test_feature_filter_decisions.py tests/test_feature_filter.py
git commit -m "fix: decouple ratio rescue floor from mnar threshold"
git push origin fix/detection-ratio-rescue-floor
Pop-Location
```

**Step 3: Commit top-level**

```powershell
git add ms-core pyproject.toml src/ms_preprocessing/config src/ms_preprocessing/main.py src/ms_preprocessing/workflow/parameter_resolver.py src/ms_preprocessing/gui tests docs/plans/2026-04-30-yaml-pipeline-profiles.md
git commit -m "feat: load pipeline profiles from yaml"
git push origin feature/detection-ratio-rescue
```

**Step 4: PR notes**

PR should explicitly call out:

- YAML profiles are workflow policy, not algorithm rules.
- Runtime input files remain outside profiles.
- JSON local reference support is temporary.
- `ms-core` must merge first if submodule pointer changed.
