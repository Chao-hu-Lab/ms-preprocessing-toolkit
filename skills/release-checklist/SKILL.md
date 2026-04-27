---
name: release-checklist
description: Use when preparing or executing a release for this repository, especially when bumping versions, creating tags, pushing release commits, or verifying that the GitHub Release workflow has produced the expected Windows executable.
---

# Release Checklist

## Overview

Run the repository's release flow in a consistent order. Use this skill when code is already ready to ship and the remaining work is versioning, tagging, pushing, and verifying the release outcome.

For test selection and verification scope, read the repo root's
`docs/TESTING.md` first.

## Preconditions

Use this skill only when:

- the requested code changes are already implemented
- relevant verification has passed
- the user wants an actual versioned release, not a draft plan

Stop and ask before proceeding if:

- the working tree contains unrelated changes
- the release version is not specified and cannot be inferred safely
- `ms-core` has local changes that have not been committed and pushed

## Workflow

1. Run pre-flight checks.
   - `git status`
   - `git branch --show-current`
   - confirm the tree is clean enough for a release
2. Verify release prerequisites.
   - if the task touched `ms-core`, confirm the submodule commit is already pushed
   - run the relevant verification command before claiming readiness
3. Update the version in both files:
   - `pyproject.toml`
   - `src/ms_preprocessing/__init__.py`
4. Re-check the exposed version string locally.
5. Commit the version bump with a release-oriented message.
6. Push the branch that should carry the release commit.
7. Create an annotated tag in the form `vX.Y.Z`.
8. Push the tag.
9. Verify that the tag-triggered GitHub Actions workflow has started or that the GitHub Release exists.
10. Report the branch commit, tag, and release status separately.

## Verification

- Do not skip fresh evidence.
- Prefer the repository default test command:

```powershell
$env:PYTHONPATH='ms-core/src'
python -m pytest tests/ -v --tb=short -x
```

- Re-check the local package version after editing:

```bash
python -c "from ms_preprocessing import __version__; print(__version__)"
```

## Release-Specific Rules

- Keep the version identical in both version files.
- Use annotated tags, not lightweight tags.
- Push `ms-core` first if the release depends on a new submodule pointer.
- Do not say the release is complete until the tag exists remotely.
- Distinguish:
  - `tag pushed`
  - `workflow triggered`
  - `GitHub Release published`

## Reference Files

- For exact commands and verification points, read:
  - `references/commands.md`

## Output

When finished, report:

- released version
- top-level commit SHA
- tag name
- whether the tag was pushed
- whether the Release workflow or GitHub Release has been verified

If any release step is blocked by auth, network, or GitHub state, state the exact blocking step instead of implying success.
