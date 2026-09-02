"""在原生 CI runner 上生成 Qt/GrabCut 运行证据。"""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")

import cv2
import numpy as np
import PySide6
from PySide6.QtCore import qVersion
from PySide6.QtGui import QRawFont
from PySide6.QtWidgets import QApplication

from app.constants import DrawingTool, LabelMode
from app.fonts import creative_font_options, install_bundled_ui_font
from app.geometry import AnnotationCommand
from app.suite_window import TrainingSuiteWindow


def main() -> int:
    output_dir = Path(os.environ.get("CI_ARTIFACT_DIR", ROOT / "ci_artifacts"))
    output_dir.mkdir(parents=True, exist_ok=True)

    cv2.ocl.setUseOpenCL(False)
    app = QApplication.instance() or QApplication([])
    font_family = install_bundled_ui_font(app)
    raw_font = QRawFont.fromFont(app.font())
    window = TrainingSuiteWindow()
    window.resize(1280, 720)
    window.show()
    app.processEvents()
    segmentation = window.segmentation
    segmentation._load_path(ROOT / "test_images" / "LENA.jpg")
    segmentation._on_annotation(
        AnnotationCommand(
            kind=DrawingTool.RECTANGLE.value,
            points=((35, 35), (476, 35), (476, 476), (35, 476)),
            label_value=LabelMode.SURE_FOREGROUND.mask_value,
            brush_size=11,
        )
    )
    app.processEvents()

    test1_screenshot = output_dir / "native_test1_grabcut.png"
    if not window.grab().save(str(test1_screenshot), "PNG"):
        raise RuntimeError("测试 1 界面截图保存失败")

    curve = window.curve_text
    window.tabs.setCurrentWidget(curve)
    curve.load_prescribed_background()
    curve.font_combo.setCurrentIndex(2)  # 毛笔艺术字体，作为评分截图证据。
    h2, w2 = curve.background_rgb.shape[:2]
    points = []
    for index in range(100):
        normalized = index / 99
        x = int(w2 * (0.06 + normalized * 0.88))
        y = int(h2 * (0.66 - 0.34 * (1 - ((normalized - 0.5) * 2) ** 2)))
        points.append((x, y))
    curve.canvas.set_curve(points)
    if not curve.render_text():
        raise RuntimeError("测试 2 曲线文字渲染失败")
    app.processEvents()
    if not window.grab().save(str(output_dir / "native_test2_curve_text.png"), "PNG"):
        raise RuntimeError("测试 2 界面截图保存失败")

    sticker = window.surface_sticker
    window.tabs.setCurrentWidget(sticker)
    sticker.load_prescribed_materials()
    sticker.surface_combo.setCurrentIndex(1)
    sticker.commit_current_operation()
    app.processEvents()
    if not window.grab().save(str(output_dir / "native_test3_surface_sticker.png"), "PNG"):
        raise RuntimeError("测试 3 界面截图保存失败")
    evidence = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "pyside6": PySide6.__version__,
        "qt": qVersion(),
        "qt_platform": os.environ["QT_QPA_PLATFORM"],
        "application_font_family": font_family,
        "creative_font_families": [label for label, _ in creative_font_options()],
        "font_supports_chinese": raw_font.supportsCharacter(ord("测")),
        "opencl_enabled": bool(cv2.ocl.useOpenCL()),
        "window_logical_size": [window.width(), window.height()],
        "screenshot_pixel_size": [window.grab().width(), window.grab().height()],
        "source_image": "LENA.jpg",
        "source_size": [segmentation.engine.width, segmentation.engine.height],
        "grabcut_initialized": segmentation.engine.initialized,
        "test1_interaction_count": segmentation.interaction_count,
        "test2_rendered": curve.layer_rgba is not None,
        "test2_glyph_count": len(curve.placements),
        "test3_rendered": sticker.result_rgb is not None,
        "test3_interaction_count": sticker.interaction_count,
        "suite_tab_count": window.tabs.count(),
    }
    (output_dir / "environment.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    window.close()
    app.processEvents()
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
