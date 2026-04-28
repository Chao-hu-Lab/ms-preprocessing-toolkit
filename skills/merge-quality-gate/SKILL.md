---
name: merge-quality-gate
description: Use before merging or marking ready a pull request in this repository, especially after CI, Copilot/code review, or ms-core submodule pointer changes. Runs a pre-merge quality gate covering clean worktrees, PR checks, unresolved review threads, test evidence, submodule landing order, and final merge readiness.
---

# Merge Quality Gate

## Overview

Run the repository pre-merge gate before landing a branch. This skill prevents the recurring failure mode where the top-level toolkit PR lands before the `ms-core` stack or where CI/review state is checked against an older commit.

Use `skills/submodule-update/SKILL.md` together with this skill when the branch changes `ms-core/` or updates the top-level submodule pointer.

## Workflow

1. Identify the active PR and exact head commit.
   - Confirm top-level branch is not `master`.
   - Run `git status --short` and `git branch --show-current`.
   - Run `git rev-parse --short HEAD`.
2. Check submodule state.
   - Run `git -C ms-core status --short`.
   - Run `git rev-parse HEAD:ms-core`.
   - Run `git -C ms-core rev-parse HEAD`.
   - If the SHAs differ, block merge until the top-level pointer and submodule checkout are reconciled.
3. Check CI on the current PR head.
   - Fetch PR checks from GitHub.
   - Verify every required check is `completed` with `success`.
   - Confirm the check suite belongs to the current head SHA, not a previous commit.
4. Check review state.
   - Fetch review threads, not only flat comments.
   - Treat unresolved non-outdated actionable threads as blockers.
   - Treat outdated threads as evidence to summarize, not blockers.
5. Check submodule landing order if the top-level PR updates `ms-core`.
   - The `ms-core` commit referenced by the top-level pointer must be pushed.
   - Before merging the top-level PR, the pointer SHA must be reachable from the `ms-core` target branch.
   - If not reachable, block merge and land the `ms-core` stack first.
6. Check local verification evidence.
   - Read `docs/TESTING.md`.
   - Confirm focused and risk-based shards were run for the touched surfaces.
   - Do not replace missing verification with CI unless the user explicitly accepts the risk.
7. Report the gate.
   - Use `PASS`, `BLOCKED`, or `PASS WITH RISKS`.
   - Include the exact top-level SHA, `ms-core` pointer SHA, CI status, review-thread status, and verification evidence.

## Blockers

Block merge when any of these are true:

- top-level worktree is dirty with uncommitted changes that belong to the PR
- `ms-core` worktree is dirty
- top-level `HEAD:ms-core` differs from the checked-out `ms-core` HEAD
- top-level pointer references an unpushed `ms-core` commit
- top-level pointer is not reachable from the `ms-core` target branch when merging toolkit
- required CI is queued, in progress, cancelled, skipped, or failed for the current head
- unresolved non-outdated review thread requests a code or test change
- verification evidence does not cover touched high-risk surfaces

## Reference

For exact PowerShell commands and report format, read:

- `references/pre-merge-checklist.md`
