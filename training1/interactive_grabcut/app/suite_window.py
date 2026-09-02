"""三个相关实训模块的统一桌面入口。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from .curve_text_widget import CurveTextWidget
from .main_window import MainWindow
from .surface_sticker_widget import SurfaceStickerWidget


class TrainingSuiteWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OpenCV 交互实训套件：分割、路径文字与表面贴图")
        self.resize(1500, 900)
        self.setMinimumSize(1120, 720)

        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        banner = QLabel("专业技能实训 1 · CPU 离线图像创作工作台")
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner.setStyleSheet("background:#172033; color:white; padding:7px; font-weight:700;")
        layout.addWidget(banner)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self.segmentation = MainWindow()
        self.segmentation.setWindowFlags(Qt.WindowType.Widget)
        self.curve_text = CurveTextWidget()
        self.surface_sticker = SurfaceStickerWidget()
        self.tabs.addTab(self.segmentation, "测试 1 · 交互分割")
        self.tabs.addTab(self.curve_text, "测试 2 · 路径文字")
        self.tabs.addTab(self.surface_sticker, "测试 3 · 平/柱面贴图")
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

        self.segmentation.foreground_ready.connect(self._receive_foreground)
        self.curve_text.layer_ready.connect(self._receive_foreground)

    def _receive_foreground(self, rgba: object, name: str) -> None:
        self.surface_sticker.set_foreground_rgba(rgba, name)
        self.tabs.setCurrentWidget(self.surface_sticker)
