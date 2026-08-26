from __future__ import annotations

import importlib.util
import unittest


CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None


@unittest.skipUnless(CV2_AVAILABLE, "需要安装 opencv-python-headless")
class EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        import numpy as np

        from app.grabcut_engine import GrabCutEngine

        # 合成一个前景/背景颜色明显的 CPU 测试样例。
        self.image = np.zeros((120, 160, 3), dtype=np.uint8)
        self.image[:] = (30, 130, 30)
        self.image[25:100, 45:120] = (30, 30, 220)
        self.engine = GrabCutEngine()
        self.engine.load(self.image)

    def test_initialize_and_outputs(self) -> None:
        import numpy as np

        self.engine.initialize_with_rect((38, 18), (128, 108), iterations=2)
        self.assertTrue(self.engine.initialized)
        mask = self.engine.binary_mask()
        self.assertEqual(mask.shape, self.image.shape[:2])
        self.assertTrue(set(np.unique(mask)).issubset({0, 255}))
        self.assertEqual(self.engine.foreground_bgr().shape, self.image.shape)
        self.assertEqual(self.engine.contour_overlay_rgb().shape, self.image.shape)

    def test_snapshot_restore(self) -> None:
        self.engine.initialize_with_rect((38, 18), (128, 108), iterations=1)
        snapshot = self.engine.snapshot()
        self.engine.reset()
        self.assertFalse(self.engine.initialized)
        self.engine.restore(snapshot)
        self.assertTrue(self.engine.initialized)

    def test_all_nine_tools_rasterize(self) -> None:
        import cv2
        import numpy as np

        from app.constants import DrawingTool
        from app.geometry import AnnotationCommand

        self.engine.initialize_with_rect((10, 10), (150, 110), iterations=1)
        commands = (
            AnnotationCommand(DrawingTool.LINE.value, ((20, 20), (40, 30)), cv2.GC_FGD, 5),
            AnnotationCommand(DrawingTool.RECTANGLE.value, ((20, 20), (40, 20), (40, 40), (20, 40)), cv2.GC_FGD, 5),
            AnnotationCommand(DrawingTool.SQUARE.value, ((50, 20), (70, 20), (70, 40), (50, 40)), cv2.GC_FGD, 5),
            AnnotationCommand(DrawingTool.CIRCLE.value, ((80, 30), (90, 30)), cv2.GC_FGD, 5),
            AnnotationCommand(DrawingTool.ELLIPSE.value, ((105, 30), (118, 38)), cv2.GC_FGD, 5),
            AnnotationCommand(DrawingTool.PENTAGON.value, ((25, 65), (35, 55), (45, 65), (42, 78), (28, 78)), cv2.GC_FGD, 5),
            AnnotationCommand(DrawingTool.HEXAGON.value, ((55, 60), (65, 55), (75, 60), (75, 72), (65, 78), (55, 72)), cv2.GC_FGD, 5),
            AnnotationCommand(DrawingTool.POLYGON.value, ((90, 55), (120, 60), (110, 82), (88, 75)), cv2.GC_FGD, 5),
            AnnotationCommand(DrawingTool.BRUSH.value, ((125, 90), (135, 95), (145, 90)), cv2.GC_FGD, 7),
        )
        for command in commands:
            before = np.count_nonzero(self.engine.user_marks != 255)
            self.engine.apply_annotation(command)
            after = np.count_nonzero(self.engine.user_marks != 255)
            self.assertGreater(after, before, command.kind)


if __name__ == "__main__":
    unittest.main()
