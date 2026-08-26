"""GrabCut 状态、标记栅格化和结果生成。"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import cv2
import numpy as np

from .constants import LABEL_BY_VALUE, DrawingTool
from .geometry import AnnotationCommand, bounds_of_points, normalized_rect


@dataclass
class EngineSnapshot:
    mask: np.ndarray
    user_marks: np.ndarray
    bgd_model: np.ndarray
    fgd_model: np.ndarray
    initialized: bool
    initial_rect: tuple[int, int, int, int] | None


class GrabCutEngine:
    def __init__(self) -> None:
        self.original_bgr: np.ndarray | None = None
        self.mask: np.ndarray | None = None
        self.user_marks: np.ndarray | None = None
        self.bgd_model = np.zeros((1, 65), np.float64)
        self.fgd_model = np.zeros((1, 65), np.float64)
        self.initialized = False
        self.initial_rect: tuple[int, int, int, int] | None = None
        self.last_runtime_ms = 0.0

    @property
    def has_image(self) -> bool:
        return self.original_bgr is not None

    @property
    def width(self) -> int:
        return 0 if self.original_bgr is None else int(self.original_bgr.shape[1])

    @property
    def height(self) -> int:
        return 0 if self.original_bgr is None else int(self.original_bgr.shape[0])

    def load(self, image_bgr: np.ndarray) -> None:
        if image_bgr is None or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
            raise ValueError("输入必须是三通道 BGR 图像")
        self.original_bgr = np.ascontiguousarray(image_bgr.copy())
        self.reset()

    def reset(self) -> None:
        if self.original_bgr is None:
            self.mask = None
            self.user_marks = None
            return
        self.mask = np.full(self.original_bgr.shape[:2], cv2.GC_BGD, dtype=np.uint8)
        # 255 表示“没有用户标记”。使用 uint8 可确保所有 OpenCV 绘图函数兼容。
        self.user_marks = np.full(self.original_bgr.shape[:2], 255, dtype=np.uint8)
        self.bgd_model = np.zeros((1, 65), np.float64)
        self.fgd_model = np.zeros((1, 65), np.float64)
        self.initialized = False
        self.initial_rect = None
        self.last_runtime_ms = 0.0

    def snapshot(self) -> EngineSnapshot:
        self._require_image()
        return EngineSnapshot(
            mask=self.mask.copy(),
            user_marks=self.user_marks.copy(),
            bgd_model=self.bgd_model.copy(),
            fgd_model=self.fgd_model.copy(),
            initialized=self.initialized,
            initial_rect=self.initial_rect,
        )

    def restore(self, snapshot: EngineSnapshot) -> None:
        self.mask = snapshot.mask.copy()
        self.user_marks = snapshot.user_marks.copy()
        self.bgd_model = snapshot.bgd_model.copy()
        self.fgd_model = snapshot.fgd_model.copy()
        self.initialized = snapshot.initialized
        self.initial_rect = snapshot.initial_rect

    def initialize_with_rect(self, start: tuple[int, int], end: tuple[int, int], iterations: int = 5) -> float:
        self._require_image()
        rect = normalized_rect(start, end, self.width, self.height)
        x, y, w, h = rect
        if w < 5 or h < 5:
            raise ValueError("初始矩形过小，请完整框住前景目标")
        # GrabCut 要求矩形严格位于图像内部。
        x = min(max(x, 0), self.width - 2)
        y = min(max(y, 0), self.height - 2)
        w = min(max(w, 1), self.width - x - 1)
        h = min(max(h, 1), self.height - y - 1)
        rect = (x, y, w, h)
        self.reset()
        started = perf_counter()
        cv2.grabCut(
            self.original_bgr,
            self.mask,
            rect,
            self.bgd_model,
            self.fgd_model,
            max(1, int(iterations)),
            cv2.GC_INIT_WITH_RECT,
        )
        self.last_runtime_ms = (perf_counter() - started) * 1000.0
        self.initialized = True
        self.initial_rect = rect
        return self.last_runtime_ms

    def apply_annotation(self, command: AnnotationCommand) -> None:
        self._require_image()
        if not self.initialized:
            raise RuntimeError("请先使用矩形工具框住前景目标")
        if command.label_value not in LABEL_BY_VALUE:
            raise ValueError("未知的 GrabCut 标记值")
        value = int(command.label_value)
        self._draw(self.mask, command, value)
        self._draw(self.user_marks, command, value)

    def refine(self, iterations: int = 1) -> float:
        self._require_image()
        if not self.initialized:
            raise RuntimeError("尚未完成矩形初始化")
        started = perf_counter()
        cv2.grabCut(
            self.original_bgr,
            self.mask,
            None,
            self.bgd_model,
            self.fgd_model,
            max(1, int(iterations)),
            cv2.GC_INIT_WITH_MASK,
        )
        self.last_runtime_ms = (perf_counter() - started) * 1000.0
        return self.last_runtime_ms

    def binary_mask(self) -> np.ndarray:
        self._require_image()
        if not self.initialized:
            return np.zeros((self.height, self.width), dtype=np.uint8)
        foreground = (self.mask == cv2.GC_FGD) | (self.mask == cv2.GC_PR_FGD)
        return np.where(foreground, 255, 0).astype(np.uint8)

    def foreground_bgr(self) -> np.ndarray:
        self._require_image()
        result = np.zeros_like(self.original_bgr)
        keep = self.binary_mask() == 255
        result[keep] = self.original_bgr[keep]
        return result

    def mask_rgb(self) -> np.ndarray:
        gray = self.binary_mask()
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    def foreground_rgb(self) -> np.ndarray:
        return cv2.cvtColor(self.foreground_bgr(), cv2.COLOR_BGR2RGB)

    def contour_overlay_bgr(self) -> np.ndarray:
        self._require_image()
        overlay = self.original_bgr.copy()
        if not self.initialized:
            return overlay
        contours, _ = cv2.findContours(self.binary_mask(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (60, 230, 90), 2, cv2.LINE_AA)
        return overlay

    def contour_overlay_rgb(self) -> np.ndarray:
        return cv2.cvtColor(self.contour_overlay_bgr(), cv2.COLOR_BGR2RGB)

    def annotation_overlay_rgb(self) -> np.ndarray:
        """原图 + 分割轮廓 + 用户显式标记；不着色 GrabCut 自动概率区域。"""
        bgr = self.contour_overlay_bgr()
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if self.user_marks is not None:
            for value, mode in LABEL_BY_VALUE.items():
                selected = self.user_marks == value
                if np.any(selected):
                    color = np.asarray(mode.rgb, dtype=np.float32)
                    rgb[selected] = (0.35 * rgb[selected] + 0.65 * color).astype(np.uint8)
        if self.initial_rect is not None:
            x, y, w, h = self.initial_rect
            cv2.rectangle(rgb, (x, y), (x + w, y + h), (250, 210, 60), 2, cv2.LINE_AA)
        return rgb

    def _require_image(self) -> None:
        if self.original_bgr is None or self.mask is None or self.user_marks is None:
            raise RuntimeError("尚未读取图像")

    @staticmethod
    def _draw(target: np.ndarray, command: AnnotationCommand, value: int) -> None:
        points = np.asarray(command.points, dtype=np.int32)
        if len(points) == 0:
            raise ValueError("标记没有有效坐标")
        thickness = max(1, int(command.brush_size))
        kind = command.kind
        if kind in (DrawingTool.LINE.value, DrawingTool.BRUSH.value):
            if len(points) == 1:
                cv2.circle(target, tuple(points[0]), max(1, thickness // 2), value, -1)
            else:
                cv2.polylines(target, [points], False, value, thickness, cv2.LINE_8)
                cv2.circle(target, tuple(points[0]), max(1, thickness // 2), value, -1)
                cv2.circle(target, tuple(points[-1]), max(1, thickness // 2), value, -1)
        elif kind in (
            DrawingTool.RECTANGLE.value,
            DrawingTool.SQUARE.value,
            DrawingTool.PENTAGON.value,
            DrawingTool.HEXAGON.value,
            DrawingTool.POLYGON.value,
        ):
            if len(points) < 3:
                raise ValueError("区域工具至少需要 3 个点")
            cv2.fillPoly(target, [points], value, cv2.LINE_8)
        elif kind in (DrawingTool.CIRCLE.value, DrawingTool.ELLIPSE.value):
            if len(points) != 2:
                raise ValueError("圆或椭圆需要中心和半径点")
            (cx, cy), (px, py) = points
            if kind == DrawingTool.CIRCLE.value:
                radius = max(1, int(round(((px - cx) ** 2 + (py - cy) ** 2) ** 0.5)))
                cv2.circle(target, (cx, cy), radius, value, -1, cv2.LINE_8)
            else:
                axes = (max(1, abs(px - cx)), max(1, abs(py - cy)))
                cv2.ellipse(target, (cx, cy), axes, 0, 0, 360, value, -1, cv2.LINE_8)
        else:
            raise ValueError(f"不支持的绘图工具：{kind}")

    def initial_rect_from_command(self, command: AnnotationCommand) -> tuple[tuple[int, int], tuple[int, int]]:
        x, y, w, h = bounds_of_points(command.points, self.width, self.height)
        return (x, y), (x + w, y + h)
