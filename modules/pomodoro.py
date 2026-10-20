"""番茄钟：专注 / 休息自动轮转，支持开始、暂停、跳过与重置。"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from modules.base import MODULE_CLASSES, Module, ModuleContext
from pet.config import get

FOCUS = "focus"
BREAK = "break"
IDLE = "idle"


class Pomodoro(Module):
    """25 分钟专注 + 5 分钟休息（时长取配置）的循环计时器。"""

    name = "pomodoro"
    title = "番茄钟"

    def __init__(self, ctx: ModuleContext, clock: Callable[[], datetime] = datetime.now):
        super().__init__(ctx)
        self._clock = clock
        self._phase = IDLE
        self._remaining = float(self._focus_seconds())
        self._running = False
        self._last_tick = clock()

    # ------------------------------------------------------------ 只读属性

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def running(self) -> bool:
        return self._running

    def remaining_seconds(self, now: datetime) -> int:
        """当前相位剩余秒数（已运行的相位会实时扣减）。"""
        remaining = self._remaining
        if self._running and self._phase != IDLE:
            remaining -= max(0.0, (now - self._last_tick).total_seconds())
        return max(0, int(remaining))

    # ------------------------------------------------------------ 生命周期

    def enable(self) -> None:
        self._enabled = True
        self.reset()

    def disable(self) -> None:
        self._enabled = False
        self._running = False

    def tick(self, now: datetime) -> None:
        if not self._enabled or not self._running or self._phase == IDLE:
            return
        self._consume(now)
        if self._remaining > 0:
            return
        self._switch(BREAK if self._phase == FOCUS else FOCUS)

    # ------------------------------------------------------------ 控制

    def start(self) -> None:
        self._phase = FOCUS
        self._remaining = float(self._focus_seconds())
        self._running = True
        self._last_tick = self._clock()

    def pause(self) -> None:
        if not self._running:
            return
        self._consume(self._clock())
        self._running = False

    def toggle(self) -> None:
        """待机 → 开始；运行中 → 暂停；暂停中 → 继续。"""
        if self._phase == IDLE:
            self.start()
        elif self._running:
            self.pause()
        else:
            self._running = True
            self._last_tick = self._clock()

    def reset(self) -> None:
        self._phase = IDLE
        self._remaining = float(self._focus_seconds())
        self._running = False
        self._last_tick = self._clock()

    def skip(self) -> None:
        """直接跳到下一相位（不发通知）。"""
        if self._phase == IDLE:
            self.start()
            return
        self._switch(BREAK if self._phase == FOCUS else FOCUS, notify=False)

    # ------------------------------------------------------------ 内部

    def _switch(self, phase: str, notify: bool = True) -> None:
        self._phase = phase
        self._remaining = float(
            self._focus_seconds() if phase == FOCUS else self._break_seconds()
        )
        self._last_tick = self._clock()
        self._running = True
        if not notify:
            return
        if phase == BREAK:
            self.ctx.notify(f"专注完成，休息 {self._break_min()} 分钟", "happy")
        else:
            self.ctx.notify("休息结束，继续专注", "idle")

    def _consume(self, now: datetime) -> None:
        """把 `now - _last_tick` 折算进剩余时间，并推进计时基准。"""
        elapsed = (now - self._last_tick).total_seconds()
        if elapsed > 0:
            self._remaining = max(0.0, self._remaining - elapsed)
        self._last_tick = now

    def _option(self, key: str, default: int) -> int:
        value = get(self.ctx.config, f"modules.pomodoro.{key}", default)
        return int(value) if isinstance(value, (int, float)) and value > 0 else default

    def _focus_min(self) -> int:
        return self._option("focus_min", 25)

    def _break_min(self) -> int:
        return self._option("break_min", 5)

    def _focus_seconds(self) -> int:
        return self._focus_min() * 60

    def _break_seconds(self) -> int:
        return self._break_min() * 60


MODULE_CLASSES.append(Pomodoro)
