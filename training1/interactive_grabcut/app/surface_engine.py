"""平面/柱面贴图的变换与融合核心。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class StickerPlacement:
    center_x: float
    center_y: float
    scale: float = 0.45
    rotation_degrees: float = 0.0
    opacity: float = 1.0
    surface: str = "plane"
    curvature: float = 0.55
    harmonize: float = 0.25


def ensure_rgba(image: np.ndarray) -> np.ndarray:
    if image.ndim != 3 or image.shape[2] not in (3, 4):
        raise ValueError("前景必须是 RGB 或 RGBA 图像")
    if image.shape[2] == 4:
        return np.ascontiguousarray(image, dtype=np.uint8).copy()
    rgb = np.ascontiguousarray(image, dtype=np.uint8)
    # 课程前景 img2.jpg 为白底；从边界颜色估计背景并生成柔和 alpha。
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0).astype(np.float32)
    background = np.median(border, axis=0)
    distance = np.linalg.norm(rgb.astype(np.float32) - background, axis=2)
    if float(np.median(distance)) < 48 or float(background.mean()) > 190:
        alpha = np.clip((distance - 8.0) * 6.0, 0, 255).astype(np.uint8)
        alpha = cv2.GaussianBlur(alpha, (0, 0), 1.0)
    else:
        alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    return np.dstack((rgb, alpha))


def clean_planar_reference(reference_rgb: np.ndarray) -> np.ndarray:
    """从课程规定素材总览中提取独立天空/草地背景。"""
    image = np.ascontiguousarray(reference_rgb, dtype=np.uint8).copy()
    height, width = image.shape[:2]
    if width / max(height, 1) > 2.5:
        # cover.jpg 左侧是课程规定背景，标题位于上方；右侧是前景预览。
        crop = image[int(height * 0.15) : int(height * 0.94), int(width * 0.01) : int(width * 0.31)]
        return cv2.resize(crop, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    return image


def warp_cylinder(rgba: np.ndarray, curvature: float) -> np.ndarray:
    """将二维贴图横向映射到圆柱面，并添加边缘光照衰减。"""
    source = ensure_rgba(rgba)
    height, width = source.shape[:2]
    if width < 2 or height < 2:
        return source
    strength = float(np.clip(curvature, 0.05, 0.95))
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    # 目标横坐标对应的源纹理坐标；中心区域略放大、边缘压缩。
    source_u = np.arcsin(np.clip(x * strength, -0.999, 0.999)) / np.arcsin(strength)
    map_x = ((source_u + 1.0) * 0.5 * (width - 1)).astype(np.float32)
    map_x = np.tile(map_x, (height, 1))
    map_y = np.tile(np.arange(height, dtype=np.float32)[:, None], (1, width))
    warped = cv2.remap(source, map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    light = (0.62 + 0.38 * np.cos(x * np.pi / 2.0)).reshape(1, width, 1)
    warped[:, :, :3] = np.clip(warped[:, :, :3].astype(np.float32) * light, 0, 255).astype(np.uint8)
    # 圆柱边缘稍透明，视觉上与背景衔接更自然。
    edge_alpha = np.clip((1.0 - np.abs(x) ** 5) * 255, 0, 255).astype(np.uint8)
    warped[:, :, 3] = np.minimum(warped[:, :, 3], edge_alpha[None, :])
    return warped


def transformed_foreground(rgba: np.ndarray, placement: StickerPlacement) -> np.ndarray:
    source = ensure_rgba(rgba)
    if placement.surface == "cylinder":
        source = warp_cylinder(source, placement.curvature)
    scale = float(np.clip(placement.scale, 0.05, 4.0))
    new_width = max(2, int(round(source.shape[1] * scale)))
    new_height = max(2, int(round(source.shape[0] * scale)))
    resized = cv2.resize(source, (new_width, new_height), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    center = (new_width / 2.0, new_height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, placement.rotation_degrees, 1.0)
    cosine, sine = abs(matrix[0, 0]), abs(matrix[0, 1])
    bound_w = max(2, int(new_height * sine + new_width * cosine))
    bound_h = max(2, int(new_height * cosine + new_width * sine))
    matrix[0, 2] += bound_w / 2.0 - center[0]
    matrix[1, 2] += bound_h / 2.0 - center[1]
    return cv2.warpAffine(resized, matrix, (bound_w, bound_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)


def blend_sticker(
    background_rgb: np.ndarray,
    foreground_rgba: np.ndarray,
    placement: StickerPlacement,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """在用户选择的中心位置融合贴图，返回结果和实际边界框。"""
    background = np.ascontiguousarray(background_rgb, dtype=np.uint8).copy()
    if background.ndim != 3 or background.shape[2] != 3:
        raise ValueError("背景必须是 RGB 三通道图像")
    transformed = transformed_foreground(foreground_rgba, placement)
    height, width = transformed.shape[:2]
    x0 = int(round(placement.center_x - width / 2))
    y0 = int(round(placement.center_y - height / 2))
    x1, y1 = x0 + width, y0 + height
    bx0, by0 = max(0, x0), max(0, y0)
    bx1, by1 = min(background.shape[1], x1), min(background.shape[0], y1)
    if bx0 >= bx1 or by0 >= by1:
        return background, (x0, y0, x1, y1)
    fx0, fy0 = bx0 - x0, by0 - y0
    fx1, fy1 = fx0 + (bx1 - bx0), fy0 + (by1 - by0)
    foreground = transformed[fy0:fy1, fx0:fx1].copy()
    target = background[by0:by1, bx0:bx1].astype(np.float32)

    amount = float(np.clip(placement.harmonize, 0.0, 1.0))
    if amount > 0:
        alpha_mask = foreground[:, :, 3] > 20
        if np.any(alpha_mask):
            fg_pixels = foreground[:, :, :3][alpha_mask].astype(np.float32)
            target_mean = target[alpha_mask].mean(axis=0)
            foreground_mean = fg_pixels.mean(axis=0)
            gain = np.clip(target_mean / np.maximum(foreground_mean, 1.0), 0.65, 1.45)
            adjusted = foreground[:, :, :3].astype(np.float32) * ((1.0 - amount) + amount * gain)
            foreground[:, :, :3] = np.clip(adjusted, 0, 255).astype(np.uint8)

    alpha = foreground[:, :, 3:4].astype(np.float32) / 255.0
    alpha *= float(np.clip(placement.opacity, 0.0, 1.0))
    blended = foreground[:, :, :3].astype(np.float32) * alpha + target * (1.0 - alpha)
    background[by0:by1, bx0:bx1] = np.clip(blended, 0, 255).astype(np.uint8)
    return background, (x0, y0, x1, y1)
