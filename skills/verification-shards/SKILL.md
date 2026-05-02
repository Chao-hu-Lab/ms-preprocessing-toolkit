---
name: verification-shards
description: Use when selecting or running focused pytest verification shards for this repository. This skill follows docs/TESTING.md as the source of truth and is appropriate for smoke, adapter, GUI, integration, marker, full-suite, and ms-core verification decisions.
---

# Verification Shards

## Purpose

Select the narrowest sufficient verification command for a change in this
repository. This skill is a thin execution helper over `docs/TESTING.md`; if the
two disagree, `docs/TESTING.md` wins.

Use this skill for:

- choosing a smoke / adapter / GUI / integration / perf shard
- validating pytest marker ownership changes
- deciding when to run `ms-core/tests/`
- reporting verification evidence after a code, docs, or release change

Do not use it as a separate quality policy. Keep test ownership and expansion
rules in `docs/TESTING.md`.

## Workflow

1. Read `docs/TESTING.md` before selecting tests.
2. Inspect the changed files with `git status --short` and, if needed, `git diff --stat`.
3. Map touched files to the change-to-test matrix in `docs/TESTING.md`.
4. Run the narrowest sufficient shard first.
5. Expand only when the touched surface or failure risk justifies it.
6. Report the exact commands and outcomes. If a check was skipped, state why.

## Common Commands

PowerShell from the toolkit repo root:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m smoke -v --tb=short
```

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m adapter -v --tb=short
```

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m gui -v --tb=short
```

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m integration -v --tb=short
```

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

For `ms-core/` changes:

```powershell
Push-Location ms-core
python -m pytest tests/ -v --tb=short -x
Pop-Location
```

## Script Helper

For repeatable local runs, use:

```powershell
powershell -ExecutionPolicy Bypass -File skills\verification-shards\scripts\run_verification_shard.ps1 -Shard smoke
```

Supported shards:

- `smoke`
- `adapter`
- `gui`
- `integration`
- `perf`
- `markers`
- `collect`
- `full`
- `ms-core`

## Output

Summarize verification with:

- shard or test file
- exact command
- pass/fail/skip
- any residual risk or untested surface
