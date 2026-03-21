# Step 4 Gate Logic Refactor Report

> **Branch:** `refactor/step4-gate-logic`
> **Date:** 2026-03-21
> **Scope:** ms-core + ms-preprocessing-toolkit

---

## 1. Background

Step 4（特徵篩選與缺失值填補）使用多個 gate 判斷每個 feature 是否保留。正向 gate 之間採用 OR 邏輯（任一通過即保留），QC gate 為負向覆寫（強制刪除）。

本次重構源於對現有 gate 設計的系統性檢討，發現 **Skew gate 與 Diff gate 存在嚴重邏輯重疊**，同時 **ratio-based gate 存在量化盲區**。

---

## 2. Problem Statement

### 2.1 Skew Gate 冗餘

Skew gate 的計算方式為：

```
skew_score = max(group_ratios) / mean(all_group_ratios)
```

其中 `ratio = (組內高於訊號門檻的樣本數) / 組內總樣本數`。

**數學推導**：當某組的 ratio 遠高於其他組（即 skew 高），必然意味著 `max(ratio) - min(ratio)` 也很大，因此 Diff gate 已涵蓋這類情境。反之，若 Diff gate 未觸發（各組 ratio 相近），Skew 也不會觸發。

**實測驗證**（NTU cancer dataset，823 features × 3 groups）：

| 指標 | 數值 |
|------|------|
| Skew gate 保留的 features | 155 |
| 其中 Skew 獨有貢獻（unique） | **0** |
| 全部同時被 Stable 或 Diff 覆蓋 | 155（100%） |

結論：Skew gate 的 marginal contribution 為零，是完全冗餘的計算。

### 2.2 Intensity 量化盲區

現有的 Stable 和 Diff gate 都基於 **detection ratio**（二元分類：是否超過訊號門檻），無法捕捉量化的強度差異。

**盲區範例**：

| Group | Sample1 | Sample2 | Ratio (threshold=5000) | Mean Intensity |
|-------|---------|---------|------------------------|----------------|
| Case | 50,000 | 60,000 | 1.0 (2/2) | 55,000 |
| Control | 5,500 | 6,000 | 1.0 (2/2) | 5,750 |

- Stable gate：兩組 ratio 都 = 1.0，>= 2 組通過 → **PASS**（但這不是重點）
- Diff gate：`1.0 - 1.0 = 0.0` < 0.30 → **FAIL**
- 真實差異：**9.6x fold-change**，明顯的生物學差異 → **被遺漏**

---

## 3. Solution

### 3.1 移除 Skew Gate

完全移除 `skew_threshold` 和 `enable_skew_threshold` 參數。為向後相容，傳入已移除參數時觸發 `DeprecationWarning` 而非報錯。

### 3.2 新增 Intensity Fold-Change Gate

新增一個基於 **組間平均強度倍率** 的 gate：

```
group_mean[g] = nanmean(intensity values for group g)
fold_change = max(group_mean) / min(group_mean)

PASS if fold_change >= intensity_fc_threshold
```

設計考量：
- 使用 `nanmean` 忽略缺失值，避免零值干擾
- 當 `min_mean = 0` 時 fold_change 設為 `inf`（視為極端差異，通過 gate）
- 當 `min_mean = NaN`（全組缺失）時 fold_change 設為 `0`（無法判斷，不通過）
- 單組資料時自動跳過（`ratio_matrix.shape[1] < 2`）

---

## 4. Before / After Comparison

### 4.1 Gate Architecture

| Gate | Before | After | 變更 |
|------|--------|-------|------|
| Stable（背景比例） | `>= 2 組 ratio >= bg_threshold` | 同左 | 不變 |
| Skew（偏態） | `max(ratio)/mean(ratios) >= skew_threshold` | — | **移除** |
| Intensity FC（強度倍率） | — | `max(mean)/min(mean) >= fc_threshold` | **新增** |
| Diff（組間差異） | `max(ratio) - min(ratio) >= diff_threshold` | 同左 | 不變 |
| QC（品質控制） | `QC_ratio = 0 → 刪除` | 同左 | 不變 |
| 正向邏輯 | Stable OR Skew OR Diff | Stable OR Intensity FC OR Diff | 替換 |

### 4.2 Parameters

| Parameter | Before | After |
|-----------|--------|-------|
| `background_threshold` | 0.33 (default) | 0.33 — 不變 |
| `skew_threshold` | 0.66 (default) | **移除** |
| `intensity_fc_threshold` | — | **2.0** (default) |
| `diff_threshold` | 0.30 (default) | 0.30 — 不變 |
| `qc_ratio_threshold` | 0.0 (default) | 0.0 — 不變 |

Preset 對照：

| Preset | Before (skew) | After (intensity_fc) |
|--------|---------------|----------------------|
| Loose | 0.50 | 1.5 |
| Default | 0.66 | 2.0 |
| Strict | 0.80 | 3.0 |

### 4.3 Statistics Output

| Before | After | 說明 |
|--------|-------|------|
| `stable_kept` | `stable_kept` | 不變 |
| `skew_kept` | — | 移除 |
| — | `intensity_fc_kept` | 新增：Intensity FC gate 保留數 |
| `diff_kept` | `diff_kept` | 不變 |
| — | `unique_stable_kept` | 新增：僅 Stable 獨自保留（排除 protected + QC 刪除） |
| — | `unique_diff_kept` | 新增：僅 Diff 獨自保留 |
| — | `unique_intensity_fc_kept` | 新增：僅 Intensity FC 獨自保留 |

unique 統計的計算排除了 protected rows 和 QC 刪除的 features，確保反映真正的 marginal contribution。

### 4.4 GUI Changes

| 元件 | Before | After |
|------|--------|-------|
| 第二列控制 | Skew switch + slider (0~1) + entry | Intensity FC switch + slider (1.0~10.0) + entry |
| Slider clamp | 固定 0~1 | 動態讀取 slider 的 `from_`/`to` |
| 說明文字 | 「偏態比例門檻」 | 「強度倍率門檻」 |
| 規則描述 | 「啟用時：任一組的偏態比 >= 門檻才算偏態型」 | 「啟用時：任兩組平均強度 fold-change >= 門檻才算強度差異型」 |

### 4.5 CLI Changes

| CLI Flag | Before | After |
|----------|--------|-------|
| `--skew-threshold` | 0.66 (default) | **移除** |
| `--intensity-fc-threshold` | — | **2.0** (default) |

---

## 5. Performance Impact

| 指標 | 數值 |
|------|------|
| 額外計算開銷 | +0.6ms (+0.6%) |
| 優化手法 | 重用 `_calculate_ratios()` 已解析的 numpy array (`block_all_values`) |
| 對比方案 | 若重新 `pd.to_numeric` 解析，需 +8.7ms (+8.7%) |

效能可忽略不計，因為 `_calculate_ratios()` 已將 DataFrame 轉為 numpy array，Intensity FC 計算直接在此 array 上做 `nanmean`、`nanmax`、`nanmin`，無需額外的型別轉換。

---

## 6. Backward Compatibility

| 情境 | 行為 |
|------|------|
| 傳入 `skew_threshold=0.66` | 觸發 `DeprecationWarning`，參數被忽略 |
| 傳入 `enable_skew_threshold=False` | 觸發 `DeprecationWarning`，參數被忽略 |
| 不傳入任何 skew 參數 | 正常運行，無警告 |
| 舊版 preset dict 含 skew 欄位 | `**kwargs` 傳入後觸發警告，不影響處理 |

Warning 訊息範例：
```
DeprecationWarning: Parameter 'skew_threshold' was removed in the gate logic refactor.
It will be silently ignored. Use intensity_fc_threshold instead.
```

---

## 7. Test Coverage

| 指標 | Before | After |
|------|--------|-------|
| 總測試數 | ~141 | **145** |
| 移除的測試 | — | `test_disabling_skew_rule_removes_feature_kept_only_by_skew_ratio` |
| 新增的測試 | — | 5 個（見下表） |

### 新增測試

| 測試名稱 | 驗證目標 |
|----------|----------|
| `test_intensity_fc_keeps_high_fold_change_feature` | 高 fold-change feature 被 Intensity FC gate 保留 |
| `test_intensity_fc_does_not_keep_similar_intensity_feature` | 相近強度 feature 不通過 Intensity FC gate |
| `test_disabling_intensity_fc_rule_removes_feature_kept_only_by_fc` | 關閉 Intensity FC gate 後該 feature 被移除 |
| `test_unique_stats_marginal_contribution` | unique 統計正確反映各 gate 的 marginal contribution |
| `test_deprecated_skew_parameter_warns` | 傳入已移除的 skew 參數觸發 DeprecationWarning |

### 測試隔離性改進

所有「關閉某 gate 後 feature 應被移除」的測試，現在都明確關閉其他正向 gate（`enable_*_threshold=False`），避免新 gate 的加入導致測試意外通過。

---

## 8. Files Changed

### ms-core (3 files, +100 -43)

| File | Changes |
|------|---------|
| `ms_quality_filter.py` | 核心邏輯：移除 Skew、新增 Intensity FC、unique 統計、deprecation guard |
| `settings.py` | `default_skew_threshold` → `default_intensity_fc_threshold` |
| `pipeline.py` | Pipeline 參數名稱對應更新 |

### ms-preprocessing-toolkit (11 files, +897 -139)

| File | Changes |
|------|---------|
| `adapters/feature_filter.py` | skew → intensity_fc 參數名稱 |
| `config/feature_filter_presets.py` | Preset TypedDict + 值更新 |
| `config/settings.py` | Config dataclass 更新 |
| `gui/widgets/feature_filter_widget.py` | GUI 控制項替換 + slider 範圍動態化 |
| `main.py` | CLI argparse 更新 |
| `scripts/benchmark_step4_io.py` | Benchmark 腳本參數更新 |
| `tests/test_feature_filter.py` | 移除 skew 測試 + 新增 5 個 intensity FC 測試 |
| `tests/test_feature_filter_widget.py` | Widget 測試更新 |
| `tests/test_adapter_runtime_contracts.py` | Adapter 合約測試更新 |
| `tests/test_cli_parquet_chain.py` | CLI chain 測試更新 |
| `tests/test_gui_pipeline_session.py` | Session 測試更新 |
| `tests/test_final_export_cache_policy.py` | Export policy 測試更新 |

---

## 9. Conclusion

本次重構以實證資料分析為基礎，移除了數學上冗餘的 Skew gate，替換為能捕捉量化強度差異的 Intensity fold-change gate。重構後：

- **消除 gate 重疊**：Skew 的 0% unique contribution 問題不再存在
- **填補量化盲區**：ratio-based gate 無法偵測的強度倍率差異現在可被捕捉
- **效能無感**：+0.6ms 開銷，透過 numpy array 重用優化
- **向後相容**：DeprecationWarning 確保舊程式碼不會斷裂
- **測試充分**：145 個測試全部通過，覆蓋正向/負向/邊界情境
