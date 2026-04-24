# 2026-04-22 FH / MZmine Session Note

## 背景

本次目標不是直接修 code，而是先釐清 `FH`、`MZmine`、`metabCombiner`、toolkit duplicate merge 之間的責任分界，避免把資料流失誤判到錯的層。

## 今日結論

### 1. `FH-anchored` 是刻意設計，不是暫時做法

- `FH` 負責提供 `NL dR` 的 MS2 證據。
- 若沒有觸發 `NL dR` tag，`FH` 不會有值。
- `MZmine` 負責補 `MS1 peak` 與協助處理同一支 MS1 重複 trigger。
- `false_positive_fix` 的目的，是用 `MZmine` 補強 `FH` row，而不是決定 `NL dR` 是否存在。

### 2. 舊 merged TSV 中的 `FH row + no MZmine ID`，應優先視為 MZmine 端問題

- 這代表 `FH` 已經 seed 出 row。
- 這時比較像：
  - `MZmine` 沒抓到峰，或
  - `metabCombiner` / matching 沒配上。
- 目前這批 `381` 列暫時歸類為 `metabCombiner` 責任，不是優先追查項。

### 3. `metabCombiner` 不是完全黑箱

- 本機安裝版本：`metabCombiner 1.20.0`
- 已抓 source 到：
  - [metabCombiner-source](</C:/Users/user/Desktop/MS Data process package/metabCombiner-source>)
- 已對齊安裝版本 commit：
  - `32c5536b9565794b11f31557760577acf8e9e86d`
- 已整理中文導讀：
  - [GUIDE.zh-TW.md](</C:/Users/user/Desktop/MS Data process package/metabCombiner-source/GUIDE.zh-TW.md:1>)

### 4. 目前 Python bridge 沒有跑到 upstream 的最終 row reduction

- 現行 bridge：
  - `metabCombiner -> selectAnchors -> fit_gam -> calcScores -> combinedTable`
- **沒有**呼叫：
  - `labelRows()`
  - `reduceTable()`

所以若要找「最終一對一裁決」在哪裡，不應直接假設是在 upstream `metabCombiner` 內完成。

### 5. 目前 workflow 的最終 duplicate 決斷，主要在 toolkit duplicate remover

核心檔案：

- [duplicate_remover.py](</C:/Users/user/Desktop/MS Data process package/ms-preprocessing-toolkit/ms-core/src/ms_core/preprocessing/duplicate_remover.py:449>)

目前規則：

- duplicate group 代表列選擇：
  - `occurrence` 優先
  - `total_intensity` 次之
- donor merge 規則：
  - 只補 `0 / NaN`
  - 不做 `sum`
  - 不做 `per-sample max`
  - 不會用 donor 覆蓋已存在的非零值

這代表它本質上是：

- `pick-one + hole filling`

而不是：

- 真正的 `collapse`

### 6. Step 2 與 Step 3 的 RT tolerance 分工目前是合理的

- Step 2 寬鬆：
  - 用來包住 drift 的 ISTD 候選，方便標記到 ISTD
- Step 3 嚴格：
  - 用來做最後 duplicate merge

這不是衝突設定，而是不同目的。

### 7. 把 Step 3 的 RT tolerance 從 `0.1` 放寬到 `0.5`，在舊資料上影響很小

測試資料：

- [MZmine_aligment_both_DNA_AfterVBA.xlsx](</C:/Users/user/Desktop/NTU cancer/Processed Data/DNA/Mzmine/new_test/20260106 tissue old version/test1/MZmine_aligment_both_DNA_AfterVBA.xlsx>)

比較結果：

- `rt_tolerance = 0.1`
  - `rows_after = 875`
  - `duplicates_removed = 195`
  - `groups_merged = 123`
  - `data_points_recovered = 1056`

- `rt_tolerance = 0.5`
  - `rows_after = 873`
  - `duplicates_removed = 197`
  - `groups_merged = 124`
  - `data_points_recovered = 1058`

結論：

- `0.1 -> 0.5` 只多影響少數 group。
- 目前的主要限制不是 RT window 太小，而是 merge rule 太保守。

## 目前最佳判斷

若要改善最終資料保留率，優先順序應是：

1. 先改 toolkit duplicate remover 的 merge rule
2. 再考慮是否放寬 Step 3 RT tolerance
3. 最後才考慮更深的 `metabCombiner` 客製

目前最值得評估的替代 merge 策略：

- `per-sample max collapse`
- `m/z + RT + pattern similarity` gate 後再 merge

## 下次回來建議先看

- [duplicate_remover.py](</C:/Users/user/Desktop/MS Data process package/ms-preprocessing-toolkit/ms-core/src/ms_core/preprocessing/duplicate_remover.py:449>)
- [metabcombiner_bridge.py](</C:/Users/user/Desktop/MS Data process package/metabcombiner/metabcombiner_bridge.py:1>)
- [GUIDE.zh-TW.md](</C:/Users/user/Desktop/MS Data process package/metabCombiner-source/GUIDE.zh-TW.md:1>)
