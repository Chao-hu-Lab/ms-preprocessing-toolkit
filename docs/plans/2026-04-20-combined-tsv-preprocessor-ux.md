# Combined TSV Preprocessor UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an optional Step 1 GUI preprocessor that turns raw combined TSV files into reusable `combined_fix.xlsx` files, then loads that file into the normal toolkit flow.

**Architecture:** Keep `ms-core` responsible for pure DataFrame processing and keep the GUI responsible for file selection, Excel persistence, one-way method-file prefilling, and complete pipeline-state reload. The normal Step 1 GUI flow should always run `normalization`; raw combined TSV processing should happen only through the dedicated preprocessor controls.

**Tech Stack:** Python, pandas, CustomTkinter, pytest, existing `DataOrganizer` / `FileHandler` / `MainWindow` event-handler patterns.

---

### Task 1: Hide Step 1 Mode Selection In GUI

**Files:**
- Modify: `src/ms_preprocessing/gui/widgets/data_organizer_widget.py`
- Test: `tests/test_data_organizer_widget.py`

**Step 1: Write the failing test**

Update the existing Step 1 widget tests so the GUI no longer exposes `mode_selector`, but `get_parameters()` still returns `mode: "normalization"` for compatibility.

```python
def test_data_organizer_widget_hides_mode_selector_and_defaults_normalization(widget) -> None:
    params = widget.get_parameters()

    assert not hasattr(widget, "mode_selector")
    assert not hasattr(widget, "mode_var")
    assert params["mode"] == "normalization"
```

Keep the existing adapter forwarding test, but call `run_processing()` without passing a visible mode from the UI and assert the adapter receives `normalization`.

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_data_organizer_widget.py -q
```

Expected: fail because `mode_selector` / `mode_var` still exist.

**Step 3: Write minimal implementation**

Remove the segmented mode controls from `_create_parameters()`. Keep `get_parameters()` returning:

```python
{
    "mode": "normalization",
    "auto_detect": True,
}
```

Update `apply_parameters()` so it ignores incoming `mode` but still applies `method_file`.

**Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_data_organizer_widget.py -q
```

Expected: pass.

---

### Task 2: Add A Toolkit Adapter Entry Point For Combined Fix Files

**Files:**
- Modify: `src/ms_preprocessing/adapters/data_organizer.py`
- Test: `tests/adapters/test_adapter_data_organizer.py`

**Step 1: Write the failing test**

Add a focused test that `run_combined_fix()` reads a TSV, calls the core processor with `mode="combined_fix"`, and returns a successful `ProcessingResult`.

```python
def test_run_combined_fix_uses_combined_fix_mode(monkeypatch, tmp_path) -> None:
    input_path = tmp_path / "raw.tsv"
    pd.DataFrame({"Mz": [1], "RT": [2], "MZmine ID": ["id"]}).to_csv(
        input_path, sep="\t", index=False
    )
    captured = {}

    def fake_run_processor(df, **kwargs):
        captured.update(kwargs)
        return ProcessingResult(
            success=True,
            step="data_organizer",
            output_path=None,
            data=df.copy(),
            metadata=ProcessingMetadata(),
            statistics={"mode": "combined_fix"},
        )

    monkeypatch.setattr(data_organizer, "_run_processor", fake_run_processor)

    result = data_organizer.run_combined_fix(str(input_path), method_file="method.docx")

    assert result.success is True
    assert captured["mode"] == "combined_fix"
    assert captured["method_file"] == "method.docx"
```

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/adapters/test_adapter_data_organizer.py -q
```

Expected: fail because `run_combined_fix()` does not exist.

**Step 3: Write minimal implementation**

Add:

```python
def run_combined_fix(
    input_path: str,
    *,
    method_file: str | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> ProcessingResult:
    if not os.path.exists(input_path):
        return ProcessingResult(...)
    df = _read_input(input_path)
    return _run_processor(
        df,
        method_file=method_file,
        mode="combined_fix",
        auto_detect=True,
        progress_callback=progress_callback,
    )
```

Reuse the existing missing-file error shape from `run()`.

**Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/adapters/test_adapter_data_organizer.py -q
```

Expected: pass.

---

### Task 3: Add Combined TSV Preprocessor Controls To Step 1

**Files:**
- Modify: `src/ms_preprocessing/gui/widgets/data_organizer_widget.py`
- Test: `tests/test_data_organizer_widget.py`

**Step 1: Write failing tests**

Add tests for these GUI behaviors:

- `combined_tsv_entry`, `combined_method_entry`, and `combined_run_btn` exist.
- no output file picker exists in the preprocessor group; output is system-generated under `OUTPUT/combined_fix/`.
- choosing or setting a combined method can be copied one-way into the normal method field after success.
- changing the normal method field does not change the combined method field.

Example:

```python
def test_combined_method_prefill_is_one_way(widget) -> None:
    widget.combined_method_entry.insert(0, "combined-method.docx")

    widget.prefill_normal_method_from_combined()

    assert widget.method_entry.get() == "combined-method.docx"
    widget.method_entry.delete(0, "end")
    widget.method_entry.insert(0, "normal-method.docx")
    assert widget.combined_method_entry.get() == "combined-method.docx"
```

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_data_organizer_widget.py -q
```

Expected: fail because controls and helper do not exist.

**Step 3: Write minimal implementation**

Create an optional preprocessor group above the normal method controls inside `DataOrganizerWidget._create_parameters()`.

Use existing CustomTkinter primitives and form grid style:

- label: `Combined TSV 前處理（選用）`
- row for combined TSV path
- row for combined method path
- button: `產生 combined_fix`

Add helpers:

```python
def get_combined_preprocessor_paths(self) -> dict[str, str]:
    ...

def prefill_normal_method_from_combined(self) -> None:
    ...
```

Do not run processing directly in the widget yet; the main window should own file persistence and full reload.

**Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_data_organizer_widget.py -q
```

Expected: pass.

---

### Task 4: Wire Combined Fix Execution Through Main Window State

**Files:**
- Modify: `src/ms_preprocessing/gui/event_handlers.py`
- Modify: `src/ms_preprocessing/gui/layout.py` only if callbacks must be passed explicitly
- Test: `tests/test_gui_event_handlers.py`

**Step 1: Write failing tests**

Add a unit test that simulates successful combined preprocessing and verifies:

- adapter `run_combined_fix()` is called once
- output is saved to a collision-safe `.xlsx`
- `_load_file_for_step(0, path=output_path)` is called
- Step 1 normal method is prefilled from the combined method

Use a fake Step 1 widget with:

```python
get_combined_preprocessor_paths()
prefill_normal_method_from_combined()
```

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_gui_event_handlers.py -q
```

Expected: fail because no combined preprocessor handler exists.

**Step 3: Write minimal implementation**

Add an event handler such as `_run_combined_tsv_preprocessor()`.

Implementation rules:

- use existing busy guard before starting
- read paths from the current Step 1 widget
- call `data_organizer_adapter.run_combined_fix()`
- save `result.data` as `.xlsx` using `FileHandler.save_data(..., save_parquet_cache=False)`
- default output path should be collision-safe, under `OUTPUT/combined_fix/`
- after save, call the existing full load path: `_load_file_for_step(0, path=output_path)`
- after load, call Step 1 widget `prefill_normal_method_from_combined()`
- log rows, columns, features removed, and next action
- on failure, do not mutate current input/data/session

**Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_gui_event_handlers.py -q
```

Expected: pass.

---

### Task 5: Prevent Silent Combined TSV Processing In Normal Step 1 GUI Flow

**Files:**
- Modify: `src/ms_preprocessing/gui/widgets/data_organizer_widget.py` or `src/ms_preprocessing/adapters/data_organizer.py`
- Test: `tests/test_data_organizer_widget.py`

**Step 1: Write failing test**

Create a DataFrame with `MZmine ID` in the middle, call `DataOrganizerWidget.run_processing()` in the normal flow, and assert it raises a clear error telling the user to use the Combined TSV preprocessor.

```python
def test_normal_step1_rejects_raw_combined_tsv(widget) -> None:
    df = pd.DataFrame(
        {
            "Mz": [1.0],
            "RT": [2.0],
            "SampleA": [10],
            "MZmine ID": ["id1"],
            "mz": [1.0],
            "rt": [2.0],
            "SampleA.1": [99],
        }
    )

    with pytest.raises(Exception, match="Combined TSV"):
        widget.run_processing(df)
```

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_data_organizer_widget.py -q
```

Expected: fail because normal flow still forwards to core, which silently auto-routes.

**Step 3: Write minimal implementation**

Add a small GUI-layer detector:

```python
def _looks_like_raw_combined_tsv(self, df: pd.DataFrame) -> bool:
    for idx, col in enumerate(df.columns):
        compact = re.sub(r"[^a-z0-9]+", "", str(col).strip().lower())
        if compact == "mzmineid":
            return 2 < idx < len(df.columns) - 1
    return False
```

In normal `run_processing()`, raise a clear error if this returns true.

Do not remove `ms-core` combined modes yet; they remain useful for the dedicated preprocessor, CLI, and tests.

**Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_data_organizer_widget.py -q
```

Expected: pass.

---

### Task 6: Verification And Regression Sweep

**Files:**
- No new source files expected
- Test commands only

**Step 1: Run focused GUI and adapter tests**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/test_data_organizer_widget.py tests/adapters/test_adapter_data_organizer.py tests/test_gui_event_handlers.py -q
```

Expected: pass.

**Step 2: Run full toolkit gate**

Run:

```powershell
$env:PYTHONPATH='ms-core/src;src'; pytest tests/ -v --tb=short -x
```

Expected: `269+ passed`, with the exact count updated for new tests.

**Step 3: Manual smoke with real dataset**

Use:

```text
C:\Users\user\Desktop\NTU cancer\Processed Data\DNA\Mzmine\new_test\preprocese\program3_DNA_alignment.tsv
C:\Users\user\Desktop\NTU cancer\2025台大乳癌組織數據for Jia\20260105中研院台大Breast cancer tissue\20260105 中研院分析.docx
```

Expected:

- combined preprocessor writes `program3_DNA_alignment_combined_fix*.xlsx`
- output shape is `1071 x 93`
- normal Step 1 can load that `.xlsx`
- normal Step 1 produces normalization-style output without re-running combined fix
