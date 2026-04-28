# Pre-Merge Checklist

Use PowerShell from the top-level toolkit repository or the active worktree.

## Local State

```powershell
git status --short
git branch --show-current
git rev-parse --short HEAD

git -C ms-core status --short
git rev-parse HEAD:ms-core
git -C ms-core rev-parse HEAD
```

Expected:

- branch is not `master`
- both worktrees are clean unless the user is explicitly still editing
- `git rev-parse HEAD:ms-core` equals `git -C ms-core rev-parse HEAD`

## Submodule Landing Gate

Run this when the top-level branch updates the `ms-core` pointer.

```powershell
$coreSha = git rev-parse HEAD:ms-core
Push-Location ms-core
git fetch origin
git merge-base --is-ancestor $coreSha origin/master
$isLanded = $LASTEXITCODE -eq 0
Pop-Location
if (-not $isLanded) { throw "Block merge: top-level ms-core pointer is not on ms-core origin/master" }
```

If this fails, do not merge the toolkit PR. Merge or rebase the `ms-core` stack first, then update or confirm the top-level pointer.

## CI Gate

Use GitHub PR checks for the current PR head. Required checks must be `completed` and `success`.

When using GitHub MCP, fetch:

- PR metadata: number, head SHA, base branch, mergeability
- check runs for the PR head
- review threads

When using `gh`, prefer:

```powershell
gh pr view --json number,url,headRefName,headRefOid,baseRefName,mergeStateStatus,isDraft
gh pr checks --watch=false
```

Do not rely on old green checks after pushing a new commit.

## Review Thread Gate

Fetch thread-aware review comments. Flat comments are not enough because they do not reliably show whether comments are outdated or resolved.

Classify threads:

- blocker: unresolved, not outdated, actionable code/test change
- non-blocker: resolved
- non-blocker: outdated after a newer commit
- informational: summary comments, praise, or suggestions that do not request a change

Do not reply to or resolve GitHub threads unless the user explicitly asks.

## Verification Gate

Read `docs/TESTING.md` before choosing tests.

Minimum expected evidence:

- top-level workflow/export/IO changes: `python -m pytest -m integration -v --tb=short`
- GUI controller/widget/session changes: `python -m pytest -m gui -v --tb=short`
- adapter or public API bridge changes: `python -m pytest -m adapter -v --tb=short`
- smoke/import/package sanity: `python -m pytest -m smoke -v --tb=short`
- `ms-core/` changes: run `python -m pytest tests/ -v --tb=short -x` from inside `ms-core`

Use:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest -m smoke -v --tb=short
python -m pytest -m integration -v --tb=short
```

## Report Format

```text
Merge Quality Gate: PASS | BLOCKED | PASS WITH RISKS

Top-level:
- branch:
- head:
- worktree:

ms-core:
- checked-out head:
- top-level pointer:
- pointer pushed:
- pointer landed on target:

GitHub:
- PR:
- draft:
- merge state:
- CI:
- review threads:

Verification:
- commands run:
- gaps:

Decision:
- merge allowed:
- required next action:
```
