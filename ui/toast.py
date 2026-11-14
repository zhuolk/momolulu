"""气泡提示：无焦点、鼠标穿透的小提示窗（提醒/状态说明统一走这里）。

`Toast` 是一个独立顶层窗（`Qt.Tool`），带 `Qt.WindowTransparentForInput` 所以
不会抢键鼠焦点，也不影响用户在其他程序里的输入。

圆角、阴影与配色取自 `ui/theme.py`，与状态卡保持同一观感。
"""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFontMetrics, QPainter
from PyQt5.QtWidgets import QApplication, QLabel, QWidget

from ui.theme import PAD, SHADOW, STYLES, draw_card

TOAST_WIDTH = 220
TOAST_MAX_LINES = 4

ANCHOR_GAP = 8
DEFAULT_DURATION_MS = 6000


def _elide_lines(text: str, metrics: QFontMetrics, width: int, max_lines: int) -> str:
    """把 text 截断到最多 max_lines 行（按 width 自动换行），超出用省略号。"""
    limit = max_lines * metrics.lineSpacing()
    if metrics.boundingRect(QRect(0, 0, width, 0), Qt.TextWordWrap, text).height() <= limit:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        probe = text[:mid] + "…"
        if metrics.boundingRect(QRect(0, 0, width, 0), Qt.TextWordWrap, probe).height() <= limit:
            low = mid
        else:
            high = mid - 1
    return text[:low] + "…"


class Toast(QWidget):
    """无边框、置顶、鼠标穿透的气泡窗；同一实例可反复 `show_message`。"""

    dismissed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._text = ""
        self._kind = "info"
        self._timer: QTimer | None = None

        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(TOAST_WIDTH)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.NoTextInteraction)
        self._label.setStyleSheet(f"color: {STYLES['info']['text']};")

        self._apply_style()
        self._relayout()

    # ------------------------------------------------------------ 属性

    @property
    def current_text(self) -> str:
        return self._text

    @property
    def kind(self) -> str:
        return self._kind

    # ------------------------------------------------------------ 对外接口

    def show_message(
        self,
        text: str,
        duration_ms: int = DEFAULT_DURATION_MS,
        anchor: tuple[int, int] | None = None,
        kind: str = "info",
    ) -> None:
        """显示气泡；`anchor` 给定时浮在锚点上方 8px 居中，`duration_ms` 后自动关闭。"""
        self._text = str(text)
        self._kind = kind if kind in STYLES else "info"
        self._apply_style()
        self._relayout()
        if anchor is not None:
            self._move_above_anchor(int(anchor[0]), int(anchor[1]))

        self.show()
        self.raise_()

        if self._timer is not None:
            self._timer.stop()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self._timer.start(max(0, int(duration_ms)))

    def move_above_anchor(self, x: int, y: int) -> None:
        """公开的定位入口（供桌宠在移动时跟随气泡）。"""
        self._move_above_anchor(int(x), int(y))

    # ------------------------------------------------------------ 内部实现

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()

    def _apply_style(self) -> None:
        self._label.setStyleSheet(f"color: {STYLES[self._kind]['text']};")
        self.update()

    def _relayout(self) -> None:
        metrics = QFontMetrics(self._label.font())
        text_w = TOAST_WIDTH - 2 * SHADOW - 2 * PAD
        shown = _elide_lines(self._text, metrics, text_w, TOAST_MAX_LINES)
        self._label.setText(shown)
        self._label.setFixedWidth(text_w)
        text_h = max(
            metrics.boundingRect(QRect(0, 0, text_w, 0), Qt.TextWordWrap, shown).height(),
            metrics.lineSpacing(),
        )
        card_h = text_h + 2 * PAD
        self.setFixedSize(TOAST_WIDTH, card_h + 2 * SHADOW)
        self._label.setGeometry(SHADOW + PAD, SHADOW + PAD, text_w, text_h)

    def _move_above_anchor(self, anchor_x: int, anchor_y: int) -> None:
        x = anchor_x - self.width() // 2
        y = anchor_y - self.height() - ANCHOR_GAP
        screen = QApplication.screenAt(QPoint(anchor_x, anchor_y))
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left(), min(x, area.right() - self.width() + 1))
            y = max(area.top(), min(y, area.bottom() - self.height() + 1))
        self.move(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        card = QRectF(SHADOW, SHADOW, self.width() - 2 * SHADOW, self.height() - 2 * SHADOW)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        draw_card(painter, card, self._kind)
        painter.end()
