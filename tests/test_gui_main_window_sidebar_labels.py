"""Regression tests for GUI sidebar workflow labels."""

from ms_preprocessing.gui.main_window import MainWindow


def test_main_window_sidebar_uses_expected_workflow_labels() -> None:
    app = MainWindow()
    try:
        assert [btn.cget("text") for btn in app.step_buttons] == [
            "1. 資料整理",
            "2. ISTD 標記",
            "3. 重複訊號刪除",
            "4. 篩選與缺失值填補",
        ]
    finally:
        app.destroy()
