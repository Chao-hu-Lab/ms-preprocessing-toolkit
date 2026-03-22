# 2026-03-22 Cross-Project Follow-Ups

## Goal

Capture the remaining review items that depend on external repositories or
cross-project runtime contracts, so they can be handled after the local-only
toolkit fixes are merged.

## Out Of Scope For This Branch

- Editing code inside `ms-core/`
- Editing code inside `Data_Normalization_project_v2/`
- Changing external repository release or deployment configuration

## Follow-Up Tasks

### 1. DNP bridge path injection hardening

Files to review:
- `src/ms_preprocessing/gui/event_handlers.py`

Current behavior:
- `_export_to_dnp()` inserts candidate `Data_Normalization_project_v2/src`
  directories into `sys.path` at runtime before importing the bridge adapter.
- `_launch_dnp()` separately discovers and launches the external project from a
  Desktop-relative path.

Status:
- Completed in `feature/cross-project-bootstrap-boundaries`.

Implemented:
- Added `bootstrap_paths.find_dnp_src()` / `ensure_dnp_src_on_path()` /
  `find_dnp_main_module()`.
- Added `find_dnp_bridge_module()` / `ensure_dnp_bridge_on_path()` so export
  discovery verifies the bridge adapter module, not just the package root.
- Export and launch now share the same discovery policy.
- Added env overrides:
  - `MSPTK_DNP_SRC`
  - `MSPTK_DNP_PROJECT_ROOT`
- Added tests for:
  - "bridge project not found"
  - "bridge path found via override"
  - "package found but bridge adapter missing"

Remaining:
- Decide whether DNP launch should eventually move to an explicit configured
  project root instead of layout discovery.

### 2. Bootstrap path policy for `ms-core`

Files to review:
- `src/ms_preprocessing/bootstrap_paths.py`

Current behavior:
- The toolkit searches upward for `ms-core/src`, including worktree-specific
  layouts, and mutates `sys.path` at import time.

Status:
- Partially completed in `feature/cross-project-bootstrap-boundaries`.

Implemented:
- Added explicit env overrides:
  - `MSPTK_MS_CORE_SRC`
  - `MSPTK_MS_CORE_ROOT`
- Added `BootstrapResolution` so bootstrap decisions are observable in tests.
- Added a clearer bootstrap error path when no local `ms-core` checkout is found
  and `ms_core` is not already importable from the Python environment.
- Kept current supported layout probes as fallback after explicit overrides.
- Added tests covering override paths, path insertion behavior, duplicate-path
  avoidance, and the "missing vs preinstalled module" split.

Remaining:
- Confirm whether import-time path mutation should remain implicit or move to a
  clearer bootstrap step.
- Verify the fallback layout probes against the actual target machine layouts
  and trim any unsupported search patterns.

### 3. Adapter/runtime contract with `ms-core`

Files to review:
- `src/ms_preprocessing/adapters/*.py`
- `ms-core` processor return contracts

Current behavior:
- Application adapters normalize `ms-core` results into
  `ms_preprocessing.utils.results.ProcessingResult`.
- This branch only fixed local handoff persistence behavior.

Status:
- Partially completed in `feature/cross-project-bootstrap-boundaries`.

Implemented:
- Added cross-repo adapter contract tests that pin the current `ms-core`
  metadata shapes consumed by toolkit adapters.
- Covered the current contract for:
  - `DataOrganizer` -> `sample_info`
  - `DuplicateRemover` -> row-marking metadata
  - `FeatureFilter` -> `deleted_features` normalization and row-marking metadata
  - `ISTDMarker` -> row-marking metadata

Remaining:
- Reconfirm which fields from `ms-core` metadata are intended to be long-term
  stable and document them explicitly.
- Decide whether adapter success should ever depend on cache/handoff artifacts
  as a shared cross-repo contract rather than a toolkit-only choice.

### 4. Release/version coordination across repositories

Files to review:
- `pyproject.toml`
- `src/ms_preprocessing/__init__.py`
- `ms-core` release notes or tags if version coupling exists

Status:
- Clarified current state in `feature/cross-project-bootstrap-boundaries`.

Current state:
- No repo-local evidence currently requires toolkit version bumps to match
  `ms-core` package version bumps.
- The strongest compatibility boundary today is the checked-in `ms-core`
  submodule pointer, not a shared semantic version number.

Remaining:
- If any non-submodule deployment flow depends on a sibling `ms-core` checkout,
  document how compatibility should be validated there.
- If a release pairing rule is later introduced, add it to release
  instructions and CI notes rather than relying on convention.

## Suggested Order

1. Recheck import-time bootstrap behavior for `ms-core`
2. Decide whether non-submodule deployments need a documented compatibility
   check against sibling `ms-core` checkouts

## Exit Criteria

- Cross-project discovery paths are explicit and testable.
- Runtime imports no longer depend only on implicit Desktop-relative
  assumptions.
- Any shared contract with `ms-core` or DNP bridge code is documented and
  covered by at least one integration test.
