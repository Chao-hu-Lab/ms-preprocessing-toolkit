# Small-N Wilson CI Correction & QC Warning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 對生物組別 N < 10 自動套用 Wilson CI 修正（避免比例高估），並在 QC 樣本數不足時於執行後記錄提示訊息。

**Architecture:**
- ms-core 層加入 Wilson CI 下界計算，在 `_filter_features` 中針對 N < 10 的生物組別，用 CI 下界取代原始比例做閾值比較。
- toolkit 層的 `FeatureFilterWidget._on_run_clicked()` 加入 pre-run 生物組別 N 檢查，若有小組別則彈出說明 Wilson CI 的確認 dialog；執行完後在 log 附加 QC N 提示。
- adapter 層新增 `get_group_summary()` 供 widget 在 pre-run 查詢各組別 N。

**Tech Stack:** Python 3.11+, numpy, pandas, pytest, customtkinter, scipy（Wilson CI 純 numpy 自行計算，不引入新依賴）

---

## 分支建立

在開始任何程式碼修改前，先建立 feature branch（ms-core 和 toolkit 各自建立）。

- [ ] **建立 ms-core feature branch**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
git checkout master
git pull
git checkout -b feat/small-n-wilson-ci
```

- [ ] **建立 toolkit worktree**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit"
git worktree add .worktrees/small-n-wilson-ci -b feat/small-n-wilson-ci
```

後續所有 toolkit 修改均在 `.worktrees/small-n-wilson-ci/` 目錄進行。

---

## Task 1: ms-core — Wilson CI helper + 統計資訊補充

**Files:**
- Modify: `ms-core/src/ms_core/preprocessing/ms_quality_filter.py`

### 背景

`_filter_features` 中 stable gate 和 MNAR high side 目前直接比較原始 ratio（`ratio_matrix >= threshold`）。
對 N < 10 的組別，觀測比例不穩定，需用 Wilson CI 95% 下界取代。

Wilson CI 下界公式（向量化版本）：

```
z = 1.96
p_lower = (p + z²/2n - z·√(p(1-p)/n + z²/4n²)) / (1 + z²/n)
```

N >= 10 的組別維持原始比例（不修正）。

### 步驟

- [ ] **Step 1: 寫 Wilson CI helper 的失敗測試**

在 `ms-core/tests/test_feature_filter_small_n.py`（新建）：

```python
"""Tests for Wilson CI correction in FeatureFilter."""
from __future__ import annotations
import numpy as np
import pytest
from ms_core.preprocessing.ms_quality_filter import FeatureFilter


def test_wilson_lower_large_n_is_close_to_p() -> None:
    ff = FeatureFilter()
    p = np.array([0.8])
    result = ff._wilson_lower_vec(p, n=1000)
    # N large → lower bound ≈ p
    assert abs(float(result[0]) - 0.8) < 0.02


def test_wilson_lower_small_n_is_significantly_below_p() -> None:
    ff = FeatureFilter()
    p = np.array([0.8])  # 4/5 = 0.8
    result = ff._wilson_lower_vec(p, n=5)
    # Wilson lower for 4/5 ≈ 0.37 (much below 0.8)
    assert float(result[0]) < 0.5


def test_wilson_lower_clamps_to_zero_for_zero_proportion() -> None:
    ff = FeatureFilter()
    p = np.array([0.0])
    result = ff._wilson_lower_vec(p, n=5)
    assert float(result[0]) >= 0.0


def test_wilson_lower_clamps_to_one_for_full_proportion() -> None:
    ff = FeatureFilter()
    p = np.array([1.0])
    result = ff._wilson_lower_vec(p, n=100)
    assert float(result[0]) <= 1.0


def test_wilson_lower_zero_n_returns_zeros() -> None:
    ff = FeatureFilter()
    p = np.array([0.5, 0.8])
    result = ff._wilson_lower_vec(p, n=0)
    np.testing.assert_array_equal(result, np.zeros(2))
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
uv run pytest tests/test_feature_filter_small_n.py -v
```

預期結果：`AttributeError: 'FeatureFilter' object has no attribute '_wilson_lower_vec'`

- [ ] **Step 3: 在 `ms_quality_filter.py` 新增 `_wilson_lower_vec` 方法**

在 `FeatureFilter` class 內，`_filter_features` 之前，加入：

```python
@staticmethod
def _wilson_lower_vec(p: np.ndarray, n: int, z: float = 1.96) -> np.ndarray:
    if n == 0:
        return np.zeros_like(p, dtype=float)
    z2 = z * z
    n_f = float(n)
    numerator = p + z2 / (2 * n_f) - z * np.sqrt(p * (1 - p) / n_f + z2 / (4 * n_f * n_f))
    denominator = 1.0 + z2 / n_f
    return np.clip(numerator / denominator, 0.0, 1.0)
```

- [ ] **Step 4: 執行 Wilson CI helper 測試確認通過**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
uv run pytest tests/test_feature_filter_small_n.py -v
```

預期結果：5 tests PASS

- [ ] **Step 5: 寫 stable gate 在小 N 下比例高估保護的失敗測試**

在 `ms-core/tests/test_feature_filter_small_n.py` 追加：

```python
def _make_df(group_data: dict[str, list]) -> "pd.DataFrame":
    """Build a minimal FeatureFilter-ready DataFrame.

    group_data: {group_name: [v1, v2, ...]} — None means missing (0).
    First row = Sample_Type row; subsequent rows = features.
    """
    import pandas as pd
    cols = {"feature": ["Sample_Type", "f1", "f2"]}
    for gname, vals in group_data.items():
        for i, v in enumerate(vals):
            cols[f"{gname}_{i+1}"] = [gname, v or 0, v or 0]
    return pd.DataFrame(cols)


def test_stable_gate_small_n_rejects_4_of_5() -> None:
    """4/5 = 80% should NOT pass 80% threshold for N=5 after Wilson CI."""
    import pandas as pd
    # Build df: 2 groups, each N=5, feature has ratio 4/5=0.8 in both groups
    signal = 10000  # above default signal_threshold=5000
    absent = 0
    rows = {"feature": ["Sample_Type", "f1"]}
    for g in ("groupA", "groupB"):
        for i in range(4):
            rows[f"{g}_{i+1}"] = [g, signal]
        rows[f"{g}_5"] = [g, absent]  # 4 present, 1 absent → ratio=0.8
    df = pd.DataFrame(rows)
    ff = FeatureFilter()
    result = ff.process(
        df,
        background_threshold=0.8,
        enable_background_threshold=True,
        enable_qc_ratio_threshold=False,
        enable_mnar_gate=False,
    )
    assert result.success
    # With Wilson CI, 4/5 Wilson lower ≈ 0.37 < 0.8 → feature deleted
    assert result.statistics["kept_count"] == 0


def test_stable_gate_large_n_accepts_80_percent() -> None:
    """16/20 = 80% should pass 80% threshold for N=20 (no Wilson correction)."""
    import pandas as pd
    signal = 10000
    absent = 0
    rows = {"feature": ["Sample_Type", "f1"]}
    for g in ("groupA", "groupB"):
        for i in range(16):
            rows[f"{g}_{i+1}"] = [g, signal]
        for i in range(16, 20):
            rows[f"{g}_{i+1}"] = [g, absent]
    df = pd.DataFrame(rows)
    ff = FeatureFilter()
    result = ff.process(
        df,
        background_threshold=0.8,
        enable_background_threshold=True,
        enable_qc_ratio_threshold=False,
        enable_mnar_gate=False,
    )
    assert result.success
    # N=20, ratio=0.8, Wilson lower ≈ 0.59 < 0.8 → actually still fails
    # Let's use 18/20=0.9 which has Wilson lower ≈ 0.70 > 0.8... no.
    # Actually for N=20, threshold=0.8: the correction only applies for N<10
    # So N=20 uses raw ratio 0.8 >= 0.8 → passes
    assert result.statistics["kept_count"] == 1
```

- [ ] **Step 6: 執行測試確認失敗（stable gate 尚未有 Wilson CI）**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
uv run pytest tests/test_feature_filter_small_n.py::test_stable_gate_small_n_rejects_4_of_5 -v
```

預期結果：FAIL（feature 目前被保留，但 Wilson CI 後應被刪除）

- [ ] **Step 7: 在 `_filter_features` 加入 Wilson CI 應用邏輯**

找到 `_filter_features` 中 ratio matrix 建立後、stable_keep 計算前（約 line 468），加入 Wilson CI effective matrix：

```python
# Wilson CI correction for small biological groups (N < 10).
# Replace raw ratio with Wilson 95% CI lower bound for groups where N < 10.
# This prevents small groups from passing thresholds via unreliable high proportions.
_SMALL_N_THRESHOLD = 10
effective_matrix = ratio_matrix.copy()
if ratio_matrix.shape[1] > 0:
    for j, group_name in enumerate(group_names):
        n = len(group_info["groups"][group_name])
        if n < _SMALL_N_THRESHOLD:
            effective_matrix[:, j] = self._wilson_lower_vec(ratio_matrix[:, j], n)
```

然後修改 stable_keep 和 mnar high side 使用 `effective_matrix`：

```python
# 原本:
# stable_keep = (ratio_matrix >= bg_threshold).sum(axis=1) >= required_groups
# 改為:
stable_keep = (effective_matrix >= bg_threshold).sum(axis=1) >= required_groups
```

對 MNAR high side（約 line 474）：

```python
# 原本:
# mnar_keep = (
#     (ratio_matrix >= high_det_thresh).any(axis=1)
#     & (ratio_matrix <= low_det_thresh).any(axis=1)
#     ...
# )
# 改為（high side 用 effective_matrix，low side 維持原始 ratio）:
mnar_keep = (
    (effective_matrix >= high_det_thresh).any(axis=1)
    & (ratio_matrix <= low_det_thresh).any(axis=1)
    if (enable_mnar_gate and ratio_matrix.shape[1] >= 2)
    else np.zeros(n_features, dtype=bool)
)
```

- [ ] **Step 8: 執行 stable gate 測試確認通過**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
uv run pytest tests/test_feature_filter_small_n.py -v
```

預期結果：所有測試 PASS

- [ ] **Step 9: 在 statistics 加入 `qc_count` 和 `group_counts`**

在 `process()` 方法中組合 stats 的地方（`final_features` 附近），加入：

```python
stats = {
    **filter_stats,
    "final_features": len(result_df) - 1,
    "groups_detected": len(group_info["groups"]),
    "has_qc": group_info["has_qc"],
    "qc_count": len(group_info.get("qc_cols", [])),
    "group_counts": {
        gname: len(cols) for gname, cols in group_info["groups"].items()
    },
}
```

- [ ] **Step 10: 執行完整 ms-core 測試**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
uv run pytest tests/ -v --tb=short
```

預期結果：所有既有測試 + 新測試全部 PASS

- [ ] **Step 11: 在 ms-core commit**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
git add src/ms_core/preprocessing/ms_quality_filter.py tests/test_feature_filter_small_n.py
git commit -m "feat: Wilson CI correction for small biological groups (N<10)

- Add _wilson_lower_vec() helper for 95% Wilson CI lower bound
- Apply Wilson lower bound to stable gate and MNAR high threshold
  when group N < 10 (preserves raw ratio for N >= 10)
- Add qc_count and group_counts to process() statistics output"
```

- [ ] **Step 12: push ms-core feature branch**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
git push origin feat/small-n-wilson-ci
```

---

## Task 2: ms-core PR（在 GitHub 開 PR）

- [ ] **開 ms-core PR**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
gh pr create \
  --title "feat: Wilson CI correction for small biological groups (N<10)" \
  --body "## Summary
- Add \`_wilson_lower_vec()\` helper using 95% Wilson CI lower bound formula
- Apply Wilson CI correction to stable gate and MNAR high threshold comparisons when group N < 10
- N >= 10 groups use raw ratio (no change to existing behavior)
- Add \`qc_count\` and \`group_counts\` to \`process()\` statistics for downstream use

## Motivation
When a biological group has small N (e.g., N=5), a ratio of 4/5=80% passes the threshold but is statistically unreliable. Wilson CI lower bound for 4/5 is ~37%, accurately reflecting that the true proportion could be much lower.

## Test plan
- [ ] \`test_wilson_lower_large_n_is_close_to_p\`: large N lower bound ≈ p
- [ ] \`test_wilson_lower_small_n_is_significantly_below_p\`: 4/5 → ~0.37
- [ ] \`test_stable_gate_small_n_rejects_4_of_5\`: N=5 at 80% → rejected
- [ ] \`test_stable_gate_large_n_accepts_80_percent\`: N=20 at 80% → accepted
- [ ] All existing ms-core tests pass

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **等 CI 通過後 merge PR**

---

## Task 3: ms-core bump（在 toolkit worktree）

**注意：以下所有步驟在 `.worktrees/small-n-wilson-ci/` 目錄執行**

- [ ] **進入 toolkit worktree**

確認 ms-core PR 已 merge 並打 tag：

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\ms-core"
git checkout master && git pull
# 查看最新 tag：
git tag --sort=-version:refname | head -5
```

根據版本策略（新增 public statistics 欄位 = patch bump），打 tag：

```bash
# 假設目前最新是 v0.X.Y，打 v0.X.Y+1
git tag -a v0.X.Y+1 -m "v0.X.Y+1: Wilson CI correction for small N + qc_count in statistics"
git push origin v0.X.Y+1
```

- [ ] **在 toolkit worktree 更新 submodule**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
cd ms-core
git fetch --tags
git checkout v0.X.Y+1  # 替換為實際 tag
cd ..
git add ms-core
```

---

## Task 4: toolkit adapter — 新增 `get_group_summary`

**Files:**
- Modify: `.worktrees/small-n-wilson-ci/src/ms_preprocessing/adapters/feature_filter.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_feature_filter_widget.py` 追加（toolkit worktree）：

```python
def test_adapter_get_group_summary_returns_correct_n(monkeypatch) -> None:
    import pandas as pd
    from ms_preprocessing.adapters import feature_filter as ff_adapter

    # Build minimal df: 2 groups (A x3, B x5), 1 QC x2
    rows = {"feature": ["Sample_Type", "f1"]}
    for i in range(3):
        rows[f"A_{i+1}"] = ["a", 10000]
    for i in range(5):
        rows[f"B_{i+1}"] = ["b", 10000]
    for i in range(2):
        rows[f"QC_{i+1}"] = ["qc", 10000]
    df = pd.DataFrame(rows)

    summary = ff_adapter.get_group_summary(df)

    assert summary["groups"]["a"]["sample_count"] == 3
    assert summary["groups"]["b"]["sample_count"] == 5
    assert summary["qc_count"] == 2
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
PYTHONPATH=ms-core/src uv run pytest tests/test_feature_filter_widget.py::test_adapter_get_group_summary_returns_correct_n -v
```

預期結果：`AttributeError: module 'ms_preprocessing.adapters.feature_filter' has no attribute 'get_group_summary'`

- [ ] **Step 3: 在 adapter 加入 `get_group_summary`**

在 `src/ms_preprocessing/adapters/feature_filter.py` 的 `count_analysis_groups` 函數後面加入：

```python
def get_group_summary(df: pd.DataFrame) -> dict:
    """Return group summary including sample counts and QC count.

    Wraps FeatureFilter.get_group_summary() so GUI code
    never needs to import ms_core directly.
    """
    raw = _FeatureFilter().get_group_summary(df)
    return {
        "groups": raw.get("groups", {}),
        "qc_count": raw.get("qc_count", 0),
        "has_qc": raw.get("has_qc", False),
    }
```

- [ ] **Step 4: 執行測試確認通過**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
PYTHONPATH=ms-core/src uv run pytest tests/test_feature_filter_widget.py::test_adapter_get_group_summary_returns_correct_n -v
```

預期結果：PASS

- [ ] **Step 5: commit**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
git add src/ms_preprocessing/adapters/feature_filter.py tests/test_feature_filter_widget.py
git commit -m "feat(adapter): expose get_group_summary for pre-run N check"
```

---

## Task 5: toolkit widget — Pre-run 小 N 警告 dialog

**Files:**
- Modify: `.worktrees/small-n-wilson-ci/src/ms_preprocessing/gui/widgets/feature_filter_widget.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_feature_filter_widget.py` 追加：

```python
def test_on_run_clicked_shows_small_group_dialog_when_any_group_lt10(
    widget, monkeypatch
) -> None:
    """When any biological group N < 10, _confirm_small_group_run must be called."""
    import pandas as pd

    # Build df: 1 group A with N=5, 1 group B with N=15
    rows = {"feature": ["Sample_Type", "f1"]}
    for i in range(5):
        rows[f"A_{i+1}"] = ["a", 10000]
    for i in range(15):
        rows[f"B_{i+1}"] = ["b", 10000]
    df = pd.DataFrame(rows)
    widget.set_data(df)

    called_with: list[dict] = []

    def fake_confirm(small_groups: dict) -> bool:
        called_with.append(small_groups)
        return False  # user cancels

    monkeypatch.setattr(widget, "_confirm_small_group_run", fake_confirm)

    widget._on_run_clicked()

    assert len(called_with) == 1
    assert "a" in called_with[0]
    assert called_with[0]["a"] == 5


def test_on_run_clicked_skips_small_group_dialog_when_all_groups_gte10(
    widget, monkeypatch
) -> None:
    """When all biological groups N >= 10, no small-group dialog."""
    import pandas as pd

    rows = {"feature": ["Sample_Type", "f1"]}
    for i in range(10):
        rows[f"A_{i+1}"] = ["a", 10000]
    for i in range(12):
        rows[f"B_{i+1}"] = ["b", 10000]
    df = pd.DataFrame(rows)
    widget.set_data(df)

    confirm_called = []
    monkeypatch.setattr(widget, "_confirm_small_group_run", lambda _: confirm_called.append(True) or False)
    # Also monkeypatch super()._on_run_clicked to avoid actual processing
    monkeypatch.setattr(
        "ms_preprocessing.gui.widgets.base_widget.BaseProcessingWidget._on_run_clicked",
        lambda self: None,
    )

    widget._on_run_clicked()

    assert len(confirm_called) == 0
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
PYTHONPATH=ms-core/src uv run pytest tests/test_feature_filter_widget.py::test_on_run_clicked_shows_small_group_dialog_when_any_group_lt10 tests/test_feature_filter_widget.py::test_on_run_clicked_skips_small_group_dialog_when_all_groups_gte10 -v
```

預期結果：FAIL（method 不存在）

- [ ] **Step 3: 在 `feature_filter_widget.py` 加入新方法**

在 `_confirm_single_group_run` 方法後加入：

```python
def _detect_small_biological_groups(self) -> dict[str, int]:
    """Return {group_name: n} for biological groups with N < 10."""
    if self._data is None:
        return {}
    summary = feature_filter_adapter.get_group_summary(self._data)
    return {
        name: info["sample_count"]
        for name, info in summary.get("groups", {}).items()
        if info["sample_count"] < 10
    }

def _confirm_small_group_run(self, small_groups: dict[str, int]) -> bool:
    """Show Wilson CI warning for small biological groups.

    Extracted as a separate method so tests can monkeypatch it without
    needing a real Tk dialog.
    """
    import tkinter.messagebox

    group_lines = "\n".join(
        f"  {name}：N={n}（每缺失 1 筆影響 {100 / n:.1f}%）"
        for name, n in small_groups.items()
    )
    return bool(
        tkinter.messagebox.askokcancel(
            "小樣本警告",
            f"偵測到以下組別樣本數不足（建議 N≥10）：\n{group_lines}\n\n"
            "系統將自動套用 Wilson CI 校正，小 N 組別需更高比例才能通過門檻。\n"
            "例：N=5 時，80% 門檻實際需要近 100% 檢出。\n\n"
            "確認要繼續嗎？",
            parent=self,
        )
    )
```

然後修改 `_on_run_clicked`，在單組別檢查後加入小 N 檢查：

```python
def _on_run_clicked(self) -> None:
    """Override to check for single-group and small-N conditions before starting worker."""
    self._allow_single_group_stable = False
    if self._data is not None and self.bg_enabled_var.get():
        if self._count_analysis_groups() == 1:
            if not self._confirm_single_group_run():
                return
            self._allow_single_group_stable = True

    if self._data is not None:
        small_groups = self._detect_small_biological_groups()
        if small_groups and not self._confirm_small_group_run(small_groups):
            return

    super()._on_run_clicked()
```

- [ ] **Step 4: 執行測試確認通過**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
PYTHONPATH=ms-core/src uv run pytest tests/test_feature_filter_widget.py::test_on_run_clicked_shows_small_group_dialog_when_any_group_lt10 tests/test_feature_filter_widget.py::test_on_run_clicked_skips_small_group_dialog_when_all_groups_gte10 -v
```

預期結果：2 tests PASS

- [ ] **Step 5: commit**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
git add src/ms_preprocessing/gui/widgets/feature_filter_widget.py tests/test_feature_filter_widget.py
git commit -m "feat(widget): pre-run Wilson CI warning for biological groups N<10"
```

---

## Task 6: toolkit widget — QC N log 提示

**Files:**
- Modify: `.worktrees/small-n-wilson-ci/src/ms_preprocessing/gui/widgets/feature_filter_widget.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_feature_filter_widget.py` 追加：

```python
def test_run_processing_logs_qc_small_n_note(widget, monkeypatch) -> None:
    """When QC N < 10, run_processing should emit a log note about per-sample impact."""
    import pandas as pd
    from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

    def fake_run_from_df(data, **kwargs):
        return ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={
                "kept_count": 1,
                "deleted_count": 0,
                "qc_count": 7,  # small QC N
                "group_counts": {"tumor": 20},
                "has_qc": True,
                "groups_detected": 1,
                "final_features": 1,
            },
        )

    monkeypatch.setattr(
        "ms_preprocessing.adapters.feature_filter.run_from_df",
        fake_run_from_df,
    )

    log_messages: list[str] = []
    widget.on_log = lambda msg: log_messages.append(msg)

    import pandas as pd
    widget._data = pd.DataFrame({"f": ["Sample_Type", "f1"]})
    widget.run_processing(widget._data)

    qc_logs = [m for m in log_messages if "QC" in m and "14.3" in m]
    assert len(qc_logs) == 1


def test_run_processing_no_qc_note_when_qc_n_gte10(widget, monkeypatch) -> None:
    """When QC N >= 10, no QC note should be emitted."""
    import pandas as pd
    from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

    def fake_run_from_df(data, **kwargs):
        return ProcessingResult(
            success=True,
            step="feature_filter",
            output_path=None,
            data=data.copy(),
            metadata=ProcessingMetadata(),
            statistics={
                "kept_count": 1,
                "deleted_count": 0,
                "qc_count": 10,
                "has_qc": True,
                "groups_detected": 1,
                "final_features": 1,
            },
        )

    monkeypatch.setattr(
        "ms_preprocessing.adapters.feature_filter.run_from_df",
        fake_run_from_df,
    )

    log_messages: list[str] = []
    widget.on_log = lambda msg: log_messages.append(msg)

    widget._data = pd.DataFrame({"f": ["Sample_Type", "f1"]})
    widget.run_processing(widget._data)

    qc_warn_logs = [m for m in log_messages if "QC 提示" in m]
    assert len(qc_warn_logs) == 0
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
PYTHONPATH=ms-core/src uv run pytest tests/test_feature_filter_widget.py::test_run_processing_logs_qc_small_n_note tests/test_feature_filter_widget.py::test_run_processing_no_qc_note_when_qc_n_gte10 -v
```

預期結果：FAIL

- [ ] **Step 3: 在 `run_processing` 加入 QC N log 提示**

在 `run_processing` 方法中，`self.log(f"Statistics: {result.statistics}")` 之後加入：

```python
if result.statistics:
    self.log(f"Statistics: {result.statistics}")
    qc_n = result.statistics.get("qc_count", 0)
    if 0 < qc_n < 10:
        step_pct = round(100 / qc_n, 1)
        self.log(
            f"[QC 提示] QC N={qc_n}（建議 ≥10）："
            f"每缺失 1 筆 QC 樣本，ratio 下降 {step_pct}%"
        )
```

- [ ] **Step 4: 執行測試確認通過**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
PYTHONPATH=ms-core/src uv run pytest tests/test_feature_filter_widget.py::test_run_processing_logs_qc_small_n_note tests/test_feature_filter_widget.py::test_run_processing_no_qc_note_when_qc_n_gte10 -v
```

預期結果：2 tests PASS

- [ ] **Step 5: commit**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
git add src/ms_preprocessing/gui/widgets/feature_filter_widget.py tests/test_feature_filter_widget.py
git commit -m "feat(widget): log QC N<10 per-sample impact note after run"
```

---

## Task 7: 完整測試 + toolkit PR

- [ ] **Step 1: 執行完整 toolkit 測試套件**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
PYTHONPATH=ms-core/src uv run pytest tests/ -v --tb=short -x
```

預期結果：全部 82+ tests PASS（含新增測試）

- [ ] **Step 2: push toolkit feature branch**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
git push origin feat/small-n-wilson-ci
```

- [ ] **Step 3: 開 toolkit PR**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit\.worktrees\small-n-wilson-ci"
gh pr create \
  --title "feat(step4): Wilson CI correction for small N + QC N warning" \
  --body "## Summary
- Pre-run check: when any biological group N < 10, show Wilson CI warning dialog before running Step 4
- Post-run: when QC N < 10, log per-sample impact note (e.g., 'QC N=7: 每缺失 1 筆 ratio 下降 14.3%')
- Adapter: expose \`get_group_summary()\` for widget to query group Ns before run
- Bumps ms-core to v0.X.Y+1 (Wilson CI applied automatically in backend)

## Motivation
Small biological groups (N < 5-9) inflate proportion estimates, causing features to pass 80% thresholds on only 4-5 detections. Wilson CI lower bound auto-corrects this without requiring users to understand the statistics.

QC N < 10 is informational only (user may have a fixed experimental design); the note explains the per-sample sensitivity.

## Test plan
- [ ] \`test_on_run_clicked_shows_small_group_dialog_when_any_group_lt10\`
- [ ] \`test_on_run_clicked_skips_small_group_dialog_when_all_groups_gte10\`
- [ ] \`test_run_processing_logs_qc_small_n_note\`
- [ ] \`test_run_processing_no_qc_note_when_qc_n_gte10\`
- [ ] \`test_adapter_get_group_summary_returns_correct_n\`
- [ ] All 82+ existing tests pass

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 注意事項

- Wilson CI 只在 ms-core 層修改，toolkit/adapter 不需感知其存在（對 GUI 透明）
- `_confirm_small_group_run` 和 `_confirm_single_group_run` 均設計為可被 monkeypatch，避免測試時彈出真實 dialog
- QC N 提示只記錄在 log panel，不阻斷任何操作
- ms-core submodule bump 必須在 toolkit PR 之前完成
