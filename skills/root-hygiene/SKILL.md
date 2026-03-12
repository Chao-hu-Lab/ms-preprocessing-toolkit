---
name: root-hygiene
description: Keep the repository root clean when working on pytest, temp files, caches, or local artifacts in the MS preprocessing toolkit. Use when tests create `tmp*` folders, `.pytest*` directories, repo-local caches, or when changing test fixtures, cleanup scripts, or temp-path behavior in either the top-level repo or `ms-core`.
---

# Root Hygiene

## Overview

Use this skill to prevent temporary files, pytest artifacts, and machine-local caches from leaking into the repository root.

This repository already has a preferred pattern:

- top-level tests use repo-local helper fixtures in `tests/conftest.py`
- `ms-core` tests use matching fixtures in `ms-core/tests/conftest.py`
- ad-hoc cleanup goes through `scripts/clean_local_artifacts.ps1`

If a change touches pytest behavior, temp directories, benchmark outputs, or cache locations, follow this skill before adding more ignore rules.

## When To Use

Use this skill when:

- `git status` shows `tmp*`, `.pytest*`, `__pycache__`, or `.tmp/` clutter in the root
- tests use `TemporaryDirectory(dir=Path.cwd())` or another path that writes into the repo root
- you are adding or editing tests that need temporary files
- pytest config or temp-path behavior is changing
- you need to clean local artifacts without touching tracked files
- a task spans both the top-level repo and `ms-core` temp behavior

Do not use this skill for general cleanup unrelated to test/temp/cache behavior.

## Rules

1. Treat root clutter as a behavior problem first, not an ignore-file problem.
2. Do not introduce `TemporaryDirectory(dir=Path.cwd())` in this repository.
3. For top-level tests, prefer fixtures from `tests/conftest.py`:
   - `project_temp_root`
   - `project_temp_dir`
   - overridden `tmp_path`
4. For `ms-core` tests, prefer fixtures from `ms-core/tests/conftest.py`:
   - `project_temp_root`
   - `project_temp_dir`
5. Use `.gitignore` only as a second line of defense after fixing the write location.
6. If old temp folders remain because of local ACL damage, report that clearly instead of pretending cleanup succeeded.

## Workflow

### 1. Inspect before editing

Run:

```powershell
git status --short --branch
Get-ChildItem -Force | Where-Object { $_.Name -like 'tmp*' -or $_.Name -like '.pytest*' -or $_.Name -eq '.tmp' -or $_.Name -eq '__pycache__' }
Get-ChildItem -Force ms-core | Where-Object { $_.Name -like 'tmp*' -or $_.Name -like '.pytest*' -or $_.Name -eq '.tmp' -or $_.Name -eq '__pycache__' }
```

If the task involves temp creation, inspect:

- `tests/conftest.py`
- `ms-core/tests/conftest.py`
- `pyproject.toml`
- `ms-core/pyproject.toml`
- `scripts/clean_local_artifacts.ps1`

### 2. Fix the source of root clutter

Common fixes:

- replace `TemporaryDirectory(dir=Path.cwd())` with `project_temp_dir()`
- use the repo fixtures instead of builtin temp helpers that are unstable in this Windows environment
- route benchmark outputs and cache roots into the test-owned temp tree
- avoid re-enabling pytest cache provider unless you have a strong reason

### 3. Update ignore rules only if needed

Expected ignored local artifacts include:

- `.tmp/`
- `.pytest-local-temp/`
- `tmp*/`

Mirror ignore changes in `ms-core/.gitignore` when `ms-core` produces the same class of artifacts.

### 4. Verify with focused checks first

Top-level focused check:

```powershell
$env:PYTHONPATH='ms-core/src'; pytest tests/test_root_hygiene.py -v --tb=short
```

Top-level full check:

```powershell
$env:PYTHONPATH='ms-core/src'; pytest tests/ -v --tb=short -x
```

`ms-core` check:

```powershell
pytest ms-core/tests -v --tb=short -x
```

### 5. Clean local artifacts

Use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\clean_local_artifacts.ps1
```

This script is reliable for normal writable temp folders created after the hygiene changes.

If cleanup fails for old folders, call out the exact directories and note that local ACL state is blocking removal.

## Output Expectations

When reporting the result:

- state which files were causing root clutter
- state which fixture or path policy now owns temp creation
- include the verification commands you ran
- mention any leftover historical temp directories separately from new behavior

## Reference Files

- `tests/conftest.py`
- `tests/test_root_hygiene.py`
- `ms-core/tests/conftest.py`
- `ms-core/tests/test_root_hygiene.py`
- `scripts/clean_local_artifacts.ps1`
