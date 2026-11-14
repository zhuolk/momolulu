"""界面统一风格：调色板、圆角阴影卡片画法、右键菜单样式表。

状态卡（`ui/status_card.py`）、气泡（`ui/toast.py`）、更新确认窗（`ui/update_prompt.py`）、
右键菜单（`ui/menu.py`）共用这一套常量与画法——改这里，几处观感一起变。
"""

from __future__ import annotations

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen

# 圆角卡片几何（阴影留白 / 圆角 / 内边距）
RADIUS = 14
SHADOW = 14
PAD = 14

# 卡片 / 气泡共用的调色板（`#RRGGBBAA`，末两位为 alpha）
BG = "#FFFFFFF2"
BORDER = "#00000014"
TITLE_COLOR = "#8A8A8A"
LABEL_COLOR = "#4A4A4A"
VALUE_COLOR = "#222222"
TRACK_COLOR = "#00000014"
NOTE_COLOR = "#333333"
TEXT_COLOR = "#333333"

# 气泡样式：info 常规 / warn 提醒
STYLES = {
    "info": {"bg": BG, "border": BORDER, "text": TEXT_COLOR},
    "warn": {"bg": "#FFF6E5F2", "border": "#D9832440", "text": "#8A5A00"},
}


def qcolor(rgba: str) -> QColor:
    """解析 `#RRGGBBAA`（CSS 风格，末两位为 alpha）。"""
    text = rgba.lstrip("#")
    if len(text) == 8:
        r, g, b, a = (int(text[i : i + 2], 16) for i in (0, 2, 4, 6))
        return QColor(r, g, b, a)
    return QColor(rgba)


def draw_card(painter: QPainter, rect: QRectF, kind: str = "info") -> None:
    """画「柔和阴影 + 圆角底 + 细边」，与状态卡同款；`kind` 取 `STYLES` 的键。"""
    style = STYLES.get(kind, STYLES["info"])
    painter.setPen(Qt.NoPen)
    for step in range(SHADOW, 0, -1):
        ratio = (SHADOW - step) / SHADOW
        alpha = int(60 * ratio * ratio / 3)
        if alpha <= 0:
            continue
        painter.setBrush(QColor(0, 0, 0, alpha))
        painter.drawRoundedRect(
            rect.adjusted(-step + 2, -step + 5, step, step), RADIUS + step, RADIUS + step
        )
    painter.setBrush(qcolor(style["bg"]))
    painter.drawRoundedRect(rect, RADIUS, RADIUS)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(qcolor(style["border"]), 1))
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)


def menu_style() -> str:
    """右键菜单样式表：留白、悬停高亮、分隔线都取卡片同一套配色。

    QSS 不认 `#RRGGBBAA`（会按 `#AARRGGBB` 解析），所以这里一律写 `rgba()`。

    注意：**这张表里不能出现 `border-radius`**（面板或 `::item` 都不行）。本机 `QStyleSheetStyle`
    处理圆角时会写坏堆，之后任意一次 `show()`（例如 `Sprite.show()`）直接报 access violation，
    表现为全量测试跑到一半整个进程崩掉。回归护栏见 `tests/test_theme.py`。
    菜单的圆角改由窗口 mask 提供（见 `ui/menu.CardMenu`）。
    """
    return f"""
QMenu {{
    background-color: rgba(255, 255, 255, 242);
    border: 1px solid rgba(0, 0, 0, 22);
    padding: 6px;
    color: {TEXT_COLOR};
}}
QMenu::item {{
    padding: 6px 18px;
    color: {TEXT_COLOR};
}}
QMenu::item:selected {{
    background-color: rgba(70, 167, 88, 0.16);
    color: #1F7A3D;
}}
QMenu::item:disabled {{
    color: #AAAAAA;
}}
QMenu::separator {{
    height: 1px;
    background: rgba(0, 0, 0, 20);
    margin: 5px 12px;
}}
QMenu::right-arrow {{
    width: 10px;
    height: 10px;
    margin-right: 8px;
}}
""".strip()
