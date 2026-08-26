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
from PySide6.QtWidgets import QApplication

from app.constants import DrawingTool, LabelMode
from app.geometry import AnnotationCommand
from app.main_window import MainWindow


def main() -> int:
    output_dir = Path(os.environ.get("CI_ARTIFACT_DIR", ROOT / "ci_artifacts"))
    output_dir.mkdir(parents=True, exist_ok=True)

    cv2.ocl.setUseOpenCL(False)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    app.processEvents()
    window._load_path(ROOT / "test_images" / "LENA.jpg")
    window._on_annotation(
        AnnotationCommand(
            kind=DrawingTool.RECTANGLE.value,
            points=((35, 35), (476, 35), (476, 476), (35, 476)),
            label_value=LabelMode.SURE_FOREGROUND.mask_value,
            brush_size=11,
        )
    )
    app.processEvents()

    screenshot = output_dir / "native_qt_grabcut.png"
    if not window.grab().save(str(screenshot), "PNG"):
        raise RuntimeError("CI 界面截图保存失败")
    evidence = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "pyside6": PySide6.__version__,
        "qt": qVersion(),
        "qt_platform": os.environ["QT_QPA_PLATFORM"],
        "opencl_enabled": bool(cv2.ocl.useOpenCL()),
        "window_logical_size": [window.width(), window.height()],
        "screenshot_pixel_size": [window.grab().width(), window.grab().height()],
        "source_image": "LENA.jpg",
        "source_size": [window.engine.width, window.engine.height],
        "grabcut_initialized": window.engine.initialized,
        "interaction_count": window.interaction_count,
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
