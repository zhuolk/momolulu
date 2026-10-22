"""行为状态机：把「待机 / 走动 / 睡觉 / 吃饭 …」等状态翻译成对 `Sprite` 的播放请求。

优先级（数字越大越强势）：idle(0) < auto(1) < user(2) < module(3) < drag(4)。
低优先级的请求被高优先级状态挡住并返回 False；同级请求可以互相覆盖。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Callable

from PyQt5.QtCore import QObject, pyqtSignal

from pet.config import get

PRIORITY_IDLE = 0
PRIORITY_AUTO = 1
PRIORITY_USER = 2
PRIORITY_MODULE = 3
PRIORITY_DRAG = 4

IDLE = "IDLE"
DRAGGED = "DRAGGED"
WANDER = "WANDER"
STROLL = "STROLL"

# 分类 → 状态名（默认取分类大写，个别需要不同叫法）
_STATE_NAMES = {"walk": WANDER, "stroll": STROLL}
# 待机时可能触发的小动作（等概率随机取一个）
_AUTO_ACTIONS = ("walk", "sad", "bath")
_SLEEP_CHANCE = 0.5
_DEFAULT_MAX_MS = 8000


def state_of(category: str) -> str:
    return _STATE_NAMES.get(category, category.upper())


class Behavior(QObject):
    """单只桌宠的行为状态机；由外部定时调用 `tick()` 推进。"""

    state_changed = pyqtSignal(str)

    def __init__(self, sprite, config: dict, clock: Callable[[], datetime] = datetime.now):
        super().__init__()
        self._sprite = sprite
        self._config = config
        self._clock = clock
        self._rng = random.Random()

        self._state = IDLE
        self._priority = PRIORITY_IDLE
        self._state_until: datetime | None = None
        self._once = False
        self._state_category: str | None = None
        self._last_user_activity = clock()
        self._next_auto_at = clock()
        self._wander_chance: float | None = None
        self._stopped = True

    # ------------------------------------------------------------ 只读属性

    @property
    def state(self) -> str:
        return self._state

    # ------------------------------------------------------------ 生命周期

    def start(self) -> None:
        self._stopped = False
        now = self._clock()
        self._last_user_activity = now
        self._next_auto_at = now + timedelta(seconds=self._wander_gap())
        self.request("idle", PRIORITY_IDLE, once=False)

    def stop(self) -> None:
        self._stopped = True

    # ------------------------------------------------------------ 状态请求

    def request(
        self,
        category: str,
        priority: int,
        once: bool = True,
        max_ms: int = _DEFAULT_MAX_MS,
    ) -> bool:
        """请求播放某分类；被更高优先级状态挡住或素材缺失时返回 False。"""
        if priority < self._priority:
            return False
        if not self._sprite.play(category, once):
            return False
        self._priority = priority
        self._once = once
        self._state_category = category
        self._state_until = (
            self._clock() + timedelta(milliseconds=max_ms) if once else None
        )
        self._set_state(state_of(category))
        return True

    # ------------------------------------------------------------ 事件入口

    def on_user_click(self) -> None:
        self._last_user_activity = self._clock()
        self.request("happy", PRIORITY_USER, once=True)

    def on_fast_click(self) -> None:
        self._last_user_activity = self._clock()
        self.request("angry", PRIORITY_USER, once=True)

    def on_drag_started(self) -> None:
        self._last_user_activity = self._clock()
        self._sprite.freeze()
        self._priority = PRIORITY_DRAG
        self._once = False
        self._state_category = None
        self._state_until = None
        self._set_state(DRAGGED)

    def on_drag_finished(self) -> None:
        self._last_user_activity = self._clock()
        self._sprite.unfreeze()
        self._to_idle()

    def on_play_finished(self, category: str) -> None:
        """一次性播放播完后回待机（仅当当前状态正是该分类驱动）。"""
        if self._once and self._state_category == category:
            self._to_idle()

    def on_stroll_finished(self) -> None:
        """绕屏一圈走完：回待机（仅当当前状态仍是散步驱动的）。"""
        if self._state == STROLL:
            self._to_idle()

    # ------------------------------------------------------------ 推进

    def tick(self, now: datetime) -> None:
        if self._stopped or self._state == DRAGGED:
            return
        if self._state_until is not None and now >= self._state_until:
            self._to_idle()
        if self._state != IDLE:
            return

        idle_seconds = (now - self._last_user_activity).total_seconds()
        if idle_seconds >= self._sleep_after():
            if self._chance(_SLEEP_CHANCE):
                self.request("sleep", PRIORITY_AUTO, once=False)
            else:
                self._auto_action(now)
            return
        if now >= self._next_auto_at:
            self._auto_action(now)

    # ------------------------------------------------------------ 内部

    def force_wander_chance(self, p: float) -> None:
        """测试钩子：把自动行为里的随机判定固定为概率 p（1.0 = 必定触发）。"""
        self._wander_chance = float(p)

    def _auto_action(self, now: datetime) -> None:
        self.request(self._rng.choice(_AUTO_ACTIONS), PRIORITY_AUTO, once=True)
        self._next_auto_at = now + timedelta(seconds=self._wander_gap())

    def _to_idle(self) -> None:
        self._priority = PRIORITY_IDLE
        self._once = False
        self._state_category = None
        self._next_auto_at = self._clock() + timedelta(seconds=self._wander_gap())
        self.request("idle", PRIORITY_IDLE, once=False)

    def _set_state(self, state: str) -> None:
        changed = state != self._state
        self._state = state
        if changed:
            self.state_changed.emit(state)

    def _chance(self, p: float) -> bool:
        threshold = p if self._wander_chance is None else self._wander_chance
        return self._rng.random() < threshold

    def _wander_gap(self) -> float:
        interval = get(self._config, "pet.state_intervals.idle_to_wander", [30, 120])
        low, high = float(interval[0]), float(interval[1])
        return self._rng.uniform(low, high)

    def _sleep_after(self) -> float:
        return float(get(self._config, "pet.state_intervals.idle_to_sleep", 900))
