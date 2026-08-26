"""界面工具和 GrabCut 标记常量。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DrawingTool(str, Enum):
    LINE = "line"
    RECTANGLE = "rectangle"
    SQUARE = "square"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    PENTAGON = "pentagon"
    HEXAGON = "hexagon"
    POLYGON = "polygon"
    BRUSH = "brush"


@dataclass(frozen=True)
class ToolInfo:
    text: str
    shortcut: str


TOOL_INFO: dict[DrawingTool, ToolInfo] = {
    DrawingTool.LINE: ToolInfo("直线", "L"),
    DrawingTool.RECTANGLE: ToolInfo("矩形", "R"),
    DrawingTool.SQUARE: ToolInfo("正方形", "S"),
    DrawingTool.CIRCLE: ToolInfo("圆", "C"),
    DrawingTool.ELLIPSE: ToolInfo("椭圆", "E"),
    DrawingTool.PENTAGON: ToolInfo("五边形", "5"),
    DrawingTool.HEXAGON: ToolInfo("六边形", "6"),
    DrawingTool.POLYGON: ToolInfo("任意多边形", "P"),
    DrawingTool.BRUSH: ToolInfo("涂抹", "B"),
}


class LabelMode(Enum):
    SURE_BACKGROUND = (0, "确定背景", (235, 72, 72))
    SURE_FOREGROUND = (1, "确定前景", (48, 205, 112))
    PROBABLE_BACKGROUND = (2, "可能背景", (255, 159, 67))
    PROBABLE_FOREGROUND = (3, "可能前景", (54, 190, 220))

    @property
    def mask_value(self) -> int:
        return self.value[0]

    @property
    def text(self) -> str:
        return self.value[1]

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self.value[2]


LABEL_BY_VALUE = {mode.mask_value: mode for mode in LabelMode}
