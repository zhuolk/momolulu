"""更新确认小窗：复用 Toast 的圆角卡片画法，但可点击（不设 WindowTransparentForInput）。"""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.toast import PAD, SHADOW, STYLES, TOAST_RADIUS, _qcolor

PROMPT_WIDTH = 240
TITLE = "有新版本，要现在更新吗"
BUSY_TEXT = "正在下载…"


class UpdatePrompt(QWidget):
    """跟随噜噜的更新确认窗；点「现在更新」发 `accepted`，点「稍后」发 `declined`。"""

    accepted = pyqtSignal()
    declined = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._version = ""
        self._notes = ""
        self._status = ""
        self._busy = False

        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(PROMPT_WIDTH)

        self._title = QLabel(TITLE, self)
        font = self._title.font()
        font.setBold(True)
        self._title.setFont(font)

        self._body = QLabel("", self)
        self._body.setWordWrap(True)
        self._body.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self._later = QPushButton("稍后", self)
        self._now = QPushButton("现在更新", self)
        self._later.clicked.connect(self._decline)
        self._now.clicked.connect(self._accept)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._later)
        row.addWidget(self._now)

        column = QVBoxLayout(self)
        column.setContentsMargins(SHADOW + PAD, SHADOW + PAD, SHADOW + PAD, SHADOW + PAD)
        column.addWidget(self._title)
        column.addWidget(self._body)
        column.addLayout(row)

        self._refresh()

    # ------------------------------------------------------------ 对外接口

    @property
    def is_busy(self) -> bool:
        return self._busy

    def current_version(self) -> str:
        return self._version

    def body_text(self) -> str:
        return self._body.text()

    def show_version(self, version: str, notes: str = "", anchor=None) -> None:
        self._version = str(version)
        self._notes = str(notes or "")
        self._busy = False
        self._status = ""
        self._refresh()
        self.show()
        self.raise_()
        if anchor is not None:
            self._move_near_anchor(int(anchor[0]), int(anchor[1]))

    def set_busy(self, busy: bool, text: str = "") -> None:
        """置忙时按钮失效并显示进度；传 `text` 可同时给出结果文案（如失败原因）。"""
        self._busy = bool(busy)
        self._status = str(text) if text else (BUSY_TEXT if self._busy else "")
        self._refresh()

    # ------------------------------------------------------------ 内部实现

    def _accept(self) -> None:
        if self._busy:
            return
        # 不 hide()：下载期间要靠这个窗口显示「正在下载…」与失败提示（设计 §7.4），
        # 隐藏由调用方在下载成功、准备退出重启时负责。
        self.accepted.emit()

    def _decline(self) -> None:
        if self._busy:
            return
        self.hide()
        self.declined.emit()

    def _refresh(self) -> None:
        lines = [f"新版本 {self._version}"] if self._version else []
        if self._notes:
            lines.append(self._notes)
        if self._status:
            lines.append(self._status)
        self._body.setText("\n".join(lines))
        for button in (self._now, self._later):
            button.setEnabled(not self._busy)
        self._body.setStyleSheet(f"color: {STYLES['info']['text']};")
        self._title.setStyleSheet(f"color: {STYLES['info']['text']};")
        self.adjustSize()

    def _move_near_anchor(self, anchor_x: int, anchor_y: int) -> None:
        x = anchor_x - self.width() // 2
        y = anchor_y - self.height() - 8
        # screenAt 对屏幕外坐标返回 None（多屏死区、噜噜贴边时会出现），
        # 此时兜底到主屏，否则弹窗会落在谁都看不见的地方。
        screen = QApplication.screenAt(QPoint(anchor_x, anchor_y)) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left(), min(x, area.right() - self.width() + 1))
            y = max(area.top(), min(y, area.bottom() - self.height() + 1))
        self.move(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        style = STYLES["info"]
        card = QRectF(SHADOW, SHADOW, self.width() - 2 * SHADOW, self.height() - 2 * SHADOW)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        for step in range(SHADOW, 0, -1):
            ratio = (SHADOW - step) / SHADOW
            alpha = int(60 * ratio * ratio / 3)
            if alpha <= 0:
                continue
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(
                card.adjusted(-step + 2, -step + 5, step, step),
                TOAST_RADIUS + step,
                TOAST_RADIUS + step,
            )
        painter.setBrush(_qcolor(style["bg"]))
        painter.drawRoundedRect(card, TOAST_RADIUS, TOAST_RADIUS)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(_qcolor(style["border"]), 1))
        painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), TOAST_RADIUS, TOAST_RADIUS)
        painter.end()
