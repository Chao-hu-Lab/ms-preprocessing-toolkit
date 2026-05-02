# Codex Skill Surface For This Repo

## Purpose

This document records the current skill strategy for `ms-preprocessing-toolkit`.
Repo-local skills should cover only workflows that are specific to this
repository and difficult to replace with global Codex skills, GitHub tools, or
general engineering judgment.

## Current Decision

Keep the repo-local skill surface small:

1. `skills/submodule-update`
2. `skills/merge-quality-gate`
3. `skills/release-checklist`
4. `skills/root-hygiene`
5. `skills/verification-shards`

Do not add repo-local skills for generic commit writing, generic code review,
generic Python style, or generic GitHub workflows. Those are already covered by
global skills, Codex plugins, or `AGENTS.md`.

## Skill Roles

### `submodule-update`

Use when a task edits `ms-core/` or advances the top-level submodule pointer.

Why it stays local:

- `ms-core` is a separate repository.
- The correct commit, push, pointer update, PR, and merge order is a recurring
  repo-specific risk.
- Generic Git skills do not know this repository's two-repo landing order.

### `merge-quality-gate`

Use before merging or marking a PR ready.

Why it stays local:

- It checks toolkit PR state, `ms-core` pointer consistency, CI, review threads,
  and verification evidence together.
- It prevents landing a top-level PR before the `ms-core` SHA it references has
  landed.

Potential future cleanup:

- Reduce duplicated submodule wording by pointing deeper details to
  `submodule-update`.

### `release-checklist`

Use only for actual versioned releases.

Why it stays local:

- Release requires updating two version files, pushing `master`, creating an
  annotated tag, and verifying the GitHub Actions Windows executable release.
- The latest GitHub Release may intentionally lag active source branches until
  the repo is stable enough to tag.

### `root-hygiene`

Use when pytest temp folders, caches, or local artifacts appear in the repo root.

Why it stays local:

- This repository has custom top-level and `ms-core` temp fixtures.
- Root clutter was a real historical failure mode.
- The cleanup script and fixture policy are repository-specific.

### `verification-shards`

Use when selecting or running focused verification.

Why it stays local:

- Test ownership is split between toolkit tests and `ms-core/tests/`.
- Marker shards, GUI tests, adapter contracts, integration tests, and root
  hygiene rules are defined in `docs/TESTING.md`.
- The skill is intentionally thin and defers to `docs/TESTING.md` as source of
  truth.

## Removed Or Replaced

### `commit-outline`

Removed.

Reason:

- Generic commit/PR summaries are covered by global commit and GitHub skills.
- The only remaining repo-specific note, "mention `ms-core` pointer updates",
  belongs in `AGENTS.md`, `submodule-update`, or `merge-quality-gate`.

### `ms-quality-gate`

Replaced by `verification-shards`.

Reason:

- The old script duplicated testing policy and drifted from `docs/TESTING.md`.
- The new skill focuses on shard selection and delegates ownership rules to the
  testing document.

## External Skill Policy

External skills should be imported only when they add a concrete workflow not
already covered locally or globally.

Currently useful external/global additions:

- `implementing-secret-scanning-with-gitleaks`: useful as a security gate before
  public release or when adding new config/secrets surfaces.
- `changelog-generator`: useful for release-note drafting.
- spreadsheet-related skills: useful when the task is directly about `.xlsx`
  inspection or formula behavior.

Avoid importing large all-in-one skill packs wholesale. Prefer one narrow skill
with a clear trigger over broad overlapping rule sets.

## Future Candidates

Only add these if they become recurring workflows:

- `ci-triage`: focused GitHub Actions failure diagnosis for this repo.
- `step4-regression-check`: focused Step4 contract and downstream handoff
  verification.
- `release-hardening`: pre-tag packaging, PyInstaller, README, and release asset
  verification.
