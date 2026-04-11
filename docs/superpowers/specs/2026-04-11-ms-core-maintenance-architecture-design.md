# ms-core 中長期維護架構設計

**日期：** 2026-04-11
**狀態：** 已核准，待實作
**作者：** bosschen0429

---

## 背景與動機

ms-core 是一個 git submodule，同時供 ms-preprocessing-toolkit 與 DNP 專案消費。目前存在三個核心痛點：

1. **靜默破壞（Silent Breaking）**：ms-core 改動後 toolkit/DNP 無預警壞掉，沒有明確的 API 邊界
2. **跨 repo PR 摩擦**：改 ms-core 需同時開兩個 PR，submodule bump 流程不標準，容易出現 detached HEAD
3. **API 邊界不清**：`_` 前綴的 private 方法與 public API 混用，消費端不知道哪些可以安全呼叫

**決策：** 採用「Adapter 完整化 + API 合約 + Submodule 紀律」方案，一次清理技術債，建立可持續的維護機制。投入約 1 週。

---

## 技術債現況（設計前盤點）

| # | 項目 | 嚴重度 | 位置 |
|---|------|--------|------|
| T1 | ms-core submodule detached HEAD | 🟡 中 | toolkit `.gitmodules` |
| T2 | Widget 層直接 import ms-core | 🟡 中 | `gui/widgets/feature_filter_widget.py:441` |
| T3 | Tests 繞過 adapter 直接測 ms-core | 🟡 中 | 8 個測試檔案 |
| T4 | Adapter 模組初始化時執行 runtime 程式碼 | 🟡 中 | `adapters/istd_marker.py:18` |
| T5 | Tests 呼叫 ms-core private 方法 | 🟢 低 | `tests/test_feature_filter.py` |
| T6 | ms-core 無 package-level `__all__` | 🟡 中 | `ms_core/preprocessing/__init__.py` |

---

## 設計：四個支柱

### 支柱 1｜ms-core Public API 定義

#### 1a. 補 `preprocessing/__init__.py` 的 `__all__`

```python
# ms-core/src/ms_core/preprocessing/__init__.py
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
    "DataOrganizer", "ISTDMarker", "DuplicateRemover", "FeatureFilter",
    "DataOrganizerConfig", "ISTDConfig", "DuplicateRemovalConfig",
    "FeatureFilterConfig", "Settings",
]
```

toolkit 的所有 adapter import 路徑統一改為：
```python
# Before
from ms_core.preprocessing.ms_quality_filter import FeatureFilter
# After
from ms_core.preprocessing import FeatureFilter
```

#### 1b. Semantic Version Tag 管理

ms-core 每次修改 public API 時打 tag，規則如下：

| 變更類型 | Bump |
|----------|------|
| 新增 public method（向後相容） | patch：`v0.x.y+1` |
| 改變 public method 簽名 | minor：`v0.x+1.0` |
| 移除 public method | minor：`v0.x+1.0` |
| 只改 private / 內部邏輯 | 不強制 tag |

```bash
git tag -a v0.3.0 -m "v0.3.0: add count_analysis_groups public API"
git push origin v0.3.0
```

#### 1c. API 合約測試

新增 `tests/test_ms_core_api_contract.py`，只驗證 API surface 存在，不測行為：

```python
def test_ms_core_public_api_surface():
    from ms_core.preprocessing import (
        DataOrganizer, ISTDMarker, DuplicateRemover, FeatureFilter, Settings
    )
    # FeatureFilter public methods
    assert hasattr(FeatureFilter, "process")
    assert hasattr(FeatureFilter, "validate_input")
    assert hasattr(FeatureFilter, "count_analysis_groups")
    assert hasattr(FeatureFilter, "get_group_summary")
    # 其他 class 同樣驗證...
```

CI 失敗 = ms-core 改了 public API 但沒有通知消費者。

---

### 支柱 2｜Adapter 完整隔離

#### 架構規則（強制）

```
gui/widgets/  →  adapters/  →  ms_core.preprocessing
     ✅               ✅               ❌（widget 禁止直接到這）
```

#### 2a. group-count 邏輯移進 adapter

在 `adapters/feature_filter.py` 新增：

```python
def count_analysis_groups(df: pd.DataFrame) -> int:
    """Return number of non-QC analysis groups in df.

    Wraps FeatureFilter.count_analysis_groups() so GUI code
    never needs to import ms_core directly.
    """
    from ms_core.preprocessing import FeatureFilter
    return FeatureFilter().count_analysis_groups(df)
```

`feature_filter_widget.py` 改為：
```python
# Before（PR #18 後）
from ms_core.preprocessing.ms_quality_filter import FeatureFilter
processor = FeatureFilter()
return processor.count_analysis_groups(self._data)

# After
from ms_preprocessing.adapters import feature_filter as feature_filter_adapter
return feature_filter_adapter.count_analysis_groups(self._data)
```

#### 2b. Ruff 靜態分析規則

`pyproject.toml` 加入，讓 CI 自動抓 widget 層違規。策略：全局 ban `ms_core`，只在 adapters/ 和 tests/ 開豁免：

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"ms_core" = {msg = "Import ms_core only through adapters, not directly in GUI or config layers."}

[tool.ruff.lint.per-file-ignores]
# adapters/ 是唯一允許直接 import ms_core 的地方
"src/ms_preprocessing/adapters/**/*.py" = ["TID251"]
# tests 允許直接 import ms_core（core unit tests 需要）
"tests/**/*.py" = ["TID251"]
```

這樣任何 widget / config / utils 直接 `import ms_core` 都會在 CI 被 ruff 攔截，不需要人工 review。

#### 2c. Lazy 初始化修正

`adapters/istd_marker.py:18` 模組初始化時執行 runtime 程式碼，改為 lazy：

```python
# Before
_DEFAULT_ISTD_MZ = tuple(_ISTDMarker().config.default_istd_mz)

# After
_DEFAULT_ISTD_MZ: tuple | None = None

def get_default_istd_mz() -> tuple:
    global _DEFAULT_ISTD_MZ
    if _DEFAULT_ISTD_MZ is None:
        from ms_core.preprocessing import ISTDMarker
        _DEFAULT_ISTD_MZ = tuple(ISTDMarker().config.default_istd_mz)
    return _DEFAULT_ISTD_MZ
```

---

### 支柱 3｜分層測試策略

#### 分層原則

| 類型 | 測什麼 | 允許直接 import ms-core？ | 目錄 |
|------|--------|--------------------------|------|
| Core unit tests | ms-core 演算法邏輯 | ✅ | `tests/core/` |
| Adapter integration tests | adapter 包裝正確性 | ❌ | `tests/adapters/` |
| API contract tests | public API surface 存在 | ✅（只 import） | `tests/` 根層 |

#### 目錄重組

```
tests/
├── core/                            # 搬自現有直接測 ms-core 的 tests
│   ├── test_data_organizer.py
│   ├── test_duplicate_remover.py
│   ├── test_feature_filter.py       # 含 private method 測試，合理保留
│   └── test_istd_marker.py
│
├── adapters/                        # adapter-only，禁止直接 import ms-core
│   ├── test_adapter_data_organizer.py
│   ├── test_adapter_duplicate_remover.py
│   ├── test_adapter_feature_filter.py
│   ├── test_adapter_istd_marker.py
│   └── test_adapter_runtime_contracts.py
│
├── test_ms_core_api_contract.py     # 新增：API 合約測試
├── conftest.py
└── ... (GUI / regression / smoke tests 維持原位)
```

#### 長期目標（本次不執行）

`tests/core/` 裡的測試理想上應搬進 ms-core repo 本身。短期先整理目錄，不搬 repo，不強求立刻完美。

---

### 支柱 4｜Submodule 工作流紀律

#### 標準 bump SOP（寫進 CLAUDE.md）

```
1. ms-core: 建 fix/* 或 feature/* branch → PR → merge 進 master
2. ms-core: 若有 public API 變動，打 tag → push tag
3. toolkit: 建 fix/* branch
4. toolkit: cd ms-core → git fetch --tags → git checkout <tag> → cd ..
5. toolkit: git add ms-core → 改 toolkit 代碼 → 跑測試 → commit → PR
```

**PR 描述模板（bump 類型）：**
```
chore: bump ms-core to v0.x.y

ms-core changes:
- <ms-core 這次改了什麼>

Toolkit changes:
- <toolkit 對應改了什麼，若有>
```

#### 處理目前 detached HEAD

目前 ms-core submodule 在 `39246c7`（`fix/public-group-count-api`，未 merge 進 ms-core master）。

清理路徑：
1. ms-core 開 PR：`fix/public-group-count-api` → master → merge
2. merge 後打 tag `v0.3.0`
3. toolkit PR #18 把 submodule 從 `39246c7` bump 到 `v0.3.0`

#### DNP 版本策略

- DNP 固定在自己使用的 tag，與 toolkit 可以不同步
- ms-core minor bump（破壞性變更）時，開 issue 標記「需要 DNP + toolkit 同步升級」，不強求同時完成但必須追蹤

---

## 實作計畫

| 階段 | 內容 | 估時 | 依賴 |
|------|------|------|------|
| **Phase 1** | ms-core：補 `__all__` + merge `fix/public-group-count-api` + 打 `v0.3.0` tag | 0.5 天 | 無 |
| **Phase 2** | toolkit：Adapter import 路徑統一 + `count_analysis_groups` 移入 adapter + lazy init fix + ruff rule | 1 天 | Phase 1 完成 |
| **Phase 3** | toolkit：Tests 目錄重組（`core/`、`adapters/`）+ 新增 `test_ms_core_api_contract.py` | 1–2 天 | Phase 2 完成 |
| **Phase 4** | 文件：CLAUDE.md 補 submodule SOP + DNP 確認 | 0.5 天 | Phase 3 完成 |

**總估時：** 3–4 天（保守估計 1 週）

---

## 成功標準

完成後，應達到以下可驗證的狀態：

- [ ] `git submodule status` 顯示版本 tag，無 detached HEAD
- [ ] `grep -r "from ms_core" src/ms_preprocessing/gui/` 無輸出
- [ ] `ruff check src/ms_preprocessing/gui/` 無 TID252 違規
- [ ] `pytest tests/test_ms_core_api_contract.py` 通過
- [ ] `pytest tests/adapters/` 無直接 `from ms_core` import
- [ ] ms-core `preprocessing/__init__.py` 有 `__all__` 定義
- [ ] CLAUDE.md 包含 submodule bump SOP
