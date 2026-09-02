"""测试 3：平面 / 柱面贴图工作台。"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .creative_canvas import StickerCanvas
from .experiment_clock import ExperimentClock
from .image_io import ImageIOError, read_bgr, write_png
from .surface_engine import StickerPlacement, blend_sticker, clean_planar_reference, ensure_rgba


ROOT = Path(__file__).resolve().parents[1]


class SurfaceStickerWidget(QWidget):
    MAX_UNDO = 30

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.background_rgb: np.ndarray | None = None
        self.foreground_rgba: np.ndarray | None = None
        self.result_rgb: np.ndarray | None = None
        self.background_path: Path | None = None
        self.foreground_name = "foreground.png"
        self.placement = StickerPlacement(0, 0)
        self._committed_placement = self.placement
        self._slider_start = self.placement
        self.interaction_count = 0
        self.undo_stack: list[StickerPlacement] = []
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
        title = QLabel("测试 3：平面 / 柱面贴图")
        title.setStyleSheet("font-size:20px; font-weight:800; color:#172033;")
        header.addWidget(title)
        header.addStretch(1)
        self.background_button = QPushButton("读取背景")
        self.foreground_button = QPushButton("读取前景")
        self.preset_button = QPushButton("载入规定素材")
        self.undo_button = QPushButton("撤销")
        self.reset_button = QPushButton("重新开始")
        self.save_button = QPushButton("结束并保存")
        for button in (self.background_button, self.foreground_button, self.preset_button, self.undo_button, self.reset_button, self.save_button):
            header.addWidget(button)
        root.addLayout(header)

        body = QHBoxLayout()
        controls = QFrame()
        controls.setFixedWidth(300)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        guide = QGroupBox("交互要求")
        guide_layout = QVBoxLayout(guide)
        guide_text = QLabel("• 拖动贴图改变位置\n• 拖右下角蓝色手柄改变大小\n• 每次松开鼠标，融合并计 1 次\n• 位置和大小不写死在代码中\n• 可撤销每一次完成的操作")
        guide_text.setWordWrap(True)
        guide_layout.addWidget(guide_text)
        controls_layout.addWidget(guide)

        transform_group = QGroupBox("表面与透视效果")
        form = QFormLayout(transform_group)
        self.surface_combo = QComboBox()
        self.surface_combo.addItem("平面贴图", "plane")
        self.surface_combo.addItem("柱面贴图", "cylinder")
        form.addRow("模式", self.surface_combo)
        self.rotation_slider = QSlider(Qt.Orientation.Horizontal)
        self.rotation_slider.setRange(-180, 180)
        self.rotation_slider.setValue(0)
        form.addRow("旋转", self.rotation_slider)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(100)
        form.addRow("透明度", self.opacity_slider)
        self.curvature_slider = QSlider(Qt.Orientation.Horizontal)
        self.curvature_slider.setRange(5, 95)
        self.curvature_slider.setValue(55)
        form.addRow("柱面弯曲", self.curvature_slider)
        self.harmonize_slider = QSlider(Qt.Orientation.Horizontal)
        self.harmonize_slider.setRange(0, 100)
        self.harmonize_slider.setValue(25)
        form.addRow("颜色协调", self.harmonize_slider)
        controls_layout.addWidget(transform_group)

        self.apply_button = QPushButton("应用当前参数（计 1 次）")
        self.apply_button.setMinimumHeight(42)
        self.apply_button.setStyleSheet("background:#2563eb; color:white; font-weight:700;")
        controls_layout.addWidget(self.apply_button)
        tip = QLabel("测试 1 的分割前景和测试 2 的透明文字层，都可以直接发送到本页继续贴图。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#475569; padding:8px;")
        controls_layout.addWidget(tip)
        controls_layout.addStretch(1)
        body.addWidget(controls)

        self.canvas = StickerCanvas()
        body.addWidget(self.canvas, 1)
        root.addLayout(body, 1)

        status = QHBoxLayout()
        self.state_label = QLabel("状态：等待背景和前景")
        self.time_label = QLabel("操作时间：0.0 s")
        self.count_label = QLabel("交互次数：0")
        self.mode_label = QLabel("当前模式：平面")
        status.addWidget(self.state_label, 1)
        status.addWidget(self.mode_label)
        status.addWidget(self.time_label)
        status.addWidget(self.count_label)
        root.addLayout(status)

    def _connect_signals(self) -> None:
        self.background_button.clicked.connect(self.open_background)
        self.foreground_button.clicked.connect(self.open_foreground)
        self.preset_button.clicked.connect(self.load_prescribed_materials)
        self.undo_button.clicked.connect(self.undo)
        self.reset_button.clicked.connect(self.reset_experiment)
        self.save_button.clicked.connect(self.save_all)
        self.apply_button.clicked.connect(self.commit_current_operation)
        self.surface_combo.currentIndexChanged.connect(self._surface_changed)
        self.canvas.placement_preview.connect(self._canvas_preview)
        self.canvas.placement_committed.connect(self._canvas_commit)
        sliders = (self.rotation_slider, self.opacity_slider, self.curvature_slider, self.harmonize_slider)
        for slider in sliders:
            slider.sliderPressed.connect(self._slider_pressed)
            slider.valueChanged.connect(self._control_preview)
            slider.sliderReleased.connect(self._slider_released)
        self.clock.tick.connect(self._update_time)

    def open_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "读取测试 3 背景", str(Path.cwd()), "图像文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if path:
            self._load_background(Path(path), clean_reference=False)

    def open_foreground(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "读取测试 3 前景", str(Path.cwd()), "图像文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if not path:
            return
        try:
            raw = np.fromfile(path, dtype=np.uint8)
            decoded = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
            if decoded is None:
                raise ImageIOError(f"不是有效图像：{path}")
            if decoded.ndim == 2:
                decoded = cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGRA)
            if decoded.shape[2] == 4:
                rgba = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGBA)
            else:
                rgba = ensure_rgba(cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB))
        except (OSError, ValueError, cv2.error, ImageIOError) as exc:
            QMessageBox.critical(self, "读取失败", str(exc))
            return
        self.set_foreground_rgba(rgba, Path(path).name)

    def load_prescribed_materials(self) -> None:
        self._load_background(ROOT / "training_images" / "planar_source_reference.jpg", clean_reference=True)
        try:
            rgb = cv2.cvtColor(read_bgr(ROOT / "training_images" / "planar_foreground.jpg"), cv2.COLOR_BGR2RGB)
        except (ImageIOError, cv2.error) as exc:
            QMessageBox.critical(self, "规定素材缺失", str(exc))
            return
        self.set_foreground_rgba(ensure_rgba(rgb), "规定前景_img2.jpg")
        self.state_label.setText("状态：规定背景与前景已载入，请拖动并缩放贴图")

    def _load_background(self, path: Path, clean_reference: bool) -> None:
        try:
            rgb = cv2.cvtColor(read_bgr(path), cv2.COLOR_BGR2RGB)
            if clean_reference:
                rgb = clean_planar_reference(rgb)
        except (ImageIOError, cv2.error, ValueError) as exc:
            QMessageBox.critical(self, "读取失败", str(exc))
            return
        self.background_rgb = rgb
        self.background_path = path
        self.result_rgb = rgb.copy()
        self.interaction_count = 0
        self.undo_stack.clear()
        self.clock.start(reset=True)
        self.placement = StickerPlacement(rgb.shape[1] / 2, rgb.shape[0] / 2)
        self._committed_placement = self.placement
        self._sync_controls_from_placement()
        self._render()
        self.state_label.setText(f"状态：已读取背景 {path.name}（{rgb.shape[1]} × {rgb.shape[0]}）")
        self._refresh_actions()

    def set_foreground_rgba(self, rgba: np.ndarray, name: str = "linked_foreground.png") -> None:
        try:
            self.foreground_rgba = ensure_rgba(rgba)
        except ValueError as exc:
            QMessageBox.warning(self, "前景无效", str(exc))
            return
        self.foreground_name = name
        if self.background_rgb is not None:
            target_width = self.background_rgb.shape[1] * 0.30
            scale = target_width / max(1, self.foreground_rgba.shape[1])
            self.placement = replace(self.placement, scale=float(np.clip(scale, 0.08, 2.5)))
            self._committed_placement = self.placement
            self._render()
        self.state_label.setText(f"状态：已载入前景 {name}，可拖动位置或右下角缩放")
        self._refresh_actions()

    def _render(self) -> None:
        if self.background_rgb is None:
            self.canvas.set_image(None)
            return
        if self.foreground_rgba is None:
            self.result_rgb = self.background_rgb.copy()
            self.canvas.set_image(self.result_rgb)
            self.canvas.set_placement((self.placement.center_x, self.placement.center_y), self.placement.scale, None)
            return
        self.result_rgb, box = blend_sticker(self.background_rgb, self.foreground_rgba, self.placement)
        self.canvas.set_image(self.result_rgb)
        self.canvas.set_placement((self.placement.center_x, self.placement.center_y), self.placement.scale, box)
        self.mode_label.setText("当前模式：柱面" if self.placement.surface == "cylinder" else "当前模式：平面")

    def _canvas_preview(self, center: object, scale: float) -> None:
        x, y = center
        self.placement = replace(self.placement, center_x=float(x), center_y=float(y), scale=float(np.clip(scale, 0.05, 4.0)))
        self._render()

    def _canvas_commit(self, center: object, scale: float) -> None:
        self._canvas_preview(center, scale)
        self._record_commit(self._committed_placement)

    def _slider_pressed(self) -> None:
        self._slider_start = self._committed_placement

    def _control_preview(self) -> None:
        self.placement = replace(
            self.placement,
            rotation_degrees=float(self.rotation_slider.value()),
            opacity=self.opacity_slider.value() / 100.0,
            curvature=self.curvature_slider.value() / 100.0,
            harmonize=self.harmonize_slider.value() / 100.0,
        )
        self._render()

    def _slider_released(self) -> None:
        self._control_preview()
        self._record_commit(self._slider_start)

    def _surface_changed(self) -> None:
        if self.background_rgb is None:
            return
        previous = self._committed_placement
        self.placement = replace(self.placement, surface=str(self.surface_combo.currentData()))
        self._render()
        if self.foreground_rgba is not None:
            self._record_commit(previous)

    def commit_current_operation(self) -> None:
        if self.background_rgb is None or self.foreground_rgba is None:
            QMessageBox.information(self, "素材不完整", "请先读取背景图像和前景图像。")
            return
        self._render()
        self._record_commit(self._committed_placement)

    def _record_commit(self, previous: StickerPlacement) -> None:
        if self.background_rgb is None or self.foreground_rgba is None:
            return
        self.undo_stack.append(previous)
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)
        self._committed_placement = self.placement
        self.interaction_count += 1
        self.state_label.setText(f"状态：第 {self.interaction_count} 次透视变换与图像融合完成")
        self._refresh_actions()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        self.placement = self.undo_stack.pop()
        self._committed_placement = self.placement
        self._sync_controls_from_placement()
        self._render()
        self.state_label.setText("状态：已撤销到上一个贴图状态（历史交互次数保持）")
        self._refresh_actions()

    def reset_experiment(self) -> None:
        if self.background_rgb is None:
            return
        scale = 0.45
        if self.foreground_rgba is not None:
            scale = float(np.clip(self.background_rgb.shape[1] * 0.30 / max(1, self.foreground_rgba.shape[1]), 0.08, 2.5))
        self.placement = StickerPlacement(self.background_rgb.shape[1] / 2, self.background_rgb.shape[0] / 2, scale=scale)
        self._committed_placement = self.placement
        self.interaction_count = 0
        self.undo_stack.clear()
        self._sync_controls_from_placement()
        self._render()
        self.clock.start(reset=True)
        self.state_label.setText("状态：实验已重置，位置、大小、时间与次数已归零")
        self._refresh_actions()

    def _sync_controls_from_placement(self) -> None:
        widgets = (self.surface_combo, self.rotation_slider, self.opacity_slider, self.curvature_slider, self.harmonize_slider)
        for widget in widgets:
            widget.blockSignals(True)
        self.surface_combo.setCurrentIndex(1 if self.placement.surface == "cylinder" else 0)
        self.rotation_slider.setValue(int(round(self.placement.rotation_degrees)))
        self.opacity_slider.setValue(int(round(self.placement.opacity * 100)))
        self.curvature_slider.setValue(int(round(self.placement.curvature * 100)))
        self.harmonize_slider.setValue(int(round(self.placement.harmonize * 100)))
        for widget in widgets:
            widget.blockSignals(False)

    def save_all(self) -> None:
        if self.result_rgb is None or self.background_rgb is None or self.foreground_rgba is None:
            QMessageBox.information(self, "暂无结果", "请先完成背景与前景贴图。")
            return
        directory = QFileDialog.getExistingDirectory(self, "选择测试 3 保存目录", str(ROOT / "results"))
        if not directory:
            return
        self.clock.pause()
        output = Path(directory) / "test3_surface_sticker"
        output.mkdir(parents=True, exist_ok=True)
        try:
            write_png(output / "test3_result.png", cv2.cvtColor(self.result_rgb, cv2.COLOR_RGB2BGR))
            write_png(output / "test3_background.png", cv2.cvtColor(self.background_rgb, cv2.COLOR_RGB2BGR))
            write_png(output / "test3_foreground.png", cv2.cvtColor(self.foreground_rgba, cv2.COLOR_RGBA2BGRA))
            if not self.grab().save(str(output / "test3_ui.png"), "PNG"):
                raise OSError("界面截图保存失败")
            metadata = {
                "test": 3,
                "title": "平面 / 柱面贴图",
                "background": self.background_path.name if self.background_path else None,
                "foreground": self.foreground_name,
                "elapsed_seconds": round(self.clock.elapsed_ms() / 1000.0, 3),
                "interaction_count": self.interaction_count,
                "placement": asdict(self.placement),
                "algorithm": "OpenCV affine/cylindrical remap + alpha blend",
                "gpu_used": False,
                "opencl_enabled": bool(cv2.ocl.useOpenCL()),
                "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            (output / "test3_experiment.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ImageIOError) as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            self.clock.resume()
            return
        self.state_label.setText(f"状态：测试 3 结果已保存到 {output}")
        QMessageBox.information(self, "保存完成", f"已保存结果、背景、透明前景、界面截图和 JSON。\n\n{output}")

    def _update_time(self, elapsed_ms: int) -> None:
        self.time_label.setText(f"操作时间：{elapsed_ms / 1000.0:.1f} s")

    def _refresh_actions(self) -> None:
        has_background = self.background_rgb is not None
        has_both = has_background and self.foreground_rgba is not None
        self.undo_button.setEnabled(bool(self.undo_stack))
        self.reset_button.setEnabled(has_background)
        self.apply_button.setEnabled(has_both)
        self.save_button.setEnabled(has_both)
        self.count_label.setText(f"交互次数：{self.interaction_count}")
