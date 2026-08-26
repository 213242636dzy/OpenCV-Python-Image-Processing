"""实验结果导出。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2

from .grabcut_engine import GrabCutEngine
from .image_io import write_png


@dataclass(frozen=True)
class ExportBundle:
    directory: Path
    ui_screenshot: Path
    binary_mask: Path
    foreground_rgb: Path
    contour_overlay: Path
    metadata: Path


def safe_stem(name: str) -> str:
    # 不使用当前操作系统的 Path 解析规则：Windows 会把反斜杠识别为目录分隔符，
    # 还会把单字母加冒号识别为盘符，导致相同输入在 Windows/macOS 结果不同。
    filename = str(name).replace("\\", "/").rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0].strip() or "image"
    return re.sub(r"[\\/:*?\"<>|]+", "_", stem)


def export_images(
    output_root: str | Path,
    source_name: str,
    engine: GrabCutEngine,
    elapsed_ms: int,
    interaction_count: int,
) -> ExportBundle:
    if not engine.initialized:
        raise RuntimeError("尚未生成可以保存的分割结果")
    stem = safe_stem(source_name)
    directory = Path(output_root) / stem
    directory.mkdir(parents=True, exist_ok=True)

    mask_path = write_png(directory / f"{stem}_mask.png", engine.binary_mask())
    foreground_path = write_png(directory / f"{stem}_foreground.png", engine.foreground_bgr())
    overlay_path = write_png(directory / f"{stem}_overlay.png", engine.contour_overlay_bgr())
    ui_path = directory / f"{stem}_ui.png"
    metadata_path = directory / f"{stem}_experiment.json"
    metadata = {
        "source": source_name,
        "image_width": engine.width,
        "image_height": engine.height,
        "elapsed_seconds": round(elapsed_ms / 1000.0, 3),
        "interaction_count": int(interaction_count),
        "last_algorithm_ms": round(engine.last_runtime_ms, 3),
        "algorithm": "OpenCV GrabCut",
        "opencv_version": cv2.__version__,
        "opencl_enabled": bool(cv2.ocl.useOpenCL()),
        "gpu_used": False,
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return ExportBundle(directory, ui_path, mask_path, foreground_path, overlay_path, metadata_path)
