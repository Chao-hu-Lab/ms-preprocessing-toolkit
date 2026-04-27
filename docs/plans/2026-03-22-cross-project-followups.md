# 2026-03-22 Cross-Project Follow-Ups

## Goal

Capture the remaining review items that depend on external repositories or
cross-project runtime contracts, so they can be handled after the local-only
toolkit fixes are merged.

## Out Of Scope For This Branch

- Editing code inside `ms-core/`
- Editing code inside downstream normalization project repositories
- Changing external repository release or deployment configuration

## Follow-Up Tasks

### 1. Downstream normalization boundary

Status:
- Superseded by toolkit boundary cleanup.

Current policy:
- Toolkit stops at Step 4 final `.xlsx` export.
- Toolkit does not import, launch, or configure downstream normalization projects.
- Users hand the exported `.xlsx` to downstream tools manually after checking SampleInfo metadata.

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
- Narrowed automatic discovery to the toolkit-local `ms-core` submodule /
  submodule worktree layout.
- Treat sibling `ms-core` checkouts as dev-only env-override scenarios instead
  of an implicit runtime contract.
- Added tests covering override paths, path insertion behavior, duplicate-path
  avoidance, and the "missing vs preinstalled module" split.

Remaining:
- Confirm whether import-time path mutation should remain implicit or move to a
  clearer bootstrap step.

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
- If a release pairing rule is later introduced, add it to release
  instructions and CI notes rather than relying on convention.

## Suggested Order

1. Recheck import-time bootstrap behavior for `ms-core`

## Exit Criteria

- Cross-project discovery paths are explicit and testable.
- Runtime imports no longer depend only on implicit Desktop-relative
  assumptions.
- Any shared contract with `ms-core` or downstream handoff code is documented and
  covered by at least one integration test.
