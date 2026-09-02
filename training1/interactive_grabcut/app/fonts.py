"""跨平台应用字体安装。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


_FONT_SPECS: tuple[tuple[str, str], ...] = (
    ("现代黑体", "NotoSansCJKsc-Regular.otf"),
    ("典雅宋体", "NotoSerifSC-VF.ttf"),
    ("马善政毛笔艺术字", "MaShanZheng-Regular.ttf"),
    ("站酷小薇艺术字", "ZCOOLXiaoWei-Regular.ttf"),
    ("龙藏书法艺术字", "LongCang-Regular.ttf"),
)
_FONT_IDS: dict[str, int] = {}
_FONT_FAMILIES: dict[str, str] = {}


def install_bundled_ui_font(app: QApplication) -> str:
    """安装五套 OFL 中文字体，供界面和路径文字使用。"""
    font_root = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    if not _FONT_FAMILIES:
        for label, filename in _FONT_SPECS:
            font_path = font_root / filename
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            if not families:
                raise RuntimeError(f"无法加载随软件提供的中文字体：{font_path}")
            _FONT_IDS[label] = font_id
            _FONT_FAMILIES[label] = families[0]

    current = app.font()
    default_family = _FONT_FAMILIES[_FONT_SPECS[0][0]]
    font = QFont(default_family)
    if current.pointSizeF() > 0:
        font.setPointSizeF(current.pointSizeF())
    app.setFont(font)
    return default_family


def creative_font_options() -> tuple[tuple[str, str], ...]:
    """返回用户可选的五个真实中文字体家族。"""
    if not _FONT_FAMILIES:
        raise RuntimeError("必须先调用 install_bundled_ui_font")
    return tuple((label, _FONT_FAMILIES[label]) for label, _ in _FONT_SPECS)
