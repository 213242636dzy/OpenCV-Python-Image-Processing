from __future__ import annotations

import unittest

import numpy as np

from app.surface_engine import StickerPlacement, blend_sticker, ensure_rgba, warp_cylinder


class SurfaceEngineTests(unittest.TestCase):
    def test_white_background_foreground_gets_alpha(self) -> None:
        image = np.full((80, 100, 3), 255, dtype=np.uint8)
        image[20:65, 25:75] = (30, 80, 220)
        rgba = ensure_rgba(image)
        self.assertEqual(rgba.shape, (80, 100, 4))
        self.assertLess(int(rgba[0, 0, 3]), 20)
        self.assertGreater(int(rgba[35, 45, 3]), 200)

    def test_plane_and_cylinder_blending_use_user_placement(self) -> None:
        background = np.full((240, 360, 3), (90, 130, 170), dtype=np.uint8)
        foreground = np.zeros((80, 120, 4), dtype=np.uint8)
        foreground[5:-5, 5:-5, :3] = (240, 60, 70)
        foreground[5:-5, 5:-5, 3] = 255
        plane = StickerPlacement(90, 100, scale=0.8, surface="plane")
        cylinder = StickerPlacement(270, 130, scale=0.8, surface="cylinder", curvature=0.7)
        plane_result, plane_box = blend_sticker(background, foreground, plane)
        cylinder_result, cylinder_box = blend_sticker(background, foreground, cylinder)
        self.assertFalse(np.array_equal(plane_result, background))
        self.assertFalse(np.array_equal(cylinder_result, background))
        self.assertLess(plane_box[0], 90)
        self.assertGreater(cylinder_box[2], 270)
        self.assertFalse(np.array_equal(plane_result, cylinder_result))
        warped = warp_cylinder(foreground, 0.7)
        self.assertEqual(warped.shape, foreground.shape)
        self.assertLess(int(warped[:, 0, 3].max()), 20)


if __name__ == "__main__":
    unittest.main()
