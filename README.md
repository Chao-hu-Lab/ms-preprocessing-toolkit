# MS Preprocessing Toolkit

質譜數據前處理工具箱 - 整合式 GUI 工具，用於質譜數據的標準化前處理流程。

## 功能概述

本工具整合了四個主要的前處理步驟：

### 1. 資料整理 (Data Organization)
- 標準化資料結構
- 自動偵測並設定 Sample Type
- 設置固定欄位名稱
- 可選擇上機順序 Word 檔案 (.docx) 以依序排序樣本

### 2. ISTD 標記 (ISTD Marking)
- 依 m/z 值排序數據
- 標記內標 (Internal Standard) 特徵
- 基於 ppm 和 RT 容差偵測重複特徵
- 移除 ISTD 標記的列

### 3. 重複訊號刪除 (Duplicate Removal)
- 自動識別 RT、m/z、Intensity 欄位
- 基於容差智慧判別重複訊號
- 保留最高強度訊號
- 支援紅色字體保護機制

### 4. 篩選與缺失值填補 (Feature Filtering)
- 動態識別 Sample Type
- 計算各組訊號比例 (ratio)
- 三重條件篩選：
  - 穩定性：≥2 組 ratio ≥ 背景門檻
  - 偏態：任一組 ratio ≥ 偏態門檻
  - 差異：任兩組差異 ≥ 差異門檻
- 使用組內最小值/2 填補缺失值

## 安裝

### 一般使用者（直接執行）

從 [Releases](https://github.com/bosschen0429/ms-preprocessing-toolkit/releases) 下載最新的 `ms-preprocessing.exe`，直接執行即可，無需安裝 Python 環境。

### 開發者（原始碼安裝）

> **注意：** 本專案包含 git submodule（ms-core），clone 時必須加上 `--recurse-submodules`。

#### 環境需求
- Python 3.9+
- Windows / macOS / Linux

#### 安裝步驟

```bash
# 1. 克隆專案（包含 submodule）
git clone --recurse-submodules https://github.com/bosschen0429/ms-preprocessing-toolkit.git
cd ms-preprocessing-toolkit

# 2. 創建虛擬環境 (建議)
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. 安裝套件
pip install -e .
```

#### 如果忘記加 `--recurse-submodules`

若已 clone 但 submodule 目錄為空，執行以下指令補救：

```bash
git submodule update --init --recursive
```

#### Advanced Dependency Overrides

- Officially supported runtime layout: this repository plus the checked-in `ms-core` submodule.
- External sibling `ms-core` checkouts are treated as a development-only override, not the default deployment contract.
- If you intentionally want to use an external `ms-core` checkout, set one of:
  - `MSPTK_MS_CORE_SRC`
  - `MSPTK_MS_CORE_ROOT`
- If `Data_Normalization_project_v2` lives outside the default discovery layout, set one of:
  - `MSPTK_DNP_SRC`
  - `MSPTK_DNP_PROJECT_ROOT`
- DNP export and launch prefer these explicit overrides before falling back to layout discovery.

## 使用方式

### GUI 模式

```bash
# 直接執行
python main.py

# 或安裝後
ms-preprocessing
```

### 命令列模式

```bash
# 執行全部流程
python main.py --input data.xlsx --output processed.xlsx

# 執行特定步驟
python main.py --input data.xlsx --step duplicate-removal --mz-tol 20 --rt-tol 1.0

# 查看幫助
python main.py --help
```

### 命令列參數

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `--input, -i` | 輸入檔案路徑 | - |
| `--output, -o` | 輸出檔案路徑 | 自動生成 |
| `--step` | 執行步驟 (organize/istd/duplicate-removal/filter/all) | all |
| `--mz-tol` | m/z 容差 (ppm) | 20 |
| `--istd-mz` | ISTD m/z 清單（逗號分隔） | 內建預設 |
| `--istd-record-file` | ISTD 記錄表 (.xlsx) | - |
| `--istd-record-date` | ISTD 日期 (YYYYMMDD) | - |
| `--rt-tol` | RT 容差 (分鐘) | 1.0 |
| `--bg-threshold` | 背景門檻 | 0.33 |
| `--skew-threshold` | 偏態門檻 | 0.66 |
| `--diff-threshold` | 差異門檻 | 0.30 |
| `--method-file` | 上機順序 Word 檔案 (.docx) | - |

## 專案結構

```
ms-preprocessing-toolkit/
├── main.py                          # 主程式入口
├── pyproject.toml                   # 專案配置
├── requirements.txt                 # 依賴清單
├── README.md                        # 說明文件
│
├── src/ms_preprocessing/
│   ├── __init__.py
│   ├── main.py                      # CLI 入口點
│   │
│   ├── core/                        # 核心處理模組
│   │   ├── __init__.py
│   │   ├── base.py                  # 基礎類別
│   │   ├── data_organizer.py        # Step 1: 資料整理
│   │   ├── istd_marker.py           # Step 2: ISTD 標記
│   │   ├── duplicate_remover.py     # Step 3: 重複刪除
│   │   └── feature_filter.py        # Step 4: 篩選填補
│   │
│   ├── utils/                       # 工具模組
│   │   ├── __init__.py
│   │   ├── file_handler.py          # 檔案處理
│   │   └── validators.py            # 資料驗證
│   │
│   ├── gui/                         # GUI 模組
│   │   ├── __init__.py
│   │   ├── main_window.py           # 主視窗
│   │   ├── styles.py                # 樣式設定
│   │   └── widgets/                 # UI 元件
│   │       ├── __init__.py
│   │       ├── base_widget.py
│   │       ├── data_organizer_widget.py
│   │       ├── istd_marker_widget.py
│   │       ├── duplicate_remover_widget.py
│   │       └── feature_filter_widget.py
│   │
│   └── config/                      # 配置模組
│       ├── __init__.py
│       └── settings.py              # 設定管理
│
└── tests/                           # 測試
    ├── __init__.py
    ├── conftest.py
    ├── test_data_organizer.py
    ├── test_duplicate_remover.py
    └── test_feature_filter.py
```

## 資料格式

### 輸入格式要求

支援的檔案格式：
- Excel (.xlsx, .xls)
- CSV (.csv)
- TSV (.tsv, .txt)

預期的資料結構：
```
| FeatureID       | Tolerance | Sample1 | Sample2 | QC1  | ... |
|-----------------|-----------|---------|---------|------|-----|
| Sample_Type     | na        | case    | case    | qc   | ... |
| 100.1234/1.50   | 20/0.5    | 5000    | 5500    | 5200 | ... |
| 200.5678/2.50   | na        | 6000    | 6500    | 6200 | ... |
```

- 第一欄：FeatureID (格式: m/z/RT)
- 第二欄：Tolerance (ppm/RT 容差，可為 "na")
- 第二列：Sample_Type (樣本類型標籤)

### Sample Type 標籤

| 標籤 | 說明 |
|------|------|
| case | 實驗組 |
| control | 對照組 |
| qc | 品質控制樣本 |
| blank | 空白樣本 (排除) |
| standard | 標準品 (排除) |

## 開發

### 執行測試

完整測試策略、責任邊界與精準測試範圍請看
[docs/TESTING.md](docs/TESTING.md)。

```powershell
# 安裝開發依賴
python -m pip install -e ".[dev]"

# 快速 smoke
$env:PYTHONPATH='ms-core/src'
python -m pytest -m smoke -v --tb=short

# top-level full suite
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

### 程式碼風格

```bash
# 格式化
black src/

# Lint
ruff check src/

# 類型檢查
mypy src/
```

## 授權

MIT License

## 致謝

本工具整合並改寫自以下專案：
- ISTD 標記邏輯: FindSTDs_mzRT_Jia_Simplified.bas
- 重複訊號刪除: [ms-data-processor](https://github.com/bosschen0429/ms-data-processor)
- 特徵篩選與填補: Feature_barrier_V3.bas

## Step 4 + Performance Notes (2026-03-04)

- Step 4 imputation now treats both `NaN` and `0` as missing values in sample and QC columns.
- Intermediate workflow outputs now prefer parquet for Step 1-3 auto-save paths.
- Parquet cache is enabled by default (`SAVE_PARQUET_CACHE = True`) to speed repeated reloads.
- Final user-facing deliverables remain `.xlsx` (including Step 4 export and final output).

## Unified Parquet V2 (2026-03-05)

- Step1-4 intermediate format = parquet
- final export/DNP = xlsx
- Step4 zero-as-missing default behavior
- Unified Parquet V2 rollout checklist: `docs/plans/2026-03-05-unified-parquet-v2-rollout-checklist.md`
