"""交互式图像分割主窗口。"""

from __future__ import annotations

from pathlib import Path

import cv2
from PySide6.QtCore import QElapsedTimer, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .canvas import ImageCanvas, ImageViewer
from .constants import DrawingTool, LabelMode, TOOL_INFO
from .exporter import export_images
from .geometry import AnnotationCommand
from .grabcut_engine import EngineSnapshot, GrabCutEngine
from .image_io import ImageIOError, read_bgr


class MainWindow(QMainWindow):
    foreground_ready = Signal(object, str)
    MAX_UNDO = 20

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("测试 1：交互式图像分割 — GrabCut CPU 离线版")
        self.resize(1480, 860)
        self.setMinimumSize(1080, 680)

        self.engine = GrabCutEngine()
        self.current_path: Path | None = None
        self.interaction_count = 0
        self.undo_stack: list[EngineSnapshot] = []
        self.last_output_root = Path(__file__).resolve().parents[1] / "results"

        self.elapsed_clock = QElapsedTimer()
        self.elapsed_accumulated_ms = 0
        self.timer_active = False
        self.display_timer = QTimer(self)
        self.display_timer.setInterval(100)
        self.display_timer.timeout.connect(self._update_time_label)

        self._build_toolbar()
        self._build_central_ui()
        self._build_status_bar()
        self._connect_signals()
        self._set_tool(DrawingTool.RECTANGLE)
        self._set_label_mode(LabelMode.SURE_FOREGROUND)
        self._refresh_actions()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("文件与实验", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        self.open_action = QAction("读取图像", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setToolTip("读取本地图像（Ctrl+O）")
        toolbar.addAction(self.open_action)

        self.test_action = QAction("打开规定测试图", self)
        self.test_action.setToolTip("从项目 test_images 目录选择 LENA、baymax 或 cat")
        toolbar.addAction(self.test_action)
        toolbar.addSeparator()

        self.undo_action = QAction("撤销标记", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        toolbar.addAction(self.undo_action)

        self.reset_action = QAction("重新开始", self)
        self.reset_action.setShortcut("Ctrl+R")
        toolbar.addAction(self.reset_action)
        toolbar.addSeparator()

        self.save_action = QAction("结束并保存全部", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.setToolTip("停止计时并保存界面截图、mask、RGB前景和轮廓图（Ctrl+S）")
        toolbar.addAction(self.save_action)

        self.send_action = QAction("发送前景到测试 3", self)
        self.send_action.setToolTip("把当前 GrabCut 结果作为透明前景送入贴图模块")
        toolbar.addAction(self.send_action)

        self.exit_action = QAction("退出", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        toolbar.addAction(self.exit_action)

    def _build_central_ui(self) -> None:
        root = QWidget(self)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 8)
        root_layout.setSpacing(10)

        toolbox = self._build_toolbox()
        root_layout.addWidget(toolbox)

        self.input_canvas = ImageCanvas()
        self.result_view = ImageViewer("分割后在这里显示结果")

        input_panel = self._viewer_panel("原始图像 / 用户标记", self.input_canvas)
        result_panel = self._viewer_panel("实验结果", self.result_view, with_result_selector=True)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(input_panel)
        splitter.addWidget(result_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([610, 610])
        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(root)

    def _build_toolbox(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(230)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        guide_group = QGroupBox("当前步骤")
        guide_layout = QVBoxLayout(guide_group)
        self.guide_label = QLabel("1. 读取图像\n2. 用矩形框住前景\n3. 用前景/背景标记修正\n4. 保存全部结果")
        self.guide_label.setWordWrap(True)
        self.guide_label.setStyleSheet("color:#354257; line-height:1.4;")
        guide_layout.addWidget(self.guide_label)
        layout.addWidget(guide_group)

        tools_group = QGroupBox("选择工具箱")
        tools_grid = QGridLayout(tools_group)
        tools_grid.setHorizontalSpacing(6)
        tools_grid.setVerticalSpacing(6)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons: dict[DrawingTool, QToolButton] = {}
        for index, (tool, info) in enumerate(TOOL_INFO.items()):
            button = QToolButton()
            button.setText(info.text)
            button.setCheckable(True)
            button.setMinimumHeight(34)
            button.setToolTip(f"{info.text}工具；快捷提示 {info.shortcut}")
            self.tool_group.addButton(button, index)
            self.tool_buttons[tool] = button
            tools_grid.addWidget(button, index // 2, index % 2)
        layout.addWidget(tools_group)

        label_group_box = QGroupBox("GrabCut 标记类型")
        label_layout = QVBoxLayout(label_group_box)
        self.label_group = QButtonGroup(self)
        self.label_buttons: dict[LabelMode, QRadioButton] = {}
        for index, mode in enumerate(LabelMode):
            button = QRadioButton(mode.text)
            r, g, b = mode.rgb
            button.setStyleSheet(f"QRadioButton {{ color: rgb({r},{g},{b}); font-weight:600; }}")
            self.label_group.addButton(button, index)
            self.label_buttons[mode] = button
            label_layout.addWidget(button)
        layout.addWidget(label_group_box)

        brush_group = QGroupBox("线宽 / 画笔大小")
        brush_layout = QVBoxLayout(brush_group)
        size_row = QHBoxLayout()
        self.brush_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_slider.setRange(1, 61)
        self.brush_slider.setSingleStep(2)
        self.brush_slider.setValue(11)
        self.brush_size_label = QLabel("11 px")
        size_row.addWidget(self.brush_slider, 1)
        size_row.addWidget(self.brush_size_label)
        brush_layout.addLayout(size_row)
        layout.addWidget(brush_group)

        polygon_tip = QLabel("任意多边形：逐点单击；双击、右键或 Enter 完成；Esc 取消。\n圆和椭圆：从中心向外拖动。")
        polygon_tip.setWordWrap(True)
        polygon_tip.setStyleSheet("color:#667085; padding:6px;")
        layout.addWidget(polygon_tip)
        layout.addStretch(1)
        return panel

    def _viewer_panel(self, title: str, viewer: QWidget, with_result_selector: bool = False) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet("QFrame { background:white; border:1px solid #d8dee6; border-radius:8px; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:15px; font-weight:700; color:#243142; border:none;")
        header.addWidget(title_label)
        header.addStretch(1)
        if with_result_selector:
            self.result_combo = QComboBox()
            self.result_combo.addItem("原图 + 分割轮廓", "overlay")
            self.result_combo.addItem("前景 RGB 图像", "foreground")
            self.result_combo.addItem("二值分割掩码", "mask")
            header.addWidget(self.result_combo)
        layout.addLayout(header)
        layout.addWidget(viewer, 1)
        return panel

    def _build_status_bar(self) -> None:
        self.state_label = QLabel("状态：等待读取图像")
        self.time_label = QLabel("操作时间：0.0 s")
        self.count_label = QLabel("交互次数：0")
        self.runtime_label = QLabel("本次算法：—")
        self.cpu_label = QLabel("CPU 离线 · OpenCL 关闭")
        self.statusBar().addWidget(self.state_label, 1)
        self.statusBar().addPermanentWidget(self.time_label)
        self.statusBar().addPermanentWidget(self.count_label)
        self.statusBar().addPermanentWidget(self.runtime_label)
        self.statusBar().addPermanentWidget(self.cpu_label)

    def _connect_signals(self) -> None:
        self.open_action.triggered.connect(self.open_image)
        self.test_action.triggered.connect(self.open_test_image)
        self.undo_action.triggered.connect(self.undo)
        self.reset_action.triggered.connect(self.reset_experiment)
        self.save_action.triggered.connect(self.save_all)
        self.send_action.triggered.connect(self.send_foreground_to_test3)
        self.exit_action.triggered.connect(self.close)
        self.input_canvas.annotation_committed.connect(self._on_annotation)
        self.input_canvas.polygon_message.connect(self._on_polygon_message)
        self.result_combo.currentIndexChanged.connect(self._update_result_view)
        self.brush_slider.valueChanged.connect(self._on_brush_size)
        for tool, button in self.tool_buttons.items():
            button.clicked.connect(lambda checked=False, selected=tool: self._set_tool(selected))
        for mode, button in self.label_buttons.items():
            button.clicked.connect(lambda checked=False, selected=mode: self._set_label_mode(selected))

    def open_image(self) -> None:
        start = str(self.current_path.parent if self.current_path else Path.cwd())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "读取实验图像",
            start,
            "图像文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*)",
        )
        if path:
            self._load_path(Path(path))

    def open_test_image(self) -> None:
        test_dir = Path(__file__).resolve().parents[1] / "test_images"
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择规定测试图",
            str(test_dir),
            "规定测试图 (LENA.jpg baymax.jpeg cat.jpg);;图像文件 (*.png *.jpg *.jpeg)",
        )
        if path:
            self._load_path(Path(path))

    def _load_path(self, path: Path) -> None:
        try:
            image = read_bgr(path)
            self.engine.load(image)
        except (ImageIOError, ValueError) as exc:
            QMessageBox.critical(self, "读取失败", str(exc))
            return
        self.current_path = path
        self.interaction_count = 0
        self.undo_stack.clear()
        self._start_timer(reset=True)
        self._set_tool(DrawingTool.RECTANGLE)
        self._set_label_mode(LabelMode.SURE_FOREGROUND)
        self.setWindowTitle(f"测试 1：交互式图像分割 — {path.name}")
        self.guide_label.setText("第 1 步：用矩形工具紧贴前景目标拖出初始框。\n矩形完成后会自动执行第 1 次 GrabCut。")
        self.state_label.setText(f"状态：已读取 {path.name}（{self.engine.width} × {self.engine.height}）")
        self.runtime_label.setText("本次算法：等待矩形初始化")
        self._update_views()
        self._refresh_actions()

    def _on_annotation(self, command: AnnotationCommand) -> None:
        if not self.engine.has_image:
            return
        if not self.engine.initialized and command.kind != DrawingTool.RECTANGLE.value:
            QMessageBox.information(self, "需要初始矩形", "第一次操作必须使用“矩形”工具框住前景目标。")
            self._set_tool(DrawingTool.RECTANGLE)
            return
        snapshot = self.engine.snapshot()
        try:
            if not self.engine.initialized:
                start, end = self.engine.initial_rect_from_command(command)
                runtime = self.engine.initialize_with_rect(start, end, iterations=5)
                self.guide_label.setText("第 2 步：选择前景或背景标记并继续修正。\n每完成一个图形或一条涂抹，自动运行 1 次 GrabCut。")
                self._set_tool(DrawingTool.BRUSH)
            else:
                self.engine.apply_annotation(command)
                runtime = self.engine.refine(iterations=1)
            self.undo_stack.append(snapshot)
            if len(self.undo_stack) > self.MAX_UNDO:
                self.undo_stack.pop(0)
            self.interaction_count += 1
            self._resume_timer()
            self.runtime_label.setText(f"本次算法：{runtime:.1f} ms")
            self.state_label.setText(f"状态：第 {self.interaction_count} 次分割完成，可继续标记或保存")
            self._update_views()
        except (cv2.error, RuntimeError, ValueError) as exc:
            self.engine.restore(snapshot)
            QMessageBox.warning(self, "分割失败", f"本次操作未计数，已恢复上一状态。\n\n{exc}")
        self._refresh_actions()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        snapshot = self.undo_stack.pop()
        self.engine.restore(snapshot)
        # 交互次数记录真实发生过的算法调用，因此撤销不回退计数。
        self.state_label.setText("状态：已撤销到上一分割状态（历史交互次数保持不变）")
        self._update_views()
        self._refresh_actions()

    def reset_experiment(self) -> None:
        if not self.engine.has_image:
            return
        self.engine.reset()
        self.interaction_count = 0
        self.undo_stack.clear()
        self._start_timer(reset=True)
        self._set_tool(DrawingTool.RECTANGLE)
        self.guide_label.setText("已重新开始：用矩形工具紧贴前景目标拖出初始框。")
        self.runtime_label.setText("本次算法：等待矩形初始化")
        self.state_label.setText("状态：实验已重置")
        self._update_views()
        self._refresh_actions()

    def save_all(self) -> None:
        if not self.engine.initialized or self.current_path is None:
            QMessageBox.information(self, "暂无结果", "请先完成至少一次矩形初始化分割。")
            return
        root = QFileDialog.getExistingDirectory(self, "选择结果保存目录", str(self.last_output_root))
        if not root:
            return
        self.last_output_root = Path(root)
        self._pause_timer()
        self._update_time_label()
        self.state_label.setText("状态：实验结束，正在保存完整结果")
        QApplication.processEvents()
        try:
            bundle = export_images(
                root,
                self.current_path.name,
                self.engine,
                self._elapsed_ms(),
                self.interaction_count,
            )
            if not self.grab().save(str(bundle.ui_screenshot), "PNG"):
                raise OSError("界面截图保存失败")
        except (OSError, RuntimeError, ImageIOError) as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            self._resume_timer()
            return
        self.state_label.setText(f"状态：结果已保存到 {bundle.directory}")
        QMessageBox.information(
            self,
            "保存完成",
            "已保存：\n"
            f"• 界面截图：{bundle.ui_screenshot.name}\n"
            f"• 二值掩码：{bundle.binary_mask.name}\n"
            f"• RGB 前景：{bundle.foreground_rgb.name}\n"
            f"• 轮廓叠加：{bundle.contour_overlay.name}\n"
            f"• 实验记录：{bundle.metadata.name}\n\n"
            f"目录：{bundle.directory}",
        )

    def send_foreground_to_test3(self) -> None:
        if not self.engine.initialized or self.current_path is None:
            QMessageBox.information(self, "暂无前景", "请先完成至少一次交互分割。")
            return
        rgb = cv2.cvtColor(self.engine.original_bgr, cv2.COLOR_BGR2RGB)
        alpha = self.engine.binary_mask()
        rgba = cv2.merge((rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2], alpha))
        self.foreground_ready.emit(rgba, f"测试1_{self.current_path.stem}_前景.png")
        self.state_label.setText("状态：透明分割前景已发送到测试 3")

    def _update_views(self) -> None:
        if not self.engine.has_image:
            self.input_canvas.set_image(None)
            self.result_view.set_image(None)
            return
        if self.engine.initialized:
            left = self.engine.annotation_overlay_rgb()
        else:
            left = cv2.cvtColor(self.engine.original_bgr, cv2.COLOR_BGR2RGB)
        self.input_canvas.set_image(left)
        self._update_result_view()
        self._update_count_label()

    def _update_result_view(self) -> None:
        if not self.engine.has_image:
            self.result_view.set_image(None)
            return
        mode = self.result_combo.currentData()
        if not self.engine.initialized:
            image = cv2.cvtColor(self.engine.original_bgr, cv2.COLOR_BGR2RGB)
        elif mode == "foreground":
            image = self.engine.foreground_rgb()
        elif mode == "mask":
            image = self.engine.mask_rgb()
        else:
            image = self.engine.contour_overlay_rgb()
        self.result_view.set_image(image)

    def _set_tool(self, tool: DrawingTool) -> None:
        self.input_canvas.set_tool(tool)
        self.tool_buttons[tool].setChecked(True)
        self.state_label.setText(f"状态：当前工具为 {TOOL_INFO[tool].text}")

    def _set_label_mode(self, mode: LabelMode) -> None:
        self.input_canvas.set_label_mode(mode)
        self.label_buttons[mode].setChecked(True)

    def _on_brush_size(self, value: int) -> None:
        if value % 2 == 0:
            value += 1
        self.input_canvas.set_brush_size(value)
        self.brush_size_label.setText(f"{value} px")

    def _on_polygon_message(self, message: str) -> None:
        if message:
            self.state_label.setText(f"状态：{message}")

    def _start_timer(self, reset: bool) -> None:
        if reset:
            self.elapsed_accumulated_ms = 0
        self.elapsed_clock.start()
        self.timer_active = True
        self.display_timer.start()
        self._update_time_label()

    def _pause_timer(self) -> None:
        if self.timer_active:
            self.elapsed_accumulated_ms += self.elapsed_clock.elapsed()
            self.timer_active = False
            self.display_timer.stop()

    def _resume_timer(self) -> None:
        if self.engine.has_image and not self.timer_active:
            self.elapsed_clock.start()
            self.timer_active = True
            self.display_timer.start()

    def _elapsed_ms(self) -> int:
        return self.elapsed_accumulated_ms + (self.elapsed_clock.elapsed() if self.timer_active else 0)

    def _update_time_label(self) -> None:
        self.time_label.setText(f"操作时间：{self._elapsed_ms() / 1000.0:.1f} s")

    def _update_count_label(self) -> None:
        self.count_label.setText(f"交互次数：{self.interaction_count}")

    def _refresh_actions(self) -> None:
        has_image = self.engine.has_image
        self.undo_action.setEnabled(bool(self.undo_stack))
        self.reset_action.setEnabled(has_image)
        self.save_action.setEnabled(self.engine.initialized)
        self.send_action.setEnabled(self.engine.initialized)
        self._update_count_label()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.display_timer.stop()
        event.accept()
