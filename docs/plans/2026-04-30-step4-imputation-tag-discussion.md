# Step4 Feature Gate 與下游補值路由收斂紀錄

Status: discussion draft
Date: 2026-04-30

## 背景

Step4 目前同時處理兩件事：

1. 判斷 feature 是否保留進入後續分析。
2. 替 feature 標記 `is_Presence_Absence_Marker`，讓下游決定補值策略。

目前下游補值邏輯已經和這個欄位強綁定：

- `is_Presence_Absence_Marker=True`：走 `min positive / 5` 補值。
- `is_Presence_Absence_Marker=False`：交給下游選定的 default/model-based 補值路徑（目前 `Metaboanalyst_clone` preset 常用 KNN）。

重要邊界：本 toolkit 不負責補值實作。KNN/RF 是否 group-agnostic、如何建模、如何加入未來方法，屬於外部下游專案 `Metaboanalyst_clone` 的責任；本文件只討論 Step4 要輸出什麼 tag/schema，讓下游可以正確分流。

過去常用 `strict` preset 時，這個二分法相對可接受。因為 strict 會先刪掉大部分邊界型 feature，留下來的 feature 通常很明確：要嘛足夠穩定，可以交給下游 default/model-based 補值路徑；要嘛明顯是 MNAR / presence-absence-like，應該走 `min/5`。

現在情境改變在於 DNA adductomics。這類資料常遇到低檢出 feature，不像典型 metabolomics 那樣多數保留 feature 都有穩定高檢出。教授希望採用較寬鬆的 `loose` 策略，是因為低檢出 feature 仍可能有生物意義。這使 Step4 需要保留更多邊界型 feature，但這些 feature 的 missingness mechanism 不會都一樣。

## 目前共識

### 1. 下游 model-based 補值不應分組補值

KNN 或 Random Forest 等 model-based 補值的前提，應該是全矩陣、group-label agnostic。這個規則已由 `Metaboanalyst_clone` 負責；Step4 不實作也不重新驗證 KNN/RF。

不應預設：

- 依 analysis group 分開訓練補值模型。
- 把 analysis group label 當作補值 predictor。

原因是這會人為強化組間差異。即使補完後矩陣看起來更完整，統計結果的可信度會下降。

Step4 可以使用 group-level detection pattern 來判斷 feature 的 missingness 類型，但補值模型本身不應直接看 group label。

### 2. Step4 不是候選 feature review generator

Step4 結束後會直接接校正與統計，不是先產生一批候選 feature 讓人工 review 後再決定。

因此 Step4 的輸出必須足夠可執行：

- 要明確決定保留或刪除。
- 要明確決定補值路由。
- 可以附帶 audit metadata 讓人理解原因，但不能只輸出「待確認」而不給下游可用決策。

### 3. `stable_keep` 和補值安全性不能畫上等號

目前的 `stable_keep` 可以讓 feature 保留下來，但它不等於「這個 feature 適合下游 default/model-based 補值」。

例如：

```text
Group A detection = 0.80
Group B detection = 0.42
Group C detection = 0.00
```

這個 feature 在 A、B 都有 evidence，因此 under loose workflow 直接刪掉可能太激進。但 Group C 完全沒有觀測到這個 feature，若直接交給下游 default/model-based 補值路徑補出一整組值，可信度會受到質疑。

## 現有 Step4 判斷

目前 Step4 主要有三種 keep reason：

1. `stable_keep`
   - 至少兩個 analysis groups 通過 `background_threshold`。

2. `mnar_keep`
   - 至少一組高於 `high_det_thresh`，且至少一組低於 `low_det_thresh`。

3. `ratio_rescue_keep`
   - 最大 / 最小 detection ratio 足夠高，且最低 detection rate 通過獨立 rescue floor。

目前 `is_Presence_Absence_Marker=True` 主要跟著：

```text
mnar_keep or ratio_rescue_keep
```

這會遇到一個問題：feature 可以因為 `stable_keep` 被保留，但同時有一組完全沒檢出，最後仍被標成 `is_Presence_Absence_Marker=False`，導致下游走 default/model-based 補值路徑。

## 需要拆開的三個概念

後續設計應該把以下三件事拆開：

1. **Keep gate**
   - 決定 feature 是否保留。
   - 可能原因包含 `stable_keep`、`mnar_keep`、`ratio_rescue_keep`、protected rows。

2. **Evidence reason**
   - 記錄 feature 為什麼被保留。
   - 同一個 feature 可以同時有多個原因，例如 `stable|mnar_like`。

3. **Imputation tag**
   - 決定下游補值路由。
   - 這是 `is_Presence_Absence_Marker` 的真正語意。
   - 不應完全等同於 keep reason。

簡化後的原則是：

```text
stable_keep = 有證據值得保留
is_Presence_Absence_Marker = 有證據不適合直接交給模型補值
```

## 代表案例推演

| Detection pattern | 解讀 | 是否保留 | 補值標記傾向 |
| --- | --- | --- | --- |
| `0.80 / 0.42 / 0.00` | 一組高檢出、一組中等檢出、一組完全缺失 | 應保留 | 傾向 `is_Presence_Absence_Marker=True` |
| `0.45 / 0.42 / 0.00` | 兩組中等檢出、一組完全缺失，但沒有明顯高檢出組 | loose 下可能保留 | 需要明確規則，不能只因 stable 就直接走 model-based 補值 |
| `0.42 / 0.35 / 0.08` | 整體偏低但不是乾淨二元 presence/absence | loose 下可能保留 | 不應自動標成 presence/absence |
| `0.32 / 0.16 / 0.11` | 低檢出但可能有 ratio rescue evidence | 取決於 rescue floor 與 ratio | 取決於 contrast 是否足夠支持結構性缺失 |

核心困難是：一個 feature 可能同時「值得保留」但「不適合被模型補值過度信任」。

## 建議輸出契約

保留既有欄位：

1. `is_Presence_Absence_Marker`

新增 kept-feature audit 欄位：

1. `Feature_Filter_Keep_Reasons`
   - 記錄保留原因，例如 `stable|mnar`、`ratio_rescue`、`protected`。

2. `Imputation_Tag_Reasons`
   - 記錄補值標記原因，例如 `structural_absence`、`low_overall_detection`。

3. 保留既有 numeric ratio 欄位
   - 例如 `exposure_ratio`、`normal_ratio`、`control_ratio`、`QC_ratio`。
   - 這些欄位是 detection evidence 的 source of truth，不應被壓成 rounded string。

Deleted-feature diagnostics 另外新增：

1. `Feature_Filter_Delete_Reasons`
   - 記錄刪除原因，例如 `no_keep_rule`、`qc_zero|no_keep_rule`、`qc_low|stable`。

因此，除了既有 `is_Presence_Absence_Marker`，kept output 會額外看到 **2 個新 metadata 欄位**，deleted-feature diagnostic output 會額外看到 **1 個診斷欄位**。既有 ratio 欄位會繼續作為 feature-level metadata 傳遞。

這些欄位是 feature-level metadata，不是 sample intensity columns。

## 對下游的影響

### 1. 補值路由

補值 router 可以先維持現有相容行為：

```text
is_Presence_Absence_Marker=True  -> min positive / 5
is_Presence_Absence_Marker=False -> downstream default/model-based imputation path
```

新增欄位初期不需要直接驅動補值，只要負責解釋 Step4 為什麼做出這個標記。

未來如果 downstream 加入 Random Forest，也應在 `Metaboanalyst_clone` 沿用同一個約束：

- 不預設使用 group label 當 predictor。
- 不預設依 group 分開補值。
- 只對被判定為 model-imputable 的 feature 使用。

### 2. Calibration 與 statistical analysis

校正與統計模組必須把新增 metadata 欄位排除在 numeric feature matrix 之外。

它們應被視為和 `is_Presence_Absence_Marker` 同類型的 metadata 欄位。

如果下游目前假設「只有一個 trailing metadata column」，就需要更新 column detector 或 metadata exclusion list。否則可能把 `Feature_Filter_Keep_Reasons`、`Imputation_Tag_Reasons`、`*_ratio` 這類 metadata 誤當成待分析 feature。

### 3. Final export

Final export 會變寬，但解釋性更高：

- 使用者可以看到低檢出 feature 為什麼被保留。
- 使用者可以看到 feature 為什麼走 `min/5` 或下游 default/model-based 補值路徑。
- 後續 threshold tuning 可以直接根據 audit columns 做檢查，不必重跑 Step4 才知道原因。

代價是所有讀取 final export 的 downstream code 都要正確忽略這些 metadata 欄位。

### 4. Preset 設計

`strict` 可以維持較簡單的行為，因為 strict 本來就會刪掉多數模糊案例。

`loose` 需要更細的 metadata：

- keep gate 可以更寬鬆，保留低檢出但可能有意義的 feature。
- imputation tag gate 要更明確，避免把結構性缺失 feature 默默送進下游 default/model-based 補值路徑。

這不代表 loose 要把所有低檢出 feature 都標成 presence/absence。標記仍應需要足夠 evidence，例如完整缺失組、強 detection contrast，或明確 MNAR-like pattern。

## 尚未決定的問題

1. 除了目前的 `mnar_keep or ratio_rescue_keep`，哪些條件應該讓 `is_Presence_Absence_Marker=True`？

2. `0.45 / 0.42 / 0.00` 這種兩組中等檢出、一組完全缺失的 feature，要自動走 `min/5`，還是需要新的明確 tag reason？

3. DNP 如何保證 `*_ratio` metadata 不進入 calibration matrix，但能原樣傳到 MA？

4. 新增 audit columns 是否永遠輸出，還是只在 profile / export option 開啟時輸出？

5. Random Forest 補值應該在 `Metaboanalyst_clone` 等 Step4 tag contract 穩定後再做，還是同步設計？

## 目前建議

不要直接移除 `stable_keep`。

比較穩的方向是重新定義它的語意：

- `stable_keep` 只表示 feature 有 enough evidence 可以保留。
- `is_Presence_Absence_Marker` 才是下游補值路由的關鍵 tag。
- `loose` 應該允許保留更多 DNA adductomics 的低檢出 feature，但同時必須輸出更多 metadata，避免下游過度信任模型補值。

下一步實作前，應先補 contract tests，至少涵蓋上述代表 detection patterns 與新增輸出欄位，然後再調整 Step4 的 tagging 規則。
