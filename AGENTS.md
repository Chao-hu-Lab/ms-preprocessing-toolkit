# AGENTS

This file defines the default working contract for coding agents in this repository.

## Scope

- This repository has two code surfaces:
  - `src/ms_preprocessing/`: GUI, CLI, packaging, wrappers
  - `ms-core/`: git submodule containing core processing logic
- Changes in `ms-core/` must be handled as submodule changes, not as regular in-repo edits.

## Rule Scope

Keep this file repo-specific. General agent behavior should live in global/user
instructions or reusable skills unless this repository needs a stricter local
override.

Rules belong here when they change how this repository must be handled:

- `ms-core` submodule ownership and pointer updates
- Step1-4 scientific/workflow contracts
- downstream handoff boundaries between toolkit, DNP, and MA
- testing marker ownership and CI shard selection
- Windows GUI, localized text, root hygiene, release, and packaging rules
- local architecture-index policy such as `.graphifyignore` and `graphify-out/`

Do not expand this file with generic rules that apply to every repository, such
as broad prompting style, memory-bank frameworks, generic tool preferences, or
general multi-agent orchestration. Promote repeated cross-repo rules to a global
agent rule or a skill instead.

## Instruction Priority And Local Context

Use the most specific trustworthy repo instruction that applies to the files
being changed. Current user instructions override this file, and this file
overrides older plans unless the user explicitly says otherwise.

Before editing, locate the local context for the target files:

```powershell
rg --files -g AGENTS.md -g CLAUDE.md -g README.md -g "docs/TESTING.md" -g "docs/plans/*.md"
```

- Read the closest relevant `AGENTS.md` / `CLAUDE.md` / `README.md` before
  editing a subdirectory or package.
- Read `docs/TESTING.md` before choosing tests, markers, CI shards, or GUI
  smoke coverage.
- Read the latest relevant contract under `docs/plans/` before changing
  scientific rules, workflow semantics, exported metadata, or downstream
  handoff behavior.
- If two sources of truth disagree, stop and report the conflict instead of
  silently choosing one.

## Task Intake

Before starting substantial work, structure the task in this order:

1. `Goal`
2. `Context`
3. `Constraints`
4. `Done When`

If the user request is ambiguous, clarify the missing part instead of guessing.

For behavior changes, also identify whether the task changes any public
surface:

- CLI flag, GUI parameter, config/profile key, worksheet name, exported column,
  metadata field, file format, cache shape, or downstream handoff document.
- If yes, treat it as an API contract change and update docs/tests with the
  implementation.

## Working Modes

- Simple, local, low-risk task:
  - Inspect the relevant files
  - Make the smallest correct change
  - Run focused verification
- Multi-file change, behavior change, bug fix, or release work:
  - Inspect code and tests first
  - Create a short execution plan before editing
  - Prefer test-first or verification-first workflow

## Pre-Flight Check

Before any development work, run:

```powershell
git status
git branch --show-current
```

Do not proceed blindly if:

- the working tree is dirty and the changes are unrelated
- you are on `master`
- the task should be isolated in a worktree but is not

## Branch And Workspace Rules

- Do not develop directly on `master`
- Use branch names under:
  - `feature/*`
  - `fix/*`
  - `chore/*`
- Prefer git worktrees for any task that changes behavior, spans multiple files, or may run for more than one session

Recommended pattern:

```powershell
git worktree add .worktrees/<branch-name> -b <type>/<branch-name>
```

## Code Change Rules

- Read the relevant implementation and test files before editing
- Keep changes narrow and local; avoid opportunistic refactors unless required
- Do not change unrelated files just because they are nearby
- When touching behavior, also touch verification
- When a past mistake repeats, encode the fix into repo instructions instead of relying on memory
- Prefer existing helpers, adapters, and file-local patterns before creating new
  abstractions.
- Avoid growing already-large orchestration modules. If a file is becoming a
  dumping ground, add a small focused module and keep ownership boundaries clear.

## Public API And Contract Rules

Public contract includes more than Python function signatures in this project.

- Preserve exported function signatures, argument names, CLI flags, GUI
  parameter names, config/profile keys, worksheet names, column names, metadata
  field names, and parquet/cache wire shapes unless the task explicitly changes
  them.
- When adding optional Python parameters to public or adapter-facing functions,
  prefer keyword-only arguments with conservative defaults.
- Before removing or renaming a public surface, search for GUI, CLI, export,
  autosave, tests, docs, and downstream handoff usage.
- If a change alters user-visible behavior, final export contents, or downstream
  routing, update README / handoff docs / GUI copy as appropriate.
- Treat generated or derived artifacts as part of the contract when the repo
  already versions them. If a schema, snapshot, lockfile, marker map, or package
  metadata is generated from source, update it in the same change or document why
  it is intentionally unchanged.

## Contract-First Rules

Scientific and workflow rules are public contracts in this repository. Do not
encode a new rule directly in code, GUI copy, or README prose before the contract
is clear.

Default order for any new rule, threshold behavior, metadata schema, or
cross-repo handoff:

1. Write or update the contract document under `docs/plans/`.
2. Add or update focused tests that encode the contract.
3. Implement the smallest code change that satisfies those tests.
4. Update GUI copy, README, and handoff docs to match the contract.

If an urgent bug fix must ship before the contract document is complete, the PR
must state that explicitly and include a follow-up plan. Do not let the code
become the only source of truth for scientific behavior.

## Downstream Boundary Rules

Treat downstream responsibility as an API contract, not as informal knowledge.

- `ms-preprocessing-toolkit` owns Step 1-4 preprocessing, final export, and
  metadata/schema emitted for downstream handoff.
- DNP owns calibration. It must exclude toolkit metadata from numeric
  calibration matrices and pass the metadata through to MA without interpreting
  imputation semantics.
- MA / `Metaboanalyst_clone` owns missing-value imputation and statistical
  analysis behavior.
- Any new downstream-facing column, worksheet, profile key, or metadata field
  must have a documented owner, a pass-through/exclusion rule, and a focused
  regression test.
- Do not make toolkit code depend on downstream internals unless the task
  explicitly changes a cross-repo contract and the corresponding downstream
  handoff document is updated.

## Text And UI Copy Rules

- Treat all repository text files as UTF-8 by default, especially `.py`, `.md`, `.yml`, `.yaml`, `.json`, `.toml`, `.txt`, and any file containing localized UI text.
- Preserve Chinese and other non-ASCII user-facing text as UTF-8 source-of-truth. Do not save localized text files in ANSI, Big5, or editor-default legacy encodings.
- Keep UI copy cleanup isolated from layout, styling, and behavior changes unless the task explicitly requires them together.
- Before editing localized strings, confirm the file reads correctly as UTF-8. If the file is already mojibake, repair the encoding or file readability first; do not patch new wording into corrupted text.
- For visible GUI text, update the source-of-truth layer first, then align downstream copies. Typical order is: shared base widgets, config/constants, event-handler messages, step widgets, tests.
- Do not rewrite scientific or workflow rule descriptions from memory when a report, design note, or commit history exists. Trace the current wording back to the latest authoritative source before updating the GUI copy.
- On Windows and CustomTkinter surfaces, default to plain-text button labels. Introduce icons, emoji, or special glyphs only after confirming stable rendering on the target platform and font stack.

## Verification Rules

Do not claim completion without fresh evidence.

Testing policy source of truth: `docs/TESTING.md`. When selecting tests or
working on testing, CI, quality gates, GUI smoke checks, root hygiene, or
verification scope, read that document first and use its change-to-test matrix.
Top-level pytest marker assignment is centralized in `tests/testing_markers.py`;
update that mapping and `tests/test_testing_markers.py` when adding marker-owned
test files.

Default verification commands:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

For smaller tasks, run the narrowest sufficient check first, then expand if risk justifies it.

Verification evidence must be fresh, task-scoped, and inspected. For expensive
suites, run focused tests first and state the remaining risk.

If you touched localized or user-visible text:

- Inspect the edited files as explicit UTF-8 text before finishing; terminal rendering alone is not sufficient evidence.
- Scan the touched files for obvious mojibake markers such as replacement characters or suspicious placeholder `??` around localized text.
- Run the narrowest relevant GUI/text regression tests so string fixes do not silently drift from the UI.
- If the change touches shared GUI layers such as `layout.py`, `base_widget.py`, `event_handlers.py`, shared style/config modules, or workflow labels, run a minimal GUI smoke check that covers startup, step switching, action-button visibility, and primary step titles/descriptions.

Useful local checks:

```powershell
python -c "from ms_preprocessing import __version__; print(__version__)"
pyinstaller ms-preprocessing.spec --clean --noconfirm
```

## Root Hygiene Rules

- Do not write test temp directories into the repository root with `TemporaryDirectory(dir=Path.cwd())`.
- For top-level tests, use the fixtures in `tests/conftest.py`; for `ms-core`, use `ms-core/tests/conftest.py`.
- If pytest/temp/cache behavior changes, use `skills/root-hygiene/SKILL.md` and verify that root-level `tmp*` and `.pytest*` clutter no longer appears.
- Use `scripts/clean_local_artifacts.ps1` for routine cleanup; treat leftover blocked temp folders as a local environment issue and report them explicitly.

## Review Rules

When asked to review:

- findings first
- severity ordered
- include concrete file paths and 1-based line references
- summaries second

If no issues are found, say so explicitly and mention residual risks or test gaps.

When reviewing or self-reviewing, explicitly check:

- public contract drift
- missing or stale tests
- GUI/CLI behavior divergence
- downstream metadata leakage into numeric matrices
- file format or worksheet compatibility
- generated artifacts, marker maps, and lockfiles that should have changed

## Submodule Rules

For `ms-core/` changes:

1. Edit inside `ms-core/`
2. Commit inside the `ms-core` repository first
3. Push `ms-core` first
4. Return to the top-level repo
5. Update the submodule pointer with `git add ms-core`
6. Commit the top-level repo change

Do not leave top-level commits pointing at an unpushed submodule commit.

When working inside a worktree, keep operations confined to that worktree. Do
not borrow build artifacts, generated outputs, or dirty files from another
worktree unless the user explicitly asks for that migration.

## Commit, Push, And PR Rules

- Commit only files related to the current task.
- Before staging, inspect `git status --short` and avoid staging unrelated local
  files, generated outputs, secrets, or temporary artifacts.
- Do not push unless the user explicitly asks to push, upload, create/update a
  PR, or otherwise publish the branch.
- For PR descriptions, keep the summary focused on what changed and why; include
  testing only when it is useful for review or risk assessment.

## Release Rules

Release flow:

1. Update version in:
   - `pyproject.toml`
   - `src/ms_preprocessing/__init__.py`
2. Commit the version bump
3. Push `master`
4. Create annotated tag `vX.Y.Z`
5. Push the tag
6. GitHub Actions builds the Windows executable and creates the GitHub Release

Relevant workflows:

- `.github/workflows/ci.yml`
- `.github/workflows/build.yml`

## Skills And Reusable Workflows

- If a workflow repeats, prefer encoding it as a skill under `skills/`
- `graphify` may be used as a local architecture memory layer. Keep
  `graphify-out/` local unless the user explicitly asks to version it; prefer
  committing only `.graphifyignore` until the generated graph is proven useful.
- Existing repo skills:
  - `skills/verification-shards/SKILL.md`
  - `skills/release-checklist/SKILL.md`
  - `skills/submodule-update/SKILL.md`
  - `skills/merge-quality-gate/SKILL.md`
  - `skills/root-hygiene/SKILL.md`

Candidate future skills:

- CI failure triage
- Step 4 regression verification

## Config And Tooling Gaps

Current repo gap list:

- no repo-level MCP configuration discovered
- no repo-level automation beyond GitHub Actions workflows

Agents should not invent missing config. If the task depends on these, state the gap explicitly.

## Prohibited Actions

- No direct feature development on `master`
- No force push to `master`
- No merge or release without verification
- No skipping pre-flight checks
- No submodule pointer update without first pushing the submodule commit
- No silent assumptions about external systems, secrets, or runtime configuration
- No new scientific/workflow rule without a contract document or an explicit
  follow-up plan documenting why the contract update is deferred

## Done Standard

A task is only done when all of the following are true:

- requested behavior is implemented
- impacted tests or checks were run
- results were inspected
- important risks or gaps were stated
- branch, submodule, and release state are consistent with the requested operation
