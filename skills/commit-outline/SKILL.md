---
name: commit-outline
description: Use when drafting commit messages, PR summaries, or release-note outlines for this repository, especially after code changes are ready and the user wants concise, repo-aligned summaries from git status, diffs, and verification results.
---

# Commit Outline

## Overview

Turn local repository changes into clean commit subjects, useful commit bodies, and short PR or release summaries. Use this skill after the implementation is understood and the remaining problem is how to describe it clearly.

## Inputs To Gather

- `git status --short`
- staged or unstaged diff for the relevant files
- test or verification results
- whether the summary is for:
  - commit
  - PR
  - release notes

## Workflow

1. Identify the true change unit.
   - one behavior fix
   - one refactor
   - one release bump
   - or multiple logically separate changes
2. Map the change to the smallest honest commit type.
   - `feat`
   - `fix`
   - `refactor`
   - `docs`
   - `test`
   - `build`
   - `ci`
   - `chore`
3. Draft a short subject line that names the user-visible or developer-visible outcome, not the mechanics.
4. Add a body only when it improves clarity.
   - multi-file change
   - behavior/risk needs explanation
   - release or migration context matters
5. For PR summaries, group into:
   - what changed
   - why it changed
   - how it was verified
6. For release summaries, prefer user-facing language and hand off to `changelog-generator` when a polished changelog is needed.

## Repository-Specific Guidance

- Prefer `feat(step4): ...` / `fix(gui): ...` style scopes when a narrow scope is obvious.
- If a change updates the `ms-core` pointer, mention that explicitly in the top-level summary.
- Version-only commits should stay in `chore(release): ...` form.
- Do not hide verification gaps. If tests were partial, say so.

## Reference Files

- For commit type choices and summary templates, read:
  - `references/templates.md`

## Output

Provide only what the user needs:

- commit subject only
- commit subject + body
- PR summary bullets
- release-note outline

Keep the output short, concrete, and aligned with the actual diff.
