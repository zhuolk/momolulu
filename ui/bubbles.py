"""吹泡泡时覆盖当前屏幕的透明动画，不接管鼠标或键盘。"""

import math
import random

from PyQt5.QtCore import QElapsedTimer, QPointF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class BubbleOverlay(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self._targets = []

    def start(self, screen_rect, origin, duration_ms):
        self.setGeometry(screen_rect)
        self._origin = origin - screen_rect.topLeft()
        self._duration = duration_ms
        rng = random.Random()
        # 每格一个落点并打乱出场顺序，既能散到四角，又不会排成整齐的队列。
        cols, rows = 12, 8
        self._targets = [
            ((col + rng.uniform(.2, .8)) * self.width() / cols,
             (row + rng.uniform(.2, .8)) * self.height() / rows,
             rng.uniform(.011, .034) * min(self.width(), self.height()),
             rng.uniform(0, math.tau), rng.choice((185, 205, 265, 315)))
            for row in range(rows) for col in range(cols)
        ]
        rng.shuffle(self._targets)
        self._clock.start()
        self.show()
        self.update()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()
        self._targets.clear()

    def _advance(self):
        if self._clock.elapsed() >= self._duration:
            self.stop()
        else:
            self.update()

    def _particles(self, progress):
        for i, (tx, ty, radius, phase, hue) in enumerate(self._targets):
            age = progress - .5 * i / len(self._targets)
            if age < 0:
                break
            travel = 1 - (1 - min(1, age / .32)) ** 2
            sway = math.sin(phase + age * 11) * radius * travel
            x = self._origin.x() + (tx - self._origin.x()) * travel + sway
            y = self._origin.y() + (ty - self._origin.y()) * travel
            y -= math.sin(travel * math.pi) * self.height() * .07 + sway * .45
            yield QPointF(x, y), radius * (.18 + .82 * travel), hue

    def paintEvent(self, event):
        if not self._targets:
            return
        progress = self._clock.elapsed() / self._duration
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(max(0., min(1., (1 - progress) / .14)))
        for center, radius, hue in self._particles(progress):
            painter.setBrush(QColor.fromHsv(hue, 80, 255, 58))
            painter.setPen(QPen(QColor.fromHsv(hue, 100, 255, 185), 1.6))
            painter.drawEllipse(center, radius, radius)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 205))
            painter.drawEllipse(center - QPointF(radius * .38, radius * .42),
                                radius * .2, radius * .12)
