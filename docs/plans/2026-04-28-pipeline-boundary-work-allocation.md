# Pipeline Boundary Work Allocation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use this file to assign subagents and prevent overlapping edits.

**Goal:** Define ownership, ordering, and handoff rules for subagents working on the pipeline boundary refactor.

**Architecture:** Subagents own disjoint write sets. The main agent owns integration, branch hygiene, submodule pointer updates, and merge ordering. Parallel work is allowed only for tasks whose output contracts do not depend on each other.

**Tech Stack:** Python, pytest, pandas, CustomTkinter, git worktrees, `ms-core` submodule workflow.

---

## Roles

### Main Agent

Owns:

- branch/worktree setup
- `ms-core` submodule coordination
- final integration and conflict resolution
- `ms-core/tests/testing_markers.py` and `ms-core/tests/test_testing_markers.py`
- top-level `tests/testing_markers.py` and `tests/test_testing_markers.py`
- top-level `ms-core` pointer commit
- PR creation, review, and merge sequencing

Does not delegate:

- submodule landing guard
- top-level pointer update
- final verification summary

### Step3 Core Subagent

Plan:

- `docs/plans/2026-04-28-pipeline-boundary-step3-core.md`

Owns:

- `ms-core/src/ms_core/preprocessing/degeneracy_annotation.py`
- `ms-core/src/ms_core/preprocessing/duplicate_intensity_merge.py`
- Step3 wrappers in `ms-core/src/ms_core/preprocessing/duplicate_remover.py`
- `ms-core/tests/test_degeneracy_annotation.py`
- `ms-core/tests/test_duplicate_intensity_merge.py`

Must not edit:

- Step4 files
- GUI files
- CLI files
- top-level adapter files
- `ms-core/tests/testing_markers.py`

### Step4 Core Subagent

Plan:

- `docs/plans/2026-04-28-pipeline-boundary-step4-core.md`

Owns:

- `ms-core/src/ms_core/preprocessing/feature_groups.py`
- `ms-core/src/ms_core/preprocessing/detection_ratios.py`
- `ms-core/src/ms_core/preprocessing/feature_filter_decisions.py`
- `ms-core/src/ms_core/preprocessing/feature_filter_output.py`
- Step4 wrappers in `ms-core/src/ms_core/preprocessing/ms_quality_filter.py`
- focused Step4 tests listed in the child plan

Must not edit:

- Step3 files
- GUI files
- CLI files
- top-level adapter files
- `ms-core/tests/testing_markers.py`

### Workflow Runner Subagent

Plan:

- `docs/plans/2026-04-28-pipeline-boundary-workflow-runner.md`

Owns:

- `src/ms_preprocessing/workflow/__init__.py`
- `src/ms_preprocessing/workflow/input_loader.py`
- `src/ms_preprocessing/workflow/workflow_runner.py`
- `src/ms_preprocessing/workflow/export_service.py`
- `src/ms_preprocessing/main.py`
- `tests/test_workflow_runner.py`
- `tests/test_workflow_input_loader.py`
- `tests/test_workflow_export_service.py`
- focused CLI tests

Must not edit:

- `src/ms_preprocessing/gui/event_handlers.py`
- `src/ms_preprocessing/gui/main_window.py`
- `ms-core/`

### GUI Controller Subagent

Plan:

- `docs/plans/2026-04-28-pipeline-boundary-gui-controller.md`

Owns:

- `src/ms_preprocessing/gui/pipeline_controller.py`
- `src/ms_preprocessing/gui/async_task_runner.py`
- `src/ms_preprocessing/workflow/combined_tsv_service.py`
- `src/ms_preprocessing/gui/event_handlers.py`
- focused GUI tests listed in the child plan

Must not edit:

- `ms-core/`
- CLI runner logic in `src/ms_preprocessing/main.py`
- workflow runner contracts except small adapter calls approved by the main agent

## Parallelism Rules

Allowed in parallel:

- Step3 Core and Step4 Core exploration and test design.
- Step3 Core and Step4 Core implementation if each subagent writes only its owned files.
- Workflow Runner test design while core work is being reviewed.

Not allowed in parallel:

- Workflow Runner implementation and GUI Controller implementation.
- Any two subagents editing `event_handlers.py`.
- Any two subagents editing `main.py`.
- Any subagent updating the submodule pointer.
- Any subagent landing or merging PRs.

## Shared File Rules

Test marker files are integration-owned:

- `tests/testing_markers.py`
- `tests/test_testing_markers.py`
- `ms-core/tests/testing_markers.py`
- `ms-core/tests/test_testing_markers.py`

Subagents must not edit these files. When a subagent adds a test file that should
be selected by `smoke`, `adapter`, `integration`, `perf`, or `serial`, it must
state the required marker decision in its handoff. The main agent updates marker
ownership after reviewing the patch and before checkpoint verification.

Workflow package ownership is split by module, not by directory:

- Workflow Runner owns `input_loader.py`, `workflow_runner.py`,
  `export_service.py`, and initial `workflow/__init__.py` exports for those
  services.
- GUI Controller owns `combined_tsv_service.py` and may request a main-agent
  `workflow/__init__.py` export update after implementation.
- The main agent owns final `workflow/__init__.py` reconciliation so package
  exports are stable and subagents do not overlap.

## Development Cadence

Each subagent works in this rhythm:

1. Read assigned child plan.
2. Confirm current branch and clean status.
3. Write the failing focused tests.
4. Run the focused tests and capture the expected failure.
5. Implement the smallest extraction that passes.
6. Run focused tests.
7. Run the child plan's compatibility tests.
8. Report changed files, commands run, and residual risks.

The main agent then:

1. Reviews the subagent patch.
2. Updates shared marker/test ownership files if needed.
3. Runs integration tests for that checkpoint.
4. Commits the checkpoint.

## Merge Integration Order

1. Integrate Step3 Core patch.
2. Integrate Step4 Core patch.
3. Run full `ms-core` suite.
4. Push `ms-core` branch.
5. Integrate Workflow Runner patch.
6. Integrate GUI Controller patch.
7. Run top-level smoke, adapter, CLI, and GUI checks.
8. Commit top-level pointer and docs.
9. Open PRs in `ms-core` first, toolkit second.

## Handoff Template

Each subagent final message should include:

```text
Scope:
- Owned files changed:
- Files intentionally not touched:

Verification:
- RED command and failure:
- GREEN command and result:
- Compatibility commands:

Risks:
- Behavior risks:
- Test gaps:
- Integration notes for main agent:
```
