from __future__ import annotations

import os
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, "需要 PySide6")
class CurveTextEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        from app.fonts import install_bundled_ui_font

        cls.family = install_bundled_ui_font(cls.app)

    def test_glyphs_follow_curve_tangents_and_render_alpha(self) -> None:
        from app.curve_text_engine import CurveTextSettings, composite_rgba_over_rgb, render_curve_text_layer

        x = np.linspace(40, 600, 120)
        y = 250 - 120 * np.sin(np.linspace(0, np.pi, 120))
        curve = [(int(px), int(py)) for px, py in zip(x, y, strict=True)]
        settings = CurveTextSettings("这是测试文字", self.family, style="rainbow", font_size=44)
        layer, placements, smoothed = render_curve_text_layer((640, 360), curve, settings)
        self.assertEqual(layer.shape, (360, 640, 4))
        self.assertEqual(len(placements), 6)
        self.assertGreater(int(layer[:, :, 3].max()), 0)
        self.assertGreater(max(item.angle_degrees for item in placements) - min(item.angle_degrees for item in placements), 15)
        self.assertGreater(len(smoothed), 10)
        background = np.full((360, 640, 3), 40, dtype=np.uint8)
        result = composite_rgba_over_rgb(background, layer)
        self.assertFalse(np.array_equal(result, background))

    def test_text_length_is_enforced(self) -> None:
        from app.curve_text_engine import validate_text

        for valid in ("ABCD", "这是测试文字", "0123456789"):
            self.assertEqual(validate_text(valid), valid)
        for invalid in ("ABC", "ABCDEFGHIJK"):
            with self.assertRaises(ValueError):
                validate_text(invalid)

    def test_five_bundled_font_families_support_chinese(self) -> None:
        from PySide6.QtGui import QFont, QRawFont

        from app.fonts import creative_font_options

        options = creative_font_options()
        self.assertGreaterEqual(len(options), 5)
        for label, family in options:
            with self.subTest(font=label):
                raw = QRawFont.fromFont(QFont(family, 32))
                self.assertTrue(raw.isValid())
                self.assertTrue(raw.supportsCharacter(ord("测")))


if __name__ == "__main__":
    unittest.main()
