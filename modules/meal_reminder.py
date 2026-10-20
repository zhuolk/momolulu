"""吃饭提醒：每天在配置的时刻（默认 12:00 / 18:30）提醒一次，错过的时刻不补发。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from modules.base import MODULE_CLASSES, Module, ModuleContext
from pet.config import get

DEFAULT_TIMES = ("12:00", "18:30")
WINDOW_SECONDS = 60


def _parse_hhmm(text: str) -> tuple[int, int] | None:
    """把 "HH:MM" 解析成 (时, 分)；格式不合法返回 None。"""
    if not isinstance(text, str) or len(text) != 5 or text[2] != ":":
        return None
    try:
        hour, minute = int(text[:2]), int(text[3:])
    except ValueError:
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


class MealReminder(Module):
    """到点提醒吃饭；同一 `(日期, 时刻)` 只提醒一次。"""

    name = "meal_reminder"
    title = "吃饭提醒"

    def __init__(self, ctx: ModuleContext, clock: Callable[[], datetime] = datetime.now):
        super().__init__(ctx)
        self._clock = clock
        self._fired: set[tuple[str, str]] = set()

    # ------------------------------------------------------------ 只读属性

    @property
    def fired_keys(self) -> set[tuple[str, str]]:
        """已触发过的 `(YYYY-MM-DD, "HH:MM")` 集合。"""
        return set(self._fired)

    # ------------------------------------------------------------ 生命周期

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def tick(self, now: datetime) -> None:
        if not self._enabled:
            return
        for target in self._times():
            key = (now.date().isoformat(), target)
            if key in self._fired:
                continue
            if self._in_window(now, target):
                self.ctx.notify(f"{target} 到啦，该吃饭咯", "eat")
                self._fired.add(key)

    # ------------------------------------------------------------ 内部

    def _in_window(self, now: datetime, target: str) -> bool:
        """`now` 是否落在目标时刻起始的 60 秒窗口内。"""
        parsed = _parse_hhmm(target)
        if parsed is None:
            return False
        start = now.replace(hour=parsed[0], minute=parsed[1], second=0, microsecond=0)
        return timedelta(0) <= (now - start) < timedelta(seconds=WINDOW_SECONDS)

    def _times(self) -> tuple[str, ...]:
        value = get(self.ctx.config, "modules.meal_reminder.times", None)
        if not isinstance(value, (list, tuple)):
            return DEFAULT_TIMES
        valid = tuple(v for v in value if _parse_hhmm(v) is not None)
        return valid or DEFAULT_TIMES


MODULE_CLASSES.append(MealReminder)
