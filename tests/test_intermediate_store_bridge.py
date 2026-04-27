"""Bridge tests for toolkit FileHandler and ms-core IntermediateStore."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_toolkit_file_handler_uses_intermediate_store_for_parquet_paths(project_temp_dir) -> None:
    from ms_preprocessing.utils.file_handler import FileHandler

    df = pd.DataFrame(
        {
            "Mz/RT": ["100.1/1.0", "200.2/2.0"],
            "Sample1": [10.0, 20.0],
        }
    )
    handler = FileHandler()

    with project_temp_dir() as temp_dir:
        parquet_path = Path(temp_dir) / "step2.parquet"
        handler.save_data(
            df=df,
            file_path=parquet_path,
            red_font_rows={1},
            blue_font_cells=[(1, 1)],
        )

        meta_path = parquet_path.with_suffix(parquet_path.suffix + ".meta.json")
        assert meta_path.exists()

        loaded_df, loaded_meta = handler.load_data(parquet_path)
        pd.testing.assert_frame_equal(loaded_df, df)
        assert loaded_meta.get("red_font_rows") == [1]
        assert loaded_meta.get("blue_font_cells") == [[1, 1]]


def test_toolkit_file_handler_uses_default_parser_when_pyarrow_missing(
    project_temp_dir,
    monkeypatch,
) -> None:
    from ms_preprocessing.utils import file_handler as file_handler_module
    from ms_preprocessing.utils.file_handler import FileHandler

    original_find_spec = file_handler_module.importlib.util.find_spec
    original_read_csv = file_handler_module.pd.read_csv
    engines: list[object] = []

    def fake_find_spec(name: str, *args, **kwargs):
        if name == "pyarrow":
            return None
        return original_find_spec(name, *args, **kwargs)

    def fake_read_csv(path, *args, **kwargs):
        engines.append(kwargs.get("engine", "<missing>"))
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(file_handler_module.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(file_handler_module.pd, "read_csv", fake_read_csv)

    with project_temp_dir() as temp_dir:
        tsv_path = Path(temp_dir) / "input.tsv"
        expected = pd.DataFrame({"feature": ["f1", "f2"], "Sample1": [10, 20]})
        expected.to_csv(tsv_path, sep="\t", index=False)

        loaded = FileHandler._load_delimited(tsv_path, header_row=0, sep="\t")

    pd.testing.assert_frame_equal(loaded, expected)
    assert engines == ["<missing>"]


def test_toolkit_file_handler_falls_back_when_pyarrow_parser_fails(
    project_temp_dir,
    monkeypatch,
) -> None:
    from ms_preprocessing.utils import file_handler as file_handler_module
    from ms_preprocessing.utils.file_handler import FileHandler

    original_find_spec = file_handler_module.importlib.util.find_spec
    original_read_csv = file_handler_module.pd.read_csv
    engines: list[object] = []

    def fake_find_spec(name: str, *args, **kwargs):
        if name == "pyarrow":
            return object()
        return original_find_spec(name, *args, **kwargs)

    def fake_read_csv(path, *args, **kwargs):
        engine = kwargs.get("engine", "<missing>")
        engines.append(engine)
        if engine == "pyarrow":
            raise ValueError("simulated pyarrow parser failure")
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(file_handler_module.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(file_handler_module.pd, "read_csv", fake_read_csv)

    with project_temp_dir() as temp_dir:
        csv_path = Path(temp_dir) / "input.csv"
        expected = pd.DataFrame({"feature": ["f1", "f2"], "Sample1": [10, 20]})
        expected.to_csv(csv_path, index=False)

        loaded = FileHandler._load_delimited(csv_path, header_row=0, sep=",")

    pd.testing.assert_frame_equal(loaded, expected)
    assert engines == ["pyarrow", "<missing>"]
