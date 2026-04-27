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

Testing policy source of truth:

- `docs/TESTING.md`

Use that document for responsibility boundaries, focused commands, GUI smoke
checks, root hygiene, and when to run `ms-core/tests`.
Top-level pytest marker assignment is centralized in `tests/testing_markers.py`;
update that mapping and `tests/test_testing_markers.py` when adding marker-owned
test files.

Default top-level full suite:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

Do not merge without fresh verification evidence.

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

## ms-core Bump SOP

每次需要更新 ms-core 版本時，按以下步驟操作：

### ms-core 變更（先做）

```bash
# 1. 在 ms-core repo 建立 feature/fix branch 開發
cd ms-core
git checkout -b fix/<description>
# ... 開發、測試、commit ...
git push origin fix/<description>

# 2. GitHub 上開 PR → 等 CI → merge 進 master

# 3. 若有 public API 變動，打 version tag
git checkout master && git pull
git tag -a v0.X.Y -m "v0.X.Y: <說明>"
git push origin v0.X.Y
```

**Version bump 規則：**

| 變更類型 | Bump |
|----------|------|
| 新增 public method（向後相容） | patch v0.x.y+1 |
| 改變 public method 簽名 | minor v0.x+1.0 |
| 移除 public method | minor v0.x+1.0 |
| 只改 private / 內部邏輯 | 不強制 tag |

### toolkit 變更（後做）

```powershell
# 4. 在 toolkit 建立 fix branch
Set-Location <toolkit-root>
git checkout -b fix/<description>

# 5. 更新 submodule 到新 tag
Set-Location ms-core
git fetch --tags
git checkout v0.X.Y
Set-Location ..
git add ms-core

# 6. 改 toolkit 代碼（若有）→ 跑測試 → commit → PR
$env:PYTHONPATH='ms-core/src'
uv run pytest tests/ -q --tb=short -x
git commit -m "chore: bump ms-core to v0.X.Y

ms-core changes:
- <ms-core 這次改了什麼>

Toolkit changes:
- <toolkit 對應改了什麼，若有>"
```

### DNP 版本策略

- DNP 獨立固定自己使用的 ms-core tag，與 toolkit 可以不同步
- ms-core minor bump（破壞性 API 變更）時，在 toolkit PR description 標記「⚠️ DNP 需同步升級」

## Hygiene Rules

- **測試暫存一律走 repo fixtures**：使用 `tests/conftest.py` 的 `tmp_path`、`tmp_path_factory`、`project_temp_dir` 或 `temp_dir`，禁止用 `Path.cwd()` 產生暫存
- **`tests/` 是原始碼，`build/pytest/` 是 runtime 暫存根**，兩者不同
- **`tests/` 下只放 `.py` 檔案**，測試用的固定資料放 `tests/fixtures/`
- 清理：使用 `scripts/clean_local_artifacts.ps1`

### Temp Path Source Of Truth

- Current repo-local pytest temp root: `build/pytest/tmp-fixtures/`
- Use the fixtures in `tests/conftest.py` instead of writing temp paths from `Path.cwd()`
- Routine cleanup command: `powershell -ExecutionPolicy Bypass -File scripts\clean_local_artifacts.ps1`

## Key Commands

```powershell
# Run tests
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x

# Build exe locally
pyinstaller ms-preprocessing.spec --clean --noconfirm

# Check version
python -c "from ms_preprocessing import __version__; print(__version__)"
```
