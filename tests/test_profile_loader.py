"""Tests for YAML-backed pipeline profile loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from ms_preprocessing.config import profile_loader


def test_built_in_default_profile_loads_from_yaml() -> None:
    profile = profile_loader.get_pipeline_profile("default")

    assert isinstance(profile["step1"]["method_file"], str)
    assert isinstance(profile["step2"]["xic_results_file"], str)
    assert profile["step3"]["merge_mode"] == "per_sample_max"
    assert profile["step4"]["ratio_rescue_threshold"] == pytest.approx(3.0)


def test_profile_loader_substitutes_local_reference_placeholders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference_path = tmp_path / "local_reference.yml"
    reference_path.write_text(
        "\n".join(
            [
                "version: 1",
                "references:",
                '  method_file: "method.docx"',
                '  xic_results_file: "xic.xlsx"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(reference_path))

    profile = profile_loader.get_pipeline_profile("default")

    assert profile["step1"]["method_file"] == "method.docx"
    assert profile["step2"]["xic_results_file"] == "xic.xlsx"


def test_profile_loader_rejects_runtime_input_keys(tmp_path: Path) -> None:
    profile_path = tmp_path / "bad.yml"
    profile_path.write_text(
        "\n".join(
            [
                "version: 1",
                "name: bad",
                "steps:",
                "  step1:",
                "    mode: normalization",
                "    auto_detect: true",
                '    method_file: ""',
                '    input_file: "locked.xlsx"',
                "  step2:",
                '    xic_results_file: ""',
                "  step3:",
                "    mz_tolerance_ppm: 20.0",
                "    rt_tolerance: 0.1",
                "    merge_mode: per_sample_max",
                "    preserve_red_font: true",
                "    top_n: null",
                "    enable_degeneracy_annotation: false",
                "    degeneracy_ppm_tolerance: 20.0",
                "    degeneracy_rt_tolerance: 0.05",
                "    degeneracy_correlation_threshold: 0.8",
                "    degeneracy_min_correlation_points: 3",
                '    degeneracy_adduct_table_file: ""',
                "  step4:",
                "    signal_threshold: 5000.0",
                "    background_threshold: 0.33",
                "    high_det_thresh: 0.8",
                "    low_det_thresh: 0.2",
                "    qc_ratio_threshold: 0.25",
                "    intensity_fc_threshold: 2.0",
                "    ratio_rescue_threshold: 3.0",
                "    enable_background_threshold: true",
                "    enable_qc_ratio_threshold: true",
                "    enable_intensity_fc_threshold: false",
                "    enable_mnar_gate: true",
                "    enable_ratio_rescue: true",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="input_file"):
        profile_loader.load_pipeline_profile_file(profile_path)


def test_profile_loader_rejects_unknown_step4_key(tmp_path: Path) -> None:
    profile_path = tmp_path / "bad.yml"
    profile_path.write_text(
        Path("src/ms_preprocessing/config/presets/default.yml").read_text(encoding="utf-8")
        + "\n    diff_threshold: 0.3\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="diff_threshold"):
        profile_loader.load_pipeline_profile_file(profile_path)


def test_profile_loader_discovers_local_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_dir = tmp_path / "presets"
    local_dir.mkdir()
    profile_path = local_dir / "lab.yml"
    profile_text = Path("src/ms_preprocessing/config/presets/default.yml").read_text(encoding="utf-8")
    profile_path.write_text(
        profile_text.replace("name: default", "name: lab").replace(
            "ratio_rescue_threshold: 3.0",
            "ratio_rescue_threshold: 4.0",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(profile_loader, "LOCAL_PROFILE_DIR", local_dir)

    assert "lab" in profile_loader.list_pipeline_profiles()
    assert profile_loader.get_pipeline_profile("lab")["step4"][
        "ratio_rescue_threshold"
    ] == pytest.approx(4.0)


def test_profile_loader_ignores_local_example_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_dir = tmp_path / "presets"
    local_dir.mkdir()
    profile_path = local_dir / "lab.example.yml"
    profile_path.write_text(
        Path("src/ms_preprocessing/config/presets/default.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(profile_loader, "LOCAL_PROFILE_DIR", local_dir)

    assert "lab.example" not in profile_loader.list_pipeline_profiles()
