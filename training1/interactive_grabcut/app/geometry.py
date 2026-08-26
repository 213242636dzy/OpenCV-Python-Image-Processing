"""与 GUI 无关的几何计算，便于单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from typing import Iterable


Point = tuple[int, int]


@dataclass(frozen=True)
class AnnotationCommand:
    """一次完整用户标记；一次命令最多触发一次 GrabCut。"""

    kind: str
    points: tuple[Point, ...]
    label_value: int
    brush_size: int = 9


def clamp_point(point: Point, width: int, height: int) -> Point:
    return (
        min(max(int(point[0]), 0), max(width - 1, 0)),
        min(max(int(point[1]), 0), max(height - 1, 0)),
    )


def normalized_rect(start: Point, end: Point, width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1 = clamp_point(start, width, height)
    x2, y2 = clamp_point(end, width, height)
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    return left, top, max(1, right - left), max(1, bottom - top)


def square_endpoint(start: Point, end: Point) -> Point:
    dx, dy = end[0] - start[0], end[1] - start[1]
    side = max(abs(dx), abs(dy))
    sx = 1 if dx >= 0 else -1
    sy = 1 if dy >= 0 else -1
    return start[0] + sx * side, start[1] + sy * side


def regular_polygon(center: Point, edge_point: Point, sides: int) -> tuple[Point, ...]:
    if sides < 3:
        raise ValueError("正多边形至少需要 3 条边")
    cx, cy = center
    dx, dy = edge_point[0] - cx, edge_point[1] - cy
    radius = max((dx * dx + dy * dy) ** 0.5, 1.0)
    start_angle = -pi / 2
    return tuple(
        (
            int(round(cx + radius * cos(start_angle + 2 * pi * i / sides))),
            int(round(cy + radius * sin(start_angle + 2 * pi * i / sides))),
        )
        for i in range(sides)
    )


def bounds_of_points(points: Iterable[Point], width: int, height: int) -> tuple[int, int, int, int]:
    values = [clamp_point(point, width, height) for point in points]
    if not values:
        raise ValueError("没有可计算边界的点")
    xs = [p[0] for p in values]
    ys = [p[1] for p in values]
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    return left, top, max(1, right - left), max(1, bottom - top)


def is_meaningful_drag(start: Point, end: Point, minimum: int = 3) -> bool:
    return abs(end[0] - start[0]) >= minimum or abs(end[1] - start[1]) >= minimum
