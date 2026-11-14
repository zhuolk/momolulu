"""状态卡：点托盘图标弹出的无边框圆角卡片，用彩色进度条展示心情 / 活力 / 饱腹。

托盘的原生悬停提示（`QSystemTrayIcon.setToolTip`）只能是一行纯文字，画不出进度条，
所以数值可视化另起一个自绘顶层窗：不抢焦点、鼠标穿透（`WindowTransparentForInput`），
弹出若干秒后自动收起，期间数值每次心跳都会刷新。

数值条按阈值变色（越健康越绿），并用横向渐变让填充更有质感。
"""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget

CARD_WIDTH = 250
RADIUS = 14
SHADOW = 14
PAD = 14
TITLE_HEIGHT = 18
ROW_HEIGHT = 26
BAR_HEIGHT = 9
GAP = 8
DURATION_MS = 8000

TITLE_TEXT = "噜噜的状态"
# (取值属性名, 文案)
ROWS = (("mood", "心情"), ("energy", "活力"), ("satiety", "饱腹"))

_BG = "#FFFFFFF2"
_BORDER = "#00000014"
_TITLE_COLOR = "#8A8A8A"
_LABEL_COLOR = "#4A4A4A"
_VALUE_COLOR = "#222222"
_TRACK_COLOR = "#00000014"
_NOTE_COLOR = "#333333"

_LABEL_WIDTH = 42
_VALUE_WIDTH = 36
_BAR_GAP = 8


def level_color(value: float) -> QColor:
    """按阈值给数值挑颜色：偏低偏红，健康偏绿。"""
    if value < 30:
        return QColor("#E5484D")
    if value < 60:
        return QColor("#F5A524")
    if value < 85:
        return QColor("#46A758")
    return QColor("#30A46C")


def _qcolor(rgba: str) -> QColor:
    """解析 `#RRGGBBAA`（CSS 风格，末两位为 alpha）。"""
    text = rgba.lstrip("#")
    if len(text) == 8:
        r, g, b, a = (int(text[i : i + 2], 16) for i in (0, 2, 4, 6))
        return QColor(r, g, b, a)
    return QColor(rgba)


def card_height() -> int:
    """卡片总高（含阴影留白）。"""
    body = TITLE_HEIGHT + GAP + ROW_HEIGHT * len(ROWS) + (GAP - 2) + GAP + TITLE_HEIGHT
    return 2 * SHADOW + 2 * PAD + body


class StatusCard(QWidget):
    """数值状态卡；同一实例可反复 `show_near`。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._mood = 0.0
        self._energy = 0.0
        self._satiety = 0.0
        self._coins = 0.0
        self._working = False
        self._earned = 0
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
        self,
        mood: float,
        energy: float,
        satiety: float,
        coins: float,
        working: bool,
        earned: int,
    ) -> None:
        """写入要展示的数值；已显示时立即重绘。"""
        self._mood = float(mood)
        self._energy = float(energy)
        self._satiety = float(satiety)
        self._coins = float(coins)
        self._working = bool(working)
        self._earned = int(earned)
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

    def note_text(self) -> str:
        """底部一行：上班中显示本班进账，否则显示余额。"""
        if self._working:
            return f"上班中 · 已赚 {self._earned} 噜噜币"
        return f"噜噜币 {int(self._coins)}"

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

        shadow = QColor(0, 0, 0)
        painter.setPen(Qt.NoPen)
        for step in range(SHADOW, 0, -1):
            ratio = (SHADOW - step) / SHADOW
            alpha = int(60 * ratio * ratio / 3)
            if alpha <= 0:
                continue
            painter.setBrush(QColor(shadow.red(), shadow.green(), shadow.blue(), alpha))
            painter.drawRoundedRect(
                card.adjusted(-step + 2, -step + 5, step, step),
                RADIUS + step,
                RADIUS + step,
            )

        painter.setBrush(_qcolor(_BG))
        painter.drawRoundedRect(card, RADIUS, RADIUS)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(_qcolor(_BORDER), 1))
        painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

        inner_x = SHADOW + PAD
        inner_w = CARD_WIDTH - 2 * (SHADOW + PAD)
        y = SHADOW + PAD

        painter.setPen(_qcolor(_TITLE_COLOR))
        painter.setFont(self._font(9.0, bold=False))
        painter.drawText(
            QRect(inner_x, y, inner_w, TITLE_HEIGHT),
            Qt.AlignLeft | Qt.AlignVCenter,
            TITLE_TEXT,
        )
        y += TITLE_HEIGHT + GAP

        label_w, value_w = _LABEL_WIDTH, _VALUE_WIDTH
        bar_w = inner_w - label_w - value_w - 2 * _BAR_GAP
        for key, label in ROWS:
            value = float(getattr(self, f"_{key}"))

            painter.setPen(_qcolor(_LABEL_COLOR))
            painter.setFont(self._font(9.5, bold=False))
            painter.drawText(
                QRect(inner_x, y, label_w, ROW_HEIGHT), Qt.AlignLeft | Qt.AlignVCenter, label
            )

            bar_x = inner_x + label_w + _BAR_GAP
            bar_y = y + (ROW_HEIGHT - BAR_HEIGHT) // 2
            painter.setPen(Qt.NoPen)
            painter.setBrush(_qcolor(_TRACK_COLOR))
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

            painter.setPen(_qcolor(_VALUE_COLOR))
            painter.setFont(self._font(9.5, bold=False))
            painter.drawText(
                QRect(inner_x + inner_w - value_w, y, value_w, ROW_HEIGHT),
                Qt.AlignRight | Qt.AlignVCenter,
                str(int(round(value))),
            )
            y += ROW_HEIGHT

        y += GAP - 2
        painter.setPen(QPen(_qcolor(_BORDER), 1))
        painter.drawLine(QPoint(int(inner_x), int(y)), QPoint(int(inner_x + inner_w), int(y)))
        y += GAP

        painter.setPen(_qcolor(_NOTE_COLOR))
        painter.setFont(self._font(9.5, bold=True))
        painter.drawText(
            QRect(inner_x, y, inner_w, TITLE_HEIGHT),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.note_text(),
        )
        painter.end()

    def _font(self, point_size: float, bold: bool) -> QFont:
        font = QFont(self.font())
        font.setPointSizeF(point_size)
        font.setBold(bold)
        return font
