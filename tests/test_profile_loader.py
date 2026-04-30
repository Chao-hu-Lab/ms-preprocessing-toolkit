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


def test_profile_loader_env_reference_overrides_local_placeholders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference_path = tmp_path / "local_reference.yml"
    reference_path.write_text(
        "\n".join(
            [
                "version: 1",
                "references:",
                '  method_file: "local-method.docx"',
                '  xic_results_file: "local-xic.xlsx"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MSPTK_LOCAL_REFERENCE_CONFIG", str(reference_path))
    monkeypatch.setenv("MSPTK_METHOD_FILE", "env-method.docx")
    monkeypatch.setenv("MSPTK_XIC_RESULTS_FILE", "env-xic.xlsx")

    profile = profile_loader.get_pipeline_profile("default")

    assert profile["step1"]["method_file"] == "env-method.docx"
    assert profile["step2"]["xic_results_file"] == "env-xic.xlsx"


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
        Path("src/ms_preprocessing/resources/builtin_profiles/default.yml").read_text(encoding="utf-8")
        + "\n    diff_threshold: 0.3\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="diff_threshold"):
        profile_loader.load_pipeline_profile_file(profile_path)


@pytest.mark.parametrize(
    ("old", "new", "expected_error"),
    [
        ("background_threshold: 0.33", "background_threshold: abc", "step4.background_threshold"),
        ('enable_ratio_rescue: true', 'enable_ratio_rescue: "true"', "step4.enable_ratio_rescue"),
        (
            "degeneracy_min_correlation_points: 3",
            "degeneracy_min_correlation_points: 0",
            "step3.degeneracy_min_correlation_points",
        ),
    ],
)
def test_profile_loader_rejects_invalid_profile_values(
    tmp_path: Path,
    old: str,
    new: str,
    expected_error: str,
) -> None:
    profile_path = tmp_path / "bad.yml"
    profile_text = Path("src/ms_preprocessing/resources/builtin_profiles/default.yml").read_text(
        encoding="utf-8"
    )
    profile_path.write_text(profile_text.replace(old, new), encoding="utf-8")

    with pytest.raises(ValueError, match=expected_error):
        profile_loader.load_pipeline_profile_file(profile_path)


def test_profile_loader_discovers_local_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_dir = tmp_path / "presets"
    local_dir.mkdir()
    profile_path = local_dir / "lab.yml"
    profile_text = Path("src/ms_preprocessing/resources/builtin_profiles/default.yml").read_text(encoding="utf-8")
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
        Path("src/ms_preprocessing/resources/builtin_profiles/default.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(profile_loader, "LOCAL_PROFILE_DIR", local_dir)

    assert "lab.example" not in profile_loader.list_pipeline_profiles()


def test_profile_loader_discovers_profiles_from_cwd_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "config" / "presets"
    config_dir.mkdir(parents=True)
    profile_path = config_dir / "lab.yml"
    profile_text = Path("src/ms_preprocessing/resources/builtin_profiles/default.yml").read_text(encoding="utf-8")
    profile_path.write_text(
        profile_text.replace("name: default", "name: lab"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MSPTK_CONFIG_DIR", raising=False)
    monkeypatch.setattr(profile_loader, "LOCAL_PROFILE_DIR", None)

    assert "lab" in profile_loader.list_pipeline_profiles()


def test_profile_loader_discovers_profiles_from_config_dir_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "lab-config"
    local_dir = config_dir / "presets"
    local_dir.mkdir(parents=True)
    profile_path = local_dir / "lab.yml"
    profile_text = Path("src/ms_preprocessing/resources/builtin_profiles/default.yml").read_text(encoding="utf-8")
    profile_path.write_text(
        profile_text.replace("name: default", "name: lab"),
        encoding="utf-8",
    )
    monkeypatch.setenv("MSPTK_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(profile_loader, "LOCAL_PROFILE_DIR", None)

    assert "lab" in profile_loader.list_pipeline_profiles()


def test_built_in_profiles_resolve_source_checkout_local_reference_when_cwd_differs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout_dir = tmp_path / "checkout"
    config_dir = checkout_dir / "config"
    package_dir = checkout_dir / "src" / "ms_preprocessing" / "config"
    config_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)
    (config_dir / "local_reference.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "references:",
                '  method_file: "checkout-method.docx"',
                '  xic_results_file: "checkout-xic.xlsx"',
            ]
        ),
        encoding="utf-8",
    )
    fake_path_resolver = package_dir / "path_resolver.py"
    fake_path_resolver.write_text("", encoding="utf-8")

    from ms_preprocessing.config import path_resolver

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    monkeypatch.chdir(outside_dir)
    monkeypatch.delenv("MSPTK_CONFIG_DIR", raising=False)
    monkeypatch.delenv("MSPTK_LOCAL_REFERENCE_CONFIG", raising=False)
    monkeypatch.delenv("MSPTK_METHOD_FILE", raising=False)
    monkeypatch.delenv("MSPTK_XIC_RESULTS_FILE", raising=False)
    monkeypatch.setattr(path_resolver, "__file__", str(fake_path_resolver))
    monkeypatch.setattr(profile_loader, "LOCAL_PROFILE_DIR", None)

    profile = profile_loader.get_pipeline_profile("default")

    assert profile["step1"]["method_file"] == "checkout-method.docx"
    assert profile["step2"]["xic_results_file"] == "checkout-xic.xlsx"
