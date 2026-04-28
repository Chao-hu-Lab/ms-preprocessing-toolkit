# Pipeline Boundary Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use this file as the umbrella map; execute the child plans listed below for implementation detail.

**Goal:** Split overloaded Step3, Step4, GUI, and CLI responsibilities into explicit internal modules while preserving the current four-step user workflow.

**Architecture:** Use one umbrella workstream rather than many small feature branches. `ms-core` owns scientific processing boundaries, while the top-level toolkit owns GUI/CLI orchestration and export boundaries. Existing public entrypoints remain compatibility facades while internals move to focused modules.

**Tech Stack:** Python, pandas, numpy, pytest, CustomTkinter, git submodule workflow for `ms-core`.

---

## Child Plans

Read these files in order:

1. `docs/plans/2026-04-28-pipeline-boundary-work-allocation.md`
2. `docs/plans/2026-04-28-pipeline-boundary-step3-core.md`
3. `docs/plans/2026-04-28-pipeline-boundary-step4-core.md`
4. `docs/plans/2026-04-28-pipeline-boundary-workflow-runner.md`
5. `docs/plans/2026-04-28-pipeline-boundary-gui-controller.md`

## Why This Is One Workstream

The goal is a large-scale responsibility split, not a series of disconnected small feature branches. Use one branch pair and checkpoint commits:

- `ms-core`: `feature/pipeline-boundary-refactor`
- toolkit: `feature/pipeline-boundary-refactor`

Because `ms-core` is a submodule, this still requires two PRs. That is a repository boundary, not a product-scope split.

## Execution Order

1. Main agent creates the umbrella worktree and branch pair.
2. Step3 core extraction can begin.
3. Step4 core extraction can run in parallel with Step3 only if write sets stay disjoint.
4. Main agent integrates and verifies all `ms-core` changes.
5. Workflow runner/CLI extraction begins after core APIs are stable.
6. GUI controller/service extraction begins after workflow runner interface is stable.
7. Main agent runs final verification and controls PR landing.

## Branch Setup

Run after the current Phase 4 branch lands:

```powershell
git fetch origin
git pull --ff-only origin master
git worktree add ".worktrees\pipeline-boundary-refactor" -b feature/pipeline-boundary-refactor
Push-Location ".worktrees\pipeline-boundary-refactor"
git submodule update --init --recursive
Push-Location ms-core
git fetch origin
git checkout -b feature/pipeline-boundary-refactor origin/master
Pop-Location
```

If this starts before Phase 4 is merged, base the umbrella branch on `feature/step1-combined-tsv-preprocessor` and mark both PRs as stacked.

## Checkpoint Commits

Use this commit rhythm:

1. `ms-core`: `refactor: extract degeneracy annotation`
2. `ms-core`: `refactor: extract duplicate intensity merge policy`
3. `ms-core`: `refactor: extract feature filter decision helpers`
4. toolkit: `refactor: route cli through shared workflow runner`
5. toolkit: `refactor: split gui pipeline controller services`
6. toolkit: `docs: track pipeline boundary refactor`

Do not squash during development. Checkpoint commits are the review units.

## Global Done Criteria

- Step3 degeneracy annotation and intensity merge policy have focused module tests.
- Step4 group detection, ratio calculation, gate decision, and output shaping have focused module tests.
- GUI Run All uses a controller/service layer instead of embedding workflow execution in `event_handlers.py`.
- CLI uses the same workflow runner as GUI for Step1-4 orchestration.
- `event_handlers.py`, `main.py`, `duplicate_remover.py`, and `ms_quality_filter.py` become mostly orchestration/facade files.
- Focused core, adapter, CLI, GUI, and smoke tests pass.

## Required Verification

Core:

```powershell
Push-Location ms-core
python -m pytest tests\ -v --tb=short -x
Pop-Location
```

Top-level focused:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m smoke -v --tb=short
$env:PYTHONPATH='ms-core/src'
python -m pytest -m adapter -v --tb=short
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_cli_parquet_chain.py tests\test_workflow_runner.py tests\test_workflow_export_service.py -v --tb=short
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\test_gui_event_handlers.py tests\test_gui_pipeline_controller.py tests\test_gui_async_task_runner.py -v --tb=short
```

Expand to top-level full suite when GUI/workflow changes are large:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests\ -v --tb=short -x
```

## Landing Guard

Open and merge in this order:

1. `ms-core` PR.
2. toolkit PR that updates the `ms-core` pointer.

Before merging the toolkit PR:

```powershell
$coreSha = git rev-parse HEAD:ms-core
Push-Location ms-core
git fetch origin
git merge-base --is-ancestor $coreSha origin/master
$isLanded = $LASTEXITCODE -eq 0
Pop-Location
if (-not $isLanded) { throw "Block merge: top-level ms-core pointer is not on ms-core origin/master" }
```

If the guard fails, do not merge toolkit. Land the `ms-core` stack first.

