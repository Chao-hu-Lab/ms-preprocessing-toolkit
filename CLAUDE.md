# MS Preprocessing Toolkit - Development Guide

## Project Structure

- **ms-core/** — git submodule, core processing logic (separate repo: bosschen0429/ms-core)
- **src/ms_preprocessing/** — toolkit GUI, CLI, and wrappers
- **tests/** — pytest test suite (run with `PYTHONPATH=ms-core/src`)

## Text And UI Copy Rules

- Treat all repository text files as UTF-8 by default, especially Python source, Markdown, config files, and any file that contains localized UI text.
- Preserve Chinese and other non-ASCII user-facing text as UTF-8 source-of-truth. Do not save localized text files in ANSI, Big5, or editor-default legacy encodings.
- Keep UI copy cleanup isolated from layout, styling, and behavior changes unless the task explicitly requires them together.
- Before editing localized strings, confirm the file reads correctly as UTF-8. If the file is already mojibake, repair the encoding or file readability first; do not patch new wording into corrupted text.
- For visible GUI text, update the source-of-truth layer first, then align downstream copies. Typical order is: shared base widgets, config/constants, event-handler messages, step widgets, tests.
- Do not rewrite scientific or workflow rule descriptions from memory when a report, design note, or commit history exists. Trace the current wording back to the latest authoritative source before updating the GUI copy.
- On Windows and CustomTkinter surfaces, default to plain-text button labels. Introduce icons, emoji, or special glyphs only after confirming stable rendering on the target platform and font stack.
- After touching localized or user-visible text, inspect the edited files as explicit UTF-8 text; terminal rendering alone is not sufficient evidence.
- After touching localized or user-visible text, scan the edited files for replacement characters or suspicious `??` placeholders, then run the narrowest relevant GUI/text regression tests.
- If the change touches shared GUI layers such as `layout.py`, `base_widget.py`, `event_handlers.py`, shared style/config modules, or workflow labels, run a minimal GUI smoke check that covers startup, step switching, action-button visibility, and primary step titles/descriptions.

## Branch Strategy

| Branch Type | Naming | Purpose |
|-------------|--------|---------|
| `master` | main branch | Merge/PR only, NO direct development |
| `feature/*` | feature branches | New features |
| `fix/*` | fix branches | Bug fixes |
| `chore/*` | chore branches | CI, deps, docs |

Use git worktree for isolation (`.worktrees/` is already in `.gitignore`):

```bash
git worktree add .worktrees/<branch-name> -b <type>/<branch-name>
```

## Pre-flight Check (MANDATORY)

Before ANY development work, always run `git status` to confirm:

- You are on the correct branch (NOT `master` for development)
- Working tree is clean — no uncommitted or untracked changes
- If dirty: commit, stash, or discard before proceeding

## Testing

Run the full test suite before considering work complete:

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

All 82+ tests must pass. No merging without passing tests.

## Release Flow

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

## Hygiene Rules

- **測試暫存一律在 `.tmp/` 下**：使用 `conftest.py` 的 `project_temp_dir` fixture，禁止用 `Path.cwd()` 產生暫存
- **`tests/` 是原始碼，`.tmp/tests/` 是 runtime 暫存**，兩者不同
- **`tests/` 下只放 `.py` 檔案**，測試用的固定資料放 `tests/fixtures/`
- 清理：`find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; rm -rf .tmp/ .pytest_cache/`

### Temp Path Source Of Truth

- Current repo-local pytest temp root: `build/pytest/tmp-fixtures/`
- Use the fixtures in `tests/conftest.py` instead of writing temp paths from `Path.cwd()`
- Routine cleanup command: `powershell -ExecutionPolicy Bypass -File scripts\clean_local_artifacts.ps1`

## Key Commands

```bash
# Run tests
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x

# Build exe locally
pyinstaller ms-preprocessing.spec --clean --noconfirm

# Check version
python -c "from ms_preprocessing import __version__; print(__version__)"
```
