"""OpenCV 交互实训套件：程序入口。"""

from __future__ import annotations

import sys


def _dependency_error() -> str | None:
    missing: list[str] = []
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    try:
        import cv2  # noqa: F401
    except ImportError:
        missing.append("opencv-python-headless")
    try:
        import PySide6  # noqa: F401
    except ImportError:
        missing.append("PySide6")
    if not missing:
        return None
    return (
        "缺少运行依赖：" + "、".join(missing) + "\n\n"
        "请先在项目目录执行：\n"
        "    python -m pip install -r requirements.txt\n\n"
        "Windows 也可以直接双击 setup_windows.bat。"
    )


def main() -> int:
    error = _dependency_error()
    if error:
        print(error, file=sys.stderr)
        return 1

    import cv2
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    # 明确禁用 OpenCL；本项目不调用 CUDA/GPU，也不进行任何网络请求。
    cv2.ocl.setUseOpenCL(False)

    from app.fonts import install_bundled_ui_font
    from app.suite_window import TrainingSuiteWindow
    from app.styles import APP_STYLE

    app = QApplication(sys.argv)
    app.setApplicationName("OpenCV 交互实训套件")
    app.setOrganizationName("OpenCV Course")
    app.setStyle("Fusion")
    install_bundled_ui_font(app)
    app.setStyleSheet(APP_STYLE)

    try:
        window = TrainingSuiteWindow()
        window.show()
        # 供打包后的 CI 启动检查使用。正常用户启动不会进入该分支。
        if "--ci-smoke" in sys.argv:
            QTimer.singleShot(1500, app.quit)
        return app.exec()
    except Exception as exc:  # 顶层保护，避免启动失败时没有可读信息
        QMessageBox.critical(None, "程序启动失败", f"{type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
