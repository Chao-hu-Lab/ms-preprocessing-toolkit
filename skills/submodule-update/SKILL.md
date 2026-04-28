---
name: submodule-update
description: Use when a task changes ms-core or the top-level repository must point at a new ms-core commit, especially for coordinated fixes spanning both repositories or when the correct submodule commit and push order matters.
---

# Submodule Update

## Overview

Handle coordinated changes between the top-level toolkit repository and `ms-core/` without leaving the repositories out of sync. Use this skill whenever `ms-core` code is modified or the submodule pointer needs to advance safely.

This skill covers both:

- commit/push ordering while developing
- PR/merge ordering while landing stacked submodule work

For test selection and verification scope, read the repo root's
`docs/TESTING.md` first.

## When To Use

Use this skill when:

- files under `ms-core/` are edited
- a top-level change depends on new behavior in `ms-core`
- the user asks to commit or push submodule work
- the correct push order matters
- the user asks to open, review, merge, or land a branch that updates `ms-core`

Do not use this skill for top-level-only changes.

## Workflow

1. Inspect both repositories before editing.
   - top-level `git status`
   - `git -C ms-core status`
2. Treat `ms-core` as its own repository.
   - create or use the appropriate branch inside `ms-core`
   - make and verify the `ms-core` change there first
3. Commit the `ms-core` change inside the submodule repository.
4. Push the `ms-core` branch or target branch before touching the top-level pointer commit.
5. Return to the top-level repo.
6. Update the submodule pointer with `git add ms-core`.
7. Stage any top-level files that depend on the new submodule state.
8. Run the relevant top-level verification command with `PYTHONPATH=ms-core/src`.
9. Commit the top-level repo change.
10. Push the top-level repo only after the submodule commit is already reachable remotely.

## PR And Merge Workflow

When a branch updates the `ms-core` pointer, landing has a strict order:

1. Open the `ms-core` PR first.
2. Open the top-level toolkit PR second.
3. Before merging the top-level PR, verify the top-level `ms-core` pointer SHA is already contained in the `ms-core` target branch.
4. If the `ms-core` PR is stacked on another `ms-core` PR, merge or rebase the lower stack first.
5. Merge the `ms-core` PR.
6. Update or confirm the top-level PR points at the landed `ms-core` SHA.
7. Merge the top-level toolkit PR last.

Use this check from the top-level repo before merging the toolkit PR:

```powershell
$coreSha = git rev-parse HEAD:ms-core
Push-Location ms-core
git fetch origin
git merge-base --is-ancestor $coreSha origin/master
$isLanded = $LASTEXITCODE -eq 0
Pop-Location
if (-not $isLanded) { throw "Block merge: top-level ms-core pointer is not on ms-core origin/master" }
```

If this check fails, do not merge the top-level PR. Land the `ms-core` stack first, then refresh the top-level pointer if needed.

## Hard Rules

- Never leave a top-level commit pointing at an unpushed `ms-core` commit.
- Never describe a coordinated change as complete if only one repository was pushed.
- Never merge a top-level PR whose `ms-core` pointer is not already reachable from the `ms-core` target branch.
- Never merge the toolkit PR before the `ms-core` PR stack it depends on has landed.
- If `git` reports safe-directory or auth issues inside `ms-core`, report the exact blocker and stop.
- When the user asks for one commit "for everything", remember that `ms-core` still needs its own commit first.

## Verification

For top-level validation, prefer:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

For submodule coordination, confirm:

- `git -C ms-core rev-parse --short HEAD`
- top-level `git diff --submodule`
- remote push status for both repositories
- `git merge-base --is-ancestor <top-level-ms-core-sha> origin/master` from inside `ms-core`

## Reference Files

- For exact command order and common failure cases, read:
  - `references/ms-core-sequence.md`

## Output

When reporting status, separate:

- `ms-core` commit SHA and push state
- top-level commit SHA and push state
- whether the top-level repo now points at the intended submodule commit
- whether the `ms-core` pointer has landed on the `ms-core` target branch before toolkit merge
