# MS Preprocessing Toolkit - Development Guide

## Project Structure

- **ms-core/** — git submodule, core processing logic (separate repo: bosschen0429/ms-core)
- **src/ms_preprocessing/** — toolkit GUI, CLI, and wrappers
- **tests/** — pytest test suite (run with `PYTHONPATH=ms-core/src`)

## Development Workflow

### 0. Pre-flight Check (MANDATORY)

Before ANY development work, always run:

```bash
git status
```

- Confirm you are on the correct branch (NOT `master` for development)
- Confirm working tree is clean — no uncommitted or untracked changes
- If dirty: commit, stash, or discard before proceeding

### 1. Branch Strategy

| Branch Type | Naming | Purpose |
|-------------|--------|---------|
| `master` | main branch | Merge/PR only, NO direct development |
| `feature/*` | feature branches | New features |
| `fix/*` | fix branches | Bug fixes |
| `chore/*` | chore branches | CI, deps, docs |

### 2. Create Isolated Workspace

Use git worktree for isolation (`.worktrees/` is already in `.gitignore`):

```bash
git worktree add .worktrees/<branch-name> -b <type>/<branch-name>
```

Use the `using-git-worktrees` skill for guided setup.

### 3. Develop and Test

Run the full test suite before considering work complete:

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

All 82+ tests must pass.

### 4. Finish Branch

Use the `finishing-a-development-branch` skill to choose:
1. Merge locally to master
2. Push and create PR
3. Keep branch as-is
4. Discard

### 5. Release

1. Update version in `pyproject.toml` AND `src/ms_preprocessing/__init__.py`
2. Commit: `chore: bump version to vX.Y.Z`
3. Push to master
4. Tag: `git tag -a vX.Y.Z -m "vX.Y.Z: description"`
5. Push tag: `git push origin vX.Y.Z`
6. Build workflow auto-creates GitHub Release with `ms-preprocessing-Win-vX.Y.Z.exe`

## Submodule Rules (ms-core)

1. Make changes inside `ms-core/`
2. Commit and push in ms-core repo FIRST
3. Return to toolkit root, `git add ms-core` to update submodule reference
4. Commit in toolkit: `fix: bump ms-core for <reason>`

## Prohibited Actions

- **NO** direct development on `master`
- **NO** force push to `master`
- **NO** merging without passing tests
- **NO** skipping `git status` check before starting work

## Key Commands

```bash
# Run tests
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x

# Build exe locally
pyinstaller ms-preprocessing.spec --clean --noconfirm

# Check version
python -c "from ms_preprocessing import __version__; print(__version__)"
```
