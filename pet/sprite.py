"""桌宠窗口：无边框透明置顶窗 + A/B 双轨渲染 + GIF 播放（LRU 缓存）+ 鼠标交互信号。

轨道 A（`transparent`）：GIF 自带透明通道，直接原样显示。
轨道 B（`card`）：给 GIF 套一层圆角卡片（圆角 + 描边 + 投影），遮掉去背不干净的背景。
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from collections import OrderedDict

from PIL import Image
from PyQt5.QtCore import QPoint, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QImage,
    QMovie,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
)
from PyQt5.QtWidgets import QWidget

from pet.catalog import pick, track_of
from pet.config import get

CARD_RADIUS = 16
CARD_BORDER = "#00000014"
CARD_SHADOW_BLUR = 24
CARD_SHADOW_COLOR = "#00000040"
MAX_MOVIE_CACHE = 3
DRAG_THRESHOLD = 4

PLACEHOLDER_SIZE = 160
STRIP_PX = 24  # 贴边隐藏缩回后，露在屏幕内的桔子窄条宽度
_CLICK_WINDOW_S = 5.0
_FAST_CLICK_COUNT = 5


def _qcolor(rgba: str) -> QColor:
    """解析 `#RRGGBBAA`（CSS 风格，末两位为 alpha），也接受 `#RRGGBB`。"""
    text = rgba.lstrip("#")
    if len(text) == 8:
        r, g, b, a = (int(text[i : i + 2], 16) for i in (0, 2, 4, 6))
        return QColor(r, g, b, a)
    return QColor(rgba)


def _qimage(rgba: Image.Image) -> QImage:
    """PIL RGBA 图 → QImage（自带内存副本，不依赖 Pillow 的 ImageQt 绑定）。"""
    data = rgba.tobytes("raw", "RGBA")
    return QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888).copy()


def _qimage_to_pil(image: QImage) -> Image.Image:
    """QImage → PIL RGBA 图。"""
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = converted.width(), converted.height()
    buffer = converted.constBits()
    buffer.setsize(converted.sizeInBytes())
    return Image.frombytes("RGBA", (width, height), bytes(buffer), "raw", "RGBA")


def render_frame(frame: Image.Image, track: str) -> QPixmap:
    """按轨道渲染单帧：透明轨直接转 QPixmap，卡片轨加圆角、描边与投影。"""
    if track != "card":
        return QPixmap.fromImage(_qimage(frame.convert("RGBA")))

    base = frame.convert("RGBA")
    width, height = base.size
    blur = CARD_SHADOW_BLUR
    canvas = QImage(width + 2 * blur, height + 2 * blur, QImage.Format_ARGB32)
    canvas.fill(Qt.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    shadow = _qcolor(CARD_SHADOW_COLOR)
    painter.setPen(Qt.NoPen)
    for step in range(blur, 0, -1):
        ratio = (blur - step) / blur
        alpha = int(shadow.alpha() * ratio * ratio / 3)
        if alpha <= 0:
            continue
        painter.setBrush(QColor(shadow.red(), shadow.green(), shadow.blue(), alpha))
        painter.drawRoundedRect(
            QRectF(
                blur - step + 2,
                blur - step + 6,
                width + 2 * step,
                height + 2 * step,
            ),
            CARD_RADIUS + step,
            CARD_RADIUS + step,
        )

    clip = QPainterPath()
    clip.addRoundedRect(QRectF(blur, blur, width, height), CARD_RADIUS, CARD_RADIUS)
    painter.setClipPath(clip)
    painter.drawImage(QRectF(blur, blur, width, height), _qimage(base))

    painter.setClipping(False)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(_qcolor(CARD_BORDER), 1))
    painter.drawRoundedRect(QRectF(blur, blur, width, height), CARD_RADIUS, CARD_RADIUS)
    painter.end()
    return QPixmap.fromImage(canvas)


def placeholder_pixmap(size: int = PLACEHOLDER_SIZE) -> QPixmap:
    """素材缺失时显示的占位图（灰底圆角 + `lulu` 字样）。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor("#EDEDED"))
    painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
    painter.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), CARD_RADIUS, CARD_RADIUS)
    painter.setPen(QColor("#9A9A9A"))
    font = painter.font()
    font.setPointSize(max(8, size // 6))
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "lulu")
    painter.end()
    return pixmap


class Sprite(QWidget):
    """桌宠主窗口。"""

    clicked = pyqtSignal()
    fast_clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    right_clicked = pyqtSignal(QPoint)
    drag_moved = pyqtSignal(QPoint)
    drag_finished = pyqtSignal(QPoint)
    moved = pyqtSignal()
    play_finished = pyqtSignal(str)
    asset_missing = pyqtSignal()

    def __init__(self, catalog_data: dict, processed_dir: Path, config: dict, parent=None):
        super().__init__(parent)
        self._catalog = catalog_data
        self._processed_dir = Path(processed_dir)
        self._config = config
        self._track = "transparent"
        self._render_track = "transparent"
        self._movies: "OrderedDict[str, QMovie]" = OrderedDict()
        self._current_movie: QMovie | None = None
        self._current_category: str | None = None
        self._current_pixmap: QPixmap | None = None
        self._frozen = False
        self._pressed = False
        self._dragging = False
        self._press_pos = QPoint()
        self._click_times: list[float] = []
        self._strip_side: str | None = None
        self._strip_px = STRIP_PX
        self._flipped = False
        self._rotation = 0

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setFixedSize(PLACEHOLDER_SIZE, PLACEHOLDER_SIZE)

    # ------------------------------------------------------------ 渲染

    def paintEvent(self, event):  # noqa: N802 (Qt 命名)
        if self._strip_side is not None:
            self._paint_strip()
            return
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        pixmap = self._current_pixmap
        if self._flipped:
            pixmap = QPixmap.fromImage(pixmap.toImage().mirrored(True, False))
        if self._rotation:
            pixmap = pixmap.transformed(QTransform().rotate(self._rotation))
        painter = QPainter(self)
        painter.drawPixmap(
            (self.width() - pixmap.width()) // 2,
            (self.height() - pixmap.height()) // 2,
            pixmap,
        )

    def _paint_strip(self) -> None:
        """在屏幕内的那一侧画桔子窄条（左侧隐藏贴窗口右缘，右侧隐藏贴窗口左缘）。

        不再画 GIF 切片：窗口只剩 48px 在屏内，居中构图的素材那一条通常全透明，
        用户会以为噜噜丢了。
        """
        badge = self.draw_orange(self._strip_px)
        painter = QPainter(self)
        x = self.width() - badge.width() if self._strip_side == "left" else 0
        painter.drawPixmap(x, (self.height() - badge.height()) // 2, badge)

    def current_frame_pixmap(self) -> QPixmap | None:
        return self._current_pixmap

    @property
    def strip_side(self) -> str | None:
        """贴边缩回时屏幕内那一侧（`"left"` / `"right"`），正常显示时为 `None`。"""
        return self._strip_side

    def set_strip(self, side: str | None, strip_px: int = STRIP_PX) -> None:
        """切换「贴边缩回」渲染：只画桔子窄条；传 `None` 恢复正常画素材。"""
        side = side if side in ("left", "right") else None
        self._strip_side = side
        self._strip_px = max(1, int(strip_px))
        self.update()

    def set_flip(self, flipped: bool) -> None:
        """水平镜像渲染（自动走动朝左时用），让噜噜转身而不是倒着走。"""
        flipped = bool(flipped)
        if flipped != self._flipped:
            self._flipped = flipped
            self.update()

    def set_rotation(self, deg: int) -> None:
        """整图顺时针旋转渲染（散步绕屏转弯时用），只接受 0/90/180/270。

        素材是正方形，转 90° 不改变画布长宽，窗口尺寸因此不用跟着调整。
        """
        deg = int(deg) % 360
        if deg not in (0, 90, 180, 270):
            deg = 0
        if deg != self._rotation:
            self._rotation = deg
            self.update()

    def _apply_pixmap(self, pixmap: QPixmap) -> None:
        self._current_pixmap = pixmap
        # 贴边缩回期间锁定窗口尺寸：素材换帧/换轨道（卡片轨比素材大一圈）会改窗口大小，
        # 而已滑到屏外的 x 是按隐藏时的尺寸算的，窗口一缩就可能整块留在屏外、看不见桔子。
        if self._strip_side is None and pixmap.size() != self.size():
            self.setFixedSize(pixmap.size())
        self.update()

    def _show_placeholder(self) -> None:
        self._apply_pixmap(placeholder_pixmap())

    # ------------------------------------------------------------ 播放

    def _scale(self) -> float:
        value = get(self._config, "pet.scale", 1.0)
        return float(value) if isinstance(value, (int, float)) and value > 0 else 1.0

    def _acquire_movie(self, path: Path) -> QMovie | None:
        key = str(path)
        movie = self._movies.get(key)
        if movie is not None:
            self._movies.move_to_end(key)
            return movie
        movie = QMovie(key)
        if not movie.isValid():
            movie.deleteLater()
            return None
        movie.setCacheMode(QMovie.CacheAll)
        scale = self._scale()
        movie.jumpToFrame(0)
        frame_size = movie.currentImage().size()
        if not frame_size.isEmpty():
            movie.setScaledSize(QSize(int(frame_size.width() * scale), int(frame_size.height() * scale)))
        movie.frameChanged.connect(self._on_frame_changed)
        self._movies[key] = movie
        self._evict_movies()
        return movie

    def _evict_movies(self) -> None:
        while len(self._movies) > MAX_MOVIE_CACHE:
            _, stale = self._movies.popitem(last=False)
            if stale is self._current_movie:
                self._current_movie = None
            stale.stop()
            stale.deleteLater()

    def _on_frame_changed(self, *_args) -> None:
        if self._frozen or self._current_movie is None:
            return
        image = self._current_movie.currentImage()
        if image.isNull():
            return
        self._apply_pixmap(self._pixmap_from_qimage(image))

    def _pixmap_from_qimage(self, image: QImage) -> QPixmap:
        if self._render_track != "card":
            return QPixmap.fromImage(image)
        return render_frame(_qimage_to_pil(image), "card")

    def play(self, category: str, once: bool = False) -> bool:
        """按分类挑一个素材播放；素材缺失时显示占位图并返回 False。

        `self._track` 只用来表达「偏好哪条轨道」；渲染始终按被选中素材的实测轨道，
        这样偏好透明素材但只挑到卡片素材时，仍会套上圆角卡片而不是露出方形背景。
        """
        wanted = None if self._track in (None, "auto") else self._track
        path = pick(self._catalog, category, self._processed_dir, track=wanted)
        if path is None:
            self._current_movie = None
            self._current_category = None
            self._show_placeholder()
            self.asset_missing.emit()
            return False
        self._render_track = track_of(self._catalog, path.name)

        movie = self._acquire_movie(path)
        if movie is None:
            self._current_movie = None
            self._current_category = None
            self._show_placeholder()
            self.asset_missing.emit()
            return False

        if movie is not self._current_movie:
            if self._current_movie is not None:
                self._current_movie.stop()
            self._current_movie = movie
            movie.start()
        self._current_category = category
        self._on_frame_changed()
        if once:
            try:
                movie.finished.disconnect()
            except TypeError:
                pass
            movie.finished.connect(lambda cat=category: self.play_finished.emit(cat))
        return True

    def set_track(self, track: str | None) -> None:
        self._track = track or "transparent"

    def release_movies(self) -> None:
        """停掉并销毁全部影片缓存。

        素材热更前必须调用：`QMovie` 打开着 GIF 文件，Windows 上覆盖被占用的文件会
        `PermissionError`，不先释放的话正在播放的素材永远更新不上。

        这里靠丢弃引用立即析构（`QMovie` 无 parent，PyQt 持有其所有权）：换成
        `deleteLater()` 只把析构推迟到下一次事件循环，热更在同一段代码里
        `os.replace()` 时句柄仍被占着，覆盖照样 `PermissionError`。
        """
        for movie in self._movies.values():
            movie.stop()
            # 清空文件名让 Qt 显式关闭底层文件句柄，不依赖 Python 引用计数的即时析构
            movie.setFileName("")
        self._movies.clear()
        self._current_movie = None

    def reload(self) -> None:
        """清空影片缓存并按当前分类重新加载（缩放等渲染参数变化后调用）。"""
        category = self._current_category
        self.release_movies()
        if category is not None:
            self.play(category, once=False)

    def set_always_on_top(self, on: bool) -> None:
        """切换「始终置顶」。"""
        flags = self.windowFlags()
        target = (flags | Qt.WindowStaysOnTopHint) if on else (flags & ~Qt.WindowStaysOnTopHint)
        self._apply_window_flags(target)

    # ------------------------------------------------------------ 冻结与穿透

    def freeze(self) -> None:
        self._frozen = True

    def unfreeze(self) -> None:
        self._frozen = False

    def is_frozen(self) -> bool:
        return self._frozen

    def movie_cache_size(self) -> int:
        return len(self._movies)

    def move_to(self, x: int, y: int) -> None:
        """把窗口移到 (x, y)；位置真的变了才发 `moved`（气泡按它跟随）。"""
        before = self.pos()
        self.move(int(x), int(y))
        if self.pos() != before:
            self.moved.emit()

    def set_passthrough(self, on: bool) -> None:
        """切换鼠标穿透：开启后本窗口不拦截鼠标事件。"""
        flags = self.windowFlags()
        target = (flags | Qt.WindowTransparentForInput) if on else (flags & ~Qt.WindowTransparentForInput)
        self._apply_window_flags(target)

    def _apply_window_flags(self, flags) -> None:
        """重设窗口标志并保住可见性。

        `setWindowFlags()` 会重建原生窗口、把窗口隐藏（Windows 上实测 `isVisible()`
        立刻变 False），所以必须在调用**之前**记住可见状态，之后主动 `show()`；
        若按调用后的 `isVisible()` 判断，窗口就再也回不来了（切穿透后噜噜直接消失）。
        """
        if flags == self.windowFlags():
            return
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    # ------------------------------------------------------------ 鼠标交互

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            self._pressed = True
            self._dragging = False
            self._press_pos = event.pos()
        event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._pressed and (event.buttons() & Qt.LeftButton):
            delta = event.pos() - self._press_pos
            if not self._dragging and math.hypot(delta.x(), delta.y()) > DRAG_THRESHOLD:
                self._dragging = True
            if self._dragging:
                self.drag_moved.emit(event.globalPos())
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        was_dragging = self._dragging
        self._pressed = False
        self._dragging = False
        if event.button() == Qt.RightButton:
            self.right_clicked.emit(event.globalPos())
        elif event.button() == Qt.LeftButton:
            if was_dragging:
                self.drag_finished.emit(event.globalPos())
            else:
                self._register_click()
        event.accept()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self._pressed = False
        self._dragging = False
        self.double_clicked.emit()
        event.accept()

    def _register_click(self) -> None:
        now = time.monotonic()
        self._click_times = [t for t in self._click_times if now - t <= _CLICK_WINDOW_S]
        self._click_times.append(now)
        self.clicked.emit()
        if len(self._click_times) >= _FAST_CLICK_COUNT:
            self._click_times.clear()
            self.fast_clicked.emit()

    # ------------------------------------------------------------ 装饰素材

    @staticmethod
    def draw_orange(size: int = 48) -> QPixmap:
        """画一个桔子（橙色果身 + 绿色叶片），贴边隐藏时露出。"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#FFA033"))
        body = size * 0.82
        painter.drawEllipse(QRectF(size * 0.09, size * 0.16, body, body))
        painter.setBrush(QColor("#5CA84D"))
        painter.drawEllipse(QRectF(size * 0.44, size * 0.02, size * 0.34, size * 0.2))
        painter.end()
        return pixmap
