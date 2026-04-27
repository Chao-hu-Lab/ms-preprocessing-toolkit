# Root Hygiene Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep the repository root clean by centralizing pytest/test temp artifacts and providing a repeatable cleanup path.

**Architecture:** Redirect pytest-managed temp paths into a single ignored `.tmp/` tree, replace test cases that force temp directories into `Path.cwd()`, and add a cleanup script plus docs so local runs use the same hygiene rules. Mirror the same policy in `ms-core` because its tests currently emit the same root-level `tmp*` directories.

**Tech Stack:** Python, pytest, PowerShell, git worktrees, ms-core submodule

---

### Task 1: Add a Failing Regression Test for Temp Root Policy

**Files:**
- Create: `tests/test_root_hygiene.py`
- Modify: `tests/conftest.py`

**Step 1: Write the failing test**

```python
def test_project_temp_root_fixture_stays_under_dot_tmp(project_temp_root):
    assert project_temp_root.parts[-2:] == (".tmp", "tests")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_root_hygiene.py -v`
Expected: FAIL because `project_temp_root` fixture does not exist yet.

**Step 3: Write minimal implementation**

```python
@pytest.fixture(scope="session")
def project_temp_root() -> Path:
    path = ROOT / ".tmp" / "tests"
    path.mkdir(parents=True, exist_ok=True)
    return path
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_root_hygiene.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_root_hygiene.py tests/conftest.py
git commit -m "test: add root hygiene temp fixture"
```

### Task 2: Centralize Toolkit Pytest Temp Directories

**Files:**
- Modify: `tests/conftest.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`

**Step 1: Write the failing test**

```python
def test_pytest_basetemp_points_inside_dot_tmp(pytestconfig):
    assert ".tmp" in str(pytestconfig.option.basetemp)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_root_hygiene.py -k basetemp -v`
Expected: FAIL because `basetemp` still points to `.pytest-tmp`.

**Step 3: Write minimal implementation**

```python
basetemp = ROOT / ".tmp" / "pytest" / "basetemp"
```

Also add `.tmp/`, `.pytest-local-temp/`, and `tmp*/` ignore rules, and add `.tmp` to pytest `norecursedirs`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_root_hygiene.py -k basetemp -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/conftest.py pyproject.toml .gitignore tests/test_root_hygiene.py
git commit -m "chore: centralize toolkit pytest temp paths"
```

### Task 3: Remove Root-Level TemporaryDirectory Usage in Toolkit Tests

**Files:**
- Modify: `tests/test_cli_parquet_chain.py`
- Modify: `tests/test_final_export_handoff.py`
- Modify: `tests/test_final_export_cache_policy.py`
- Modify: `tests/test_integration_parquet_pipeline.py`
- Modify: `tests/test_intermediate_store_bridge.py`

**Step 1: Write the failing test**

```python
def test_project_temp_dir_factory_creates_dirs_under_dot_tmp(project_temp_dir):
    with project_temp_dir() as temp_dir:
        assert temp_dir.is_dir()
        assert ".tmp" in str(temp_dir)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_root_hygiene.py -k project_temp_dir -v`
Expected: FAIL because `project_temp_dir` fixture does not exist yet.

**Step 3: Write minimal implementation**

```python
@pytest.fixture
def project_temp_dir(project_temp_root):
    def _factory(prefix: str = "case-"):
        return TemporaryDirectory(dir=project_temp_root, prefix=prefix)
    return _factory
```

Then replace each `TemporaryDirectory(dir=Path.cwd())` call with `project_temp_dir()`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_root_hygiene.py tests/test_cli_parquet_chain.py tests/test_final_export_handoff.py tests/test_final_export_cache_policy.py tests/test_integration_parquet_pipeline.py tests/test_intermediate_store_bridge.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_root_hygiene.py tests/conftest.py tests/test_cli_parquet_chain.py tests/test_final_export_handoff.py tests/test_final_export_cache_policy.py tests/test_integration_parquet_pipeline.py tests/test_intermediate_store_bridge.py
git commit -m "test: keep toolkit temp directories out of repo root"
```

### Task 4: Mirror Temp Hygiene in ms-core Tests

**Files:**
- Create: `ms-core/tests/conftest.py`
- Modify: `ms-core/tests/test_cache_path_policy.py`
- Modify: `ms-core/tests/test_intermediate_store.py`
- Modify: `ms-core/pyproject.toml`
- Modify: `ms-core/.gitignore`

**Step 1: Write the failing test**

```python
def test_ms_core_temp_root_stays_under_dot_tmp(project_temp_root):
    assert project_temp_root.parts[-2:] == (".tmp", "tests")
```

**Step 2: Run test to verify it fails**

Run: `pytest ms-core/tests/test_root_hygiene.py -v`
Expected: FAIL because `ms-core/tests/conftest.py` does not exist yet.

**Step 3: Write minimal implementation**

```python
ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="session")
def project_temp_root() -> Path:
    path = ROOT / ".tmp" / "tests"
    path.mkdir(parents=True, exist_ok=True)
    return path
```

Add the matching fixture factory and use it in the ms-core tests that currently pin temp dirs to `Path.cwd()`.

**Step 4: Run test to verify it passes**

Run: `pytest ms-core/tests/test_cache_path_policy.py ms-core/tests/test_intermediate_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd ms-core
git add tests/conftest.py tests/test_cache_path_policy.py tests/test_intermediate_store.py pyproject.toml .gitignore
git commit -m "test: centralize ms-core temp directories"
cd ..
git add ms-core
git commit -m "chore: update ms-core root hygiene pointer"
```

### Task 5: Add Cleanup Tooling and Verification Docs

**Files:**
- Create: `scripts/clean_local_artifacts.ps1`
- Modify: `README.md`
- Modify: `AGENTS.md`

**Step 1: Write the failing test**

```python
def test_cleanup_script_exists():
    assert Path("scripts/clean_local_artifacts.ps1").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_root_hygiene.py -k cleanup_script -v`
Expected: FAIL because the script does not exist yet.

**Step 3: Write minimal implementation**

```powershell
$targets = @(".tmp", ".pytest_cache", "__pycache__")
```

Make the script remove known local artifacts and root-level `tmp*` directories, then document when to use it.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_root_hygiene.py -k cleanup_script -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/clean_local_artifacts.ps1 README.md AGENTS.md tests/test_root_hygiene.py
git commit -m "docs: add local cleanup workflow"
```

### Task 6: Full Verification

**Files:**
- Modify: `docs/plans/2026-03-12-root-hygiene-cleanup.md`

**Step 1: Run focused toolkit verification**

Run: `PYTHONPATH=ms-core/src pytest tests/test_root_hygiene.py tests/test_cli_parquet_chain.py tests/test_final_export_handoff.py tests/test_final_export_cache_policy.py tests/test_integration_parquet_pipeline.py tests/test_intermediate_store_bridge.py -v --tb=short`
Expected: PASS

**Step 2: Run focused ms-core verification**

Run: `pytest ms-core/tests/test_cache_path_policy.py ms-core/tests/test_intermediate_store.py -v --tb=short`
Expected: PASS

**Step 3: Run default repo verification**

Run: `PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x`
Expected: PASS

**Step 4: Inspect root hygiene**

Run: `Get-ChildItem -Force`
Expected: no new root-level `tmp*` directories are present after test execution.

**Step 5: Commit final verification note**

```bash
git add docs/plans/2026-03-12-root-hygiene-cleanup.md
git commit -m "docs: record root hygiene verification"
```
