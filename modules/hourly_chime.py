"""整点报时：每到一个整点提醒一次（不播放声音）。"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from modules.base import MODULE_CLASSES, Module, ModuleContext


class HourlyChime(Module):
    """每个整点让噜噜冒个泡报时；同一 `(日期, 小时)` 只提醒一次。"""

    name = "hourly_chime"
    title = "整点报时"

    def __init__(self, ctx: ModuleContext, clock: Callable[[], datetime] = datetime.now):
        super().__init__(ctx)
        self._clock = clock
        self._fired: set[tuple[str, int]] = set()

    # ------------------------------------------------------------ 只读属性

    @property
    def fired_keys(self) -> set[tuple[str, int]]:
        """已报时过的 `(YYYY-MM-DD, 小时)` 集合。"""
        return set(self._fired)

    # ------------------------------------------------------------ 生命周期

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def tick(self, now: datetime) -> None:
        if not self._enabled:
            return
        key = (now.date().isoformat(), now.hour)
        if now.minute != 0 or key in self._fired:
            return
        self.ctx.notify(f"现在是 {now.hour:02d}:00", "idle")
        self._fired.add(key)


MODULE_CLASSES.append(HourlyChime)
