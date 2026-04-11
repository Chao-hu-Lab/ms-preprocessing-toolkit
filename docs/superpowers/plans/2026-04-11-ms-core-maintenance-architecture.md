# ms-core 中長期維護架構 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可持續的跨 repo 維護架構：定義 ms-core public API、強制 adapter 邊界、分層測試、規範化 submodule 工作流。

**Architecture:** ms-core 暴露正式 `__all__`；toolkit 的 GUI 層只能透過 adapter 呼叫 ms-core；ruff 靜態分析強制邊界；tests 依目的分層到 `core/`、`adapters/` 兩個子目錄。

**Tech Stack:** Python 3.11+, ruff, pytest, git submodule, uv

---

## 檔案變更總覽

### ms-core repo（`ms-core/`）
| 動作 | 檔案 |
|------|------|
| Modify | `src/ms_core/preprocessing/__init__.py` |

### toolkit repo（根目錄）
| 動作 | 檔案 |
|------|------|
| Modify | `ms-core`（submodule bump） |
| Modify | `src/ms_preprocessing/adapters/data_organizer.py` |
| Modify | `src/ms_preprocessing/adapters/istd_marker.py` |
| Modify | `src/ms_preprocessing/adapters/duplicate_remover.py` |
| Modify | `src/ms_preprocessing/adapters/feature_filter.py` |
| Modify | `src/ms_preprocessing/gui/widgets/feature_filter_widget.py` |
| Modify | `pyproject.toml` |
| Move | `tests/test_data_organizer.py` → `tests/core/test_data_organizer.py` |
| Move | `tests/test_duplicate_remover.py` → `tests/core/test_duplicate_remover.py` |
| Move | `tests/test_feature_filter.py` → `tests/core/test_feature_filter.py` |
| Move | `tests/test_istd_marker.py` → `tests/core/test_istd_marker.py` |
| Move | `tests/test_adapter_data_organizer.py` → `tests/adapters/test_adapter_data_organizer.py` |
| Move | `tests/test_adapter_duplicate_remover.py` → `tests/adapters/test_adapter_duplicate_remover.py` |
| Move | `tests/test_adapter_feature_filter.py` → `tests/adapters/test_adapter_feature_filter.py` |
| Move | `tests/test_adapter_istd_marker.py` → `tests/adapters/test_adapter_istd_marker.py` |
| Move | `tests/test_adapter_runtime_contracts.py` → `tests/adapters/test_adapter_runtime_contracts.py` |
| Move | `tests/test_cross_project_adapter_contracts.py` → `tests/adapters/test_cross_project_adapter_contracts.py` |
| Create | `tests/core/__init__.py` |
| Create | `tests/adapters/__init__.py` |
| Create | `tests/test_ms_core_api_contract.py` |
| Modify | `CLAUDE.md` |

---

## Phase 1：ms-core Public API 定義

> **執行環境：** `C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core`

---

### Task 1：補 ms-core `preprocessing/__init__.py` 的 `__all__`

**Files:**
- Modify: `ms-core/src/ms_core/preprocessing/__init__.py`

- [ ] **Step 1：確認目前在正確的 branch**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
git branch --show-current
git log --oneline -3
```

預期：在 `fix/public-group-count-api` branch，最新 commit 是 `feat: expose count_analysis_groups as public API on FeatureFilter`。

- [ ] **Step 2：修改 `src/ms_core/preprocessing/__init__.py`**

將檔案內容完整替換為：

```python
"""MS-specific preprocessing — data organization, ISTD marking, deduplication, quality filtering.

Source: ms-preprocessing-toolkit
"""

from ms_core.preprocessing.data_organizer import DataOrganizer
from ms_core.preprocessing.istd_marker import ISTDMarker
from ms_core.preprocessing.duplicate_remover import DuplicateRemover
from ms_core.preprocessing.ms_quality_filter import FeatureFilter
from ms_core.preprocessing.settings import (
    DataOrganizerConfig,
    ISTDConfig,
    DuplicateRemovalConfig,
    FeatureFilterConfig,
    Settings,
)

__all__ = [
    "DataOrganizer",
    "ISTDMarker",
    "DuplicateRemover",
    "FeatureFilter",
    "DataOrganizerConfig",
    "ISTDConfig",
    "DuplicateRemovalConfig",
    "FeatureFilterConfig",
    "Settings",
]
```

- [ ] **Step 3：驗證 import 可以正常運作**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
python -c "from ms_core.preprocessing import FeatureFilter, ISTDMarker, DuplicateRemover, DataOrganizer, Settings; print('OK')"
```

預期輸出：`OK`

- [ ] **Step 4：Commit**

```bash
git add src/ms_core/preprocessing/__init__.py
git commit -m "feat: expose preprocessing package public API via __all__

Add explicit __all__ and module-level imports to preprocessing/__init__.py.
Consumers can now use:
    from ms_core.preprocessing import FeatureFilter
instead of the deep path:
    from ms_core.preprocessing.ms_quality_filter import FeatureFilter

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 2：ms-core merge + tag v0.3.0

**Files:** git operations only

- [ ] **Step 1：push 更新後的 branch**

```bash
git push origin fix/public-group-count-api
```

- [ ] **Step 2：在 GitHub 上開 PR 並 merge**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
gh pr create \
  --title "feat: expose preprocessing public API + count_analysis_groups" \
  --body "$(cat <<'EOF'
## Summary

- Add `count_analysis_groups(df)` as public method on `FeatureFilter`
- Add `__all__` to `ms_core/preprocessing/__init__.py` — consumers can now use short-form imports
- No breaking changes; all existing deep-path imports still work

## Changes

- `src/ms_core/preprocessing/ms_quality_filter.py` — new public method
- `src/ms_core/preprocessing/__init__.py` — new `__all__` + module-level imports

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

等 CI 通過後 merge：

```bash
gh pr merge --squash
```

- [ ] **Step 3：取得 merge 後的 master HEAD commit**

```bash
git checkout master
git pull origin master
git log --oneline -1
```

記下這個 commit hash（後面 toolkit 需要用到）。

- [ ] **Step 4：打 v0.3.0 tag**

```bash
git tag -a v0.3.0 -m "v0.3.0: expose preprocessing public API and count_analysis_groups"
git push origin v0.3.0
```

- [ ] **Step 5：驗證 tag 存在**

```bash
git tag -l "v0.3.0"
```

預期輸出：`v0.3.0`

---

## Phase 2：Toolkit Adapter 完整隔離

> **執行環境：** `C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit`
> **前提：** Phase 1 全部完成（ms-core v0.3.0 tag 已存在）

---

### Task 3：建立 toolkit 新 branch + 更新 submodule

**Files:**
- Modify: `ms-core`（submodule）

- [ ] **Step 1：確認在 master 且 working tree 乾淨**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit"
git branch --show-current
git status --short
```

預期：在 `master`，無 uncommitted changes。

- [ ] **Step 2：建立新 branch**

```bash
git checkout -b refactor/adapter-architecture
```

- [ ] **Step 3：更新 submodule 到 v0.3.0**

```bash
cd ms-core
git fetch --tags
git checkout v0.3.0
cd ..
git add ms-core
```

- [ ] **Step 4：驗證 submodule 狀態**

```bash
git submodule status ms-core
```

預期：顯示 `v0.3.0`（不再是 detached commit hash）。

- [ ] **Step 5：Commit submodule bump**

```bash
git commit -m "chore: bump ms-core to v0.3.0

ms-core changes:
- feat: expose count_analysis_groups as public API on FeatureFilter
- feat: expose preprocessing package public API via __all__

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4：統一 adapter 的 ms-core import 路徑

**Files:**
- Modify: `src/ms_preprocessing/adapters/data_organizer.py`
- Modify: `src/ms_preprocessing/adapters/istd_marker.py`
- Modify: `src/ms_preprocessing/adapters/duplicate_remover.py`
- Modify: `src/ms_preprocessing/adapters/feature_filter.py`

- [ ] **Step 1：修改 `adapters/data_organizer.py` 的 import**

找到第 10–11 行：
```python
from ms_core.preprocessing.data_organizer import DataOrganizer as _DataOrganizer
from ms_core.preprocessing.settings import Settings as _CoreSettings
```

改為：
```python
from ms_core.preprocessing import DataOrganizer as _DataOrganizer
from ms_core.preprocessing import Settings as _CoreSettings
```

- [ ] **Step 2：修改 `adapters/istd_marker.py` 的 import**

找到第 11–12 行：
```python
from ms_core.preprocessing.istd_marker import ISTDMarker as _ISTDMarker
from ms_core.preprocessing.settings import Settings as _CoreSettings
```

改為：
```python
from ms_core.preprocessing import ISTDMarker as _ISTDMarker
from ms_core.preprocessing import Settings as _CoreSettings
```

- [ ] **Step 3：修改 `adapters/duplicate_remover.py` 的 import**

找到第 10–11 行：
```python
from ms_core.preprocessing.duplicate_remover import DuplicateRemover as _DuplicateRemover
from ms_core.preprocessing.settings import Settings as _CoreSettings
```

改為：
```python
from ms_core.preprocessing import DuplicateRemover as _DuplicateRemover
from ms_core.preprocessing import Settings as _CoreSettings
```

- [ ] **Step 4：修改 `adapters/feature_filter.py` 的 import**

找到第 10–11 行：
```python
from ms_core.preprocessing.ms_quality_filter import FeatureFilter as _FeatureFilter
from ms_core.preprocessing.settings import Settings as _CoreSettings
```

改為：
```python
from ms_core.preprocessing import FeatureFilter as _FeatureFilter
from ms_core.preprocessing import Settings as _CoreSettings
```

- [ ] **Step 5：跑測試確認 import 路徑變更無破壞**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/ -q --tb=short -x
```

預期：全部通過（257+ tests）。

- [ ] **Step 6：Commit**

```bash
git add src/ms_preprocessing/adapters/
git commit -m "refactor(adapters): use short-form ms_core.preprocessing imports

Use 'from ms_core.preprocessing import X' instead of deep module paths.
This relies on the new __all__ in ms-core v0.3.0.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5：將 `count_analysis_groups` 移入 adapter 層，widget 改用 adapter

**Files:**
- Modify: `src/ms_preprocessing/adapters/feature_filter.py`
- Modify: `src/ms_preprocessing/gui/widgets/feature_filter_widget.py`

- [ ] **Step 1：在 `adapters/feature_filter.py` 新增 public function**

在檔案末尾（所有現有 function 之後）加入：

```python
def count_analysis_groups(df: pd.DataFrame) -> int:
    """Return the number of non-QC analysis groups in df.

    Wraps FeatureFilter.count_analysis_groups() so GUI code
    never needs to import ms_core directly.
    """
    return _FeatureFilter().count_analysis_groups(df)
```

（`_FeatureFilter` 已在 Task 4 的 import 中定義，不需要重複 import。）

- [ ] **Step 2：修改 `feature_filter_widget.py` 的 `_count_analysis_groups` 方法**

找到約第 437–445 行的 `_count_analysis_groups` 方法：
```python
def _count_analysis_groups(self) -> int:
    """Count non-QC analysis groups in the loaded data."""
    if self._data is None:
        return 0
    from ms_core.preprocessing.ms_quality_filter import FeatureFilter

    processor = FeatureFilter()
    return processor.count_analysis_groups(self._data)
```

改為：
```python
def _count_analysis_groups(self) -> int:
    """Count non-QC analysis groups in the loaded data."""
    if self._data is None:
        return 0
    from ms_preprocessing.adapters import feature_filter as _ff_adapter

    return _ff_adapter.count_analysis_groups(self._data)
```

- [ ] **Step 3：確認 widget 已無 ms_core import**

```bash
grep -n "ms_core" src/ms_preprocessing/gui/widgets/feature_filter_widget.py
```

預期：無任何輸出。

- [ ] **Step 4：跑測試**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/ -q --tb=short -x
```

預期：全部通過。

- [ ] **Step 5：Commit**

```bash
git add src/ms_preprocessing/adapters/feature_filter.py \
        src/ms_preprocessing/gui/widgets/feature_filter_widget.py
git commit -m "refactor(gui): remove direct ms_core import from widget layer

Move count_analysis_groups to adapter layer (feature_filter.py).
feature_filter_widget now calls the adapter function instead of
directly importing FeatureFilter from ms_core.

GUI layer no longer has any ms_core imports.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 6：修正 istd_marker 的模組初始化 runtime 問題

**Files:**
- Modify: `src/ms_preprocessing/adapters/istd_marker.py`

- [ ] **Step 1：找到問題所在**

開啟 `src/ms_preprocessing/adapters/istd_marker.py`，找到約第 18–19 行：
```python
_DEFAULT_ISTD_MZ: tuple[float, ...] | None = None
_DEFAULT_ISTD_MZ = tuple(_ISTDMarker().config.default_istd_mz)
```

（或只有一行 `_DEFAULT_ISTD_MZ = tuple(_ISTDMarker().config.default_istd_mz)`）

這在模組被 import 時就立即執行 `_ISTDMarker()`，若 ms-core 未正確安裝會讓整個 adapters 模組 import 失敗。

- [ ] **Step 2：改為 lazy 初始化**

將上述行（無論是一行還是兩行）改為：

```python
_DEFAULT_ISTD_MZ: tuple[float, ...] | None = None
```

找到現有的 `get_default_istd_mz()` function（約第 21–24 行），確認它已有 lazy 邏輯，若沒有則改為：

```python
def get_default_istd_mz() -> tuple[float, ...]:
    """Expose default ISTD targets without leaking core imports into widgets."""
    global _DEFAULT_ISTD_MZ
    if _DEFAULT_ISTD_MZ is None:
        _DEFAULT_ISTD_MZ = tuple(_ISTDMarker().config.default_istd_mz)
    return _DEFAULT_ISTD_MZ
```

- [ ] **Step 3：跑 ISTD 相關測試確認行為不變**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/ -k "istd" -v --tb=short
```

預期：全部通過。

- [ ] **Step 4：Commit**

```bash
git add src/ms_preprocessing/adapters/istd_marker.py
git commit -m "fix(adapters): lazy-initialize _DEFAULT_ISTD_MZ in istd_marker

Module-level _ISTDMarker() call fails if ms-core isn't installed yet.
Defer initialization to first call of get_default_istd_mz().

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 7：加入 ruff 靜態分析規則強制 adapter 邊界

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1：寫一個會被規則抓到的測試 import（先驗證規則生效）**

在 `src/ms_preprocessing/gui/layout.py` 最頂部暫時加一行：
```python
import ms_core  # TEMP: testing ruff rule
```

- [ ] **Step 2：修改 `pyproject.toml`，加入 ruff 規則**

找到現有的 `[tool.ruff]` section：
```toml
[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I", "N", "UP", "B", "C4"]
ignore = ["E501"]
```

改為：
```toml
[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "TID"]
ignore = ["E501"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"ms_core" = {msg = "Import ms_core only through adapters, not directly in GUI or config layers."}

[tool.ruff.lint.per-file-ignores]
# adapters/ 是唯一允許直接 import ms_core 的地方
"src/ms_preprocessing/adapters/**/*.py" = ["TID251"]
# tests 允許直接 import ms_core（core unit tests 需要）
"tests/**/*.py" = ["TID251"]
```

- [ ] **Step 3：確認規則抓到暫時的違規 import**

```bash
uv run ruff check src/ms_preprocessing/gui/layout.py
```

預期輸出包含類似：
```
src/ms_preprocessing/gui/layout.py:1:1: TID251 `ms_core` is banned: Import ms_core only through adapters...
```

- [ ] **Step 4：移除暫時加入的測試 import**

從 `src/ms_preprocessing/gui/layout.py` 移除剛才加的那一行。

- [ ] **Step 5：確認整個 gui/ 目錄無違規**

```bash
uv run ruff check src/ms_preprocessing/gui/
```

預期：無任何輸出（全部通過）。

- [ ] **Step 6：確認 adapters/ 不被誤攔**

```bash
uv run ruff check src/ms_preprocessing/adapters/
```

預期：無 TID251 錯誤（有豁免）。

- [ ] **Step 7：跑完整測試**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/ -q --tb=short -x
```

預期：全部通過。

- [ ] **Step 8：Commit**

```bash
git add pyproject.toml
git commit -m "chore(lint): add ruff TID251 rule to enforce adapter boundary

Ban ms_core imports in gui/ and config/ layers.
Only adapters/ and tests/ are exempted.
Violations will fail CI automatically.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 3：分層測試策略

---

### Task 8：建立 `tests/core/` 並搬移 ms-core 直接測試

**Files:**
- Create: `tests/core/__init__.py`
- Move: 4 個 test 檔案到 `tests/core/`

- [ ] **Step 1：建立目錄與 `__init__.py`**

```bash
mkdir tests/core
touch tests/core/__init__.py
```

- [ ] **Step 2：搬移 4 個 core test 檔案**

```bash
git mv tests/test_data_organizer.py tests/core/test_data_organizer.py
git mv tests/test_duplicate_remover.py tests/core/test_duplicate_remover.py
git mv tests/test_feature_filter.py tests/core/test_feature_filter.py
git mv tests/test_istd_marker.py tests/core/test_istd_marker.py
```

- [ ] **Step 3：驗證搬移後測試仍可執行**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/core/ -q --tb=short
```

預期：4 個檔案的所有 tests 全部通過。

- [ ] **Step 4：Commit**

```bash
git add tests/core/
git add tests/test_data_organizer.py tests/test_duplicate_remover.py \
        tests/test_feature_filter.py tests/test_istd_marker.py
git commit -m "refactor(tests): move ms-core direct tests into tests/core/

tests/core/ = tests that directly import and test ms-core internals
(including private method tests, which are valid in this layer).

Long-term goal: migrate these into ms-core repo itself.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 9：建立 `tests/adapters/` 並搬移 adapter 測試

**Files:**
- Create: `tests/adapters/__init__.py`
- Move: 6 個 adapter test 檔案到 `tests/adapters/`

- [ ] **Step 1：建立目錄與 `__init__.py`**

```bash
mkdir tests/adapters
touch tests/adapters/__init__.py
```

- [ ] **Step 2：搬移 6 個 adapter test 檔案**

```bash
git mv tests/test_adapter_data_organizer.py tests/adapters/test_adapter_data_organizer.py
git mv tests/test_adapter_duplicate_remover.py tests/adapters/test_adapter_duplicate_remover.py
git mv tests/test_adapter_feature_filter.py tests/adapters/test_adapter_feature_filter.py
git mv tests/test_adapter_istd_marker.py tests/adapters/test_adapter_istd_marker.py
git mv tests/test_adapter_runtime_contracts.py tests/adapters/test_adapter_runtime_contracts.py
git mv tests/test_cross_project_adapter_contracts.py tests/adapters/test_cross_project_adapter_contracts.py
```

- [ ] **Step 3：驗證搬移後測試仍可執行**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/adapters/ -q --tb=short
```

預期：6 個檔案的所有 tests 全部通過。

- [ ] **Step 4：跑全套測試確認沒有破壞**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/ -q --tb=short
```

預期：全部通過（數量應與搬移前相同）。

- [ ] **Step 5：Commit**

```bash
git add tests/adapters/
git add tests/test_adapter_data_organizer.py tests/test_adapter_duplicate_remover.py \
        tests/test_adapter_feature_filter.py tests/test_adapter_istd_marker.py \
        tests/test_adapter_runtime_contracts.py tests/test_cross_project_adapter_contracts.py
git commit -m "refactor(tests): move adapter tests into tests/adapters/

tests/adapters/ = tests that verify adapter public interface only.
These tests must not import ms_core directly (enforced by ruff TID251).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 10：新增 API 合約測試

**Files:**
- Create: `tests/test_ms_core_api_contract.py`

- [ ] **Step 1：先寫測試（TDD — 先讓它跑，確認它通過）**

建立 `tests/test_ms_core_api_contract.py`：

```python
"""API surface contract tests for ms-core.

These tests do NOT verify behaviour — they verify that the public API
symbols exist at the expected locations. CI failure here means ms-core
changed a public API without notifying consumers (toolkit, DNP).

When ms-core removes or renames a symbol listed here:
  1. Bump ms-core minor version (v0.x+1.0)
  2. Update this file to match the new API
  3. Update all adapter call sites
"""

from __future__ import annotations


def test_preprocessing_package_exports_all_expected_symbols() -> None:
    """ms_core.preprocessing must export these symbols at package level."""
    from ms_core.preprocessing import (  # noqa: F401
        DataOrganizer,
        DataOrganizerConfig,
        DuplicateRemovalConfig,
        DuplicateRemover,
        FeatureFilter,
        FeatureFilterConfig,
        ISTDConfig,
        ISTDMarker,
        Settings,
    )


def test_feature_filter_public_methods_exist() -> None:
    from ms_core.preprocessing import FeatureFilter

    assert callable(getattr(FeatureFilter, "validate_input", None))
    assert callable(getattr(FeatureFilter, "process", None))
    assert callable(getattr(FeatureFilter, "count_analysis_groups", None))
    assert callable(getattr(FeatureFilter, "get_group_summary", None))


def test_istd_marker_public_methods_exist() -> None:
    from ms_core.preprocessing import ISTDMarker

    assert callable(getattr(ISTDMarker, "validate_input", None))
    assert callable(getattr(ISTDMarker, "process", None))


def test_duplicate_remover_public_methods_exist() -> None:
    from ms_core.preprocessing import DuplicateRemover

    assert callable(getattr(DuplicateRemover, "validate_input", None))
    assert callable(getattr(DuplicateRemover, "process", None))


def test_data_organizer_public_methods_exist() -> None:
    from ms_core.preprocessing import DataOrganizer

    assert callable(getattr(DataOrganizer, "validate_input", None))
    assert callable(getattr(DataOrganizer, "process", None))


def test_settings_public_methods_exist() -> None:
    from ms_core.preprocessing import Settings

    assert callable(getattr(Settings, "get_parquet_cache_root", None))
```

- [ ] **Step 2：跑測試確認全部通過（Phase 1 完成後才會通過）**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/test_ms_core_api_contract.py -v
```

預期：6 個 tests 全部 PASSED。

若失敗（因為 ms-core `__all__` 尚未就位），先確認 Phase 1 Task 1–2 已完成。

- [ ] **Step 3：Commit**

```bash
git add tests/test_ms_core_api_contract.py
git commit -m "test: add ms-core API surface contract tests

These tests verify public API symbols exist at expected locations.
CI failure = ms-core changed a public API without notifying consumers.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 4：文件與 SOP

---

### Task 11：更新 CLAUDE.md — submodule bump SOP

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1：在 CLAUDE.md 的「Submodule Rules」section 後面新增 SOP**

找到現有的 `## Submodule Rules (ms-core)` section，在它後面加入：

```markdown
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

```bash
# 4. 在 toolkit 建立 fix branch
cd <toolkit-root>
git checkout -b fix/<description>

# 5. 更新 submodule 到新 tag
cd ms-core
git fetch --tags
git checkout v0.X.Y
cd ..
git add ms-core

# 6. 改 toolkit 代碼（若有）→ 跑測試 → commit → PR
PYTHONPATH=ms-core/src uv run pytest tests/ -q --tb=short -x
git commit -m "chore: bump ms-core to v0.X.Y

ms-core changes:
- <ms-core 這次改了什麼>

Toolkit changes:
- <toolkit 對應改了什麼，若有>"
```

### DNP 版本策略

- DNP 獨立固定自己使用的 ms-core tag，與 toolkit 可以不同步
- ms-core minor bump（破壞性 API 變更）時，在 toolkit PR description 標記「⚠️ DNP 需同步升級」
```

- [ ] **Step 2：跑測試確認文件變更沒有副作用**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/ -q --tb=short
```

預期：全部通過。

- [ ] **Step 3：Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add ms-core submodule bump SOP to CLAUDE.md

Formalizes the cross-repo workflow:
- ms-core first, toolkit second
- semantic version tags for public API changes
- DNP version independence policy

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 12：開 toolkit PR + 驗證成功標準

- [ ] **Step 1：跑完整測試套件**

```bash
PYTHONPATH=ms-core/src uv run pytest tests/ -v --tb=short
```

預期：全部通過。

- [ ] **Step 2：驗證所有成功標準**

```bash
# 1. submodule 顯示版本 tag
git submodule status ms-core

# 2. gui/ 無 ms_core import
grep -r "from ms_core" src/ms_preprocessing/gui/ && echo "FAIL" || echo "PASS"

# 3. ruff 無 TID251 違規
uv run ruff check src/ms_preprocessing/gui/ src/ms_preprocessing/config/

# 4. API 合約測試通過
PYTHONPATH=ms-core/src uv run pytest tests/test_ms_core_api_contract.py -v

# 5. adapters/ 測試無 ms_core 直接 import（手動確認）
grep -r "from ms_core" tests/adapters/ && echo "FAIL" || echo "PASS"
```

每一條預期都通過才算完成。

- [ ] **Step 3：開 PR**

```bash
git push -u origin refactor/adapter-architecture

gh pr create \
  --title "refactor: adapter architecture cleanup — enforce boundary, layer tests, submodule discipline" \
  --body "$(cat <<'EOF'
## Summary

- **Submodule**: bump ms-core to v0.3.0 (new `__all__` + `count_analysis_groups`)
- **Adapters**: unify import paths to short-form `from ms_core.preprocessing import X`
- **GUI**: remove last direct `ms_core` import from widget layer; route through adapter
- **Lint**: add ruff TID251 rule — CI will catch any future gui→ms_core boundary violation
- **Tests**: reorganize into `tests/core/` (ms-core logic) and `tests/adapters/` (adapter interface)
- **Contract test**: new `tests/test_ms_core_api_contract.py` — CI fails if ms-core public API disappears
- **Docs**: add submodule bump SOP to CLAUDE.md

## Success Criteria

- [ ] `git submodule status` shows v0.3.0 tag
- [ ] `grep -r "from ms_core" src/ms_preprocessing/gui/` returns nothing
- [ ] `ruff check src/ms_preprocessing/gui/` has no TID251 errors
- [ ] `pytest tests/test_ms_core_api_contract.py` passes
- [ ] `pytest tests/adapters/` has no direct ms_core imports

## Spec

`docs/superpowers/specs/2026-04-11-ms-core-maintenance-architecture-design.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## 執行後的目錄結構

```
tests/
├── core/                        ← ms-core 邏輯測試（允許 ms_core import）
│   ├── __init__.py
│   ├── test_data_organizer.py
│   ├── test_duplicate_remover.py
│   ├── test_feature_filter.py
│   └── test_istd_marker.py
│
├── adapters/                    ← adapter interface 測試（禁止 ms_core import）
│   ├── __init__.py
│   ├── test_adapter_data_organizer.py
│   ├── test_adapter_duplicate_remover.py
│   ├── test_adapter_feature_filter.py
│   ├── test_adapter_istd_marker.py
│   ├── test_adapter_runtime_contracts.py
│   └── test_cross_project_adapter_contracts.py
│
├── test_ms_core_api_contract.py ← 新增：API surface 合約測試
├── conftest.py                  ← 共用 fixtures（不動）
└── ... (其餘 GUI / smoke / regression tests)
```
