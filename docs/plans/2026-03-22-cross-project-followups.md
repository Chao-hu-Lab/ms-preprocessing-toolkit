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

Follow-up work:
- Define a single discovery strategy for the DNP project root.
- Replace ad-hoc `sys.path.insert()` calls with one tested helper.
- Decide whether bridge discovery should come from config/env vars instead of
  Desktop-relative conventions.
- Add tests for "bridge project not found" and "bridge path found via override".

### 2. Bootstrap path policy for `ms-core`

Files to review:
- `src/ms_preprocessing/bootstrap_paths.py`

Current behavior:
- The toolkit searches upward for `ms-core/src`, including worktree-specific
  layouts, and mutates `sys.path` at import time.

Follow-up work:
- Confirm the supported checkout layouts and remove any accidental path probes.
- Decide whether import-time path mutation should remain implicit or move to a
  clearer bootstrap step.
- Verify the behavior against real multi-worktree usage on the target machines.

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

1. DNP bridge discovery and override policy
2. `ms-core` bootstrap path policy
3. Cross-repo adapter metadata contract tests
4. Release/version coordination notes

## Exit Criteria

- Cross-project discovery paths are explicit and testable.
- Runtime imports no longer depend on implicit Desktop-relative assumptions.
- Any shared contract with `ms-core` or DNP bridge code is documented and
  covered by at least one integration test.
