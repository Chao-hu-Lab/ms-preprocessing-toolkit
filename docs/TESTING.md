# Testing Strategy

This document is the source of truth for test ownership, local test selection, and
verification scope in `ms-preprocessing-toolkit`.

Agent-facing trigger rules live in `AGENTS.md` and repo skills. Those entry points
must point here instead of duplicating long test policy.

## Goals

- Keep verification proportional to the change.
- Make ownership boundaries explicit between toolkit code and the `ms-core`
  submodule.
- Keep GUI tests isolated from fast non-GUI checks.
- Avoid hidden CI drift by documenting the repo-owned test contract.
- Preserve root hygiene on Windows by using the repo-local temp fixtures.

## Code Surfaces

| Surface | Owner | Test location | Notes |
| --- | --- | --- | --- |
| `src/ms_preprocessing/` | toolkit | `tests/` | GUI, CLI, adapters, packaging, export paths |
| `ms-core/` | submodule | `ms-core/tests/` | core processing logic and algorithm internals |
| toolkit to `ms-core` bridge | toolkit | `tests/adapters/`, `tests/test_ms_core_api_contract.py` | public API and adapter contract only |

Do not recreate `tests/core/` in the top-level repo. Algorithm/internal
`ms-core` tests belong in `ms-core/tests/` and should be committed in the
submodule first. The top-level suite should only assert toolkit behavior,
adapter/API contracts, GUI, CLI, IO, and export flows.

## Test Layers

| Layer | Marker | Main files | Purpose | Run style |
| --- | --- | --- | --- | --- |
| Smoke | `smoke` | `tests/test_smoke_guardrails.py`, `tests/test_bootstrap_paths.py`, `tests/test_ms_core_api_contract.py` | Startup, import, packaging, public API sanity | Fast, first-pass check |
| Adapter contract | `adapter` | `tests/adapters/`, `tests/test_ms_core_api_contract.py` | Toolkit adapters preserve the bridge to `ms-core` | Focused when adapter or `ms-core` public API changes |
| GUI | `gui` | `tests/test_*widget.py`, `tests/test_gui_*.py` | GUI layer behavior, widget state, event handlers, validation helpers | Serial, no xdist by default |
| Integration / IO | `integration` | parquet, export, cache, pipeline bridge, regression tests | Multi-step file and workflow behavior | Focused after IO/session changes |
| Performance guardrails | `perf` | `tests/test_perf_guardrails.py`, benchmark-style tests | Detect obvious runtime regressions | Run only when performance-sensitive code changes |
| Serial-only | `serial` | GUI tests, root cleanup tests, shared-temp tests | Tests that mutate process-wide or repo-wide state | Never run in parallel until proven safe |

Markers describe execution concerns. Folder and filename still carry the main
ownership signal. Do not add a marker unless it changes how a test should be
selected, isolated, or scheduled.

Marker assignment for the top-level suite is centralized in
`tests/testing_markers.py` and applied by `tests/conftest.py` during collection.
When a new test file belongs to an existing layer, update that mapping and its
unit tests instead of adding one-off decorators across many files.

## Marker Policy

Registered markers:

- `smoke`: fast entrypoint, import, packaging, or public API sanity checks.
- `adapter`: toolkit adapter contract tests.
- `gui`: GUI layer tests, including widgets, workflow labels, validation
  helpers, styles, session summaries, or event scheduling.
- `integration`: multi-component workflow, file IO, export, or cache behavior.
- `perf`: runtime or performance guardrails.
- `serial`: tests that must not run concurrently because they touch global GUI
  state, shared temp roots, cleanup scripts, or process-wide state.

`pyproject.toml` uses `--strict-markers`, so every custom marker must be
registered before use.

## Local Commands

Use PowerShell from the toolkit repo root.

### Fast smoke

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m smoke -v --tb=short
```

### Focused file or node

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_feature_filter_widget.py -v --tb=short
```

For one test:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/test_feature_filter_widget.py::test_name -v --tb=short
```

### GUI-focused

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m gui -v --tb=short
```

### Adapter-focused

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m adapter -v --tb=short
```

### Integration / IO-focused

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m integration -v --tb=short
```

### Performance guardrails

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m perf -v --tb=short
```

### Top-level full suite

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

### `ms-core` submodule suite

Run this only when `ms-core/` changed or when a toolkit change depends on a new
or changed `ms-core` contract.

```powershell
Push-Location ms-core
python -m pytest tests/ -v --tb=short -x
Pop-Location
```

## Change-To-Test Matrix

| Change | Minimum verification | Expand when |
| --- | --- | --- |
| Documentation only | Read affected docs as UTF-8; run smoke only if docs are asserted by tests | README / release docs touched |
| `pyproject.toml` pytest config or marker mapping | `tests/test_testing_markers.py`, smoke, plus `python -m pytest --collect-only tests -q` | Marker behavior or temp behavior changed |
| GUI layout, labels, or widgets | Related widget tests plus GUI workflow label/sidebar tests | Shared layout, base widget, or event handler changed |
| `event_handlers.py` / Run All | Related widget tests plus `tests/test_gui_event_handlers.py` | Threading, export, or session state changed |
| Adapter code | `tests/adapters/` plus API contract smoke | `ms-core` public API changed |
| Pipeline profiles / presets | `tests/test_profile_loader.py`, `tests/test_pipeline_profiles.py`, `tests/test_feature_filter_presets.py` | Preset values affect Step 4 output |
| File IO, parquet, export, cache | Integration / IO-focused command | Output format or cache policy changed |
| Root hygiene, temp fixtures, cleanup scripts | `tests/test_root_hygiene.py` | Any pytest temp root or cleanup behavior changed |
| `ms-core/` submodule | `ms-core/tests/`, then adapter contract tests in toolkit | Submodule pointer is updated |

For small changes, start with the narrowest relevant command, then expand only
when the changed surface is shared or risky.

## GUI Test Rules

- GUI tests should use shared fixtures from `tests/conftest.py`.
- Prefer `ctk_root`, `step_widget_factory`, and `spin_until` over ad hoc Tk
  setup.
- Do not rely on real dialogs in automated tests. Confirmation paths should be
  monkeypatch-friendly.
- Treat GUI tests as serial unless they have been proven safe under parallel
  execution.
- Minimal GUI smoke for shared GUI changes: startup, step switching, action
  button visibility, and primary step titles/descriptions.

## Root Hygiene Rules

- Do not create temp directories in the repository root.
- Use `tmp_path`, `tmp_path_factory`, `project_temp_dir`, or `temp_dir` from
  `tests/conftest.py`.
- Current top-level pytest temp root is `build/pytest/tmp-fixtures/`.
- Do not re-enable pytest's cache provider unless the root-hygiene policy is
  updated and verified.
- Cleanup-script tests and GUI tests should be considered `serial` until their
  shared-state behavior is isolated.

## CI Contract

Repo-local CI is defined in `.github/workflows/ci.yml` and delegates execution to
`Chao-hu-Lab/shared-workflows/.github/workflows/python-ci.yml@main`.

Current repo-owned expectations:

- CI checks PRs targeting `master` or `main`.
- Push CI should cover `master`, `main`, `feature/*`, `fix/*`, and `chore/*`.
- CI passes `pythonpath: "ms-core/src"` and checks out submodules.

Because the actual pytest command is delegated to a shared workflow, local
verification commands in this document are the stable developer contract. If the
shared workflow changes, update this document or add a repo-local wrapper script
so local and CI behavior do not drift silently.

## Parallelization Policy

Do not enable global `pytest -n auto` yet.

Known blockers:

- GUI tests share one `CTk` root and depend on event-loop scheduling.
- Root-hygiene cleanup tests can mutate `build/pytest`.
- Custom repo-local `tmp_path` and `tmp_path_factory` are intentionally different
  from pytest's built-in temp handling.

Future parallelization should start with non-GUI, non-serial tests only, after
the cleanup-script tests are isolated in a fake repo root.

## Adding Tests

Before adding a test:

1. Pick the owning surface: toolkit, adapter contract, or `ms-core`.
2. Put algorithm/internal `ms-core` tests in `ms-core/tests/`.
3. Put toolkit behavior tests under `tests/`.
4. Use existing fixtures before creating new temp or GUI setup.
5. If the file should be selected by a marker, update `tests/testing_markers.py`
   and `tests/test_testing_markers.py`.
6. Add a new marker only if it changes selection or scheduling.
7. Run the narrowest relevant command from this document.

Do not create new long-lived testing rules in task plans. Plans may list
task-specific verification commands, but this file remains the durable policy.
