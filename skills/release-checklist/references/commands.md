# Release Commands

## Pre-flight

```bash
git status
git branch --show-current
```

## Version Files

Update both:

- `pyproject.toml`
- `src/ms_preprocessing/__init__.py`

## Local Version Check

```bash
python -c "from ms_preprocessing import __version__; print(__version__)"
```

## Default Verification

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

## Version Bump Commit

Example:

```bash
git add pyproject.toml src/ms_preprocessing/__init__.py
git commit -m "chore(release): bump version to 1.1.4"
```

## Push And Tag

```bash
git push origin master
git tag -a v1.1.4 -m "Release v1.1.4"
git push origin v1.1.4
```

## GitHub Release Notes

This repository relies on the tag-triggered workflow:

- `.github/workflows/build.yml`

The workflow:

- builds the Windows executable
- uploads the artifact
- creates the GitHub Release

## Verification Targets

Check these separately:

1. remote branch updated
2. remote tag exists
3. release workflow started
4. GitHub Release exists
5. release asset exists

Never collapse all five into one vague "release done" statement.
