from __future__ import annotations

import math
import unittest

from app.geometry import bounds_of_points, clamp_point, normalized_rect, regular_polygon, square_endpoint


class GeometryTests(unittest.TestCase):
    def test_clamp_point(self) -> None:
        self.assertEqual(clamp_point((-3, 99), 20, 30), (0, 29))

    def test_normalized_rect_reverse_drag(self) -> None:
        self.assertEqual(normalized_rect((18, 25), (2, 5), 30, 40), (2, 5, 16, 20))

    def test_square_endpoint_preserves_sign(self) -> None:
        self.assertEqual(square_endpoint((10, 10), (3, 15)), (3, 17))

    def test_regular_polygon_vertex_count_and_radius(self) -> None:
        points = regular_polygon((50, 50), (60, 50), 6)
        self.assertEqual(len(points), 6)
        for x, y in points:
            self.assertAlmostEqual(math.hypot(x - 50, y - 50), 10, delta=1)

    def test_bounds_of_points(self) -> None:
        self.assertEqual(bounds_of_points([(5, 9), (25, 30), (10, 12)], 100, 100), (5, 9, 20, 21))


if __name__ == "__main__":
    unittest.main()
