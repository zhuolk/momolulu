"""散步：瞬移到当前屏幕的右下角，沿屏幕边缘逆时针绕一圈再回待机。

只负责位移与朝向——走路的 GIF 由 `Behavior` 按 `stroll` 分类播放；窗口移动会触发
`Sprite.moved`，气泡据此跟随。

路线起点与终点都是右下角，四段依次是「右边向上 → 顶边向左 → 左边向下 → 底边向右」。
素材是朝右走的，所以旋转角以 0 为基准按逆时针 90° 递推（270 → 180 → 90 → 0），
每一段都把噜噜的脚压在对应的边缘上。

**贴的是「工作区」边缘而不是整屏边缘**：任务栏占着屏幕底边那一条（本机 48px），
噜噜是置顶窗口但任务栏同属置顶层，走进去会被压住看不见。所以底边那段要按
`availableGeometry` 内缩，脚踩在任务栏上沿；左 / 右 / 顶边通常不受影响，
但任务栏挪到别的边时也一并避让。要按哪块屏算，仍然按**整屏**矩形判断。
"""

from __future__ import annotations

from typing import Callable

# 每个心跳（`main._TICK_MS` = 100ms）位移的像素，约 80px/秒
STROLL_SPEED_PX = 8

# 四段路线：(移动轴, 方向, 旋转角)。旋转角顺时针为正，270 即逆时针 90°。
_LEGS = (("y", -1, 270), ("x", -1, 180), ("y", 1, 90), ("x", 1, 0))


class Stroller:
    """把「散步」翻译成沿工作区边缘的位移与整图旋转。"""

    def __init__(
        self,
        sprite,
        screens_provider: Callable[[], list[tuple[int, int, int, int]]],
        speed_px: int = STROLL_SPEED_PX,
        on_finished: Callable[[], None] | None = None,
        bounds_provider: Callable[[], list[tuple[int, int, int, int]]] | None = None,
    ):
        self._sprite = sprite
        self._screens_provider = screens_provider
        # 实际贴着走的矩形（工作区），与 `screens_provider` 同序同长；不给就整屏。
        self._bounds_provider = bounds_provider
        self._speed_px = int(speed_px)
        self._on_finished = on_finished
        self._screen: tuple[int, int, int, int] | None = None
        self._leg = 0
        self._x = 0.0
        self._y = 0.0
        self._active = False

    # ------------------------------------------------------------ 只读属性

    @property
    def active(self) -> bool:
        """是否正在绕屏散步。"""
        return self._active

    # ------------------------------------------------------------ 开始 / 中止

    def start(self) -> bool:
        """瞬移到当前所在屏幕的右下角并起步；找不到屏幕时返回 False。"""
        screens = self._screens_provider() or []
        if not screens:
            return False
        self._screen = self._walk_bounds(screens, self._find_screen(screens))
        self._leg = 0
        self._x, self._y = self._corner(0)
        self._active = True
        self._sprite.set_flip(False)  # 用旋转表达朝向，先清掉走动留下的镜像
        self._apply_rotation()
        self._move()
        return True

    def tick(self) -> None:
        """走一步；绕完一圈后回调 `on_finished` 并停下。"""
        if not self._active or self._sprite.strip_side is not None:
            return
        remaining = float(self._speed_px)
        while remaining > 0 and self._active:
            remaining = self._advance(remaining)

    def stop(self) -> None:
        """中止散步（拖拽、状态被抢）并恢复直立。"""
        self._active = False
        self._sprite.set_rotation(0)

    # ------------------------------------------------------------ 内部

    def _advance(self, step: float) -> float:
        """沿当前段前进 step 像素，跨过拐角时继续走并返回剩余距离。"""
        axis, sign, _ = _LEGS[self._leg]
        target = self._corner(self._leg + 1)[0 if axis == "x" else 1]
        current = self._x if axis == "x" else self._y
        distance = abs(target - current)
        if step < distance:
            current += sign * step
            step = 0.0
        else:
            current = target
            step -= distance
        if axis == "x":
            self._x = current
        else:
            self._y = current
        self._move()
        if current == target:  # 到拐角：换下一段（顺带转 90°）
            self._next_leg()
        return step

    def _next_leg(self) -> None:
        self._leg += 1
        if self._leg >= len(_LEGS):
            self._finish()
            return
        self._apply_rotation()

    def _finish(self) -> None:
        self._active = False
        self._sprite.set_rotation(0)
        if self._on_finished is not None:
            self._on_finished()

    def _apply_rotation(self) -> None:
        self._sprite.set_rotation(_LEGS[self._leg][2])

    def _move(self) -> None:
        self._sprite.move_to(round(self._x), round(self._y))

    def _corner(self, index: int) -> tuple[float, float]:
        """四角的窗口左上角坐标：右下 → 右上 → 左上 → 左下（逆时针一圈）。"""
        sx, sy, sw, sh = self._screen
        left, top = float(sx), float(sy)
        right = float(sx + sw - self._sprite.width())
        bottom = float(sy + sh - self._sprite.height())
        return ((right, bottom), (right, top), (left, top), (left, bottom))[index % 4]

    def _find_screen(self, screens: list[tuple[int, int, int, int]]) -> int:
        """窗口所在屏幕的下标（按**整屏**矩形判断）。

        贴边缩回时窗口大半在屏外，窗口中心甚至可能已经压到邻屏上，只有露在屏内的
        桔子窄条一定在「自己那块屏」里，所以缩回时只按那一侧取参考点。
        """
        x, y = self._sprite.x(), self._sprite.y()
        width, height = self._sprite.width(), self._sprite.height()
        middle = y + height // 2
        side = self._sprite.strip_side
        if side == "left":
            points = ((x + width - 1, middle),)
        elif side == "right":
            points = ((x, middle),)
        else:
            points = ((x + width // 2, middle), (x + width - 1, middle), (x, middle))
        for px, py in points:
            for index, screen in enumerate(screens):
                sx, sy, sw, sh = screen
                if sx <= px < sx + sw and sy <= py < sy + sh:
                    return index
        return 0

    def _walk_bounds(
        self, screens: list[tuple[int, int, int, int]], index: int
    ) -> tuple[int, int, int, int]:
        """该屏幕实际贴着走的矩形：给了 `bounds_provider`（工作区）就用它，否则整屏。"""
        if self._bounds_provider is None:
            return screens[index]
        bounds = self._bounds_provider() or []
        return bounds[index] if index < len(bounds) else screens[index]
