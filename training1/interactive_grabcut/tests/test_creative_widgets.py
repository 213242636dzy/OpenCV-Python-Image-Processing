from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

try:
    from PySide6.QtWidgets import QApplication

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, "需要 PySide6")
class CreativeWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        from app.fonts import install_bundled_ui_font

        install_bundled_ui_font(cls.app)

    def test_suite_links_test2_layer_into_test3(self) -> None:
        from app.suite_window import TrainingSuiteWindow

        window = TrainingSuiteWindow()
        window.resize(1280, 760)
        window.show()
        self.app.processEvents()
        curve = window.curve_text
        self.assertGreaterEqual(curve.font_combo.count(), 5)
        curve.load_prescribed_background()
        height, width = curve.background_rgb.shape[:2]
        points = []
        for index in range(80):
            x = int(width * (0.08 + 0.84 * index / 79))
            normalized = (index / 79 - 0.5) * 2
            y = int(height * (0.66 - 0.34 * (1 - normalized * normalized)))
            points.append((x, y))
        curve.canvas.set_curve(points)
        self.assertTrue(curve.render_text())
        self.assertIsNotNone(curve.layer_rgba)
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.curve_text_widget.QFileDialog.getExistingDirectory", return_value=directory), patch(
                "app.curve_text_widget.QMessageBox.information"
            ):
                curve.save_all()
            output = Path(directory) / "test2_curve_text"
            for filename in ("test2_result.png", "test2_text_layer.png", "test2_background.png", "test2_ui.png", "test2_experiment.json"):
                self.assertTrue((output / filename).is_file(), filename)
            curve.clock.resume()
        curve.send_to_test3()
        self.app.processEvents()
        self.assertIs(window.tabs.currentWidget(), window.surface_sticker)
        self.assertIsNotNone(window.surface_sticker.foreground_rgba)

        sticker = window.surface_sticker
        sticker.load_prescribed_materials()
        sticker.surface_combo.setCurrentIndex(1)
        sticker.commit_current_operation()
        self.assertIsNotNone(sticker.result_rgb)
        self.assertGreaterEqual(sticker.interaction_count, 1)
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.surface_sticker_widget.QFileDialog.getExistingDirectory", return_value=directory), patch(
                "app.surface_sticker_widget.QMessageBox.information"
            ):
                sticker.save_all()
            output = Path(directory) / "test3_surface_sticker"
            for filename in ("test3_result.png", "test3_background.png", "test3_foreground.png", "test3_ui.png", "test3_experiment.json"):
                self.assertTrue((output / filename).is_file(), filename)
        window.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
