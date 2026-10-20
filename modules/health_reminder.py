"""喝水与久坐提醒：两个独立子开关 + 独立间隔，支持小睡（snooze）延后。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from modules.base import MODULE_CLASSES, Module, ModuleContext
from pet.config import get

WATER = "water"
SIT = "sit"

# which → (间隔配置键, 子开关配置键, 通知文案, 表情分类)
_SPECS = {
    WATER: ("water_min", "water_enabled", "该喝水啦", "drink"),
    SIT: ("sit_min", "sit_enabled", "起来动一动吧", "happy"),
}


class HealthReminder(Module):
    """到点提醒喝水 / 起身活动；两个子项各自独立计时、独立开关。"""

    name = "health_reminder"
    title = "喝水·久坐"

    def __init__(self, ctx: ModuleContext, clock: Callable[[], datetime] = datetime.now):
        super().__init__(ctx)
        self._clock = clock
        self._next: dict[str, datetime] = {which: clock() for which in _SPECS}

    # ------------------------------------------------------------ 只读属性

    def sub_switches(self) -> tuple[str, ...]:
        return (WATER, SIT)

    def next_at(self, which: str) -> datetime:
        """下一次提醒时刻。"""
        if which not in self._next:
            raise KeyError(which)
        return self._next[which]

    # ------------------------------------------------------------ 生命周期

    def enable(self) -> None:
        self._enabled = True
        self.reset_schedule()

    def disable(self) -> None:
        self._enabled = False

    def tick(self, now: datetime) -> None:
        if not self._enabled:
            return
        for which in (WATER, SIT):
            if not self._sub_on(which):
                # 关闭期间不堆积：把计时基准推到「此刻 + 间隔」
                self._next[which] = now + timedelta(minutes=self._interval_min(which))
                continue
            if now >= self._next[which]:
                text, category = _SPECS[which][2], _SPECS[which][3]
                self.ctx.notify(text, category)
                # 以 now 为基准重排，长时间挂起也只补发一次
                self._next[which] = now + timedelta(minutes=self._interval_min(which))

    # ------------------------------------------------------------ 控制

    def reset_schedule(self) -> None:
        """把两个提醒重新排到「此刻 + 各自间隔」。"""
        now = self._clock()
        self._next = {
            which: now + timedelta(minutes=self._interval_min(which)) for which in _SPECS
        }

    def snooze(self, which: str) -> None:
        """把指定提醒推后 `snooze_min` 分钟。"""
        if which not in self._next:
            raise KeyError(which)
        self._next[which] = self._clock() + timedelta(minutes=self._snooze_min())

    # ------------------------------------------------------------ 内部

    def _option(self, key: str, default: int) -> int:
        value = get(self.ctx.config, f"modules.health_reminder.{key}", default)
        return int(value) if isinstance(value, (int, float)) and value > 0 else default

    def _sub_on(self, which: str) -> bool:
        key = _SPECS[which][1]
        value = get(self.ctx.config, f"modules.health_reminder.{key}", True)
        return bool(value) if isinstance(value, bool) else True

    def _interval_min(self, which: str) -> int:
        return self._option(_SPECS[which][0], 45)

    def _snooze_min(self) -> int:
        return self._option("snooze_min", 10)


MODULE_CLASSES.append(HealthReminder)
