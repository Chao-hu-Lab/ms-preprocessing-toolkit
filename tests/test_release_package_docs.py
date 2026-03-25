"""Checks for release-package helper documents."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_readme_exists_with_end_user_runtime_guidance() -> None:
    readme = (ROOT / "docs" / "release" / "README.md").read_text(encoding="utf-8")

    assert "Windows" in readme
    assert "macOS" in readme
    assert "OUTPUT" in readme
    assert "Open Output Folder" in readme
    assert "right-click the app and choose `Open`" in readme


def test_license_file_exists_for_release_packages() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "MIT License" in license_text
    assert "Permission is hereby granted" in license_text


def test_build_workflow_copies_release_docs_into_packaged_zip() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    assert 'Copy-Item "docs\\release\\README.md"' in workflow
    assert 'Copy-Item "LICENSE"' in workflow
    assert 'cp "docs/release/README.md" "$stage_dir/README.md"' in workflow
    assert 'cp "LICENSE" "$stage_dir/LICENSE"' in workflow
