---
name: ms-quality-gate
description: Run standardized testing and code-review workflows for the MS preprocessing toolkit. Use when asked to do comprehensive project checks, smoke tests, regression verification, or severity-ranked code review findings with file/line references.
---

# MS Quality Gate

Run deterministic quality checks and structure review output for this repository.

Before choosing test commands, read `docs/TESTING.md`. It is the source of truth
for test ownership, focused verification scope, GUI smoke checks, root hygiene,
and when to run `ms-core/tests`.

## Quick Start

- Run full quality gate:
  - `powershell -ExecutionPolicy Bypass -File "<path-to-skill>/scripts/run_quality_checks.ps1"`
- Run fast gate (compile/version/smoke only; skips advisory ruff):
  - `powershell -ExecutionPolicy Bypass -File "<path-to-skill>/scripts/run_quality_checks.ps1" -Fast`
- Collect review context snapshot:
  - `powershell -ExecutionPolicy Bypass -File "<path-to-skill>/scripts/review_snapshot.ps1"`

## Workflow

1. Run `run_quality_checks.ps1` first to detect hard blockers (syntax, startup, tests).
2. If failures appear, fix blockers before deeper review.
3. Run `review_snapshot.ps1` to gather risk signals (`TODO`, broad `except`, placeholder `pass`).
4. Review high-risk modules manually with file+line references.
5. Report findings by severity:
   - `Critical`: app cannot start, data corruption, hard crash.
   - `High`: wrong results, major regression risk, broken core workflow.
   - `Medium`: reliability/performance/maintainability risks.
   - `Low`: style/readability or minor hardening opportunities.
6. If no findings exist, state that explicitly and list residual testing gaps.

## Output Requirements

- Always include concrete file paths with 1-based line references.
- Keep findings first; summaries second.
- For review format details, read:
  - `references/review-checklist.md`
