# AGENTS

This file defines the default working contract for coding agents in this repository.

## Scope

- This repository has two code surfaces:
  - `src/ms_preprocessing/`: GUI, CLI, packaging, wrappers
  - `ms-core/`: git submodule containing core processing logic
- Changes in `ms-core/` must be handled as submodule changes, not as regular in-repo edits.

## Task Intake

Before starting substantial work, structure the task in this order:

1. `Goal`
2. `Context`
3. `Constraints`
4. `Done When`

If the user request is ambiguous, clarify the missing part instead of guessing.

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

```bash
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

```bash
git worktree add .worktrees/<branch-name> -b <type>/<branch-name>
```

## Code Change Rules

- Read the relevant implementation and test files before editing
- Keep changes narrow and local; avoid opportunistic refactors unless required
- Do not change unrelated files just because they are nearby
- When touching behavior, also touch verification
- When a past mistake repeats, encode the fix into repo instructions instead of relying on memory

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

Default verification commands:

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

For smaller tasks, run the narrowest sufficient check first, then expand if risk justifies it.

If you touched localized or user-visible text:

- Inspect the edited files as explicit UTF-8 text before finishing; terminal rendering alone is not sufficient evidence.
- Scan the touched files for obvious mojibake markers such as replacement characters or suspicious placeholder `??` around localized text.
- Run the narrowest relevant GUI/text regression tests so string fixes do not silently drift from the UI.
- If the change touches shared GUI layers such as `layout.py`, `base_widget.py`, `event_handlers.py`, shared style/config modules, or workflow labels, run a minimal GUI smoke check that covers startup, step switching, action-button visibility, and primary step titles/descriptions.

Useful local checks:

```bash
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

## Submodule Rules

For `ms-core/` changes:

1. Edit inside `ms-core/`
2. Commit inside the `ms-core` repository first
3. Push `ms-core` first
4. Return to the top-level repo
5. Update the submodule pointer with `git add ms-core`
6. Commit the top-level repo change

Do not leave top-level commits pointing at an unpushed submodule commit.

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
- Existing repo skills:
  - `skills/ms-quality-gate/SKILL.md`
  - `skills/release-checklist/SKILL.md`
  - `skills/submodule-update/SKILL.md`
  - `skills/commit-outline/SKILL.md`
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

## Done Standard

A task is only done when all of the following are true:

- requested behavior is implemented
- impacted tests or checks were run
- results were inspected
- important risks or gaps were stated
- branch, submodule, and release state are consistent with the requested operation
