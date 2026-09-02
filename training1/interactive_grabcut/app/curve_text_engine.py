"""沿任意曲线逐字排版的几何与渲染核心。"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, ceil, degrees

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QTransform


STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("实心字", "regular"),
    ("醒目粗体", "bold"),
    ("灵动斜体", "italic"),
    ("空心艺术效果", "outline"),
    ("霓虹艺术效果", "neon"),
    ("七彩艺术效果", "rainbow"),
)


@dataclass(frozen=True)
class CurveTextSettings:
    text: str
    font_family: str
    style: str = "regular"
    font_size: int = 48
    color_rgb: tuple[int, int, int] = (255, 245, 200)
    opacity: int = 235
    outline_width: int = 1
    start_fraction: float = 0.08
    path_offset: float = 0.0


@dataclass(frozen=True)
class GlyphPlacement:
    character: str
    x: float
    y: float
    angle_degrees: float


def validate_text(text: str) -> str:
    value = text.strip()
    visible_count = sum(not char.isspace() for char in value)
    if not 4 <= visible_count <= 10:
        raise ValueError("请输入 4–10 个可见文字")
    return value


def smooth_curve(points: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> np.ndarray:
    """去重并用一维高斯平滑手绘路径，保留首尾位置。"""
    if len(points) < 2:
        raise ValueError("请在图像上拖出一条曲线")
    array = np.asarray(points, dtype=np.float32)
    keep = np.ones(len(array), dtype=bool)
    keep[1:] = np.any(np.diff(array, axis=0) != 0, axis=1)
    array = array[keep]
    if len(array) < 2:
        raise ValueError("曲线长度不足")
    if len(array) >= 5:
        kernel = min(21, len(array) if len(array) % 2 else len(array) - 1)
        if kernel >= 5:
            x = cv2.GaussianBlur(array[:, 0].reshape(-1, 1), (1, kernel), 0).ravel()
            y = cv2.GaussianBlur(array[:, 1].reshape(-1, 1), (1, kernel), 0).ravel()
            smoothed = np.column_stack((x, y)).astype(np.float32)
            smoothed[0], smoothed[-1] = array[0], array[-1]
            return smoothed
    return array


def place_glyphs(
    text: str,
    curve: np.ndarray,
    start_fraction: float = 0.08,
    path_offset: float = 0.0,
) -> list[GlyphPlacement]:
    """按弧长均匀放置字符，并让字符基线平行于局部切线。"""
    value = validate_text(text)
    if curve.ndim != 2 or curve.shape[0] < 2 or curve.shape[1] != 2:
        raise ValueError("曲线数据无效")
    segments = np.diff(curve.astype(np.float64), axis=0)
    lengths = np.linalg.norm(segments, axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    total = float(cumulative[-1])
    if total < 20.0:
        raise ValueError("曲线太短，请拖出更长的曲线")

    start = np.clip(float(start_fraction), 0.0, 0.72) * total
    end = min(total * 0.96, start + total * 0.82)
    if end <= start:
        end = total
    targets = np.linspace(start, end, len(value))
    placements: list[GlyphPlacement] = []
    for char, target in zip(value, targets, strict=True):
        index = min(int(np.searchsorted(cumulative, target, side="right") - 1), len(segments) - 1)
        index = max(index, 0)
        length = max(lengths[index], 1e-6)
        ratio = (target - cumulative[index]) / length
        point = curve[index] + segments[index] * ratio
        tangent = segments[index] / length
        normal = np.array([-tangent[1], tangent[0]])
        point = point + normal * float(path_offset)
        angle = degrees(atan2(float(tangent[1]), float(tangent[0])))
        placements.append(GlyphPlacement(char, float(point[0]), float(point[1]), angle))
    return placements


def _qimage_from_rgba(array: np.ndarray) -> QImage:
    image = np.ascontiguousarray(array, dtype=np.uint8)
    height, width = image.shape[:2]
    return QImage(image.data, width, height, int(image.strides[0]), QImage.Format.Format_RGBA8888).copy()


def _rgba_from_qimage(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    view = converted.bits()
    return np.frombuffer(view, dtype=np.uint8, count=converted.sizeInBytes()).reshape(
        converted.height(), converted.width(), 4
    ).copy()


def _render_glyph(character: str, settings: CurveTextSettings, index: int) -> QImage:
    font = QFont(settings.font_family)
    font.setPixelSize(max(12, int(settings.font_size)))
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    if settings.style == "bold":
        font.setWeight(QFont.Weight.Black)
    elif settings.style == "italic":
        font.setItalic(True)

    metrics = QFontMetricsF(font)
    canvas_size = max(96, int(ceil(max(metrics.height(), metrics.horizontalAdvance(character)) * 3.2)))
    image = QImage(canvas_size, canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    path = QPainterPath()
    path.addText(QPointF(0, 0), font, character)
    bounds = path.boundingRect()
    transform = QTransform()
    transform.translate((canvas_size - bounds.width()) / 2 - bounds.left(), (canvas_size - bounds.height()) / 2 - bounds.top())
    path = transform.map(path)

    base_color = QColor(*settings.color_rgb, settings.opacity)
    if settings.style == "rainbow":
        base_color = QColor.fromHsv((index * 47) % 360, 205, 255, settings.opacity)

    if settings.style == "neon":
        for width, alpha in ((10, 40), (6, 75), (3, 145)):
            glow = QColor(base_color)
            glow.setAlpha(alpha)
            painter.setPen(QPen(glow, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_color)
        painter.drawPath(path)
    elif settings.style == "outline":
        painter.setPen(QPen(base_color, max(2, settings.outline_width + 1), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        inner = QColor(255, 255, 255, max(80, settings.opacity // 3))
        painter.setBrush(inner)
        painter.drawPath(path)
    else:
        if settings.outline_width > 0:
            outline = QColor(15, 23, 42, min(220, settings.opacity))
            painter.setPen(QPen(outline, settings.outline_width * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(base_color)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(base_color)
        painter.drawPath(path)
    painter.end()
    return image


def render_curve_text_layer(
    image_size: tuple[int, int],
    curve_points: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    settings: CurveTextSettings,
) -> tuple[np.ndarray, list[GlyphPlacement], np.ndarray]:
    """返回 RGBA 文字层、逐字位置和已平滑曲线。"""
    width, height = image_size
    if width <= 0 or height <= 0:
        raise ValueError("背景图像尺寸无效")
    curve = smooth_curve(curve_points)
    placements = place_glyphs(settings.text, curve, settings.start_fraction, settings.path_offset)
    layer = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    layer.fill(Qt.GlobalColor.transparent)
    painter = QPainter(layer)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for index, placement in enumerate(placements):
        glyph = _render_glyph(placement.character, settings, index)
        rotated = glyph.transformed(QTransform().rotate(placement.angle_degrees), Qt.TransformationMode.SmoothTransformation)
        target = QPointF(placement.x - rotated.width() / 2, placement.y - rotated.height() / 2)
        painter.drawImage(target, rotated)
    painter.end()
    return _rgba_from_qimage(layer), placements, curve


def composite_rgba_over_rgb(background_rgb: np.ndarray, layer_rgba: np.ndarray) -> np.ndarray:
    if background_rgb.shape[:2] != layer_rgba.shape[:2]:
        raise ValueError("背景与文字图层尺寸不一致")
    alpha = layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
    result = layer_rgba[:, :, :3].astype(np.float32) * alpha + background_rgb.astype(np.float32) * (1.0 - alpha)
    return np.clip(result, 0, 255).astype(np.uint8)


def clean_rainbow_reference(reference_rgb: np.ndarray) -> np.ndarray:
    """从课程示例中去除旧白色文字，得到可重新排版的规定背景。"""
    image = reference_rgb.copy()
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 1] < 45) & (hsv[:, :, 2] > 205)).astype(np.uint8) * 255
    height, width = mask.shape
    region = np.zeros_like(mask)
    region[int(height * 0.18) : int(height * 0.70), int(width * 0.04) : int(width * 0.96)] = 255
    mask = cv2.bitwise_and(mask, region)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    filtered = np.zeros_like(mask)
    for label in range(1, count):
        area = stats[label, cv2.CC_STAT_AREA]
        component_h = stats[label, cv2.CC_STAT_HEIGHT]
        component_w = stats[label, cv2.CC_STAT_WIDTH]
        if 3 <= area <= 1400 and component_h <= max(70, int(height * 0.13)) and component_w <= max(70, int(width * 0.10)):
            filtered[labels == label] = 255
    filtered = cv2.dilate(filtered, np.ones((3, 3), np.uint8), iterations=1)
    return cv2.inpaint(image, filtered, 4, cv2.INPAINT_TELEA)
