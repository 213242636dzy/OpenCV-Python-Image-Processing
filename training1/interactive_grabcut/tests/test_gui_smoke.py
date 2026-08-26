from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

try:
    from PySide6.QtWidgets import QApplication

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, "需要可导入 QtWidgets 的 PySide6 运行环境")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_window_load_segment_reset_and_close(self) -> None:
        from app.constants import DrawingTool, LabelMode
        from app.geometry import AnnotationCommand
        from app.main_window import MainWindow

        root = Path(__file__).resolve().parents[1]
        window = MainWindow()
        window.show()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        self.assertEqual(len(window.tool_buttons), 9)
        self.assertEqual(len(window.label_buttons), 4)

        window._load_path(root / "test_images" / "LENA.jpg")
        command = AnnotationCommand(
            kind=DrawingTool.RECTANGLE.value,
            points=((35, 35), (476, 35), (476, 476), (35, 476)),
            label_value=LabelMode.SURE_FOREGROUND.mask_value,
            brush_size=11,
        )
        window._on_annotation(command)
        self.app.processEvents()
        self.assertTrue(window.engine.initialized)
        self.assertEqual(window.interaction_count, 1)
        self.assertTrue(window.save_action.isEnabled())
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "window.png"
            self.assertTrue(window.grab().save(str(screenshot), "PNG"))
            self.assertGreater(screenshot.stat().st_size, 0)

        window.undo()
        self.assertFalse(window.engine.initialized)
        self.assertEqual(window.interaction_count, 1)
        window.reset_experiment()
        self.assertEqual(window.interaction_count, 0)
        window.close()
        self.app.processEvents()
        self.assertFalse(window.isVisible())


if __name__ == "__main__":
    unittest.main()
