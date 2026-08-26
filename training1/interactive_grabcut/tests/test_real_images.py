from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from app.grabcut_engine import GrabCutEngine
from app.image_io import read_bgr


ROOT = Path(__file__).resolve().parents[1]


class RealImageTests(unittest.TestCase):
    def test_all_required_images_decode_and_segment(self) -> None:
        for name in ("LENA.jpg", "baymax.jpeg", "cat.jpg"):
            with self.subTest(image=name):
                image = read_bgr(ROOT / "test_images" / name)
                height, width = image.shape[:2]
                self.assertGreaterEqual(width, 500)
                self.assertGreaterEqual(height, 500)

                engine = GrabCutEngine()
                engine.load(image)
                margin_x = max(2, width // 20)
                margin_y = max(2, height // 20)
                engine.initialize_with_rect(
                    (margin_x, margin_y),
                    (width - margin_x - 1, height - margin_y - 1),
                    iterations=1,
                )
                mask = engine.binary_mask()
                self.assertEqual(mask.shape, (height, width))
                self.assertTrue(set(np.unique(mask)).issubset({0, 255}))
                self.assertGreater(np.count_nonzero(mask), 0)


if __name__ == "__main__":
    unittest.main()
