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
- Export and launch now share the same discovery policy.
- Added env overrides:
  - `MSPTK_DNP_SRC`
  - `MSPTK_DNP_PROJECT_ROOT`
- Added tests for:
  - "bridge project not found"
  - "bridge path found via override"

Remaining:
- Reconfirm whether DNP bridge import should validate adapter-module presence
  instead of package-level presence only.
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
- Kept current supported layout probes as fallback after explicit overrides.
- Added tests covering both override paths.

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

Follow-up work:
- Reconfirm which fields from `ms-core` metadata are guaranteed stable.
- Decide whether adapter success should ever depend on cache/handoff artifacts.
- Add integration coverage that pins the expected metadata contract across both
  repositories.

### 4. Release/version coordination across repositories

Files to review:
- `pyproject.toml`
- `src/ms_preprocessing/__init__.py`
- `ms-core` release notes or tags if version coupling exists

Follow-up work:
- Confirm whether toolkit and `ms-core` version bumps need explicit pairing.
- If they do, document the pairing rule in release instructions and CI notes.

## Suggested Order

1. Recheck import-time bootstrap behavior for `ms-core`
2. Cross-repo adapter metadata contract tests
3. Release/version coordination notes

## Exit Criteria

- Cross-project discovery paths are explicit and testable.
- Runtime imports no longer depend only on implicit Desktop-relative
  assumptions.
- Any shared contract with `ms-core` or DNP bridge code is documented and
  covered by at least one integration test.
