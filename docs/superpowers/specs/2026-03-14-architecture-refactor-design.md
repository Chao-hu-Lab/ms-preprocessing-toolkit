# Architecture Refactor Design — ms-preprocessing-toolkit

**Date**: 2026-03-14
**Status**: Draft
**Scope**: Application layer only (`src/ms_preprocessing/`); `ms-core` submodule algorithms are frozen.

---

## 1. Goals & Scope

### Goals

1. Establish clear four-layer architecture with single-direction dependencies
2. Unify CLI and GUI state management under a shared mechanism
3. Eliminate duplicate `Settings` imports and the orphaned `core/` wrapper layer
4. Improve maintainability and testability without touching any algorithm logic

### Out of Scope

- `ms-core/` submodule algorithm implementations (completely frozen)
- External CLI interface (`--input`, `--step`, `--no-gui` flags remain unchanged)
- All existing tests must remain green throughout migration

### Files Changed

```
src/ms_preprocessing/
├── config/__init__.py          ← Remove ms_core re-export (see 3.5)
├── config/settings.py          ← Restrict to GUI/App constants only
├── core/           → adapters/ ← Rename + slim down to ~80 LOC each
├── utils/results.py            ← NEW: ProcessingResult dataclass
├── utils/validators.py         ← Refactor to DataValidator class
├── gui/pipeline_session.py     ← Strengthen context structure
├── gui/main_window.py          ← Split into layout.py + event_handlers.py
├── gui/widgets/*.py            ← Replace direct ms_core calls with adapters
└── main.py                     ← CLI adopts adapters/ + PipelineSession
```

---

## 2. Four-Layer Architecture

### Layer Model

```
┌─────────────────────────────────────────────────────┐
│  Layer 4: GUI Layer                                 │
│  gui/layout.py          — customtkinter layout defs │
│  gui/event_handlers.py  — button events, callbacks  │
│  gui/main_window.py     — thin assembler (< 200 LOC)│
│  gui/widgets/           — step widgets (unchanged)  │
│  gui/pipeline_session.py — strengthened state mgmt  │
├─────────────────────────────────────────────────────┤
│  Layer 3: Application Layer                         │
│  main.py                — CLI entry, uses adapters  │
│  utils/results.py       — ProcessingResult dataclass│
│  utils/validators.py    — DataValidator class       │
│  config/settings.py     — GUI/App constants only    │
├─────────────────────────────────────────────────────┤
│  Layer 2: Adapter Layer                             │
│  adapters/data_organizer.py    — thin wrapper       │
│  adapters/istd_marker.py       — thin wrapper       │
│  adapters/duplicate_remover.py — thin wrapper       │
│  adapters/feature_filter.py    — thin wrapper       │
├─────────────────────────────────────────────────────┤
│  Layer 1: Core Layer (ms-core submodule — FROZEN)   │
│  ms_core.preprocessing.{DataOrganizer, ISTDMarker,  │
│    DuplicateRemover, FeatureFilter}                  │
└─────────────────────────────────────────────────────┘
```

### Dependency Rules (strictly enforced)

| From | To | Allowed? |
|------|----|----------|
| GUI Layer | Application Layer | ✅ Yes |
| GUI Layer | Adapter Layer | ❌ No |
| GUI Layer | ms_core | ❌ No |
| Application Layer | Adapter Layer | ✅ Yes |
| Application Layer | ms_core | ❌ No (only via adapters) |
| Adapter Layer | ms_core | ✅ Yes (only place allowed) |

---

## 3. Component Designs

### 3.1 `ProcessingResult` and `ProcessingMetadata` (new)

**File**: `src/ms_preprocessing/utils/results.py`

> **Naming note**: `ms_core/src/ms_core/preprocessing/base.py:16` already defines a `ProcessingResult` class in the ms_core namespace. The new `ms_preprocessing.utils.results.ProcessingResult` is a **different class** in a different namespace — it is the application-layer result wrapper, not the core-layer result. Imports must always use the full qualified name to avoid shadowing:
> - ✅ `from ms_preprocessing.utils.results import ProcessingResult`
> - ❌ `from ms_core.preprocessing.base import ProcessingResult` (never imported above adapter layer)

Replaces the untyped `context` dict in `PipelineSession` and the manual variable passing in `run_cli()`.

```python
@dataclass
class ProcessingMetadata:
    red_font_rows: set[int] = field(default_factory=set)
    protected_rows: set[int] = field(default_factory=set)
    blue_font_cells: list = field(default_factory=list)
    highlight_rows: set[int] = field(default_factory=set)
    sample_info: Optional[pd.DataFrame] = None
    deleted_feature_df: Optional[pd.DataFrame] = None

@dataclass
class ProcessingResult:
    success: bool
    step: str                           # "data_organizer" | "istd_marker" | ...
    output_path: Optional[str]
    data: Optional[pd.DataFrame]
    metadata: ProcessingMetadata
    error: Optional[str] = None
```

**Fixes**:
- Eliminates `set()` vs `list()` inconsistency in context dict
- Removes `metadata_refs` redundant nesting
- Provides IDE autocomplete and type safety

### 3.2 `DataValidator` — add `ValidationResult` and new APIs

**File**: `src/ms_preprocessing/utils/validators.py`

`DataValidator` class already exists (`validators.py:27`). This step **adds** two things to the existing class rather than rewriting it:

1. **`ValidationResult` dataclass** — structured return type (currently methods return `bool` or raise):

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

2. **New method on existing `DataValidator`** — step prerequisite checking that replaces the implicit `elif` logic in `update_context_from_metadata()`:

```python
class DataValidator:
    # ... existing methods unchanged ...

    def validate_step_prerequisites(
        self, step: str, session: "PipelineSession"
    ) -> ValidationResult:
        """New: explicit prerequisite check for GUI-mode step ordering."""
```

Existing free functions and the existing `DataValidator` methods are **not removed** in this step; they are migrated to return `ValidationResult` progressively in later steps.

### 3.3 Adapter Layer Pattern

**Directory**: `src/ms_preprocessing/adapters/`

Each adapter follows this identical structure (~80 LOC each):

```python
# adapters/istd_marker.py
from ms_core.preprocessing.istd_marker import ISTDMarker as _ISTDMarker
from ms_preprocessing.utils.results import ProcessingResult, ProcessingMetadata
from ms_preprocessing.utils.validators import DataValidator

def run(
    input_path: str,
    mz_tolerance: float,
    rt_tolerance: float,
    progress_callback: Optional[Callable] = None,
) -> ProcessingResult:
    """Validate → call ms_core → return ProcessingResult."""
    validator = DataValidator()
    validation = validator.validate_input_file(input_path)
    if not validation.is_valid:
        return ProcessingResult(
            success=False, step="istd_marker",
            output_path=None, data=None,
            metadata=ProcessingMetadata(),
            error=validation.errors[0],
        )

    result = _ISTDMarker().process(...)  # Only place ms_core is called

    return ProcessingResult(
        success=result.success,
        step="istd_marker",
        output_path=result.output_path,
        data=result.data,
        metadata=ProcessingMetadata(
            red_font_rows=set(result.metadata.get("red_font_rows", [])),
            protected_rows=set(result.metadata.get("protected_rows", [])),
        ),
    )
```

**Key property**: All four adapters become the **intended** long-term boundary for ms_core imports.

**Current integration points that also import ms_core** (to be resolved in Steps C–F):

| File | Current ms_core import | Resolution |
|------|----------------------|-----------|
| `__init__.py:21` | re-exports `DataOrganizer` etc. | Step F: update public API |
| `utils/file_handler.py:19` | `ms_core.preprocessing.settings.Settings` | Step C: access Settings via adapter |
| `utils/__init__.py:3` | re-export of file_handler | Step C: remove re-export |
| `config/__init__.py:3` | `ms_core.preprocessing.settings` | Step C: remove re-export (see 3.5) |

These files are **integration boundaries** — they are known violations that the migration plan explicitly addresses. Until each step is completed, their ms_core imports remain acceptable.

### 3.4 `PipelineSession` Strengthening

**File**: `src/ms_preprocessing/gui/pipeline_session.py`

Replace untyped `context` dict with `ProcessingMetadata` dataclass; add explicit step prerequisite checking.

```python
class PipelineSession:
    def __init__(self):
        self.metadata = ProcessingMetadata()      # replaces context dict
        self.step_outputs: dict[str, str] = {}    # step_name → parquet path
        self.completed_steps: set[str] = set()

    def can_run_step(self, step: str) -> bool:
        """Explicit prerequisite check — GUI mode only.

        CLI single-step mode (main.py:284) bypasses this check intentionally:
        the user is responsible for providing valid input when running a step
        in isolation via --step. This method is called only from GUI event
        handlers to disable/enable buttons in the workflow UI.
        """
        prerequisites = {
            "istd_marker": set(),
            "duplicate_remover": {"data_organizer"},
            "feature_filter": {"data_organizer"},
        }
        return prerequisites.get(step, set()).issubset(self.completed_steps)

    def update_from_result(self, result: ProcessingResult) -> None:
        """Single method to absorb a ProcessingResult into session state."""
        if result.success:
            self.metadata = result.metadata
            self.completed_steps.add(result.step)
            if result.output_path:
                self.step_outputs[result.step] = result.output_path
```

### 3.5 `Settings` Responsibility Split

| Constant Type | Lives In | Examples |
|---------------|----------|---------|
| GUI visual constants | `ms_preprocessing/config/settings.py` | `WINDOW_TITLE`, `SIDEBAR_WIDTH`, `WINDOW_MIN_SIZE` |
| Processing constants | import from `ms_core` directly at call site | `SAVE_PARQUET_CACHE`, `get_parquet_cache_root()` |

`main.py` will only import `ms_preprocessing/config/settings.py` for GUI/App constants. Processing constants are accessed by calling adapters (which internally use ms_core Settings), not by importing `ms_core.preprocessing.settings` directly.

**`config/__init__.py` final state**: Remove the current `from ms_core.preprocessing.settings import Settings, ProcessingConfig` re-export entirely. Any callers that need processing constants must go through the adapter layer, not through `config/__init__.py`.

### 3.5a `FileHandler` in `main_window.py`

`gui/main_window.py` currently imports `from ms_core.utils.file_handler import FileHandler` directly (violates layer rule). Resolution: move all `FileHandler` usages into `event_handlers.py` and wrap them via `ms_preprocessing.utils.file_handler` (the existing application-layer wrapper), keeping the GUI layer free of direct ms_core dependencies.

### 3.6 GUI Split: `main_window.py`

| File | Responsibility | Est. LOC |
|------|---------------|---------|
| `gui/layout.py` | All customtkinter widget creation and layout definitions | ~400 |
| `gui/event_handlers.py` | Button events, progress callbacks, step execution, FileHandler via utils wrapper | ~300 |
| `gui/main_window.py` | Assembles layout + event_handlers, holds session | ~150 |

---

## 4. Migration Strategy

### Migration Order (bottom-up)

Each step must leave all existing tests green before proceeding.

```
Step A — Foundation (non-breaking additions)
  ├─ Add utils/results.py (ProcessingResult + ProcessingMetadata)
  └─ Refactor utils/validators.py to DataValidator class

Step B — Adapter Layer
  ├─ Create adapters/ directory
  ├─ Write 4 thin adapters (data_organizer, istd_marker, duplicate_remover, feature_filter)
  └─ Write unit tests for adapters/

Step C — Migrate CLI (main.py)
  ├─ main.py calls adapters/ instead of ms_core directly
  ├─ CLI state management uses PipelineSession
  ├─ Unify Settings import (ms_preprocessing/config/settings.py only)
  └─ Verify all existing CLI tests pass

Step D — Strengthen PipelineSession
  ├─ context dict → ProcessingMetadata dataclass
  ├─ Add can_run_step() prerequisite check
  └─ Verify GUI state management tests pass

Step E — Split main_window.py
  ├─ Extract layout.py
  ├─ Extract event_handlers.py
  ├─ Route FileHandler usage through ms_preprocessing.utils.file_handler (not ms_core directly)
  └─ main_window.py becomes thin assembler

Step E.5 — Migrate widgets/ ms_core dependencies
  ├─ Current widget contract: BaseStepWidget.run_processing(...) -> DataFrame (base_widget.py:179)
  ├─ Widgets also read processor config defaults directly (e.g. istd_marker_widget.py:29)
  ├─ Migration strategy:
  │    • Change BaseStepWidget.run_processing() return type to ProcessingResult
  │    • Each widget calls adapter.run() internally; extracts DataFrame from result.data
  │    • Widget config defaults moved to adapter default parameters (not from ms_core directly)
  ├─ Keep widget public API surface identical to avoid breaking callers in main_window.py
  └─ Verify: test_feature_filter_widget.py:56, test_gui_main_window_sidebar_labels.py pass

Step F — Cleanup (last)
  ├─ Verify no remaining `from ms_preprocessing.core` imports (grep)
  ├─ Delete core/ directory
  └─ Update __init__.py public API
```

### New Test Coverage (additions only)

```
tests/
├── unit/
│   ├── test_results.py                        ← ProcessingResult + ProcessingMetadata
│   ├── test_validators.py                     ← DataValidator class
│   └── adapters/
│       ├── test_adapter_data_organizer.py
│       ├── test_adapter_istd_marker.py
│       ├── test_adapter_duplicate_remover.py
│       └── test_adapter_feature_filter.py
└── (existing 24 test files — unchanged)
```

Each adapter test covers:
1. Valid input → `ProcessingResult(success=True)` with correct metadata fields
2. Invalid input → `ProcessingResult(success=False, error=...)`
3. Metadata fields correctly populated (`red_font_rows`, `protected_rows`, etc.)

### Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Adapter wrapping changes behavior | Medium | Run full test suite after Step B |
| GUI event binding breaks after split | Low | Step E moves code only, no logic change |
| Settings unification drops a constant | Low | Audit constant inventory before Step C |
| Widget callback interface breaks after adapter migration | Medium | Run test_feature_filter_widget.py and test_gui_main_window_sidebar_labels.py after Step E.5 |
| `ProcessingResult` name collision with `ms_core.preprocessing.base.ProcessingResult` | Medium | Always import from `ms_preprocessing.utils.results`; add import linting rule |
| Actual test file count differs from "24" | Low | Run `ls tests/` and count before Step A; update success criterion accordingly |
| Remaining `core/` import missed | Low | `grep -r "from ms_core" src/ms_preprocessing/` before Step F |

---

## 5. Success Criteria

1. All pre-existing tests pass after each migration step (count verified before Step A with `ls tests/`)
2. New tests pass (6 new test files: test_results, test_validators, 4 adapter tests)
3. No file in `ms_preprocessing` imports directly from `ms_core` except `adapters/` — verified by `grep -r "from ms_core" src/ms_preprocessing/` returning only adapter paths (integration boundary files in Steps C–F are resolved before this criterion is checked)
4. `main_window.py` is under 200 LOC
5. `core/` directory no longer exists
6. CLI and GUI both use `PipelineSession` for state management
7. Only one `Settings` import path used throughout `ms_preprocessing`
