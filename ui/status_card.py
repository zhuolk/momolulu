"""状态卡：用彩色进度条展示心情 / 活力 / 饱腹 + 噜噜币 / 上班状态。

托盘的原生悬停提示（`QSystemTrayIcon.setToolTip`）只能是一行纯文字，画不出进度条，
所以数值可视化另起一个自绘顶层窗（`StatusCard`）：不抢焦点、鼠标穿透
（`WindowTransparentForInput`），弹出若干秒后自动收起，期间数值每次心跳都会刷新。

右键菜单顶部也放一份同款进度条（`StatusHeader`），观感与卡片一致。
圆角、阴影与配色取自 `ui/theme.py`。
"""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from ui.theme import (
    BORDER,
    LABEL_COLOR,
    NOTE_COLOR,
    PAD,
    SHADOW,
    TITLE_COLOR,
    TRACK_COLOR,
    VALUE_COLOR,
    draw_card,
    qcolor,
)

CARD_WIDTH = 250
TITLE_HEIGHT = 18
ROW_HEIGHT = 26
BAR_HEIGHT = 9
GAP = 8
DURATION_MS = 8000

TITLE_TEXT = "噜噜的状态"
# (取值属性名, 文案)
ROWS = (("mood", "心情"), ("energy", "活力"), ("satiety", "饱腹"))

_LABEL_WIDTH = 42
_VALUE_WIDTH = 36
_BAR_GAP = 8

# 菜单顶部摘要条宽度（与卡片正文区等宽）
HEADER_WIDTH = CARD_WIDTH - 2 * (SHADOW + PAD)


def level_color(value: float) -> QColor:
    """按阈值给数值挑颜色：偏低偏红，健康偏绿。"""
    if value < 30:
        return QColor("#E5484D")
    if value < 60:
        return QColor("#F5A524")
    if value < 85:
        return QColor("#46A758")
    return QColor("#30A46C")


def note_text(working: bool, earned: int, coins: float) -> str:
    """底部一行：上班中显示本班进账，否则显示余额。"""
    if working:
        return f"上班中 · 已赚 {int(earned)} 噜噜币"
    return f"噜噜币 {int(coins)}"


def header_height() -> int:
    """菜单摘要条高度（标题 + 三行数值 + 备注）。"""
    return TITLE_HEIGHT + GAP + ROW_HEIGHT * len(ROWS) + GAP + TITLE_HEIGHT


def card_height() -> int:
    """卡片总高（含阴影留白）。"""
    return 2 * SHADOW + 2 * PAD + header_height() + (GAP - 2) + GAP


def _font_of(base: QFont, point_size: float, bold: bool) -> QFont:
    font = QFont(base)
    font.setPointSizeF(point_size)
    font.setBold(bold)
    return font


def _paint_title(painter: QPainter, x: float, y: float, width: float, font) -> float:
    """画小标题，返回下一行的 y。"""
    painter.setPen(qcolor(TITLE_COLOR))
    painter.setFont(font(9.0, False))
    painter.drawText(
        QRect(int(x), int(y), int(width), TITLE_HEIGHT),
        Qt.AlignLeft | Qt.AlignVCenter,
        TITLE_TEXT,
    )
    return y + TITLE_HEIGHT + GAP


def _paint_rows(painter: QPainter, x: float, y: float, width: float, values, font) -> float:
    """画三行「标签 + 渐变进度条 + 数值」，返回下一行的 y。"""
    label_w, value_w = _LABEL_WIDTH, _VALUE_WIDTH
    bar_w = width - label_w - value_w - 2 * _BAR_GAP
    for (_key, label), value in zip(ROWS, values):
        value = float(value)

        painter.setPen(qcolor(LABEL_COLOR))
        painter.setFont(font(9.5, False))
        painter.drawText(
            QRect(int(x), int(y), label_w, ROW_HEIGHT), Qt.AlignLeft | Qt.AlignVCenter, label
        )

        bar_x = x + label_w + _BAR_GAP
        bar_y = y + (ROW_HEIGHT - BAR_HEIGHT) // 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(qcolor(TRACK_COLOR))
        painter.drawRoundedRect(
            QRectF(bar_x, bar_y, bar_w, BAR_HEIGHT), BAR_HEIGHT / 2, BAR_HEIGHT / 2
        )

        ratio = max(0.0, min(1.0, value / 100.0))
        fill_w = bar_w * ratio
        if fill_w > 0.5:
            colour = level_color(value)
            gradient = QLinearGradient(bar_x, 0.0, bar_x + bar_w, 0.0)
            gradient.setColorAt(0.0, colour.lighter(135))
            gradient.setColorAt(1.0, colour)
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                QRectF(bar_x, bar_y, max(fill_w, BAR_HEIGHT), BAR_HEIGHT),
                BAR_HEIGHT / 2,
                BAR_HEIGHT / 2,
            )

        painter.setPen(qcolor(VALUE_COLOR))
        painter.setFont(font(9.5, False))
        painter.drawText(
            QRect(int(x + width - value_w), int(y), value_w, ROW_HEIGHT),
            Qt.AlignRight | Qt.AlignVCenter,
            str(int(round(value))),
        )
        y += ROW_HEIGHT
    return y


def _paint_note(painter: QPainter, x: float, y: float, width: float, text: str, font) -> None:
    painter.setPen(qcolor(NOTE_COLOR))
    painter.setFont(font(9.5, True))
    painter.drawText(
        QRect(int(x), int(y), int(width), TITLE_HEIGHT), Qt.AlignLeft | Qt.AlignVCenter, text
    )


class _VitalsView:
    """三类数值（心情 / 活力 / 饱腹）在卡片与菜单摘要条之间共用的一份读写。"""

    _mood = 0.0
    _energy = 0.0
    _satiety = 0.0
    _coins = 0.0
    _working = False
    _earned = 0

    def _store(self, mood: float, energy: float, satiety: float, coins, working, earned) -> None:
        self._mood = float(mood)
        self._energy = float(energy)
        self._satiety = float(satiety)
        self._coins = float(coins)
        self._working = bool(working)
        self._earned = int(earned)

    def _values(self) -> list[float]:
        return [getattr(self, f"_{key}") for key, _label in ROWS]

    def note_text(self) -> str:
        """底部一行：上班中显示本班进账，否则显示余额。"""
        return note_text(self._working, self._earned, self._coins)


class StatusCard(_VitalsView, QWidget):
    """自绘浮窗状态卡；同一实例可反复 `show_near`。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._store(0, 0, 0, 0, False, 0)
        self._timer: QTimer | None = None

        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(CARD_WIDTH, card_height())

    # ------------------------------------------------------------ 对外接口

    def set_state(
        self, mood: float, energy: float, satiety: float, coins, working: bool, earned: int
    ) -> None:
        """写入要展示的数值；已显示时立即重绘。"""
        self._store(mood, energy, satiety, coins, working, earned)
        if self.isVisible():
            self.update()

    def show_near(self, anchor_x: int, anchor_y: int) -> None:
        """浮在锚点上方并居中；`DURATION_MS` 后自动收起。"""
        self.update()
        self.show()
        self.raise_()
        self._move_above(int(anchor_x), int(anchor_y))

        if self._timer is not None:
            self._timer.stop()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._timer.start(DURATION_MS)

    # ------------------------------------------------------------ 内部实现

    def _font(self, point_size: float, bold: bool) -> QFont:
        return _font_of(self.font(), point_size, bold)

    def _move_above(self, anchor_x: int, anchor_y: int) -> None:
        x = anchor_x - self.width() // 2
        y = anchor_y - self.height() - GAP
        screen = QApplication.screenAt(QPoint(anchor_x, anchor_y))
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left(), min(x, area.right() - self.width() + 1))
            y = max(area.top(), min(y, area.bottom() - self.height() + 1))
        self.move(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        card = QRectF(SHADOW, SHADOW, self.width() - 2 * SHADOW, self.height() - 2 * SHADOW)
        draw_card(painter, card)

        inner_x = SHADOW + PAD
        inner_w = CARD_WIDTH - 2 * (SHADOW + PAD)
        y = _paint_title(painter, inner_x, SHADOW + PAD, inner_w, self._font)
        y = _paint_rows(painter, inner_x, y, inner_w, self._values(), self._font)

        y += GAP - 2
        painter.setPen(QPen(qcolor(BORDER), 1))
        painter.drawLine(QPoint(int(inner_x), int(y)), QPoint(int(inner_x + inner_w), int(y)))
        _paint_note(painter, inner_x, y + GAP, inner_w, self.note_text(), self._font)
        painter.end()


class StatusHeader(_VitalsView, QWidget):
    """右键菜单顶部的数值摘要：与状态卡同款进度条，但不画卡片边框与阴影。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._store(0, 0, 0, 0, False, 0)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(HEADER_WIDTH, header_height())

    def set_state(
        self, mood: float, energy: float, satiety: float, coins, working: bool, earned: int
    ) -> None:
        """写入要展示的数值并重绘。"""
        self._store(mood, energy, satiety, coins, working, earned)
        self.update()

    def _font(self, point_size: float, bold: bool) -> QFont:
        return _font_of(self.font(), point_size, bold)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        y = _paint_title(painter, 0, 0, self.width(), self._font)
        y = _paint_rows(painter, 0, y, self.width(), self._values(), self._font)
        _paint_note(painter, 0, y + GAP, self.width(), self.note_text(), self._font)
        painter.end()
