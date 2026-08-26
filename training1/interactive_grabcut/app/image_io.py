"""兼容中文路径的 OpenCV 图像读写。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class ImageIOError(RuntimeError):
    pass


def read_bgr(path: str | Path) -> np.ndarray:
    file_path = Path(path)
    try:
        raw = np.fromfile(str(file_path), dtype=np.uint8)
    except OSError as exc:
        raise ImageIOError(f"无法读取文件：{file_path}") from exc
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ImageIOError(f"不是有效的图像文件：{file_path}")
    return image


def write_png(path: str | Path, image: np.ndarray) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ImageIOError(f"图像编码失败：{file_path.name}")
    try:
        encoded.tofile(str(file_path))
    except OSError as exc:
        raise ImageIOError(f"无法保存文件：{file_path}") from exc
    return file_path
