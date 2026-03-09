# Git Submodule + GitHub Actions 部署計畫

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 讓 ms-preprocessing-toolkit 能透過 git submodule 攜帶 ms-core，並透過 GitHub Actions 自動執行 CI 測試與打包 Windows .exe。

**Architecture:**
1. 將 `ms-core` 加入為 git submodule（放在 `ms-preprocessing-toolkit/ms-core/`），`bootstrap_paths.py` 現有的路徑搜尋邏輯會自動在 toolkit root 找到它，不需修改核心邏輯。
2. GitHub Actions CI (`ci.yml`) 在每次 push/PR 執行 pytest，checkout 時帶 `submodules: recursive`。
3. GitHub Actions Build (`build.yml`) 在 tag `v*` 觸發，用 PyInstaller 打包 Windows `.exe`，上傳為 Release asset。

**Tech Stack:** Git Submodule, GitHub Actions, PyInstaller, customtkinter, pytest

---

## 重要前置知識

### 為什麼 bootstrap_paths.py 不用改？

`bootstrap_paths.py:7-36` 的搜尋邏輯從 anchor（`__init__.py` 所在位置）向上爬升父目錄，每層都檢查 `base / "ms-core"`。

路徑爬升順序（以 `__init__.py` 為起點）：
```
src/ms_preprocessing/__init__.py   → 不存在 ms-core
src/ms_preprocessing/              → 不存在 ms-core
src/                               → 不存在 ms-core
ms-preprocessing-toolkit/          → ✅ 找到 ms-core (submodule 在此!)
MS Data process package/           → 會找到 sibling ms-core (開發機才有)
```

Submodule 在第 4 層就被找到，優先於 sibling repo，**無需修改**。

### PyInstaller 的動態 sys.path 問題

PyInstaller 靜態分析時不執行 `bootstrap_paths.py`，所以找不到 `ms_core.*`。
解法：在 spec 的 `pathex` 明確加上 `ms-core/src`，讓 PyInstaller 分析時能看到它。

---

## Task 1：加入 git submodule

**Files:**
- Create: `.gitmodules`（git 自動產生）
- Create: `ms-core/`（submodule checkout，git 管理）

**Step 1: 執行 submodule add 指令**

```bash
cd "path/to/ms-preprocessing-toolkit"
git submodule add https://github.com/bosschen0429/ms-core.git ms-core
```

Expected: 產生 `.gitmodules` 檔，`ms-core/` 目錄出現，內有 ms-core 的程式碼。

**Step 2: 驗證目錄結構正確**

```bash
ls ms-core/src/ms_core/
```

Expected: 看到 `__init__.py`、`preprocessing/`、`utils/` 等目錄。

**Step 3: 驗證 bootstrap 現在找得到 submodule**

```bash
python -c "
from pathlib import Path
from src.ms_preprocessing.bootstrap_paths import find_ms_core_src
result = find_ms_core_src(Path('src/ms_preprocessing/__init__.py').resolve())
print(result)
assert 'ms-core' in str(result), f'Expected ms-core in path, got {result}'
print('OK: bootstrap找到', result)
"
```

Expected: 輸出包含 `ms-core` 的路徑（可能是 submodule 或原本的 sibling，兩者都算找到）。

**Step 4: Commit**

```bash
git add .gitmodules ms-core
git commit -m "feat: add ms-core as git submodule for portable deployment"
```

---

## Task 2：新增 submodule 情境的 bootstrap 測試

**Files:**
- Modify: `tests/test_bootstrap_paths.py`

**Step 1: 閱讀現有測試**

讀 `tests/test_bootstrap_paths.py`，目前只測試「sibling + worktree」的情境。

**Step 2: 新增 submodule 情境測試**

在 `tests/test_bootstrap_paths.py` 末尾加入：

```python
def test_find_ms_core_src_finds_submodule_at_toolkit_root(tmp_path):
    """When ms-core is a git submodule inside the toolkit, bootstrap should find it."""
    # Simulate: ms-preprocessing-toolkit/
    #               ms-core/src/ms_core/   ← submodule layout
    #               src/ms_preprocessing/  ← toolkit source
    toolkit_root = tmp_path / "ms-preprocessing-toolkit"
    submodule_src = toolkit_root / "ms-core" / "src"
    (submodule_src / "ms_core").mkdir(parents=True, exist_ok=True)

    # anchor = toolkit_root/src/ms_preprocessing (simulates __init__.py location)
    anchor = toolkit_root / "src" / "ms_preprocessing"
    anchor.mkdir(parents=True, exist_ok=True)

    result = find_ms_core_src(anchor)
    assert result == submodule_src, f"Expected submodule src at {submodule_src}, got {result}"


def test_find_ms_core_src_submodule_takes_priority_over_sibling(tmp_path):
    """Submodule (closer in dir tree) should win over sibling repo."""
    toolkit_root = tmp_path / "MS Data process package" / "ms-preprocessing-toolkit"

    # Submodule inside toolkit
    submodule_src = toolkit_root / "ms-core" / "src"
    (submodule_src / "ms_core").mkdir(parents=True, exist_ok=True)

    # Sibling repo (further up the tree)
    sibling_src = tmp_path / "MS Data process package" / "ms-core" / "src"
    (sibling_src / "ms_core").mkdir(parents=True, exist_ok=True)

    anchor = toolkit_root / "src" / "ms_preprocessing"
    anchor.mkdir(parents=True, exist_ok=True)

    result = find_ms_core_src(anchor)
    assert result == submodule_src, (
        f"Submodule should take priority over sibling; got {result}"
    )
```

**Step 3: 執行新測試確認通過**

```bash
pytest tests/test_bootstrap_paths.py -v
```

Expected: 全部 PASS（包含舊的 worktree 測試和 2 個新測試）。

**Step 4: Commit**

```bash
git add tests/test_bootstrap_paths.py
git commit -m "test: add submodule bootstrap discovery scenarios"
```

---

## Task 3：建立 GitHub Actions CI 工作流程

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: 建立目錄**

```bash
mkdir -p .github/workflows
```

**Step 2: 建立 ci.yml**

建立 `.github/workflows/ci.yml`，內容如下：

```yaml
name: CI

on:
  push:
    branches: ["master", "main"]
  pull_request:
    branches: ["master", "main"]

jobs:
  test:
    runs-on: windows-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest tests/ -v --tb=short -x
        env:
          PYTHONPATH: ms-core/src
```

**Step 3: 在本機驗證 pytest 仍全過**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: 所有測試 PASS，無 FAIL。

**Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions CI workflow with submodule support"
```

---

## Task 4：建立 PyInstaller spec 檔

**Files:**
- Create: `ms-preprocessing.spec`

**Step 1: 安裝 PyInstaller（開發環境）**

```bash
pip install pyinstaller
```

**Step 2: 確認 customtkinter 位置**

```bash
python -c "import customtkinter; print(customtkinter.__path__[0])"
```

記下輸出路徑，用於 spec 的 datas。

**Step 3: 建立 ms-preprocessing.spec**

建立 `ms-preprocessing.spec`，內容如下：

```python
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
import customtkinter

block_cipher = None

# ms-core submodule src (讓 PyInstaller 靜態分析時能看到 ms_core.*)
ms_core_src = str(Path("ms-core/src").resolve())

a = Analysis(
    ["src/ms_preprocessing/main.py"],
    pathex=[ms_core_src],
    binaries=[],
    datas=[
        # customtkinter 需要帶入主題檔案
        (customtkinter.__path__[0], "customtkinter/"),
    ],
    hiddenimports=[
        "customtkinter",
        "PIL._tkinter_finder",
        "openpyxl.cell._writer",
        "ms_core.preprocessing.data_organizer",
        "ms_core.preprocessing.istd_marker",
        "ms_core.preprocessing.duplicate_remover",
        "ms_core.preprocessing.ms_quality_filter",
        "ms_core.utils.file_handler",
        "ms_core.preprocessing.settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "sklearn",
        "statsmodels",
        "seaborn",
        "plotly",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ms-preprocessing",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # False = 無黑色終端機視窗（GUI 模式）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,       # 可改為 "assets/icon.ico"
)
```

**Step 4: 本機測試打包（可選，需要數分鐘）**

```bash
pyinstaller ms-preprocessing.spec --clean
```

Expected: `dist/ms-preprocessing.exe` 出現，無 ERROR（WARNING 可忽略）。

**Step 5: 測試 .exe 能啟動（若有 GUI 環境）**

```bash
dist/ms-preprocessing.exe --version
```

Expected: `MS Preprocessing Toolkit v1.0.0`

**Step 6: Commit**

```bash
git add ms-preprocessing.spec
git commit -m "build: add PyInstaller spec for Windows executable packaging"
```

---

## Task 5：建立 GitHub Actions Build/Release 工作流程

**Files:**
- Create: `.github/workflows/build.yml`

**Step 1: 建立 build.yml**

建立 `.github/workflows/build.yml`，內容如下：

```yaml
name: Build Windows Executable

on:
  push:
    tags:
      - "v*.*.*"
  workflow_dispatch:
    inputs:
      upload_artifact:
        description: "Upload as artifact (for testing without a tag)"
        type: boolean
        default: true

jobs:
  build-windows:
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pyinstaller

      - name: Build executable
        run: |
          pyinstaller ms-preprocessing.spec --clean --noconfirm
        env:
          PYTHONPATH: ms-core/src

      - name: Verify executable
        run: |
          dist\ms-preprocessing.exe --version

      - name: Upload artifact (testing / manual runs)
        uses: actions/upload-artifact@v4
        with:
          name: ms-preprocessing-windows
          path: dist/ms-preprocessing.exe
          retention-days: 7

      - name: Create GitHub Release
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          files: dist/ms-preprocessing.exe
          generate_release_notes: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Step 2: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: add GitHub Actions build workflow for Windows executable release"
```

---

## Task 6：更新 README（讓使用者知道如何 clone）

**Files:**
- Modify: `README.md`

**Step 1: 讀現有 README**

讀 `README.md`，找到 Installation / Getting Started 區塊。

**Step 2: 確認 clone 指令有 --recurse-submodules**

確保 README 包含以下內容（加入或更新現有 Installation 區塊）：

```markdown
## Installation

### 選項 A：直接下載執行檔（推薦給一般使用者）

從 [Releases](https://github.com/bosschen0429/ms-preprocessing-toolkit/releases) 頁面下載最新的 `ms-preprocessing.exe`，直接執行即可，無需安裝 Python。

### 選項 B：從原始碼安裝（開發者）

```bash
# 必須加 --recurse-submodules 才能一起下載 ms-core 相依套件
git clone --recurse-submodules https://github.com/bosschen0429/ms-preprocessing-toolkit.git
cd ms-preprocessing-toolkit
pip install -e .
ms-preprocessing  # 啟動 GUI
```

若已 clone 但忘記加 --recurse-submodules：
```bash
git submodule update --init --recursive
```
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with submodule clone instructions and release download"
```

---

## Task 7：推送並驗證 GitHub Actions 觸發

**Step 1: 推送所有 commits 到 GitHub**

```bash
git push origin master
```

**Step 2: 到 GitHub Actions 頁面確認 CI 觸發**

瀏覽 `https://github.com/bosschen0429/ms-preprocessing-toolkit/actions`，
確認 CI workflow 出現並通過。

**Step 3: 手動觸發 Build workflow（不需要 tag）**

在 GitHub Actions UI 中選 "Build Windows Executable" → "Run workflow" → 勾選 upload_artifact → Run。

Expected: 約 5-10 分鐘後完成，可在 Artifacts 下載 `ms-preprocessing.exe`。

**Step 4: 建立第一個正式 Release（選做）**

```bash
git tag v1.0.0
git push origin v1.0.0
```

Expected: GitHub Actions 自動觸發 build，完成後自動建立 Release 頁面並附上 .exe。

---

## 驗收清單

- [ ] `git submodule status` 顯示 ms-core submodule 已綁定
- [ ] `pytest tests/test_bootstrap_paths.py -v` 全部 PASS（含新增的 2 個測試）
- [ ] `pytest tests/ -v` 全部 PASS
- [ ] `.github/workflows/ci.yml` 在 GitHub 上顯示為綠色
- [ ] `.github/workflows/build.yml` 手動觸發後產生可下載的 `ms-preprocessing.exe`
- [ ] 下載的 `.exe` 執行 `--version` 顯示正確版本號
- [ ] README 包含正確的 `--recurse-submodules` clone 指令
