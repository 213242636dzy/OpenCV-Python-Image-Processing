"""测试 2/3 使用的交互画布。"""

from __future__ import annotations

from math import hypot

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen

from .canvas import ImageViewer


class CurveCanvas(ImageViewer):
    curve_committed = Signal(object)
    curve_preview = Signal(object)

    def __init__(self) -> None:
        super().__init__("先读取背景，再按住鼠标沿目标曲线拖动")
        self.curve_points: list[tuple[int, int]] = []
        self.show_guide = True
        self._drawing = False

    def set_curve(self, points: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> None:
        self.curve_points = list(points)
        self.update()

    def clear_curve(self) -> None:
        self.curve_points.clear()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self.widget_to_image(event.position())
        if point is None:
            return
        self._drawing = True
        self.curve_points = [point]
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._drawing:
            return
        point = self.widget_to_image(event.position())
        if point is None:
            return
        if not self.curve_points or hypot(point[0] - self.curve_points[-1][0], point[1] - self.curve_points[-1][1]) >= 2:
            self.curve_points.append(point)
            self.curve_preview.emit(tuple(self.curve_points))
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self._drawing:
            return
        self._drawing = False
        if len(self.curve_points) >= 2:
            self.curve_committed.emit(tuple(self.curve_points))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self.show_guide or len(self.curve_points) < 2 or self._image is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(34, 211, 238, 220), 2.5, Qt.PenStyle.DashLine))
        points = [self.image_to_widget(point) for point in self.curve_points]
        for start, end in zip(points, points[1:]):
            painter.drawLine(start, end)
        painter.setBrush(QColor(245, 158, 11))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(points[0], 5, 5)


class StickerCanvas(ImageViewer):
    placement_preview = Signal(object, float)
    placement_committed = Signal(object, float)

    def __init__(self) -> None:
        super().__init__("先读取背景与前景，再拖动贴图")
        self.box: tuple[int, int, int, int] | None = None
        self.center = (0.0, 0.0)
        self.scale = 1.0
        self._drag_mode: str | None = None
        self._start_point: tuple[int, int] | None = None
        self._start_center = (0.0, 0.0)
        self._start_scale = 1.0
        self._start_box: tuple[int, int, int, int] | None = None

    def set_placement(self, center: tuple[float, float], scale: float, box: tuple[int, int, int, int] | None) -> None:
        self.center = center
        self.scale = scale
        self.box = box
        self.update()

    def _inside_box(self, point: tuple[int, int]) -> bool:
        if self.box is None:
            return False
        x0, y0, x1, y1 = self.box
        return x0 <= point[0] <= x1 and y0 <= point[1] <= y1

    def _on_resize_handle(self, point: tuple[int, int]) -> bool:
        if self.box is None:
            return False
        _, _, x1, y1 = self.box
        threshold = max(10, int(14 / max(self.image_rect().width() / max(1, self._image.shape[1]), 0.01)))
        return abs(point[0] - x1) <= threshold and abs(point[1] - y1) <= threshold

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self.box is None:
            return
        point = self.widget_to_image(event.position())
        if point is None or not self._inside_box(point):
            return
        self._drag_mode = "resize" if self._on_resize_handle(point) else "move"
        self._start_point = point
        self._start_center = self.center
        self._start_scale = self.scale
        self._start_box = self.box

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_mode is None or self._start_point is None:
            return
        point = self.widget_to_image(event.position())
        if point is None:
            return
        dx, dy = point[0] - self._start_point[0], point[1] - self._start_point[1]
        if self._drag_mode == "move":
            center = (self._start_center[0] + dx, self._start_center[1] + dy)
            scale = self._start_scale
        else:
            assert self._start_box is not None
            width = max(10.0, self._start_box[2] - self._start_box[0])
            height = max(10.0, self._start_box[3] - self._start_box[1])
            factor = max((width + dx) / width, (height + dy) / height, 0.12)
            center = self._start_center
            scale = self._start_scale * factor
        self.center, self.scale = center, scale
        self.placement_preview.emit(center, scale)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._drag_mode is None:
            return
        self._drag_mode = None
        self._start_point = None
        self.placement_committed.emit(self.center, self.scale)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self.box is None or self._image is None:
            return
        x0, y0, x1, y1 = self.box
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(34, 211, 238, 230), 2.2, Qt.PenStyle.DashLine))
        top_left = self.image_to_widget((x0, y0))
        bottom_right = self.image_to_widget((x1, y1))
        painter.drawRect(int(top_left.x()), int(top_left.y()), int(bottom_right.x() - top_left.x()), int(bottom_right.y() - top_left.y()))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.setBrush(QColor("#2563eb"))
        painter.drawRect(int(bottom_right.x() - 6), int(bottom_right.y() - 6), 12, 12)
