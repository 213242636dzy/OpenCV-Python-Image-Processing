"""跨平台应用字体安装。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


_FONT_ID: int | None = None
_FONT_FAMILY: str | None = None


def install_bundled_ui_font(app: QApplication) -> str:
    """安装包含本软件全部中英文界面字符的 OFL 字体子集。"""
    global _FONT_ID, _FONT_FAMILY
    if _FONT_FAMILY is None:
        font_path = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSansCJKsc-UI-Subset.otf"
        _FONT_ID = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(_FONT_ID) if _FONT_ID >= 0 else []
        if not families:
            raise RuntimeError(f"无法加载随软件提供的中文字体：{font_path}")
        _FONT_FAMILY = families[0]

    current = app.font()
    font = QFont(_FONT_FAMILY)
    if current.pointSizeF() > 0:
        font.setPointSizeF(current.pointSizeF())
    app.setFont(font)
    return _FONT_FAMILY
