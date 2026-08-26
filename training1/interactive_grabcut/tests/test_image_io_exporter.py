from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from app.exporter import export_images, safe_stem
from app.grabcut_engine import GrabCutEngine
from app.image_io import read_bgr, write_png


class ImageIOExporterTests(unittest.TestCase):
    def test_unicode_path_round_trip(self) -> None:
        image = np.zeros((24, 32, 3), dtype=np.uint8)
        image[4:20, 7:25] = (20, 80, 240)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "中文 路径" / "测试图.png"
            write_png(path, image)
            decoded = read_bgr(path)
            self.assertTrue(np.array_equal(decoded, image))

    def test_export_bundle_content(self) -> None:
        image = np.zeros((120, 160, 3), dtype=np.uint8)
        image[:] = (30, 130, 30)
        image[25:100, 45:120] = (30, 30, 220)
        engine = GrabCutEngine()
        engine.load(image)
        engine.initialize_with_rect((38, 18), (128, 108), iterations=2)

        with tempfile.TemporaryDirectory() as directory:
            bundle = export_images(directory, '含非法字符:a?.jpg', engine, 2345, 3)
            self.assertEqual(bundle.directory.name, "含非法字符_a_")
            self.assertTrue(bundle.binary_mask.is_file())
            self.assertTrue(bundle.foreground_rgb.is_file())
            self.assertTrue(bundle.contour_overlay.is_file())
            self.assertFalse(bundle.ui_screenshot.exists())  # 截图由主窗口保存

            mask = cv2.imdecode(np.fromfile(bundle.binary_mask, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            foreground = cv2.imdecode(np.fromfile(bundle.foreground_rgb, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            self.assertEqual(mask.shape, image.shape[:2])
            self.assertTrue(set(np.unique(mask)).issubset({0, 255}))
            self.assertEqual(foreground.shape, image.shape)

            metadata = json.loads(bundle.metadata.read_text(encoding="utf-8"))
            self.assertEqual(metadata["interaction_count"], 3)
            self.assertEqual(metadata["elapsed_seconds"], 2.345)
            self.assertFalse(metadata["gpu_used"])
            self.assertFalse(metadata["opencl_enabled"])

    def test_safe_stem_is_cross_platform(self) -> None:
        # 连续非法字符会被折叠成一个下划线，避免生成冗长文件名。
        self.assertEqual(safe_stem('folder\\a:b*?"<>|.jpg'), "a_b_")
        self.assertEqual(safe_stem("folder/sub/image.tar.png"), "image.tar")


if __name__ == "__main__":
    unittest.main()
