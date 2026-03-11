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

## Verification Rules

Do not claim completion without fresh evidence.

Default verification commands:

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

For smaller tasks, run the narrowest sufficient check first, then expand if risk justifies it.

Useful local checks:

```bash
python -c "from ms_preprocessing import __version__; print(__version__)"
pyinstaller ms-preprocessing.spec --clean --noconfirm
```

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
