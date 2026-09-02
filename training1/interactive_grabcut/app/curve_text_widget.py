"""测试 2：沿路径逐字排版工作台。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .creative_canvas import CurveCanvas
from .curve_text_engine import (
    STYLE_OPTIONS,
    CurveTextSettings,
    clean_rainbow_reference,
    composite_rgba_over_rgb,
    render_curve_text_layer,
    validate_text,
)
from .experiment_clock import ExperimentClock
from .fonts import creative_font_options
from .image_io import ImageIOError, read_bgr, write_png


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CurveSnapshot:
    curve: tuple[tuple[int, int], ...]
    layer_rgba: np.ndarray | None
    result_rgb: np.ndarray | None


class CurveTextWidget(QWidget):
    layer_ready = Signal(object, str)
    MAX_UNDO = 20

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.background_rgb: np.ndarray | None = None
        self.current_path: Path | None = None
        self.layer_rgba: np.ndarray | None = None
        self.result_rgb: np.ndarray | None = None
        self.placements: list[object] = []
        self.render_count = 0
        self.undo_stack: list[CurveSnapshot] = []
        self.text_color = QColor(255, 245, 200)
        self.clock = ExperimentClock(self)
        self._build_ui()
        self._connect_signals()
        self._update_time(0)
        self._refresh_actions()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("测试 2：路径文字")
        title.setStyleSheet("font-size:20px; font-weight:800; color:#172033;")
        header.addWidget(title)
        header.addStretch(1)
        self.open_button = QPushButton("读取背景")
        self.preset_button = QPushButton("规定彩虹背景")
        self.undo_button = QPushButton("撤销")
        self.reset_button = QPushButton("重新开始")
        self.save_button = QPushButton("结束并保存")
        self.send_button = QPushButton("送入测试 3")
        for button in (self.open_button, self.preset_button, self.undo_button, self.reset_button, self.save_button, self.send_button):
            header.addWidget(button)
        root.addLayout(header)

        body = QHBoxLayout()
        controls = QFrame()
        controls.setFixedWidth(290)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        guide = QGroupBox("操作步骤")
        guide_layout = QVBoxLayout(guide)
        guide_text = QLabel("1. 读取规定彩虹背景\n2. 输入 4–10 个文字\n3. 按住鼠标沿彩虹外缘拖动\n4. 选择字体效果并渲染\n5. 保存或送入测试 3")
        guide_text.setWordWrap(True)
        guide_layout.addWidget(guide_text)
        controls_layout.addWidget(guide)

        text_group = QGroupBox("文字与字体")
        form = QFormLayout(text_group)
        self.text_edit = QLineEdit("这是测试文字")
        self.text_edit.setMaxLength(16)
        form.addRow("文字（4–10个）", self.text_edit)
        self.font_combo = QComboBox()
        for label, family in creative_font_options():
            self.font_combo.addItem(label, family)
        form.addRow("字体（5种）", self.font_combo)
        self.style_combo = QComboBox()
        for label, value in STYLE_OPTIONS:
            self.style_combo.addItem(label, value)
        form.addRow("艺术效果", self.style_combo)
        self.font_size = QSpinBox()
        self.font_size.setRange(18, 128)
        self.font_size.setValue(52)
        form.addRow("字号", self.font_size)
        self.color_button = QPushButton("选择文字颜色")
        self._update_color_button()
        form.addRow("颜色", self.color_button)
        controls_layout.addWidget(text_group)

        effect_group = QGroupBox("协调与插入位置")
        effect_form = QFormLayout(effect_group)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(40, 255)
        self.opacity_slider.setValue(235)
        effect_form.addRow("透明度", self.opacity_slider)
        self.outline_slider = QSlider(Qt.Orientation.Horizontal)
        self.outline_slider.setRange(0, 6)
        self.outline_slider.setValue(1)
        effect_form.addRow("描边", self.outline_slider)
        self.start_slider = QSlider(Qt.Orientation.Horizontal)
        self.start_slider.setRange(0, 70)
        self.start_slider.setValue(8)
        effect_form.addRow("曲线起点", self.start_slider)
        self.offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.offset_slider.setRange(-100, 100)
        self.offset_slider.setValue(-18)
        effect_form.addRow("法线偏移", self.offset_slider)
        self.guide_check = QCheckBox("显示辅助曲线（保存结果不包含）")
        self.guide_check.setChecked(True)
        effect_form.addRow(self.guide_check)
        controls_layout.addWidget(effect_group)

        self.render_button = QPushButton("按切线方向渲染文字")
        self.render_button.setMinimumHeight(42)
        self.render_button.setStyleSheet("background:#2563eb; color:white; font-weight:700;")
        controls_layout.addWidget(self.render_button)
        controls_layout.addStretch(1)
        body.addWidget(controls)

        self.canvas = CurveCanvas()
        body.addWidget(self.canvas, 1)
        root.addLayout(body, 1)

        status = QHBoxLayout()
        self.state_label = QLabel("状态：等待读取背景")
        self.time_label = QLabel("操作时间：0.0 s")
        self.count_label = QLabel("成功排版：0 次")
        self.direction_label = QLabel("切线角度：—")
        status.addWidget(self.state_label, 1)
        status.addWidget(self.direction_label)
        status.addWidget(self.time_label)
        status.addWidget(self.count_label)
        root.addLayout(status)

    def _connect_signals(self) -> None:
        self.open_button.clicked.connect(self.open_background)
        self.preset_button.clicked.connect(self.load_prescribed_background)
        self.undo_button.clicked.connect(self.undo)
        self.reset_button.clicked.connect(self.reset_experiment)
        self.save_button.clicked.connect(self.save_all)
        self.send_button.clicked.connect(self.send_to_test3)
        self.render_button.clicked.connect(lambda: self.render_text(record_history=True))
        self.color_button.clicked.connect(self.choose_color)
        self.guide_check.toggled.connect(self._toggle_guide)
        self.canvas.curve_committed.connect(self._on_curve_committed)
        self.clock.tick.connect(self._update_time)

    def open_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "读取测试 2 背景", str(Path.cwd()), "图像文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if path:
            self._load_path(Path(path), clean_reference=False)

    def load_prescribed_background(self) -> None:
        path = ROOT / "training_images" / "rainbow_reference.jpg"
        self._load_path(path, clean_reference=True)

    def _load_path(self, path: Path, clean_reference: bool = False) -> None:
        try:
            rgb = cv2.cvtColor(read_bgr(path), cv2.COLOR_BGR2RGB)
            if clean_reference:
                rgb = clean_rainbow_reference(rgb)
        except (ImageIOError, cv2.error, ValueError) as exc:
            QMessageBox.critical(self, "读取失败", str(exc))
            return
        self.background_rgb = rgb
        self.current_path = path
        self.layer_rgba = None
        self.result_rgb = rgb.copy()
        self.placements.clear()
        self.render_count = 0
        self.undo_stack.clear()
        self.canvas.clear_curve()
        self.canvas.set_image(self.result_rgb)
        self.clock.start(reset=True)
        self.state_label.setText(f"状态：已读取 {path.name}（{rgb.shape[1]} × {rgb.shape[0]}），请沿目标曲线拖动")
        self._refresh_actions()

    def _snapshot(self) -> CurveSnapshot:
        return CurveSnapshot(
            tuple(self.canvas.curve_points),
            None if self.layer_rgba is None else self.layer_rgba.copy(),
            None if self.result_rgb is None else self.result_rgb.copy(),
        )

    def _push_snapshot(self) -> None:
        self.undo_stack.append(self._snapshot())
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)

    def _on_curve_committed(self, points: object) -> None:
        del points
        self.render_text(record_history=True)

    def _settings(self) -> CurveTextSettings:
        return CurveTextSettings(
            text=validate_text(self.text_edit.text()),
            font_family=str(self.font_combo.currentData()),
            style=str(self.style_combo.currentData()),
            font_size=self.font_size.value(),
            color_rgb=(self.text_color.red(), self.text_color.green(), self.text_color.blue()),
            opacity=self.opacity_slider.value(),
            outline_width=self.outline_slider.value(),
            start_fraction=self.start_slider.value() / 100.0,
            path_offset=float(self.offset_slider.value()),
        )

    def render_text(self, record_history: bool = True) -> bool:
        if self.background_rgb is None:
            QMessageBox.information(self, "缺少背景", "请先读取背景图像。")
            return False
        if len(self.canvas.curve_points) < 2:
            QMessageBox.information(self, "缺少曲线", "请按住鼠标，沿背景中的曲线拖出文字路径。")
            return False
        try:
            settings = self._settings()
            if record_history:
                self._push_snapshot()
            layer, placements, smoothed = render_curve_text_layer(
                (self.background_rgb.shape[1], self.background_rgb.shape[0]),
                self.canvas.curve_points,
                settings,
            )
            result = composite_rgba_over_rgb(self.background_rgb, layer)
        except (ValueError, RuntimeError) as exc:
            if record_history and self.undo_stack:
                self.undo_stack.pop()
            QMessageBox.warning(self, "排版失败", str(exc))
            return False
        self.layer_rgba = layer
        self.result_rgb = result
        self.placements = placements
        self.canvas.set_curve([(int(x), int(y)) for x, y in smoothed])
        self.canvas.set_image(result)
        if record_history:
            self.render_count += 1
        angles = [placement.angle_degrees for placement in placements]
        spread = max(angles) - min(angles) if angles else 0.0
        self.direction_label.setText(f"切线角度范围：{min(angles):.1f}°～{max(angles):.1f}°" if angles else "切线角度：—")
        self.state_label.setText(f"状态：已逐字沿切线排版，方向变化 {spread:.1f}°")
        self._refresh_actions()
        return True

    def choose_color(self) -> None:
        color = QColorDialog.getColor(self.text_color, self, "选择文字颜色")
        if color.isValid():
            self.text_color = color
            self._update_color_button()

    def _update_color_button(self) -> None:
        foreground = "#111827" if self.text_color.lightness() > 155 else "#ffffff"
        self.color_button.setStyleSheet(f"background:{self.text_color.name()}; color:{foreground};")

    def _toggle_guide(self, checked: bool) -> None:
        self.canvas.show_guide = checked
        self.canvas.update()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        snapshot = self.undo_stack.pop()
        self.canvas.set_curve(snapshot.curve)
        self.layer_rgba = snapshot.layer_rgba
        self.result_rgb = snapshot.result_rgb if snapshot.result_rgb is not None else self.background_rgb
        self.canvas.set_image(self.result_rgb)
        self.state_label.setText("状态：已撤销上一次路径或排版结果")
        self._refresh_actions()

    def reset_experiment(self) -> None:
        if self.background_rgb is None:
            return
        self.layer_rgba = None
        self.result_rgb = self.background_rgb.copy()
        self.placements.clear()
        self.render_count = 0
        self.undo_stack.clear()
        self.canvas.clear_curve()
        self.canvas.set_image(self.result_rgb)
        self.clock.start(reset=True)
        self.state_label.setText("状态：已重置，请重新沿曲线拖动")
        self.direction_label.setText("切线角度：—")
        self._refresh_actions()

    def send_to_test3(self) -> None:
        if self.layer_rgba is None:
            QMessageBox.information(self, "暂无文字图层", "请先完成一次曲线文字排版。")
            return
        self.layer_ready.emit(self.layer_rgba.copy(), "测试2_曲线文字.png")
        self.state_label.setText("状态：透明文字图层已送入测试 3")

    def save_all(self) -> None:
        if self.result_rgb is None or self.layer_rgba is None:
            QMessageBox.information(self, "暂无结果", "请先完成一次曲线文字排版。")
            return
        directory = QFileDialog.getExistingDirectory(self, "选择测试 2 保存目录", str(ROOT / "results"))
        if not directory:
            return
        self.clock.pause()
        output = Path(directory) / "test2_curve_text"
        output.mkdir(parents=True, exist_ok=True)
        try:
            write_png(output / "test2_result.png", cv2.cvtColor(self.result_rgb, cv2.COLOR_RGB2BGR))
            write_png(output / "test2_text_layer.png", cv2.cvtColor(self.layer_rgba, cv2.COLOR_RGBA2BGRA))
            if self.background_rgb is not None:
                write_png(output / "test2_background.png", cv2.cvtColor(self.background_rgb, cv2.COLOR_RGB2BGR))
            if not self.grab().save(str(output / "test2_ui.png"), "PNG"):
                raise OSError("界面截图保存失败")
            metadata = {
                "test": 2,
                "title": "路径文字",
                "source": self.current_path.name if self.current_path else None,
                "elapsed_seconds": round(self.clock.elapsed_ms() / 1000.0, 3),
                "render_count": self.render_count,
                "settings": asdict(self._settings()),
                "glyphs": [asdict(item) for item in self.placements],
                "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            (output / "test2_experiment.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ImageIOError, ValueError) as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            self.clock.resume()
            return
        self.state_label.setText(f"状态：测试 2 结果已保存到 {output}")
        QMessageBox.information(self, "保存完成", f"已保存结果图、透明文字层、背景、界面截图和 JSON。\n\n{output}")

    def _update_time(self, elapsed_ms: int) -> None:
        self.time_label.setText(f"操作时间：{elapsed_ms / 1000.0:.1f} s")

    def _refresh_actions(self) -> None:
        has_background = self.background_rgb is not None
        has_result = self.layer_rgba is not None
        self.undo_button.setEnabled(bool(self.undo_stack))
        self.reset_button.setEnabled(has_background)
        self.render_button.setEnabled(has_background)
        self.save_button.setEnabled(has_result)
        self.send_button.setEnabled(has_result)
        self.count_label.setText(f"成功排版：{self.render_count} 次")
