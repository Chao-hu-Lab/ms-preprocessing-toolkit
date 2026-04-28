# ms-core Sequence

## Inspect State

```bash
git status
git -C ms-core status
git -C ms-core branch --show-current
```

## Commit In ms-core First

```powershell
git -C ms-core add <files>
git -C ms-core commit -m "fix: ..."
git -C ms-core push origin <branch>
```

## Update Pointer In Top-Level Repo

```powershell
git add ms-core
git add <top-level-files>
git commit -m "fix: bump ms-core for <reason>"
git push origin <branch>
```

## Land PRs In Dependency Order

Open and merge in this order:

1. `ms-core` PR for the core commit.
2. Top-level toolkit PR that updates the `ms-core` pointer.

If the `ms-core` PR is stacked on another core branch, land the lower stack first. The top-level toolkit PR must wait until its pointed `ms-core` SHA is reachable from the `ms-core` target branch.

Before merging the top-level PR, run from the top-level repo:

```powershell
$coreSha = git rev-parse HEAD:ms-core
Push-Location ms-core
git fetch origin
git merge-base --is-ancestor $coreSha origin/master
$isLanded = $LASTEXITCODE -eq 0
Pop-Location
if (-not $isLanded) { throw "Block merge: top-level ms-core pointer is not on ms-core origin/master" }
```

## Useful Checks

```powershell
git -C ms-core rev-parse --short HEAD
git diff --submodule
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

## Common Failure Modes

- `ms-core` commit exists only locally
  - fix by pushing `ms-core` first
- top-level repo points to the wrong submodule SHA
  - fix by restaging `ms-core` after checking out the intended submodule commit
- top-level PR points at an `ms-core` SHA from an unmerged or stacked core PR
  - fix by landing the `ms-core` PR stack first, then merging the toolkit PR
- coordinated fix tested without `$env:PYTHONPATH='ms-core/src'`
  - rerun verification with the correct environment
