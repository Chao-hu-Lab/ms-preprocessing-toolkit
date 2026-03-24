# Step 4 Gate Logic Refactor — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重構 Step 4 的 feature filter gate 系統——移除冗餘的 Skew gate、新增 intensity fold-change gate、改進統計報告以顯示各 gate 的獨有貢獻。

**Architecture:** 在 ms-core 的 `FeatureFilter._filter_features()` 中，將三正向 gate（Stable/Skew/Diff）替換為兩正向 gate（Stable/Diff）加一個新的 Intensity gate。Intensity gate 計算各組平均強度的 fold-change，補足現有偵測率維度的盲區。統計報告新增 `unique_*` 欄位顯示各 gate 的邊際貢獻。GUI、adapter、presets、CLI、pipeline 同步更新。

**Tech Stack:** Python 3.12+, pandas, numpy, pytest, customtkinter

---

## 背景與動機

### 資料分析結果（internal validation dataset: 823 features, 3 groups）

| 指標 | 數值 |
|------|------|
| Skew gate 通過總數 | 155 |
| **Skew gate 獨有貢獻** | **0** |
| Diff gate 獨有貢獻 | 83 |
| Stable gate 獨有貢獻 | 10 |
| 三 gate 全沒過但 QC 正常 | 142（其中 89 個偵測強度 >100 萬） |
| 已保留 features 中強度 fold-change >2x | 112（45%） |
| 已保留 features 中強度 fold-change >10x | 7（3%），但 gate 完全看不到 |

### 三個改動

1. **移除 Skew gate**：實證冗餘，獨有貢獻 = 0
2. **新增 Intensity gate**：補足強度維度盲區，抓「偵測率相似但強度差異大」的 features
3. **統計報告改進**：新增各 gate 的 `unique_*` 計數，讓使用者能評估邊際貢獻

---

## File Structure

### ms-core（子模組，需先 commit/push）

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `ms-core/src/ms_core/preprocessing/ms_quality_filter.py:331-469` | 移除 skew gate，新增 intensity gate，改進 stats |
| Modify | `ms-core/src/ms_core/preprocessing/settings.py:59-76` | 移除 `default_skew_threshold`，新增 `default_intensity_fc_threshold` |
| Modify | `ms-core/src/ms_core/pipeline.py:65,166,471` | 移除 `quality_skew_threshold`，新增 `quality_intensity_fc_threshold` |

### toolkit

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/ms_preprocessing/config/feature_filter_presets.py` | 移除 skew 參數，新增 intensity_fc 參數 |
| Modify | `src/ms_preprocessing/config/settings.py` | 移除 `default_skew_threshold`，新增 `default_intensity_fc_threshold` |
| Modify | `src/ms_preprocessing/adapters/feature_filter.py` | 更新參數傳遞 |
| Modify | `src/ms_preprocessing/gui/widgets/feature_filter_widget.py` | 移除 skew 控件，新增 intensity_fc 控件 |
| Modify | `src/ms_preprocessing/main.py` | 更新 CLI argparse 定義和參數傳遞 |

### tests

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `tests/test_feature_filter.py` | 移除 skew 測試，新增 intensity gate 測試 |
| Modify | `tests/test_feature_filter_widget.py` | 更新 GUI 測試 |
| Modify | `tests/test_adapter_runtime_contracts.py` | 更新參數轉發測試 |
| Modify | `tests/test_cli_parquet_chain.py` | 更新 CLI 參數 |
| Modify | `tests/test_gui_pipeline_session.py` | 更新 session snapshot assertions |
| Modify | `tests/test_final_export_cache_policy.py` | 移除 skew_threshold fixture 參數 |

### scripts / docs（非核心，但需同步）

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `scripts/benchmark_step4_io.py` | 更新 benchmark 參數 |

---

## Commit Strategy

> **重要：** 所有程式碼修改（ms-core + toolkit + tests）在 **全量測試通過後** 才進行 commit。
> 避免中途 commit 造成 broken state。

順序：
1. 修改所有程式碼（Tasks 1-3，不 commit）
2. 全量測試通過後 → commit ms-core
3. push ms-core
4. commit toolkit（含 submodule reference update）

---

## Task 1: ms-core — 移除 Skew gate + 新增 Intensity gate

**Files:**
- Modify: `ms-core/src/ms_core/preprocessing/ms_quality_filter.py:68-112` (process 參數)
- Modify: `ms-core/src/ms_core/preprocessing/ms_quality_filter.py:331-469` (_filter_features)
- Modify: `ms-core/src/ms_core/preprocessing/settings.py:59-76` (FeatureFilterConfig)
- Modify: `ms-core/src/ms_core/pipeline.py:65,166,471` (pipeline 參數)

### Task 1a: 更新 FeatureFilterConfig

- [ ] **Step 1: 修改 ms-core settings.py — 移除 skew，新增 intensity_fc**

在 `ms-core/src/ms_core/preprocessing/settings.py` 的 `FeatureFilterConfig` 中：
- 移除 `default_skew_threshold: float = 0.66`
- 新增 `default_intensity_fc_threshold: float = 2.0`（fold-change ≥ 2 表示有意義的強度差異）

```python
@dataclass
class FeatureFilterConfig:
    """Configuration for Feature Filter module."""
    signal_threshold: float = 5000.0
    qc_warning_threshold: float = 0.5
    default_background_threshold: float = 0.33
    default_diff_threshold: float = 0.30
    default_qc_ratio_threshold: float = 0.0
    default_intensity_fc_threshold: float = 2.0
    excluded_types: list = field(default_factory=lambda: ["blank", "standard", "sdolek", "qc"])
```

- [ ] **Step 2: 確認所有 `default_skew_threshold` 引用**

Run: `grep -r "default_skew_threshold" ms-core/src/`
Expected: 只在 settings.py 和 ms_quality_filter.py 中出現

### Task 1b: 更新 FeatureFilter.process() 參數簽名

- [ ] **Step 3: 修改 process() 方法簽名**

在 `ms-core/src/ms_core/preprocessing/ms_quality_filter.py` 中：
- 移除 `skew_threshold` 參數和 `enable_skew_threshold` 參數
- 新增 `intensity_fc_threshold` 參數和 `enable_intensity_fc_threshold` 參數
- 更新 docstring
- **在 `**kwargs` 處新增棄用警告**，偵測舊參數名

```python
def process(
    self,
    df: pd.DataFrame,
    background_threshold: Optional[float] = None,
    diff_threshold: Optional[float] = None,
    qc_ratio_threshold: Optional[float] = None,
    intensity_fc_threshold: Optional[float] = None,
    enable_background_threshold: bool = True,
    enable_diff_threshold: bool = True,
    enable_qc_ratio_threshold: bool = True,
    enable_intensity_fc_threshold: bool = True,
    protected_rows: Optional[Set[int]] = None,
    **kwargs,
) -> ProcessingResult:
```

在 process() 開頭新增棄用警告：
```python
import warnings

# Deprecation guard for removed parameters
_REMOVED = {"skew_threshold", "enable_skew_threshold"}
for removed_key in _REMOVED & kwargs.keys():
    warnings.warn(
        f"Parameter '{removed_key}' was removed in the gate logic refactor. "
        "It will be silently ignored. Use intensity_fc_threshold instead.",
        DeprecationWarning,
        stacklevel=2,
    )
```

- [ ] **Step 4: 更新 process() 內部的 threshold 解析和傳遞**

```python
intensity_fc_thresh = (
    intensity_fc_threshold
    if intensity_fc_threshold is not None
    else self.config.default_intensity_fc_threshold
)
```

並更新 `_filter_features` 的呼叫，移除 `skew_thresh`，加入 `intensity_fc_thresh`。

### Task 1c: 重寫 _filter_features() 核心邏輯

- [ ] **Step 5: 移除 skew gate 邏輯，新增 intensity gate**

在 `_filter_features()` 中：

1. 移除 `skew_threshold` 參數和 `enable_skew_threshold` 參數
2. 新增 `intensity_fc_threshold` 參數和 `enable_intensity_fc_threshold` 參數
3. 移除 skew_keep 計算（原 L405-409）
4. 新增 intensity fold-change 計算：

```python
# Intensity fold-change gate: max group mean / min group mean >= threshold
# Note: requires >= 2 groups (same guard as diff gate)
if enable_intensity_fc_threshold and ratio_matrix.shape[1] >= 2:
    # Build numeric block for intensity means per group
    intensity_means = []
    for group_name in group_names:
        col_indices = group_info["groups"][group_name]
        block = df.iloc[1:, col_indices].apply(pd.to_numeric, errors="coerce")
        intensity_means.append(block.mean(axis=1).to_numpy())
    intensity_matrix = np.vstack(intensity_means).T  # (n_features, n_groups)

    # Replace 0/NaN with NaN for safe division
    safe_matrix = np.where(intensity_matrix > 0, intensity_matrix, np.nan)
    max_mean = np.nanmax(safe_matrix, axis=1)
    min_mean = np.nanmin(safe_matrix, axis=1)
    # If min_mean is 0/NaN → one group has no signal at all → meaningful difference → pass
    with np.errstate(divide="ignore", invalid="ignore"):
        fold_change = np.where(min_mean > 0, max_mean / min_mean, np.inf)
    # Handle all-NaN rows (no signal in any group) → fold_change = NaN → fail
    fold_change = np.where(np.isnan(fold_change), 0.0, fold_change)
    intensity_fc_keep = fold_change >= intensity_fc_threshold
else:
    intensity_fc_keep = np.zeros(len(df) - 1, dtype=bool)
```

5. 更新 positive_rules：

```python
positive_rules = []
if enable_background_threshold:
    positive_rules.append(stable_keep)
if enable_diff_threshold:
    positive_rules.append(diff_keep)
if enable_intensity_fc_threshold:
    positive_rules.append(intensity_fc_keep)
```

6. 更新 stats dict，移除 skew_kept，新增 intensity_fc_kept 和 unique_* 計數：

```python
stats = {
    "kept_count": 0,
    "deleted_count": 0,
    "stable_kept": 0,
    "diff_kept": 0,
    "intensity_fc_kept": 0,
    "qc_zero_deleted": 0,
    "qc_low_deleted": 0,
    "protected_kept": 0,
    "unique_stable_kept": 0,
    "unique_diff_kept": 0,
    "unique_intensity_fc_kept": 0,
}
```

```python
# 計算各 gate 通過數和獨有貢獻（排除 protected 和 QC 刪除）
non_protected = ~protected_mask
not_qc_killed = ~(qc_zero | qc_low)
effective = non_protected & not_qc_killed

stats["stable_kept"] = int((stable_keep & non_protected).sum())
stats["diff_kept"] = int((diff_keep & non_protected).sum())
stats["intensity_fc_kept"] = int((intensity_fc_keep & non_protected).sum())
stats["unique_stable_kept"] = int((stable_keep & ~diff_keep & ~intensity_fc_keep & effective).sum())
stats["unique_diff_kept"] = int((diff_keep & ~stable_keep & ~intensity_fc_keep & effective).sum())
stats["unique_intensity_fc_kept"] = int((intensity_fc_keep & ~stable_keep & ~diff_keep & effective).sum())
```

- [ ] **Step 6: 更新 process() 返回的 metadata**

```python
"thresholds": {
    "background": bg_thresh,
    "diff": diff_thresh,
    "qc_ratio": qc_ratio_thresh,
    "intensity_fc": intensity_fc_thresh,
},
"enabled_thresholds": {
    "background": bool(enable_background_threshold),
    "diff": bool(enable_diff_threshold),
    "qc_ratio": bool(enable_qc_ratio_threshold),
    "intensity_fc": bool(enable_intensity_fc_threshold),
},
```

- [ ] **Step 7: 更新 class docstring**

移除 "Skewed: Any group with ratio >= skew threshold"，新增 "Intensity: Any two groups with mean intensity fold-change >= threshold"

### Task 1d: 更新 ms-core pipeline.py

- [ ] **Step 8: 修改 pipeline.py**

- `quality_skew_threshold` → `quality_intensity_fc_threshold`
- `enable_skew_threshold` → `enable_intensity_fc_threshold`
- 更新 `kw` dict 和 step 3 params 中的參數名

---

## Task 2: 更新 toolkit 層（adapter + presets + GUI + CLI + settings）

**Files:**
- Modify: `src/ms_preprocessing/config/feature_filter_presets.py`
- Modify: `src/ms_preprocessing/config/settings.py`
- Modify: `src/ms_preprocessing/adapters/feature_filter.py`
- Modify: `src/ms_preprocessing/gui/widgets/feature_filter_widget.py`
- Modify: `src/ms_preprocessing/main.py`

### Task 2a: 更新 presets

- [ ] **Step 9: 修改 feature_filter_presets.py**

移除所有 `skew_threshold` 和 `enable_skew_threshold`，新增 `intensity_fc_threshold` 和 `enable_intensity_fc_threshold`：

```python
class Step4Params(TypedDict):
    signal_threshold: float
    background_threshold: float
    diff_threshold: float
    qc_ratio_threshold: float
    intensity_fc_threshold: float
    enable_background_threshold: bool
    enable_diff_threshold: bool
    enable_qc_ratio_threshold: bool
    enable_intensity_fc_threshold: bool
```

Presets：

| Preset | intensity_fc_threshold | 說明 |
|--------|----------------------|------|
| loose  | 1.5 | 低門檻，1.5 倍差異即保留 |
| default | 2.0 | 2 倍差異 |
| strict | 3.0 | 3 倍以上才保留 |

更新 `PRESET_DESCRIPTIONS` 移除 skew 描述，加入 intensity_fc 描述。

### Task 2b: 更新 toolkit settings.py

- [ ] **Step 10: 修改 src/ms_preprocessing/config/settings.py**

- 移除 `default_skew_threshold: float = 0.66`
- 新增 `default_intensity_fc_threshold: float = 2.0`

### Task 2c: 更新 adapter

- [ ] **Step 11: 修改 feature_filter.py adapter**

在 `_run_processor()`、`run()`、`run_from_df()` 三個函式中：
- 移除 `skew_threshold` 和 `enable_skew_threshold` 參數
- 新增 `intensity_fc_threshold` 和 `enable_intensity_fc_threshold` 參數
- 更新 `core_result = processor.process(...)` 呼叫

### Task 2d: 更新 GUI widget

- [ ] **Step 12: 修改 feature_filter_widget.py**

1. 移除 skew 相關控件（`skew_enabled_var`, `skew_enabled_switch`, `skew_slider`, `skew_entry`, `_update_skew`, `_apply_skew`）
2. 新增 intensity_fc 控件，預設值 2.0：
   - slider range: 1.0–10.0（fold-change 不是 0-1 比例）
   - 說明文字：「啟用時：任兩組平均強度 fold-change >= 門檻才算強度差異型」
3. 更新 `_threshold_controls` dict
4. 更新 `get_parameters()` 移除 skew，加入 intensity_fc
5. 更新 `run_processing()` 參數傳遞
6. 更新 criteria_text 文字說明
7. 調整 row 編號（skew 原本在 row=2，用 intensity_fc 取代）

### Task 2e: 更新 CLI（main.py）

- [ ] **Step 13: 修改 main.py**

1. 移除 `--skew-threshold` argparse 定義
2. 新增 `--intensity-fc-threshold` argparse 定義（default=2.0, type=float）
3. 更新 `args.skew_threshold` → `args.intensity_fc_threshold` 的兩處呼叫（adapter 傳參）
4. 移除 `--enable-skew-threshold` 相關邏輯，新增 `--enable-intensity-fc-threshold`

### Task 2f: 更新 benchmark script

- [ ] **Step 14: 修改 scripts/benchmark_step4_io.py**

更新 skew 相關參數為 intensity_fc

---

## Task 3: 更新所有測試

**Files:**
- Modify: `tests/test_feature_filter.py`
- Modify: `tests/test_feature_filter_widget.py`
- Modify: `tests/test_adapter_runtime_contracts.py`
- Modify: `tests/test_cli_parquet_chain.py`
- Modify: `tests/test_gui_pipeline_session.py`
- Modify: `tests/test_final_export_cache_policy.py`

### Task 3a: 更新 core filter 測試

- [ ] **Step 15: 修改 test_feature_filter.py**

1. 移除 `test_disabling_skew_rule_removes_feature_kept_only_by_skew_ratio` 測試
2. 所有 `process()` 呼叫移除 `skew_threshold=` 參數
3. 新增 intensity gate 測試：

```python
def test_intensity_fc_gate_keeps_feature_with_high_fold_change(self, filter_proc):
    """Feature with similar detection ratio but high intensity fold-change should be kept."""
    df = pd.DataFrame({
        "Mz/RT": ["Sample_Type", "100.000/1.0"],
        "Tolerance": ["na", "na"],
        "Case1": ["case", 6000],
        "Case2": ["case", 7000],
        "Control1": ["control", 300000],
        "Control2": ["control", 500000],
        "QC1": ["qc", 8000],
    })
    result = filter_proc.process(
        df,
        background_threshold=0.33,
        diff_threshold=0.30,
        qc_ratio_threshold=0.0,
        intensity_fc_threshold=2.0,
    )
    assert result.success
    assert "100.000/1.0" in result.data["Mz/RT"].tolist()
    assert result.statistics.get("intensity_fc_kept", 0) >= 1

def test_intensity_fc_gate_does_not_keep_similar_intensity(self, filter_proc):
    """Feature with similar intensity should not be kept by intensity gate alone."""
    df = pd.DataFrame({
        "Mz/RT": ["Sample_Type", "100.000/1.0"],
        "Tolerance": ["na", "na"],
        "Case1": ["case", 8000],
        "Case2": ["case", 100],
        "Control1": ["control", 7000],
        "Control2": ["control", 100],
        "QC1": ["qc", 8000],
    })
    # Cleanly isolate: only intensity gate active, and it should NOT save this feature
    result = filter_proc.process(
        df,
        background_threshold=0.33,
        diff_threshold=0.30,
        qc_ratio_threshold=0.0,
        intensity_fc_threshold=2.0,
        enable_background_threshold=False,
        enable_diff_threshold=False,
        enable_intensity_fc_threshold=True,
    )
    assert result.success
    # Case mean ≈ 4050, Control mean ≈ 3550, FC ≈ 1.14 < 2.0
    assert "100.000/1.0" not in result.data["Mz/RT"].tolist()

def test_disabling_intensity_fc_rule(self, filter_proc):
    """Feature kept only by intensity FC should be removed when gate is disabled."""
    df = pd.DataFrame({
        "Mz/RT": ["Sample_Type", "100.000/1.0"],
        "Tolerance": ["na", "na"],
        "Case1": ["case", 6000],
        "Case2": ["case", 6000],
        "Control1": ["control", 500000],
        "Control2": ["control", 500000],
        "QC1": ["qc", 8000],
    })
    enabled = filter_proc.process(
        df,
        background_threshold=0.33,
        diff_threshold=0.30,
        qc_ratio_threshold=0.0,
        intensity_fc_threshold=2.0,
        enable_background_threshold=False,
        enable_diff_threshold=False,
        enable_intensity_fc_threshold=True,
    )
    disabled = filter_proc.process(
        df,
        background_threshold=0.33,
        diff_threshold=0.30,
        qc_ratio_threshold=0.0,
        intensity_fc_threshold=2.0,
        enable_background_threshold=False,
        enable_diff_threshold=False,
        enable_intensity_fc_threshold=False,
    )
    assert enabled.success and disabled.success
    assert "100.000/1.0" in enabled.data["Mz/RT"].tolist()
    assert "100.000/1.0" not in disabled.data["Mz/RT"].tolist()

def test_unique_stats_report_marginal_contribution(self, filter_proc):
    """Stats should report unique (marginal) contribution of each gate."""
    df = pd.DataFrame({
        "Mz/RT": ["Sample_Type", "A", "B", "C"],
        "Tolerance": ["na", "na", "na", "na"],
        "Case1": ["case", 8000, 8000, 6000],
        "Case2": ["case", 8000, 100, 6000],
        "Control1": ["control", 8000, 100, 500000],
        "Control2": ["control", 8000, 100, 500000],
        "QC1": ["qc", 8000, 8000, 8000],
    })
    # A: both groups ratio=1.0, similar intensity → Stable only
    # B: case ratio=1.0, control ratio=0 → Diff only (large ratio diff)
    # C: both groups ratio=1.0, intensity 6k vs 500k → Intensity FC only
    result = filter_proc.process(
        df,
        background_threshold=0.33,
        diff_threshold=0.30,
        qc_ratio_threshold=0.0,
        intensity_fc_threshold=2.0,
    )
    assert result.success
    assert result.statistics.get("unique_stable_kept", 0) >= 1
    assert result.statistics.get("unique_diff_kept", 0) >= 1
    assert result.statistics.get("unique_intensity_fc_kept", 0) >= 1

def test_deprecated_skew_parameter_warns(self, filter_proc):
    """Passing removed skew_threshold should emit DeprecationWarning."""
    df = pd.DataFrame({
        "Mz/RT": ["Sample_Type", "100.000/1.0"],
        "Tolerance": ["na", "na"],
        "Case1": ["case", 8000],
        "Control1": ["control", 8000],
        "QC1": ["qc", 8000],
    })
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = filter_proc.process(df, skew_threshold=0.66)
        assert result.success
        assert any("skew_threshold" in str(warning.message) for warning in w)
```

- [ ] **Step 16: 執行 test_feature_filter.py 確認通過**

Run: `PYTHONPATH=ms-core/src pytest tests/test_feature_filter.py -v --tb=short -x`
Expected: ALL PASS

### Task 3b: 更新其他測試檔案

- [ ] **Step 17: 修改 test_feature_filter_widget.py**

- 移除所有 `skew_enabled_switch`、`skew_threshold`、`enable_skew_threshold` 引用
- 新增 `intensity_fc` 相關 assertions
- 更新 `test_feature_filter_widget_run_processing_passes_toggle_flags` 中的參數

- [ ] **Step 18: 修改 test_gui_pipeline_session.py**

- 移除 `enable_skew_threshold` assertions
- 新增 `enable_intensity_fc_threshold` assertions

- [ ] **Step 19: 修改 test_adapter_runtime_contracts.py**

搜尋並替換 `skew_threshold` → 移除，新增 `intensity_fc_threshold`

- [ ] **Step 20: 修改 test_cli_parquet_chain.py**

搜尋並替換 CLI 參數中的 `skew_threshold` → 移除，新增 `intensity_fc_threshold`

- [ ] **Step 21: 修改 test_final_export_cache_policy.py**

移除 `skew_threshold=0.66` fixture 參數，新增 `intensity_fc_threshold=2.0`

- [ ] **Step 22: 執行全量測試**

Run: `PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x`
Expected: ALL 141+ tests PASS

---

## Task 4: Commit 和 Push

> **前提：** Task 3 Step 22 全量測試通過後才執行以下步驟。

- [ ] **Step 23: Commit ms-core changes**

```bash
cd .worktrees/refactor-step4-gates/ms-core
git add -A
git commit -m "refactor: replace skew gate with intensity fold-change gate

- Remove skew_threshold and enable_skew_threshold parameters
- Add intensity_fc_threshold and enable_intensity_fc_threshold
- Add unique_* stats for marginal contribution of each gate
- Intensity gate computes max(group_mean)/min(group_mean) fold-change
- Add DeprecationWarning for removed skew parameters in **kwargs"
```

- [ ] **Step 24: Push ms-core changes**

```bash
cd .worktrees/refactor-step4-gates/ms-core
git push origin HEAD
```

- [ ] **Step 25: Commit toolkit changes（含 submodule reference）**

```bash
cd .worktrees/refactor-step4-gates
git add ms-core \
        src/ms_preprocessing/config/feature_filter_presets.py \
        src/ms_preprocessing/config/settings.py \
        src/ms_preprocessing/adapters/feature_filter.py \
        src/ms_preprocessing/gui/widgets/feature_filter_widget.py \
        src/ms_preprocessing/main.py \
        scripts/benchmark_step4_io.py \
        tests/
git commit -m "refactor: replace skew gate with intensity fold-change gate

- Remove skew gate (empirically proven 0 unique contribution)
- Add intensity FC gate (max group mean / min group mean)
- Add unique_* stats showing marginal contribution per gate
- Update presets, adapter, GUI, CLI, and all tests
- Bump ms-core submodule for gate logic refactor"
```

- [ ] **Step 26: 最終全量測試確認**

Run: `PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x`
Expected: ALL PASS

---

## Design Decisions & Rationale

### Intensity FC gate 的計算方式

**選擇：** `max(group_mean_intensity) / min(group_mean_intensity)`

**為什麼用 mean 而不是 median：**
- 與現有 ratio 計算一致（都是對整組操作）
- Mean 對異常值敏感 → 在 metabolomics 中，這是優點而非缺點，因為高強度訊號本身就是重要資訊

**為什麼 fold-change 而不是 absolute difference：**
- 強度範圍跨越多個數量級（5,000 到 500,000,000），absolute difference 無法統一標準化
- Fold-change 是 metabolomics 領域的標準量化方式

**單組情境處理：**
- 當只有 1 組時，intensity FC gate 自動停用（與 diff gate 相同行為）
- 需要 ≥ 2 組才能計算 fold-change

**全零/全 NaN 行處理：**
- 所有組 mean 都是 0 或 NaN → fold_change 設為 0.0 → 不通過 gate
- 某些組 mean > 0、其他組 mean = 0 → fold_change = inf → 通過 gate（因為有組偵測到、有組完全沒偵測到 = 有意義差異）

### 預設 threshold = 2.0 的依據

- FC ≥ 2.0 是 metabolomics/proteomics 領域常用的「有意義差異」門檻
- 對應到 log2 fold-change = 1，是常見的 volcano plot 過濾線
- 在 NTU 資料中，保留的 250 features 中有 112 個（45%）FC > 2x，gate 的區分度良好

### 向下相容性

此變更是 **breaking change**：
- `skew_threshold` 和 `enable_skew_threshold` 參數已移除
- **棄用防護**：`process()` 的 `**kwargs` 會檢測已移除的參數名並發出 `DeprecationWarning`
- CLI 的 `--skew-threshold` flag 將被移除（直接不可用）

### unique_* 統計的排除邏輯

`unique_*` 計數排除 protected rows **和** QC 刪除的 features：
- Protected rows 無論如何都保留 → 不歸功於任何 gate
- QC 刪除的 features 即使通過正向 gate 也會被刪除 → 計入 unique 會高估 gate 貢獻
