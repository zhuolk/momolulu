"""自动走动：`WANDER` 状态期间让噜噜在屏幕上缓慢水平移动，碰到左右边缘折返。

只负责位移，不驱动动画——走路的 GIF 由 `Behavior` 按 `walk` 分类播放。窗口移动会
触发 `Sprite.moved`，气泡据此跟随。
"""

from __future__ import annotations

from typing import Callable

# 每个心跳（`main._TICK_MS` = 100ms）位移的像素，约 40px/秒
WALK_SPEED_PX = 4


class Wanderer:
    """把「正在走动」翻译成窗口位移；朝左走时让噜噜镜像转身。"""

    def __init__(
        self,
        sprite,
        screens_provider: Callable[[], list[tuple[int, int, int, int]]],
        speed_px: int = WALK_SPEED_PX,
    ):
        self._sprite = sprite
        self._screens_provider = screens_provider
        self._speed_px = int(speed_px)
        self._direction = 1  # 1 向右，-1 向左；折返后保持新方向

    def tick(self, walking: bool) -> None:
        """`walking` 为真时走一步；贴边缩回或没有屏幕时不动。"""
        if not walking or self._sprite.strip_side is not None:
            return
        screen = self._screen()
        if screen is None:
            return
        sx, _, sw, _ = screen
        left, right = sx, sx + sw - self._sprite.width()
        x = self._sprite.x() + self._direction * self._speed_px
        if x <= left:  # 到左缘：贴住并折返向右
            x, self._direction = left, 1
        elif x >= right:  # 到右缘：贴住并折返向左
            x, self._direction = right, -1
        self._sprite.move_to(x, self._sprite.y())
        self._sprite.set_flip(self._direction < 0)

    def _screen(self) -> tuple[int, int, int, int] | None:
        screens = self._screens_provider() or []
        for screen in screens:
            sx, sy, sw, sh = screen
            if sx <= self._sprite.x() < sx + sw and sy <= self._sprite.y() < sy + sh:
                return screen
        return screens[0] if screens else None
