"""贴边隐藏：拖到屏幕左右边缘松手后滑出屏外，只留一条桔子。

缩回后不会因为鼠标划过桔子就自己弹出来（避免误触），必须把桔子拖离边缘再松手才会恢复显示。
"""

from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import QObject, pyqtSignal

from pet.config import get

DEFAULT_EDGE_PX = 24
DEFAULT_STRIP_PX = 48


def hidden_x(
    pos: tuple[int, int],
    size: tuple[int, int],
    screen: tuple[int, int, int, int],
    edge_px: int = DEFAULT_EDGE_PX,
    strip_px: int = DEFAULT_STRIP_PX,
) -> int | None:
    """靠近左右边缘时返回「贴边隐藏」后的窗口左上角 x；不在边缘返回 None。"""
    sx, sy, sw, sh = screen
    if pos[0] - sx <= edge_px:
        return sx - size[0] + strip_px
    if pos[0] + size[0] >= sx + sw - edge_px:
        return sx + sw - strip_px
    return None


def strip_rect(
    hidden_x_value: int,
    screen: tuple[int, int, int, int],
    size: tuple[int, int],
    y: int,
    strip_px: int = DEFAULT_STRIP_PX,
) -> tuple[int, int, int, int] | None:
    """隐藏状态下露在屏幕内的桔子窄条 (x, y, w, h)；未贴边返回 None。"""
    sx, sy, sw, sh = screen
    if hidden_x_value < sx:
        return sx, int(y), strip_px, size[1]
    if hidden_x_value + size[0] > sx + sw:
        return sx + sw - strip_px, int(y), strip_px, size[1]
    return None


class EdgeHider(QObject):
    """管理贴边隐藏的两个动作：隐藏（缩回只留桔子）、拖离边缘恢复。"""

    hidden_changed = pyqtSignal(bool)

    def __init__(
        self,
        sprite,
        config: dict,
        screens_provider: Callable[[], list[tuple[int, int, int, int]]],
        strip_px: int = DEFAULT_STRIP_PX,
        edge_px: int = DEFAULT_EDGE_PX,
    ):
        super().__init__()
        self._sprite = sprite
        self._config = config
        self._screens_provider = screens_provider
        self._strip_px = strip_px
        self._edge_px = edge_px

        self._hidden = False
        self._side: str | None = None
        self._y = 0

    # ------------------------------------------------------------ 只读属性

    @property
    def is_hidden(self) -> bool:
        """是否处于贴边隐藏模式（屏外只留桔子窄条）。"""
        return self._hidden

    @property
    def side(self) -> str | None:
        return self._side

    # ------------------------------------------------------------ 隐藏 / 恢复

    def maybe_hide(self, pos: tuple[int, int]) -> bool:
        """松手位置靠近左右边缘则贴边隐藏；不在边缘则取消贴边模式（恢复显示）。"""
        screen = self._screen_for(pos)
        if screen is None:
            self.detach()
            return False
        x = hidden_x(pos, self._size(), screen, self._edge_px, self._strip_px)
        if x is None:
            self.detach()
            return False
        self._side = "left" if x < screen[0] else "right"
        self._y = int(pos[1])
        self._hidden = True
        self._sprite.move_to(x, self._y)
        self._show_strip(True)
        self.save_to_config()
        self.hidden_changed.emit(True)
        return True

    def detach(self) -> None:
        """退出贴边模式（被拖离边缘），并清除配置里的贴边记录。"""
        if not self._hidden:
            return
        self._hidden = False
        self._side = None
        self._show_strip(False)
        self.save_to_config()
        self.hidden_changed.emit(False)

    def retract(self) -> None:
        """缩回屏外，只留桔子窄条。"""
        if not self._hidden:
            return
        screen = self._screen()
        if screen is None:
            return
        sx, _, sw, _ = screen
        if self._side == "left":
            x = sx - self._size()[0] + self._strip_px
        else:
            x = sx + sw - self._strip_px
        self._sprite.move_to(x, self._y)
        self._show_strip(True)

    # ------------------------------------------------------------ 持久化

    def save_to_config(self) -> None:
        self._config.setdefault("pet", {})["edge_hide"] = (
            {"side": self._side, "y": self._y} if self._hidden else None
        )

    def restore_from_config(self) -> None:
        """按配置恢复「上次退出时处于贴边隐藏」的形态。"""
        spec = get(self._config, "pet.edge_hide", None)
        if not isinstance(spec, dict):
            return
        side, y = spec.get("side"), spec.get("y")
        if side not in ("left", "right") or not isinstance(y, int):
            return
        self._side = side
        self._y = y
        self._hidden = True
        self.retract()
        self.hidden_changed.emit(True)

    # ------------------------------------------------------------ 内部

    def _show_strip(self, on: bool) -> None:
        """告诉窗口是否只画桔子窄条（缩回时露在屏幕内的那一侧）。"""
        self._sprite.set_strip(self._side if on else None, self._strip_px)

    def _size(self) -> tuple[int, int]:
        return int(self._sprite.width()), int(self._sprite.height())

    def _screen_for(self, pos: tuple[int, int]) -> tuple[int, int, int, int] | None:
        screens = self._screens_provider() or []
        for screen in screens:
            sx, sy, sw, sh = screen
            if sx <= pos[0] < sx + sw and sy <= pos[1] < sy + sh:
                return screen
        return screens[0] if screens else None

    def _screen(self) -> tuple[int, int, int, int] | None:
        screens = self._screens_provider() or []
        for screen in screens:
            sx, sy, sw, sh = screen
            if sy <= self._y < sy + sh:
                return screen
        return screens[0] if screens else None
