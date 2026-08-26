"""等比例图像显示和鼠标标注画布。"""

from __future__ import annotations

from typing import Iterable

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .constants import DrawingTool, LabelMode
from .geometry import AnnotationCommand, is_meaningful_drag, regular_polygon, square_endpoint


class ImageViewer(QWidget):
    def __init__(self, empty_text: str = "请先打开图像", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: np.ndarray | None = None
        self._qimage: QImage | None = None
        self._empty_text = empty_text
        self.setMinimumSize(360, 320)
        self.setAutoFillBackground(False)

    def set_image(self, image_rgb: np.ndarray | None) -> None:
        if image_rgb is None:
            self._image = None
            self._qimage = None
        else:
            image = np.ascontiguousarray(image_rgb, dtype=np.uint8)
            if image.ndim != 3 or image.shape[2] != 3:
                raise ValueError("画布图像必须是 RGB 三通道")
            self._image = image.copy()
            height, width = image.shape[:2]
            self._qimage = QImage(
                self._image.data,
                width,
                height,
                int(self._image.strides[0]),
                QImage.Format.Format_RGB888,
            ).copy()
        self.update()

    def image_rect(self) -> QRectF:
        if self._image is None:
            return QRectF()
        height, width = self._image.shape[:2]
        available_w = max(1, self.width() - 20)
        available_h = max(1, self.height() - 20)
        scale = min(available_w / width, available_h / height)
        draw_w, draw_h = width * scale, height * scale
        return QRectF((self.width() - draw_w) / 2, (self.height() - draw_h) / 2, draw_w, draw_h)

    def image_to_widget(self, point: tuple[int, int]) -> QPointF:
        rect = self.image_rect()
        if self._image is None or rect.isEmpty():
            return QPointF()
        height, width = self._image.shape[:2]
        return QPointF(rect.left() + point[0] * rect.width() / width, rect.top() + point[1] * rect.height() / height)

    def widget_to_image(self, position: QPointF) -> tuple[int, int] | None:
        if self._image is None:
            return None
        rect = self.image_rect()
        if not rect.contains(position):
            return None
        height, width = self._image.shape[:2]
        x = int((position.x() - rect.left()) * width / rect.width())
        y = int((position.y() - rect.top()) * height / rect.height())
        return min(max(x, 0), width - 1), min(max(y, 0), height - 1)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111827"))
        if self._qimage is None:
            painter.setPen(QColor("#aab4c3"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_text)
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(self.image_rect(), self._qimage)


class ImageCanvas(ImageViewer):
    annotation_committed = Signal(object)
    polygon_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("打开图片后，先用矩形框住前景目标", parent)
        self.tool = DrawingTool.RECTANGLE
        self.label_mode = LabelMode.SURE_FOREGROUND
        self.brush_size = 11
        self._drawing = False
        self._start: tuple[int, int] | None = None
        self._current: tuple[int, int] | None = None
        self._brush_points: list[tuple[int, int]] = []
        self._polygon_points: list[tuple[int, int]] = []
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_tool(self, tool: DrawingTool) -> None:
        if tool != self.tool:
            self.cancel_partial()
        self.tool = tool

    def set_label_mode(self, mode: LabelMode) -> None:
        self.label_mode = mode
        self.update()

    def set_brush_size(self, size: int) -> None:
        self.brush_size = max(1, int(size))

    def cancel_partial(self) -> None:
        self._drawing = False
        self._start = None
        self._current = None
        self._brush_points.clear()
        self._polygon_points.clear()
        self.polygon_message.emit("")
        self.update()

    def has_partial_polygon(self) -> bool:
        return bool(self._polygon_points)

    def finish_polygon(self) -> bool:
        points = self._deduplicate(self._polygon_points)
        if len(points) < 3:
            self.polygon_message.emit("任意多边形至少需要 3 个顶点")
            return False
        self.annotation_committed.emit(
            AnnotationCommand(
                kind=DrawingTool.POLYGON.value,
                points=tuple(points),
                label_value=self.label_mode.mask_value,
                brush_size=self.brush_size,
            )
        )
        self._polygon_points.clear()
        self._current = None
        self.polygon_message.emit("")
        self.update()
        return True

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            if event.button() == Qt.MouseButton.RightButton and self.tool == DrawingTool.POLYGON:
                self.finish_polygon()
            return
        point = self.widget_to_image(event.position())
        if point is None:
            return
        self.setFocus()
        if self.tool == DrawingTool.POLYGON:
            self._polygon_points.append(point)
            self._current = point
            self.polygon_message.emit(f"多边形：已添加 {len(self._polygon_points)} 个顶点；双击、右键或 Enter 完成")
            self.update()
            return
        self._drawing = True
        self._start = point
        self._current = point
        self._brush_points = [point]
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        point = self.widget_to_image(event.position())
        if point is None:
            return
        self._current = point
        if self._drawing and self.tool == DrawingTool.BRUSH:
            if not self._brush_points or point != self._brush_points[-1]:
                self._brush_points.append(point)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self._drawing:
            return
        end = self.widget_to_image(event.position()) or self._current
        start = self._start
        self._drawing = False
        if start is None or end is None:
            return
        command = self._build_command(start, end)
        self._start = None
        self._current = None
        self._brush_points.clear()
        self.update()
        if command is not None:
            self.annotation_committed.emit(command)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.tool == DrawingTool.POLYGON and event.button() == Qt.MouseButton.LeftButton:
            self.finish_polygon()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self.tool == DrawingTool.POLYGON and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish_polygon()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self.has_partial_polygon():
            self.cancel_partial()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._image is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(*self.label_mode.rgb, 185)
        fill = QColor(*self.label_mode.rgb, 65)
        image_scale = self.image_rect().width() / self._image.shape[1]
        pen_width = max(2.0, self.brush_size * image_scale)

        if self.tool == DrawingTool.POLYGON and self._polygon_points:
            widget_points = [self.image_to_widget(point) for point in self._polygon_points]
            if self._current is not None:
                widget_points.append(self.image_to_widget(self._current))
            painter.setPen(QPen(color, 2.5))
            painter.setBrush(fill)
            painter.drawPolyline(QPolygonF(widget_points))
            for point in widget_points[:-1]:
                painter.drawEllipse(point, 3.5, 3.5)
            return

        if not self._drawing or self._start is None or self._current is None:
            return
        start, end = self._start, self._current
        painter.setPen(QPen(color, pen_width if self.tool in (DrawingTool.LINE, DrawingTool.BRUSH) else 2.5))
        painter.setBrush(fill)
        if self.tool == DrawingTool.BRUSH:
            painter.drawPolyline(QPolygonF([self.image_to_widget(p) for p in self._brush_points]))
        elif self.tool == DrawingTool.LINE:
            painter.drawLine(self.image_to_widget(start), self.image_to_widget(end))
        elif self.tool in (DrawingTool.RECTANGLE, DrawingTool.SQUARE):
            if self.tool == DrawingTool.SQUARE:
                end = square_endpoint(start, end)
            painter.drawPolygon(QPolygonF([self.image_to_widget(p) for p in self._rect_points(start, end)]))
        elif self.tool in (DrawingTool.CIRCLE, DrawingTool.ELLIPSE):
            center = self.image_to_widget(start)
            if self.tool == DrawingTool.CIRCLE:
                dx, dy = end[0] - start[0], end[1] - start[1]
                radius = ((dx * dx + dy * dy) ** 0.5) * image_scale
                painter.drawEllipse(center, radius, radius)
            else:
                rx = abs(end[0] - start[0]) * image_scale
                ry = abs(end[1] - start[1]) * image_scale
                painter.drawEllipse(QRectF(center.x() - rx, center.y() - ry, 2 * rx, 2 * ry))
        elif self.tool in (DrawingTool.PENTAGON, DrawingTool.HEXAGON):
            sides = 5 if self.tool == DrawingTool.PENTAGON else 6
            points = regular_polygon(start, end, sides)
            painter.drawPolygon(QPolygonF([self.image_to_widget(p) for p in points]))

    def _build_command(self, start: tuple[int, int], end: tuple[int, int]) -> AnnotationCommand | None:
        if self.tool != DrawingTool.BRUSH and not is_meaningful_drag(start, end):
            return None
        if self.tool == DrawingTool.BRUSH:
            points = tuple(self._deduplicate(self._brush_points or [start]))
        elif self.tool == DrawingTool.LINE:
            points = (start, end)
        elif self.tool in (DrawingTool.RECTANGLE, DrawingTool.SQUARE):
            adjusted = square_endpoint(start, end) if self.tool == DrawingTool.SQUARE else end
            points = tuple(self._rect_points(start, adjusted))
        elif self.tool in (DrawingTool.CIRCLE, DrawingTool.ELLIPSE):
            points = (start, end)
        elif self.tool in (DrawingTool.PENTAGON, DrawingTool.HEXAGON):
            sides = 5 if self.tool == DrawingTool.PENTAGON else 6
            points = regular_polygon(start, end, sides)
        else:
            return None
        return AnnotationCommand(self.tool.value, points, self.label_mode.mask_value, self.brush_size)

    @staticmethod
    def _rect_points(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        x1, y1 = start
        x2, y2 = end
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    @staticmethod
    def _deduplicate(points: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for point in points:
            if not result or point != result[-1]:
                result.append(point)
        while len(result) > 1 and result[-1] == result[-2]:
            result.pop()
        return result
