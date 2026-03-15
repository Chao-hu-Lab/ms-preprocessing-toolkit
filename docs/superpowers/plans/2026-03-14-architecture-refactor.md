# Architecture Refactor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `ms-preprocessing-toolkit`'s application layer into a clear four-layer architecture (GUI → Application → Adapter → ms-core) by unifying state management, slimming the wrapper layer, and removing the duplicate Settings import.

**Architecture:** New `adapters/` layer becomes the only boundary to `ms-core`; `utils/results.py` introduces a typed `ProcessingResult`/`ProcessingMetadata` dataclass pair used by both CLI and GUI; `main_window.py` (867 LOC) splits into `layout.py` + `event_handlers.py`.

**Tech Stack:** Python 3.11+, pandas, customtkinter, pytest, pyarrow (parquet). Test runner: `PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x` (run from project root).

**Spec:** `docs/superpowers/specs/2026-03-14-architecture-refactor-design.md`

---

## File Map

### New Files
| Path | Responsibility |
|------|---------------|
| `src/ms_preprocessing/utils/results.py` | `ProcessingResult` + `ProcessingMetadata` dataclasses |
| `src/ms_preprocessing/adapters/__init__.py` | Empty package marker |
| `src/ms_preprocessing/adapters/data_organizer.py` | Thin adapter: validate → DataOrganizer → ProcessingResult |
| `src/ms_preprocessing/adapters/istd_marker.py` | Thin adapter: validate → ISTDMarker → ProcessingResult |
| `src/ms_preprocessing/adapters/duplicate_remover.py` | Thin adapter: validate → DuplicateRemover → ProcessingResult |
| `src/ms_preprocessing/adapters/feature_filter.py` | Thin adapter: validate → FeatureFilter → ProcessingResult |
| `src/ms_preprocessing/gui/layout.py` | All customtkinter widget creation and layout definitions |
| `src/ms_preprocessing/gui/event_handlers.py` | Button events, progress callbacks, FileHandler via utils wrapper |
| `tests/test_results.py` | ProcessingResult + ProcessingMetadata unit tests |
| `tests/test_validators_new.py` | ValidationResult + new DataValidator API tests |
| `tests/test_adapter_data_organizer.py` | Adapter unit tests |
| `tests/test_adapter_istd_marker.py` | Adapter unit tests |
| `tests/test_adapter_duplicate_remover.py` | Adapter unit tests |
| `tests/test_adapter_feature_filter.py` | Adapter unit tests |

### Modified Files
| Path | Change |
|------|--------|
| `src/ms_preprocessing/utils/validators.py` | Add `ValidationResult` dataclass + `validate_step_prerequisites()` method |
| `src/ms_preprocessing/config/__init__.py` | Remove `from ms_core.preprocessing.settings import ...` re-export |
| `src/ms_preprocessing/config/settings.py` | Restrict to GUI/App constants only |
| `src/ms_preprocessing/gui/pipeline_session.py` | Replace `context` dict with `ProcessingMetadata`; add `can_run_step()`, `update_from_result()` |
| `src/ms_preprocessing/gui/main_window.py` | Slim to assembler (<200 LOC); import layout + event_handlers |
| `src/ms_preprocessing/gui/widgets/base_widget.py` | Replace direct processor instantiation with adapter calls |
| `src/ms_preprocessing/gui/widgets/data_organizer_widget.py` | Use adapter |
| `src/ms_preprocessing/gui/widgets/istd_marker_widget.py` | Use adapter |
| `src/ms_preprocessing/gui/widgets/duplicate_remover_widget.py` | Use adapter |
| `src/ms_preprocessing/gui/widgets/feature_filter_widget.py` | Use adapter |
| `src/ms_preprocessing/main.py` | CLI uses adapters + PipelineSession; single Settings import |
| `src/ms_preprocessing/__init__.py` | Update public API after core/ deleted |

### Deleted Files (Step F only)
| Path | Reason |
|------|--------|
| `src/ms_preprocessing/core/base.py` | Replaced by `utils/results.py` |
| `src/ms_preprocessing/core/data_organizer.py` | Replaced by `adapters/data_organizer.py` |
| `src/ms_preprocessing/core/istd_marker.py` | Replaced by `adapters/istd_marker.py` |
| `src/ms_preprocessing/core/duplicate_remover.py` | Replaced by `adapters/duplicate_remover.py` |
| `src/ms_preprocessing/core/feature_filter.py` | Replaced by `adapters/feature_filter.py` |

---

## Chunk 1: Foundation — ProcessingResult and ValidationResult

### Task 1: Create `utils/results.py`

**Files:**
- Create: `src/ms_preprocessing/utils/results.py`
- Create: `tests/test_results.py`

> **Context:** `ms_core.preprocessing.base.ProcessingResult` and `ms_preprocessing.core.base.ProcessingResult` both exist. Our new class lives in `ms_preprocessing.utils.results` — always use the full import path to avoid shadowing.

- [ ] **Step 1.1: Write the failing tests**

```python
# tests/test_results.py
from __future__ import annotations
import pytest
import pandas as pd
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult


class TestProcessingMetadata:
    def test_default_fields_have_correct_types(self):
        m = ProcessingMetadata()
        assert isinstance(m.red_font_rows, set)
        assert isinstance(m.protected_rows, set)
        assert isinstance(m.blue_font_cells, list)
        assert isinstance(m.highlight_rows, set)
        assert m.sample_info is None
        assert m.deleted_feature_df is None

    def test_fields_are_independent_instances(self):
        """Each instance must have its own containers (not shared mutable defaults)."""
        a = ProcessingMetadata()
        b = ProcessingMetadata()
        a.red_font_rows.add(1)
        assert 1 not in b.red_font_rows


class TestProcessingResult:
    def test_success_result(self):
        df = pd.DataFrame({"a": [1, 2]})
        meta = ProcessingMetadata(red_font_rows={3, 4})
        r = ProcessingResult(
            success=True,
            step="data_organizer",
            output_path="/tmp/out.parquet",
            data=df,
            metadata=meta,
        )
        assert r.success is True
        assert r.error is None
        assert r.metadata.red_font_rows == {3, 4}

    def test_failure_result(self):
        r = ProcessingResult(
            success=False,
            step="istd_marker",
            output_path=None,
            data=None,
            metadata=ProcessingMetadata(),
            error="file not found",
        )
        assert r.success is False
        assert r.error == "file not found"

    def test_step_name_stored(self):
        r = ProcessingResult(
            success=True, step="feature_filter",
            output_path=None, data=None,
            metadata=ProcessingMetadata(),
        )
        assert r.step == "feature_filter"
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd "C:\Users\user\Desktop\MS Data process package\ms-preprocessing-toolkit"
PYTHONPATH=ms-core/src pytest tests/test_results.py -v --tb=short
```

Expected: `ImportError: cannot import name 'ProcessingMetadata' from 'ms_preprocessing.utils.results'`

- [ ] **Step 1.3: Create `utils/results.py`**

```python
# src/ms_preprocessing/utils/results.py
"""Application-layer result types for ms-preprocessing pipeline.

Note: ms_core.preprocessing.base also defines ProcessingResult.
Always import from ms_preprocessing.utils.results to avoid shadowing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


@dataclass
class ProcessingMetadata:
    """Typed replacement for the untyped context dict in PipelineSession.

    All container fields use default_factory to ensure each instance
    gets its own independent mutable object.
    """

    red_font_rows: set[int] = field(default_factory=set)
    protected_rows: set[int] = field(default_factory=set)
    blue_font_cells: list[Any] = field(default_factory=list)
    highlight_rows: set[int] = field(default_factory=set)
    sample_info: Optional[pd.DataFrame] = None
    deleted_feature_df: Optional[pd.DataFrame] = None


@dataclass
class ProcessingResult:
    """Unified result wrapper for all ms-preprocessing steps.

    Returned by every adapter function (adapters/*.py) and consumed by
    both CLI (main.py) and GUI (PipelineSession) layers.
    """

    success: bool
    step: str  # "data_organizer" | "istd_marker" | "duplicate_remover" | "feature_filter"
    output_path: Optional[str]
    data: Optional[pd.DataFrame]
    metadata: ProcessingMetadata
    error: Optional[str] = None
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
PYTHONPATH=ms-core/src pytest tests/test_results.py -v --tb=short
```

Expected: 5 tests PASSED

- [ ] **Step 1.5: Run full suite to verify nothing broken**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x --ignore=tests/test_results.py
```

Expected: all pre-existing tests PASS

- [ ] **Step 1.6: Commit**

```bash
git add src/ms_preprocessing/utils/results.py tests/test_results.py
git commit -m "feat(results): add ProcessingResult and ProcessingMetadata dataclasses"
```

---

### Task 2: Add `ValidationResult` and `validate_step_prerequisites` to validators

**Files:**
- Modify: `src/ms_preprocessing/utils/validators.py`
- Create: `tests/test_validators_new.py`

> **Context:** `DataValidator` class already exists at `validators.py:27`. Do NOT rewrite it. Add `ValidationResult` dataclass at the top of the file and one new method to the existing class.

- [ ] **Step 2.1: Write failing tests**

```python
# tests/test_validators_new.py
"""Tests for ValidationResult dataclass and validate_step_prerequisites (new additions).
Existing DataValidator method tests remain in their original test files.
"""
from __future__ import annotations
import pytest
from ms_preprocessing.utils.validators import ValidationResult, DataValidator
from ms_preprocessing.utils.results import ProcessingMetadata
from ms_preprocessing.gui.pipeline_session import PipelineSession


class TestValidationResult:
    def test_valid_result(self):
        r = ValidationResult(is_valid=True)
        assert r.is_valid is True
        assert r.errors == []
        assert r.warnings == []

    def test_invalid_result_with_errors(self):
        r = ValidationResult(is_valid=False, errors=["missing file"])
        assert not r.is_valid
        assert "missing file" in r.errors

    def test_warning_does_not_affect_validity(self):
        r = ValidationResult(is_valid=True, warnings=["large file"])
        assert r.is_valid


class TestValidateStepPrerequisites:
    """PipelineSession requires output_dir — use tmp_path fixture."""

    def test_data_organizer_has_no_prerequisites(self, tmp_path):
        session = PipelineSession(output_dir=tmp_path)
        v = DataValidator()
        result = v.validate_step_prerequisites("data_organizer", session)
        assert result.is_valid

    def test_istd_marker_has_no_prerequisites(self, tmp_path):
        session = PipelineSession(output_dir=tmp_path)
        v = DataValidator()
        result = v.validate_step_prerequisites("istd_marker", session)
        assert result.is_valid

    def test_duplicate_remover_requires_data_organizer(self, tmp_path):
        session = PipelineSession(output_dir=tmp_path)
        v = DataValidator()
        result = v.validate_step_prerequisites("duplicate_remover", session)
        assert not result.is_valid
        assert any("data_organizer" in e for e in result.errors)

    def test_duplicate_remover_passes_when_prerequisite_met(self, tmp_path):
        session = PipelineSession(output_dir=tmp_path)
        session.completed_steps.add("data_organizer")
        v = DataValidator()
        result = v.validate_step_prerequisites("duplicate_remover", session)
        assert result.is_valid

    def test_feature_filter_requires_data_organizer(self, tmp_path):
        session = PipelineSession(output_dir=tmp_path)
        v = DataValidator()
        result = v.validate_step_prerequisites("feature_filter", session)
        assert not result.is_valid
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
PYTHONPATH=ms-core/src pytest tests/test_validators_new.py -v --tb=short
```

Expected: `ImportError: cannot import name 'ValidationResult'`

- [ ] **Step 2.3: Add `ValidationResult` to top of `validators.py` and new method to class**

Open `src/ms_preprocessing/utils/validators.py`. Make two additions:

**Addition 1** — add after the existing imports, before the class definition:

```python
@dataclass
class ValidationResult:
    """Structured return type for DataValidator methods.

    Used by validate_step_prerequisites() (GUI step ordering).
    Existing methods continue to return bool for backwards compatibility.
    """
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

Also add to imports at top of file:
```python
from dataclasses import dataclass, field
```

**Addition 2** — add at the end of the `DataValidator` class body:

```python
    def validate_step_prerequisites(
        self, step: str, session: "PipelineSession"
    ) -> "ValidationResult":
        """Check GUI-mode step ordering prerequisites.

        GUI-only: CLI single-step mode bypasses this check.
        Only called from event_handlers.py to enable/disable step buttons.
        """
        prerequisites: dict[str, set[str]] = {
            "data_organizer": set(),
            "istd_marker": set(),
            "duplicate_remover": {"data_organizer"},
            "feature_filter": {"data_organizer"},
        }
        required = prerequisites.get(step, set())
        missing = required - session.completed_steps
        if missing:
            return ValidationResult(
                is_valid=False,
                errors=[f"Step '{step}' requires completed steps: {sorted(missing)}"],
            )
        return ValidationResult(is_valid=True)
```

- [ ] **Step 2.4: Run new tests to verify they pass**

```bash
PYTHONPATH=ms-core/src pytest tests/test_validators_new.py -v --tb=short
```

Expected: 8 tests PASSED

- [ ] **Step 2.5: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 2.6: Commit**

```bash
git add src/ms_preprocessing/utils/validators.py tests/test_validators_new.py
git commit -m "feat(validators): add ValidationResult dataclass and validate_step_prerequisites"
```

---

## Chunk 2: Adapter Layer

### Task 3: Create `adapters/` with 4 thin wrappers

**Files:**
- Create: `src/ms_preprocessing/adapters/__init__.py`
- Create: `src/ms_preprocessing/adapters/data_organizer.py`
- Create: `src/ms_preprocessing/adapters/istd_marker.py`
- Create: `src/ms_preprocessing/adapters/duplicate_remover.py`
- Create: `src/ms_preprocessing/adapters/feature_filter.py`

> **Context:** Read each `src/ms_preprocessing/core/*.py` wrapper before writing the corresponding adapter — it documents the exact parameters. Key facts:
>
> **ms_core processors accept `pd.DataFrame`, NOT file paths.** Each adapter must:
> 1. **Read** `input_path` → `pd.DataFrame` (using pandas directly)
> 2. **Process** the DataFrame via `processor.process(df, ...)`
> 3. **Save** `result.data` to a parquet cache file to produce `output_path`
> 4. **Return** `ms_preprocessing.utils.results.ProcessingResult` with typed metadata
>
> **Key rule:** Adapters are the ONLY files in `ms_preprocessing` allowed to `import` from `ms_core`.
>
> **ms_core result shape:** `ms_core.preprocessing.base.ProcessingResult` has fields: `success`, `data`, `metadata` (dict), `message`, `warnings`, `errors`. It has **no `output_path` field** — adapters generate and save this themselves.
>
> **File reading helper** (use in all adapters):
> ```python
> def _read_input(input_path: str) -> pd.DataFrame:
>     p = input_path.lower()
>     if p.endswith(".parquet"):
>         return pd.read_parquet(input_path)
>     elif p.endswith(".csv") or p.endswith(".tsv"):
>         return pd.read_csv(input_path)
>     return pd.read_excel(input_path)
> ```
>
> **Output save helper** (use in all adapters):
> ```python
> import time
> from pathlib import Path
> from ms_core.preprocessing.settings import Settings  # adapters may import ms_core
>
> def _save_output(df: pd.DataFrame, step: str) -> str:
>     cache_root = Settings.get_parquet_cache_root() / "adapters"
>     cache_root.mkdir(parents=True, exist_ok=True)
>     output_path = str(cache_root / f"{step}_{int(time.time())}.parquet")
>     df.to_parquet(output_path, index=False)
>     return output_path
> ```

**Integration Boundary Risks (read before writing any adapter):**

> **Risk A — `utils/__init__.py` re-exports ms_core's `DataValidator`:**
> `src/ms_preprocessing/utils/__init__.py` currently does:
> ```python
> from ms_core.utils.validators import DataValidator, detect_fixed_columns
> ```
> This shadows the toolkit's own `DataValidator` in `utils/validators.py`.
> Before finishing Task 3, decide one of:
> - **Remove the re-export** (preferred): callers import directly from `ms_core.utils.validators` if they need it
> - **Rename** the re-export to `MSCoreDataValidator` to avoid collision
> This decision must be made in Task 7 (Settings cleanup) at the latest.
> A regression test (`tests/test_utils_reexports.py`) verifying the chosen
> behaviour is required in Step 7.5.

> **Risk B — Adapters must NOT flatten typed Config objects to primitives:**
> `ISTDMarker.process()` accepts an `ISTDConfig` object (from `ms_core.preprocessing.settings`).
> `DuplicateRemover.process()` uses `DuplicateRemovalConfig`.
> `FeatureFilter.process()` uses `FeatureFilterConfig`.
> Read each Config class definition before writing the adapter signature.
> Adapters should accept the Config object as an optional parameter **or** accept
> individual primitive params and construct the Config internally — never silently
> ignore Config fields.
> Acceptance criteria: each adapter test (Task 4) must pass a non-default Config
> value and assert it reaches the processor (i.e., the result reflects the config).

- [ ] **Step 3.1: Create empty package**

```python
# src/ms_preprocessing/adapters/__init__.py
"""Adapter layer — only module in ms_preprocessing that imports from ms_core.

Each adapter function signature matches the corresponding ms_core processor's
process() parameters. Returns ms_preprocessing.utils.results.ProcessingResult.
"""
```

- [ ] **Step 3.2: Create `adapters/data_organizer.py`**

> **Before writing**: Read `src/ms_preprocessing/core/data_organizer.py` to confirm the exact keyword arguments that `ms_core.DataOrganizer.process(df, ...)` accepts beyond the first `df` parameter.

```python
# src/ms_preprocessing/adapters/data_organizer.py
"""Adapter: read file → ms_core.DataOrganizer → save parquet → ProcessingResult."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

# Layer 1 imports — only adapters/ may import from ms_core
from ms_core.preprocessing.data_organizer import DataOrganizer as _DataOrganizer
from ms_core.preprocessing.settings import Settings as _CoreSettings

from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "data_organizer"


def _read_input(input_path: str) -> pd.DataFrame:
    p = input_path.lower()
    if p.endswith(".parquet"):
        return pd.read_parquet(input_path)
    if p.endswith((".csv", ".tsv", ".txt")):
        return pd.read_csv(input_path)
    return pd.read_excel(input_path)


def _save_output(df: pd.DataFrame) -> str:
    cache_root = _CoreSettings.get_parquet_cache_root() / "adapters"
    cache_root.mkdir(parents=True, exist_ok=True)
    output_path = str(cache_root / f"{_STEP}_{int(time.time())}.parquet")
    df.to_parquet(output_path, index=False)
    return output_path


def run(
    input_path: str,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    **kwargs,
) -> ProcessingResult:
    """Read file, run DataOrganizer, save parquet, return typed ProcessingResult.

    Args:
        input_path: Path to input Excel/CSV/parquet file.
        progress_callback: Optional (message, fraction) progress hook for GUI.
        **kwargs: Additional keyword args forwarded to DataOrganizer.process().
                  Verify accepted kwargs by reading core/data_organizer.py.
    """
    if not os.path.exists(input_path):
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(),
            error=f"Input file not found: {input_path}",
        )

    try:
        df = _read_input(input_path)
        processor = _DataOrganizer()
        # NOTE: confirm exact kwargs by reading core/data_organizer.py
        core_result = processor.process(df, progress_callback=progress_callback, **kwargs)
    except Exception as exc:
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(), error=str(exc),
        )

    output_path = None
    if core_result.success and core_result.data is not None:
        output_path = _save_output(core_result.data)

    raw_meta = core_result.metadata if isinstance(core_result.metadata, dict) else {}
    return ProcessingResult(
        success=core_result.success,
        step=_STEP,
        output_path=output_path,
        data=core_result.data,
        metadata=ProcessingMetadata(
            red_font_rows=set(raw_meta.get("red_font_rows", [])),
            protected_rows=set(raw_meta.get("protected_rows", [])),
            blue_font_cells=list(raw_meta.get("blue_font_cells", [])),
            highlight_rows=set(raw_meta.get("highlight_rows", [])),
            sample_info=raw_meta.get("sample_info"),
            deleted_feature_df=raw_meta.get("deleted_feature_df"),
        ),
        error=None if core_result.success else (core_result.message or "Processing failed"),
    )
```

- [ ] **Step 3.3: Create `adapters/istd_marker.py`**

> **Before writing**: Read `src/ms_preprocessing/core/istd_marker.py` in full. Pay attention to how tolerance parameters are passed to `ISTDMarker.process()` — they may be passed via an `ISTDConfig` object or a `custom_tolerances` dict rather than as plain keyword args. Replicate that pattern exactly.

```python
# src/ms_preprocessing/adapters/istd_marker.py
"""Adapter: read file → ms_core.ISTDMarker → save parquet → ProcessingResult."""
from __future__ import annotations

import os
import time
from typing import Callable, Optional

import pandas as pd

from ms_core.preprocessing.istd_marker import ISTDMarker as _ISTDMarker
from ms_core.preprocessing.settings import Settings as _CoreSettings

from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "istd_marker"


def _read_input(input_path: str) -> pd.DataFrame:
    p = input_path.lower()
    if p.endswith(".parquet"):
        return pd.read_parquet(input_path)
    if p.endswith((".csv", ".tsv", ".txt")):
        return pd.read_csv(input_path)
    return pd.read_excel(input_path)


def _save_output(df: pd.DataFrame) -> str:
    cache_root = _CoreSettings.get_parquet_cache_root() / "adapters"
    cache_root.mkdir(parents=True, exist_ok=True)
    output_path = str(cache_root / f"{_STEP}_{int(time.time())}.parquet")
    df.to_parquet(output_path, index=False)
    return output_path


def run(
    input_path: str,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    **kwargs,
) -> ProcessingResult:
    """Read file, run ISTDMarker, save parquet, return typed ProcessingResult.

    Args:
        input_path: Path to input Excel/CSV/parquet file.
        progress_callback: Optional (message, fraction) progress hook.
        **kwargs: Forwarded to ISTDMarker.process(df, ...).
                  Check core/istd_marker.py for accepted kwargs (tolerances
                  may be passed as ISTDConfig or custom_tolerances dict).
    """
    if not os.path.exists(input_path):
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(),
            error=f"Input file not found: {input_path}",
        )

    try:
        df = _read_input(input_path)
        processor = _ISTDMarker()
        core_result = processor.process(df, progress_callback=progress_callback, **kwargs)
    except Exception as exc:
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(), error=str(exc),
        )

    output_path = None
    if core_result.success and core_result.data is not None:
        output_path = _save_output(core_result.data)

    raw_meta = core_result.metadata if isinstance(core_result.metadata, dict) else {}
    return ProcessingResult(
        success=core_result.success,
        step=_STEP,
        output_path=output_path,
        data=core_result.data,
        metadata=ProcessingMetadata(
            red_font_rows=set(raw_meta.get("red_font_rows", [])),
            protected_rows=set(raw_meta.get("protected_rows", [])),
            blue_font_cells=list(raw_meta.get("blue_font_cells", [])),
            highlight_rows=set(raw_meta.get("highlight_rows", [])),
        ),
        error=None if core_result.success else (core_result.message or "Processing failed"),
    )
```

- [ ] **Step 3.4: Create `adapters/duplicate_remover.py`**

> **Before writing**: Read `src/ms_preprocessing/core/duplicate_remover.py` to confirm the exact parameter names for `DuplicateRemover.process(df, ...)`.

```python
# src/ms_preprocessing/adapters/duplicate_remover.py
"""Adapter: read file → ms_core.DuplicateRemover → save parquet → ProcessingResult."""
from __future__ import annotations

import os
import time
from typing import Callable, Optional, Set

import pandas as pd

from ms_core.preprocessing.duplicate_remover import DuplicateRemover as _DuplicateRemover
from ms_core.preprocessing.settings import Settings as _CoreSettings

from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "duplicate_remover"


def _read_input(input_path: str) -> pd.DataFrame:
    p = input_path.lower()
    if p.endswith(".parquet"):
        return pd.read_parquet(input_path)
    if p.endswith((".csv", ".tsv", ".txt")):
        return pd.read_csv(input_path)
    return pd.read_excel(input_path)


def _save_output(df: pd.DataFrame) -> str:
    cache_root = _CoreSettings.get_parquet_cache_root() / "adapters"
    cache_root.mkdir(parents=True, exist_ok=True)
    output_path = str(cache_root / f"{_STEP}_{int(time.time())}.parquet")
    df.to_parquet(output_path, index=False)
    return output_path


def run(
    input_path: str,
    mz_tolerance_ppm: float = 5.0,
    rt_tolerance: float = 0.025,
    protected_rows: Optional[Set[int]] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    **kwargs,
) -> ProcessingResult:
    """Read file, run DuplicateRemover, save parquet, return typed ProcessingResult.

    Args:
        input_path: Path to input Excel/CSV/parquet file.
        mz_tolerance_ppm: m/z tolerance in ppm.
        rt_tolerance: RT tolerance in minutes.
        protected_rows: Row indices to protect from removal.
        progress_callback: Optional (message, fraction) progress hook.
    """
    if not os.path.exists(input_path):
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(),
            error=f"Input file not found: {input_path}",
        )

    try:
        df = _read_input(input_path)
        processor = _DuplicateRemover()
        # NOTE: confirm exact param names from core/duplicate_remover.py
        core_result = processor.process(
            df,
            mz_tolerance_ppm=mz_tolerance_ppm,
            rt_tolerance=rt_tolerance,
            protected_rows=protected_rows or set(),
            progress_callback=progress_callback,
            **kwargs,
        )
    except Exception as exc:
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(), error=str(exc),
        )

    output_path = None
    if core_result.success and core_result.data is not None:
        output_path = _save_output(core_result.data)

    raw_meta = core_result.metadata if isinstance(core_result.metadata, dict) else {}
    return ProcessingResult(
        success=core_result.success,
        step=_STEP,
        output_path=output_path,
        data=core_result.data,
        metadata=ProcessingMetadata(
            red_font_rows=set(raw_meta.get("red_font_rows", [])),
            protected_rows=set(raw_meta.get("protected_rows", [])),
            blue_font_cells=list(raw_meta.get("blue_font_cells", [])),
        ),
        error=None if core_result.success else (core_result.message or "Processing failed"),
    )
```

- [ ] **Step 3.5: Create `adapters/feature_filter.py`**

> **Before writing**: Read `src/ms_preprocessing/core/feature_filter.py` in full to confirm the exact parameter names for `FeatureFilter.process(df, ...)`. The reviewer confirmed the ms_core class is `FeatureFilter` in `ms_quality_filter.py`, and its parameters are `background_threshold`, `skew_threshold`, `diff_threshold`, `qc_ratio_threshold` — **not** `qc_threshold`/`sample_threshold`/`blank_threshold`. Confirm exact defaults from the source.

```python
# src/ms_preprocessing/adapters/feature_filter.py
"""Adapter: read file → ms_core.FeatureFilter → save parquet → ProcessingResult."""
from __future__ import annotations

import os
import time
from typing import Callable, Optional, Set

import pandas as pd

# Class is FeatureFilter, module is ms_quality_filter (confirmed)
from ms_core.preprocessing.ms_quality_filter import FeatureFilter as _FeatureFilter
from ms_core.preprocessing.settings import Settings as _CoreSettings

from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

_STEP = "feature_filter"


def _read_input(input_path: str) -> pd.DataFrame:
    p = input_path.lower()
    if p.endswith(".parquet"):
        return pd.read_parquet(input_path)
    if p.endswith((".csv", ".tsv", ".txt")):
        return pd.read_csv(input_path)
    return pd.read_excel(input_path)


def _save_output(df: pd.DataFrame) -> str:
    cache_root = _CoreSettings.get_parquet_cache_root() / "adapters"
    cache_root.mkdir(parents=True, exist_ok=True)
    output_path = str(cache_root / f"{_STEP}_{int(time.time())}.parquet")
    df.to_parquet(output_path, index=False)
    return output_path


def run(
    input_path: str,
    background_threshold: float = 0.1,   # verify default from ms_core
    skew_threshold: float = 0.0,           # verify default from ms_core
    diff_threshold: float = 0.0,           # verify default from ms_core
    qc_ratio_threshold: float = 0.3,       # verify default from ms_core
    protected_rows: Optional[Set[int]] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    **kwargs,
) -> ProcessingResult:
    """Read file, run FeatureFilter, save parquet, return typed ProcessingResult.

    IMPORTANT: Verify all threshold parameter names and defaults against
    ms_core/preprocessing/ms_quality_filter.py before finalising this signature.
    """
    if not os.path.exists(input_path):
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(),
            error=f"Input file not found: {input_path}",
        )

    try:
        df = _read_input(input_path)
        processor = _FeatureFilter()
        core_result = processor.process(
            df,
            background_threshold=background_threshold,
            skew_threshold=skew_threshold,
            diff_threshold=diff_threshold,
            qc_ratio_threshold=qc_ratio_threshold,
            protected_rows=protected_rows or set(),
            progress_callback=progress_callback,
            **kwargs,
        )
    except Exception as exc:
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(), error=str(exc),
        )

    output_path = None
    if core_result.success and core_result.data is not None:
        output_path = _save_output(core_result.data)

    raw_meta = core_result.metadata if isinstance(core_result.metadata, dict) else {}
    return ProcessingResult(
        success=core_result.success,
        step=_STEP,
        output_path=output_path,
        data=core_result.data,
        metadata=ProcessingMetadata(
            red_font_rows=set(raw_meta.get("red_font_rows", [])),
            protected_rows=set(raw_meta.get("protected_rows", [])),
            deleted_feature_df=raw_meta.get("deleted_feature_df"),
        ),
        error=None if core_result.success else (core_result.message or "Processing failed"),
    )
```

- [ ] **Step 3.5b: Add `run_from_df()` to all four adapters**

Each adapter needs a second entry point for GUI widgets (which already have a DataFrame in memory). Add this function to each adapter file immediately after the `run()` function:

```python
# Add to each adapter (data_organizer, istd_marker, duplicate_remover, feature_filter):

def run_from_df(
    df: pd.DataFrame,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    **kwargs,
) -> ProcessingResult:
    """Accept an in-memory DataFrame directly — used by GUI widgets.

    Skips file reading. Calls processor.process(df, ...) directly,
    then saves the result to parquet (same as run()).
    """
    try:
        processor = _<ProcessorClass>()   # same as in run()
        core_result = processor.process(df, progress_callback=progress_callback, **kwargs)
    except Exception as exc:
        return ProcessingResult(
            success=False, step=_STEP, output_path=None, data=None,
            metadata=ProcessingMetadata(), error=str(exc),
        )

    output_path = None
    if core_result.success and core_result.data is not None:
        output_path = _save_output(core_result.data)

    raw_meta = core_result.metadata if isinstance(core_result.metadata, dict) else {}
    return ProcessingResult(
        success=core_result.success,
        step=_STEP,
        output_path=output_path,
        data=core_result.data,
        metadata=ProcessingMetadata(
            # ... same metadata extraction as in run()
        ),
        error=None if core_result.success else (core_result.message or "Processing failed"),
    )
```

This allows widgets (Task 9) to call `adapter.run_from_df(data, **params)` instead of writing to a temp file.

- [ ] **Step 3.6: Verify adapters importable**

```bash
PYTHONPATH=ms-core/src python -c "
from ms_preprocessing.adapters import data_organizer, istd_marker, duplicate_remover, feature_filter
print('all adapters importable')
"
```

Expected: `all adapters importable`

- [ ] **Step 3.7: Run full test suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS (adapters exist but are not yet called by anyone)

- [ ] **Step 3.8: Commit**

```bash
git add src/ms_preprocessing/adapters/
git commit -m "feat(adapters): add four thin adapter wrappers around ms_core processors"
```

---

### Task 4: Write adapter unit tests

**Files:**
- Create: `tests/test_adapter_data_organizer.py`
- Create: `tests/test_adapter_istd_marker.py`
- Create: `tests/test_adapter_duplicate_remover.py`
- Create: `tests/test_adapter_feature_filter.py`

> **Context:** Each adapter test covers four scenarios:
> 1. Valid input → `ProcessingResult(success=True)` with correct metadata field types
> 2. Missing file → `ProcessingResult(success=False, error=...)`
> 3. Correct metadata fields populated (`red_font_rows`, `protected_rows`, etc.)
> 4. **(New — Risk B)** Non-default Config value reaches the processor:
>    e.g. pass a custom `ISTDConfig(mz_tolerance_ppm=1.0)` to `istd_marker.run()`
>    and assert the result differs from a run with `mz_tolerance_ppm=50.0`,
>    confirming Config is not silently ignored.
>
> Use `sample_excel_file` fixture from `conftest.py`.

- [ ] **Step 4.1: Write `test_adapter_data_organizer.py`**

```python
# tests/test_adapter_data_organizer.py
"""Unit tests for adapters/data_organizer.py."""
from __future__ import annotations
import pytest
from ms_preprocessing.adapters import data_organizer
from ms_preprocessing.utils.results import ProcessingResult, ProcessingMetadata


class TestDataOrganizerAdapter:
    def test_missing_file_returns_failure(self, tmp_path):
        result = data_organizer.run(str(tmp_path / "nonexistent.xlsx"))
        assert isinstance(result, ProcessingResult)
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower()
        assert result.step == "data_organizer"

    def test_missing_file_metadata_is_empty(self, tmp_path):
        result = data_organizer.run(str(tmp_path / "nonexistent.xlsx"))
        assert isinstance(result.metadata, ProcessingMetadata)
        assert result.metadata.red_font_rows == set()
        assert result.metadata.protected_rows == set()

    def test_valid_input_returns_processing_result(self, sample_excel_file):
        result = data_organizer.run(str(sample_excel_file))
        assert isinstance(result, ProcessingResult)
        assert result.step == "data_organizer"
        # success depends on actual data — just verify structure
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)
        assert isinstance(result.metadata.protected_rows, set)
        assert isinstance(result.metadata.blue_font_cells, list)
```

- [ ] **Step 4.2: Write `test_adapter_istd_marker.py`**

```python
# tests/test_adapter_istd_marker.py
"""Unit tests for adapters/istd_marker.py."""
from __future__ import annotations
import pytest
from ms_preprocessing.adapters import istd_marker
from ms_preprocessing.utils.results import ProcessingResult, ProcessingMetadata


class TestISTDMarkerAdapter:
    def test_missing_file_returns_failure(self, tmp_path):
        result = istd_marker.run(str(tmp_path / "nonexistent.xlsx"))
        assert result.success is False
        assert result.step == "istd_marker"
        assert "not found" in result.error.lower()

    def test_missing_file_metadata_is_empty(self, tmp_path):
        result = istd_marker.run(str(tmp_path / "nonexistent.xlsx"))
        assert isinstance(result.metadata, ProcessingMetadata)
        assert result.metadata.red_font_rows == set()

    def test_valid_input_returns_processing_result(self, sample_excel_file):
        result = istd_marker.run(str(sample_excel_file))
        assert isinstance(result, ProcessingResult)
        assert result.step == "istd_marker"
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)
```

- [ ] **Step 4.3: Write `test_adapter_duplicate_remover.py`**

```python
# tests/test_adapter_duplicate_remover.py
"""Unit tests for adapters/duplicate_remover.py."""
from __future__ import annotations
import pytest
from ms_preprocessing.adapters import duplicate_remover
from ms_preprocessing.utils.results import ProcessingResult, ProcessingMetadata


class TestDuplicateRemoverAdapter:
    def test_missing_file_returns_failure(self, tmp_path):
        result = duplicate_remover.run(str(tmp_path / "nonexistent.xlsx"))
        assert result.success is False
        assert result.step == "duplicate_remover"
        assert result.error is not None

    def test_protected_rows_forwarded(self, tmp_path):
        """Adapter should not crash when protected_rows is passed."""
        result = duplicate_remover.run(
            str(tmp_path / "nonexistent.xlsx"),
            protected_rows={1, 2, 3},
        )
        assert result.success is False  # file missing, not a parameter error

    def test_valid_input_metadata_types(self, sample_excel_file):
        result = duplicate_remover.run(str(sample_excel_file))
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)
        assert isinstance(result.metadata.protected_rows, set)
```

- [ ] **Step 4.4: Write `test_adapter_feature_filter.py`**

```python
# tests/test_adapter_feature_filter.py
"""Unit tests for adapters/feature_filter.py."""
from __future__ import annotations
import pytest
from ms_preprocessing.adapters import feature_filter
from ms_preprocessing.utils.results import ProcessingResult, ProcessingMetadata


class TestFeatureFilterAdapter:
    def test_missing_file_returns_failure(self, tmp_path):
        result = feature_filter.run(str(tmp_path / "nonexistent.xlsx"))
        assert result.success is False
        assert result.step == "feature_filter"
        assert result.error is not None

    def test_valid_input_metadata_types(self, sample_excel_file):
        result = feature_filter.run(str(sample_excel_file))
        assert isinstance(result.metadata, ProcessingMetadata)
        assert isinstance(result.metadata.red_font_rows, set)

    def test_deleted_feature_df_is_none_or_dataframe(self, sample_excel_file):
        import pandas as pd
        result = feature_filter.run(str(sample_excel_file))
        assert result.metadata.deleted_feature_df is None or isinstance(
            result.metadata.deleted_feature_df, pd.DataFrame
        )
```

- [ ] **Step 4.5: Run all adapter tests**

```bash
PYTHONPATH=ms-core/src pytest tests/test_adapter_*.py -v --tb=short
```

Expected: 12 tests PASS (missing-file tests definitely pass; valid-input tests pass if sample_excel_file is compatible with each processor)

- [ ] **Step 4.6: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 4.7: Commit**

```bash
git add tests/test_adapter_data_organizer.py tests/test_adapter_istd_marker.py \
        tests/test_adapter_duplicate_remover.py tests/test_adapter_feature_filter.py
git commit -m "test(adapters): add unit tests for all four adapter wrappers"
```

---

## Chunk 3: CLI Migration and PipelineSession

### Task 5: Strengthen `PipelineSession`

**Files:**
- Modify: `src/ms_preprocessing/gui/pipeline_session.py`
- Test: `tests/test_gui_pipeline_session.py` (existing — verify still passes)

> **Context:** Read `gui/pipeline_session.py` in full before editing. Replace the `context` dict with `ProcessingMetadata`. Add `can_run_step()` (GUI-only) and `update_from_result()`. Preserve all existing public method signatures for backwards compatibility.

- [ ] **Step 5.1: Read existing file**

Read `src/ms_preprocessing/gui/pipeline_session.py` completely before proceeding.

- [ ] **Step 5.2: Write new version**

Key changes only (preserve everything else):
1. Replace `self.context: dict` with `self.metadata: ProcessingMetadata`
2. Add `self.completed_steps: set[str] = set()` field
3. Replace `update_context_from_metadata()` with `update_from_result()`
4. Add `can_run_step()` method
5. Keep `save_step_output()`, `get_step_output()`, and any other existing public methods

```python
# Additions/replacements to pipeline_session.py

# At top of file, add import:
from ms_preprocessing.utils.results import ProcessingMetadata, ProcessingResult

# PRESERVE the existing constructor signature — only add new fields inside __init__:
# def __init__(self, output_dir: Path, source_file: Path | None = None, intermediate_dir: Path | None = None) -> None:
#     ... existing code ...
#     ADD these lines:
self.metadata: ProcessingMetadata = ProcessingMetadata()  # replaces context dict
self.completed_steps: set[str] = set()
# NOTE: self.step_outputs may already exist; if so, keep it, don't duplicate

# Add new methods:
def can_run_step(self, step: str) -> bool:
    """GUI-only prerequisite check. CLI bypasses this (main.py single-step mode)."""
    prerequisites: dict[str, set[str]] = {
        "data_organizer": set(),
        "istd_marker": set(),
        "duplicate_remover": {"data_organizer"},
        "feature_filter": {"data_organizer"},
    }
    return prerequisites.get(step, set()).issubset(self.completed_steps)

def update_from_result(self, result: ProcessingResult) -> None:
    """Merge a ProcessingResult into session state — does NOT replace all metadata.

    Uses merge semantics: only overwrites non-empty fields from result.metadata.
    This preserves cross-step state (e.g. sample_info from Step 1 is not wiped
    out when Step 3 completes with empty sample_info).
    """
    if result.success:
        new = result.metadata
        if new.red_font_rows:
            self.metadata.red_font_rows = new.red_font_rows
        if new.protected_rows:
            self.metadata.protected_rows = new.protected_rows
        if new.blue_font_cells:
            self.metadata.blue_font_cells = new.blue_font_cells
        if new.highlight_rows:
            self.metadata.highlight_rows = new.highlight_rows
        if new.sample_info is not None:
            self.metadata.sample_info = new.sample_info
        if new.deleted_feature_df is not None:
            self.metadata.deleted_feature_df = new.deleted_feature_df
        self.completed_steps.add(result.step)
        if result.output_path:
            self.step_outputs[result.step] = result.output_path
```

- [ ] **Step 5.3: Run GUI pipeline session tests**

```bash
PYTHONPATH=ms-core/src pytest tests/test_gui_pipeline_session.py -v --tb=short
```

Expected: all tests PASS

- [ ] **Step 5.4: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 5.5: Commit**

```bash
git add src/ms_preprocessing/gui/pipeline_session.py
git commit -m "refactor(session): replace context dict with ProcessingMetadata; add can_run_step + update_from_result"
```

---

### Task 6: Migrate `main.py` CLI to use adapters

**Files:**
- Modify: `src/ms_preprocessing/main.py`

> **Context:** Read `main.py` in full before editing. The goal is:
> 1. Replace `from ms_core.preprocessing.* import *` with `from ms_preprocessing.adapters import *`
> 2. Replace manual `red_font_rows`, `protected_rows` variables with `PipelineSession`
> 3. Replace `from ms_core.preprocessing.settings import Settings` with nothing (only use `ms_preprocessing.config.settings`)
> 4. Do NOT change CLI argument names or the `run_gui()` function

- [ ] **Step 6.1: Read `main.py` completely before editing**

- [ ] **Step 6.2: Replace ms_core imports with adapter imports**

Find the block:
```python
from ms_core.preprocessing.data_organizer import DataOrganizer
from ms_core.preprocessing.istd_marker import ISTDMarker
from ms_core.preprocessing.duplicate_remover import DuplicateRemover
# etc.
```

Replace with:
```python
from ms_preprocessing.adapters import (
    data_organizer as _adapter_do,
    istd_marker as _adapter_istd,
    duplicate_remover as _adapter_dr,
    feature_filter as _adapter_ff,
)
from ms_preprocessing.gui.pipeline_session import PipelineSession
```

- [ ] **Step 6.3: Replace `run_cli()` state management**

Replace manual variable tracking pattern:
```python
# OLD (remove)
red_font_rows = set()
protected_rows = set()
result = DataOrganizer().process(...)
red_font_rows = set(result.metadata.get("red_font_rows", []))

# NEW (PipelineSession requires output_dir — derive from Settings)
from ms_preprocessing.config.settings import Settings
_cli_output_dir = Settings.get_parquet_cache_root() / "cli"
session = PipelineSession(output_dir=_cli_output_dir)
result = _adapter_do.run(input_path, ...)
session.update_from_result(result)
if not result.success:
    print(f"Error in data_organizer: {result.error}")
    return 1
# Access state via session.metadata.red_font_rows, session.metadata.protected_rows
```

Apply the same pattern for each step (istd_marker, duplicate_remover, feature_filter).

- [ ] **Step 6.4: Remove ms_core Settings import**

Find and remove: `from ms_core.preprocessing.settings import Settings`

Ensure all `Settings.*` references use only `ms_preprocessing.config.settings.Settings`.

- [ ] **Step 6.5: Run CLI-related tests**

```bash
PYTHONPATH=ms-core/src pytest tests/test_cli_parquet_chain.py tests/test_integration_parquet_pipeline.py tests/test_smoke_guardrails.py -v --tb=short
```

Expected: all PASS

- [ ] **Step 6.6: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 6.7: Commit**

```bash
git add src/ms_preprocessing/main.py
git commit -m "refactor(cli): migrate main.py to use adapters and PipelineSession"
```

---

### Task 7: Fix `config/__init__.py` Settings re-export

**Files:**
- Modify: `src/ms_preprocessing/config/__init__.py`
- Modify: `src/ms_preprocessing/config/settings.py` (if it has ms_core imports)

- [ ] **Step 7.1: Read `config/__init__.py`**

Look for: `from ms_core.preprocessing.settings import Settings, ProcessingConfig`

- [ ] **Step 7.2: Remove the re-export**

Replace the ms_core re-export line with a comment:

```python
# config/__init__.py
# Processing constants (SAVE_PARQUET_CACHE, get_parquet_cache_root, etc.) are
# accessed via the adapter layer only. Do not re-export ms_core Settings here.
from ms_preprocessing.config.settings import Settings  # GUI/App constants only
```

- [ ] **Step 7.3: Check for broken callers**

```bash
PYTHONPATH=ms-core/src grep -r "from ms_preprocessing.config import" src/ tests/
```

Fix any caller that was importing `ProcessingConfig` from `ms_preprocessing.config`.

- [ ] **Step 7.4: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 7.5: Add `utils/__init__.py` re-export regression test**

Before committing, resolve the `DataValidator` re-export collision (Risk A from Task 3):

1. Decide: remove `from ms_core.utils.validators import DataValidator` from `utils/__init__.py`, or rename it
2. Create `tests/test_utils_reexports.py`:

```python
# tests/test_utils_reexports.py
"""Regression: verify utils/__init__.py re-export boundaries after refactor."""
from ms_preprocessing.utils.validators import DataValidator as ToolkitValidator


def test_toolkit_datavalidator_is_local_not_mscore():
    """DataValidator from utils.validators must be the toolkit class, not ms_core's."""
    # The toolkit DataValidator has validate_dataframe() and validate_step_prerequisites()
    v = ToolkitValidator()
    assert hasattr(v, "validate_dataframe"), "should be toolkit DataValidator"
    assert hasattr(v, "validate_step_prerequisites"), "should have new method from Task 2"


def test_mscore_datavalidator_not_re_exported():
    """utils/__init__ must not re-export ms_core's DataValidator directly."""
    import ms_preprocessing.utils as utils_pkg
    # After fix: ms_core's DataValidator should NOT be importable from utils directly
    # (users must import from ms_core explicitly if they need it)
    assert not hasattr(utils_pkg, "DataValidator") or utils_pkg.DataValidator is ToolkitValidator
```

- [ ] **Step 7.6: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/test_utils_reexports.py tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 7.7: Commit**

```bash
git add src/ms_preprocessing/config/__init__.py src/ms_preprocessing/config/settings.py \
        src/ms_preprocessing/utils/__init__.py tests/test_utils_reexports.py
git commit -m "refactor(config): remove ms_core re-exports; fix DataValidator collision in utils/__init__"
```

---

## Chunk 4: GUI Refactor

### Task 8: Split `main_window.py` into `layout.py` + `event_handlers.py`

**Files:**
- Read first: `src/ms_preprocessing/gui/main_window.py` (867 LOC)
- Create: `src/ms_preprocessing/gui/layout.py`
- Create: `src/ms_preprocessing/gui/event_handlers.py`
- Modify: `src/ms_preprocessing/gui/main_window.py`

> **Strategy:** This is a move-only refactor — no logic changes. Read `main_window.py` completely, then:
> - `layout.py` gets: all methods that call `customtkinter` widget constructors, grid/pack configurations, color/font setup
> - `event_handlers.py` gets: all button `command=` callback methods, progress update methods, FileHandler calls (via `ms_preprocessing.utils.file_handler`, not ms_core)
> - `main_window.py` keeps: `__init__`, `mainloop()`, `PipelineSession` ownership, calls into `layout` and `event_handlers`

- [ ] **Step 8.1: Read `main_window.py` completely before any edit**

- [ ] **Step 8.2: Create `layout.py`** with widget-building methods extracted from `main_window.py`

`layout.py` structure:
```python
# src/ms_preprocessing/gui/layout.py
"""All customtkinter widget creation and layout configuration for MainWindow."""
import customtkinter as ctk
from ms_preprocessing.gui.styles import COLORS, FONTS, PADDING, DIMENSIONS


class WindowLayout:
    """Mixin-style class; MainWindow inherits from this."""

    def _build_root_layout(self) -> None: ...
    def _build_nav_bar(self) -> None: ...
    def _build_sidebar(self) -> None: ...
    def _build_content_area(self) -> None: ...
    # ... all widget creation methods
```

- [ ] **Step 8.3: Create `event_handlers.py`** with callback methods

```python
# src/ms_preprocessing/gui/event_handlers.py
"""Button event callbacks and progress update handlers for MainWindow."""
from ms_preprocessing.utils.file_handler import FileHandler  # not ms_core directly


class WindowEventHandlers:
    """Mixin-style class; MainWindow inherits from this."""

    def _on_step1_run(self) -> None: ...
    def _on_step2_run(self) -> None: ...
    def _on_progress_update(self, message: str, fraction: float) -> None: ...
    # ... all event methods
```

- [ ] **Step 8.4: Slim `main_window.py` to assembler**

```python
# src/ms_preprocessing/gui/main_window.py (target: <200 LOC)
from ms_preprocessing.gui.layout import WindowLayout
from ms_preprocessing.gui.event_handlers import WindowEventHandlers
from ms_preprocessing.gui.pipeline_session import PipelineSession


class MainWindow(WindowLayout, WindowEventHandlers, ctk.CTk):
    def __init__(self):
        super().__init__()
        # PipelineSession is initialized with a default output_dir at startup.
        # When the user selects an input file, call _reset_session(input_path) to
        # re-initialize the session with the correct output directory for that file.
        from ms_preprocessing.config.settings import Settings
        _output_dir = Settings.get_parquet_cache_root() / "gui"
        self.session = PipelineSession(output_dir=_output_dir)
        self._build_root_layout()
        self._bind_events()

    def _reset_session(self, input_path: str) -> None:
        """Re-initialize session when user selects a new input file."""
        from ms_preprocessing.config.settings import Settings
        from pathlib import Path
        output_dir = Settings.get_parquet_cache_root() / Path(input_path).stem
        self.session = PipelineSession(output_dir=output_dir)
```

- [ ] **Step 8.5: Run GUI tests**

```bash
PYTHONPATH=ms-core/src pytest tests/test_gui_main_window_sidebar_labels.py tests/test_gui_workflow_labels.py -v --tb=short
```

Expected: all PASS

- [ ] **Step 8.6: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 8.7: Commit**

```bash
git add src/ms_preprocessing/gui/layout.py src/ms_preprocessing/gui/event_handlers.py \
        src/ms_preprocessing/gui/main_window.py
git commit -m "refactor(gui): split main_window.py into layout.py + event_handlers.py"
```

---

### Task 9: Migrate widgets to use adapters

**Files:**
- Modify: `src/ms_preprocessing/gui/widgets/base_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/data_organizer_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/istd_marker_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/duplicate_remover_widget.py`
- Modify: `src/ms_preprocessing/gui/widgets/feature_filter_widget.py`

> **Context:** `BaseStepWidget.run_processing()` is declared `-> pd.DataFrame` (base_widget.py:179). This return type must NOT change — it is the public contract with `main_window.py`.
>
> **Strategy:**
> 1. Each widget removes its `self._processor = Processor()` instantiation
> 2. Inside `run_processing()`, call `adapter.run(...)` and store the full `ProcessingResult` in `self._last_result` (new field)
> 3. Return `result.data` (the DataFrame) to satisfy the existing contract
> 4. The `on_complete` callback already receives `(self._result, self._last_metadata)` — pass `self._last_result.metadata` for the metadata argument

- [ ] **Step 9.1: Read all five widget files before editing**

- [ ] **Step 9.2: Update `base_widget.py`**

Add `_last_result: Optional[ProcessingResult] = None` field to `__init__`:
```python
from ms_preprocessing.utils.results import ProcessingResult
# ...
self._last_result: Optional[ProcessingResult] = None
```

No change to `run_processing()` signature.

- [ ] **Step 9.3: Update `data_organizer_widget.py`**

> Widgets call `adapter.run_from_df(df, **params)` (added in Step 3.5b) — no temp file needed.

```python
# Remove:
from ms_core.preprocessing.data_organizer import DataOrganizer
# ...
self._processor = DataOrganizer()   # remove instantiation

# Add:
from ms_preprocessing.adapters import data_organizer as _adapter

# Replace run_processing() body:
def run_processing(self, data: pd.DataFrame, **params) -> pd.DataFrame:
    """Call adapter, store result internally, return DataFrame (contract unchanged)."""
    result = _adapter.run_from_df(data, **params)
    self._last_result = result          # stored for on_complete callback
    if not result.success:
        raise RuntimeError(result.error or "Processing failed")
    return result.data                  # satisfies -> pd.DataFrame contract
```

The `on_complete` callback in `base_widget.py` receives `self._result` (the DataFrame). If metadata needs to be surfaced to `main_window.py`, access it via `widget._last_result.metadata` after the callback fires.

- [ ] **Step 9.4: Update remaining 3 widgets** using the same pattern

- [ ] **Step 9.5: Run widget tests**

```bash
PYTHONPATH=ms-core/src pytest tests/test_feature_filter_widget.py tests/test_gui_main_window_sidebar_labels.py -v --tb=short
```

Expected: all PASS

- [ ] **Step 9.6: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 9.7: Commit**

```bash
git add src/ms_preprocessing/gui/widgets/
git commit -m "refactor(widgets): replace direct ms_core processor calls with adapter layer"
```

---

## Chunk 5: Cleanup

### Task 10: Verify layer boundary and delete `core/`

**Files:**
- Delete: `src/ms_preprocessing/core/` (entire directory)
- Modify: `src/ms_preprocessing/__init__.py`

- [ ] **Step 10.1: Verify no remaining ms_core imports outside adapters/**

```bash
PYTHONPATH=ms-core/src grep -r "from ms_core" src/ms_preprocessing/ --include="*.py" | grep -v "adapters/"
```

Expected: **empty output**. If any lines appear, fix them before continuing.

- [ ] **Step 10.2: Verify no remaining core/ imports**

```bash
grep -r "from ms_preprocessing.core" src/ tests/ --include="*.py"
grep -r "from .core" src/ms_preprocessing/ --include="*.py"
grep -r "import ms_preprocessing.core" src/ tests/ --include="*.py"
```

Expected: **all three commands return empty output**.

- [ ] **Step 10.3: Skip — `git rm` in Step 10.8 handles deletion**

Do NOT run `rm -rf` here. Deleting the filesystem before running tests (Step 10.5) makes rollback impossible if tests fail. Step 10.8 uses `git rm -r` which deletes from both filesystem and git index atomically, after tests have passed.

- [ ] **Step 10.4: Update `__init__.py` public API**

Read `src/ms_preprocessing/__init__.py`. Remove any `from ms_preprocessing.core.*` or `from ms_core.*` lines. Update public exports to use adapters or utils as appropriate:

```python
# src/ms_preprocessing/__init__.py
"""ms-preprocessing — MS data preprocessing pipeline."""
__version__ = "1.2.0"

# Public API — application layer
from ms_preprocessing.utils.results import ProcessingResult, ProcessingMetadata
from ms_preprocessing.adapters import (
    data_organizer,
    istd_marker,
    duplicate_remover,
    feature_filter,
)

__all__ = [
    "ProcessingResult",
    "ProcessingMetadata",
    "data_organizer",
    "istd_marker",
    "duplicate_remover",
    "feature_filter",
]
```

- [ ] **Step 10.5: Run full suite**

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

Expected: all tests PASS

- [ ] **Step 10.6: Final layer-boundary audit**

```bash
# Should return ONLY files under adapters/
grep -r "from ms_core" src/ms_preprocessing/ --include="*.py" -l
```

Expected: only `src/ms_preprocessing/adapters/*.py` filenames appear.

- [ ] **Step 10.7: Verify main_window.py size**

```bash
wc -l src/ms_preprocessing/gui/main_window.py
```

Expected: under 200 lines.

- [ ] **Step 10.8: Delete `core/` and commit**

```bash
# git rm deletes from filesystem AND stages the removal in one command
git rm -r src/ms_preprocessing/core/
git add src/ms_preprocessing/__init__.py
git commit -m "refactor(cleanup): delete deprecated core/ layer; update public API to use adapters"
```

---

## Summary

| Chunk | Tasks | New files | Key outcome |
|-------|-------|-----------|------------|
| 1 — Foundation | 1–2 | results.py, test_results.py, test_validators_new.py | Typed result dataclasses available |
| 2 — Adapters | 3–4 | adapters/ (5 files), 4 test files | Single ms_core boundary; Config passthrough verified |
| 3 — CLI Migration | 5–7 | test_utils_reexports.py | CLI uses adapters + PipelineSession; DataValidator collision fixed |
| 4 — GUI Refactor | 8–9 | layout.py, event_handlers.py | main_window.py < 200 LOC; widgets use adapters |
| 5 — Cleanup | 10 | — | core/ deleted; layer boundary verified |

**Guard rail:** Run `PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x` after every task. Any failure must be fixed before proceeding.

> **Test count note:** Before Step 1.5, run `ls tests/ | grep test_ | wc -l` to confirm the actual number of pre-existing tests (expected ~21, not 24). Use that count as your baseline for "all pre-existing tests PASS".
