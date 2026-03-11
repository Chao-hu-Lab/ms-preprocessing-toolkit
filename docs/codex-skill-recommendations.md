# Codex Skill Recommendations For This Repo

## Goal

This document maps `ComposioHQ/awesome-codex-skills` to the actual needs of `ms-preprocessing-toolkit`.

Focus areas:

- Python development workflow
- data processing and spreadsheet-adjacent work
- general development rules
- commit / changelog / release support

## Current Skill Inventory

### Already available in this environment

Global or system-level skills already cover several categories:

- `gh-address-comments`
- `gh-fix-ci`
- `skill-creator`
- `mcp-builder`
- `webapp-testing`
- `xlsx`
- `internal-comms`
- several planning / execution skills already exist outside the repo

### Repo-local skill already present

- `skills/ms-quality-gate`
  - good fit for local testing, smoke checks, and code review structure

## Install First

These are the best additions from `awesome-codex-skills` for this repository.

### 1. `changelog-generator`

Why install:

- directly useful for release notes
- useful for commit summary -> release summary conversion
- fits the current tag-driven release workflow

Best use cases here:

- summarize changes between `v1.1.2` -> `v1.1.3`
- draft GitHub Release notes
- produce user-facing update summaries from technical commits

Install:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo ComposioHQ/awesome-codex-skills --path changelog-generator
```

### 2. `file-organizer`

Why install:

- this repo produces outputs, docs, temporary artifacts, and test byproducts
- useful for cleaning local workspace clutter and archiving old outputs

Best use cases here:

- organize `OUTPUT/`, temp exports, benchmark files, and user-deliverable folders
- clean old generated artifacts before release packaging

Install:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo ComposioHQ/awesome-codex-skills --path file-organizer
```

## Install If You Actually Need The Workflow

These are useful, but not mandatory for this repo.

### 3. `spreadsheet-formula-helper`

Why optional:

- strong for Excel / Google Sheets formulas
- not a replacement for pandas / parquet / schema-validation work
- overlaps partially with the existing `xlsx` skill

Install if:

- you often debug Excel formulas for users
- you need help translating spreadsheet logic into reliable formulas

Skip if:

- most work stays in pandas, pytest, and Python pipelines

Install:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo ComposioHQ/awesome-codex-skills --path spreadsheet-formula-helper
```

### 4. `connect` or `connect-apps`

Why optional:

- only useful if you plan to wire Codex to external tools
- most valuable when paired with MCP or Composio actions

Install if:

- you want Codex to act on Slack, Notion, Jira, Linear, or email

Skip if:

- your current workflow stays inside git, pytest, and local files

## Do Not Install From Awesome Because You Already Have Equivalent Or Better Coverage

These would be redundant in the current environment.

### Planning / workflow overlap

- `create-plan`

Reason:

- your environment already includes stronger planning and execution-oriented skills
- repo guidance is now encoded in `AGENTS.md` and `CLAUDE.md`

### GitHub review / CI overlap

- `gh-fix-ci`
- `gh-address-comments`

Reason:

- already available globally

### Skill authoring overlap

- `skill-creator`

Reason:

- already available globally

### MCP / app testing overlap

- `mcp-builder`
- `webapp-testing`

Reason:

- already available globally

### Writing / Notion overlap

- `internal-comms`
- Notion-related skills from the awesome repo ecosystem

Reason:

- equivalents already exist in the current environment

## What Awesome-Codex-Skills Does Not Solve Well For This Repo

The external repo does **not** provide a strong ready-made skill for:

- Python data engineering workflow
- pandas / parquet / dataframe validation
- submodule-safe development flow
- release checklist with version bump + tag + release verification
- commit-outline generation tuned to this repository

These should be repo-specific skills.

## Recommended Private Skills To Build Next

### 1. `python-data-workflow`

Purpose:

- standard Python + pandas + pytest workflow for this repo

Should include:

- default commands
- preferred test scope strategy
- parquet / xlsx / csv validation rules
- common failure patterns in this codebase

### 2. `submodule-update`

Purpose:

- encode the safe `ms-core` update sequence

Should include:

- commit in submodule first
- push submodule first
- update top-level pointer second
- verify repo state before final commit

### 3. `release-checklist`

Purpose:

- make release flow deterministic

Should include:

- bump version in both files
- verify version output
- run validation
- push branch
- create and push tag
- verify GitHub Release exists

### 4. `commit-outline`

Purpose:

- generate clean commit / PR / release summaries

Should include:

- conventional commit suggestions
- summary from changed files
- PR summary bullets
- release-note draft handoff to `changelog-generator`

### 5. `step4-regression-check`

Purpose:

- protect the most fragile, domain-specific part of this toolkit

Should include:

- Step 4 threshold checks
- zero-as-missing checks
- QC ratio behavior
- GUI/processor parameter sync

## Recommended Install Set

If you only want the highest-value set, install exactly these:

1. `changelog-generator`
2. `file-organizer`
3. `spreadsheet-formula-helper` only if Excel formula support matters

Then build these private skills:

1. `python-data-workflow`
2. `submodule-update`
3. `release-checklist`
4. `commit-outline`
5. `step4-regression-check`

## Source

- `https://github.com/ComposioHQ/awesome-codex-skills`
