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
SLEEP = "SLEEP"
AWAKE = "AWAKE"

# 分类 → 状态名（默认取分类大写，个别需要不同叫法）
_STATE_NAMES = {"walk": WANDER, "stroll": STROLL, "sleep1": SLEEP, "sleep2": SLEEP}
# 待机时可能触发的小动作（顺序尝试，抽到的分类没素材就试下一个）
_AUTO_ACTIONS = ("walk",)
_SLEEP_CHANCE = 0.5
_DEFAULT_MAX_MS = 8000

_SLEEP_CATEGORY = "sleep"       # 待机太久自动入睡时循环播的分类
_SLEEP_INTRO = "sleep1"         # 哄睡：入场动画（播一次）
_SLEEP_LOOP = "sleep2"          # 哄睡：睡着后持续循环
_SLEEP_CATEGORIES = (_SLEEP_CATEGORY, _SLEEP_INTRO, _SLEEP_LOOP)
_MOVE_CATEGORY = "move"
_AWAKE_CATEGORY = "awake"
_SHOWUP_CATEGORY = "showup"


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
        self._state_category: str | None = None
        self._idle_category = "idle"
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
        self.request(self._idle_category, PRIORITY_IDLE, once=False)

    def stop(self) -> None:
        self._stopped = True

    def set_idle_category(self, category: str = "idle") -> None:
        """换掉「待机」时播的分类（番茄钟专注换 `think`、上班换 `work`）；正待机就立即生效。"""
        if category == self._idle_category:
            return
        self._idle_category = category
        if self._priority == PRIORITY_IDLE:
            self.request(category, PRIORITY_IDLE, once=False)

    def play_showup(self, priority: int = PRIORITY_AUTO) -> bool:
        """刚露面（启动、从贴边隐藏恢复）时播一次 `showup`。

        只占 auto 级：露面是装饰，不该把用户点击 / 模块通知挡在外面。
        """
        return self.request(_SHOWUP_CATEGORY, priority, once=True)

    def sleep(self, priority: int = PRIORITY_MODULE) -> bool:
        """哄睡：先播一次 `sleep1` 作入场动画，播完由 `on_play_finished` 接 `sleep2` 持续循环。

        两个分类都没素材时返回 False（调用方只弹气泡）。
        """
        if self.request(_SLEEP_INTRO, priority, once=False):
            return True
        return self.request(_SLEEP_LOOP, priority, once=False)

    # ------------------------------------------------------------ 状态请求

    def request(
        self,
        category: str,
        priority: int,
        once: bool = True,
        max_ms: int = _DEFAULT_MAX_MS,
    ) -> bool:
        """请求播放某分类；被更高优先级状态挡住或素材缺失时返回 False。

        `once` 只影响状态持续时间（`once=True` 时最多 `max_ms` 后回待机）；
        素材到底循环还是只播一次，由素材自己的 `loops` 属性说了算。
        """
        if priority < self._priority:
            return False
        waking = self._state == SLEEP and category not in _SLEEP_CATEGORIES
        if not self._sprite.play(category):
            return False
        self._priority = priority
        self._state_category = category
        self._state_until = (
            self._clock() + timedelta(milliseconds=max_ms) if once else None
        )
        self._set_state(state_of(category))
        if waking:
            self._insert_awake(max_ms)
        return True

    # ------------------------------------------------------------ 事件入口

    def on_user_click(self) -> None:
        self._last_user_activity = self._clock()
        self.request("confuse", PRIORITY_USER, once=True)

    def wake(self) -> None:
        if self._state == SLEEP:
            self._last_user_activity = self._clock()
            self._to_idle()

    def on_fast_click(self) -> None:
        self._last_user_activity = self._clock()
        self.request("angry", PRIORITY_USER, once=True)

    def on_drag_started(self) -> None:
        self._last_user_activity = self._clock()
        self._priority = PRIORITY_DRAG
        self._state_category = None
        self._state_until = None
        if not self._sprite.play(_MOVE_CATEGORY):  # 没有「被拎起来」的素材就定格当前一帧
            self._sprite.freeze()
        self._set_state(DRAGGED)

    def on_drag_finished(self) -> None:
        self._last_user_activity = self._clock()
        self._sprite.unfreeze()
        self._to_idle()

    def on_play_finished(self, category: str) -> None:
        """只播一次的素材播完了：回待机（仅当当前状态仍由该分类驱动）。

        散步是持续状态，素材播完不代表走完一圈（收尾交给 `on_stroll_finished`），
        否则不可循环的散步素材会让噜噜半路停下。哄睡的入场动画 `sleep1` 播完则接 `sleep2`。
        """
        if self._state_category != category or self._state == STROLL:
            return
        if self._state == state_of(self._idle_category):
            self.request(self._idle_category, PRIORITY_IDLE, once=False)  # 接着挑下一个待机素材
            return
        if category == _SLEEP_INTRO:
            if not self.request(_SLEEP_LOOP, self._priority, once=False):
                self._to_idle()
            return
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
        if self._state not in (IDLE, state_of(self._idle_category)):
            return

        idle_seconds = (now - self._last_user_activity).total_seconds()
        if self._idle_category == "idle" and idle_seconds >= self._sleep_after():
            if self._chance(_SLEEP_CHANCE) and self.request("sleep", PRIORITY_AUTO, once=False):
                return
            # 掷到不睡、或压根没有睡觉素材（`request` 返回 False）：按常规节奏走小动作。
            # 「到点就无脑动一下」加上每 tick 重掷，会让动作一个接一个连播（看着像抽搐）。
            if now >= self._next_auto_at:
                self._auto_action(now)
            return
        if now >= self._next_auto_at:
            self._auto_action(now)

    # ------------------------------------------------------------ 内部

    def force_wander_chance(self, p: float) -> None:
        """测试钩子：把自动行为里的随机判定固定为概率 p（1.0 = 必定触发）。"""
        self._wander_chance = float(p)

    def _auto_action(self, now: datetime) -> None:
        """做一次待机小动作。

        抽到的分类没素材就接着试下一个，否则这一轮会白等一整个 `idle_to_wander` 间隔。
        间隔先排上，避免每一 tick 重来。
        """
        self._next_auto_at = now + timedelta(seconds=self._wander_gap())
        for category in _AUTO_ACTIONS:
            if self.request(category, PRIORITY_AUTO, once=True):
                return

    def _insert_awake(self, max_ms: int) -> None:
        """刚睡醒：插播一次「醒觉」，播完（或到时）再回待机。

        睡眠是持续状态，只能被更高优先级的请求打断，所以「醒来」这一幕在打断的
        那一刻插进去，而不是等状态自己回到待机。
        """
        if not self._sprite.play(_AWAKE_CATEGORY):
            return  # 没有「醒觉」素材就算了，直接演打断它的那个分类
        self._state_category = _AWAKE_CATEGORY
        self._state_until = self._clock() + timedelta(milliseconds=max_ms)
        self._set_state(AWAKE)

    def _to_idle(self) -> None:
        self._priority = PRIORITY_IDLE
        self._state_category = None
        self._next_auto_at = self._clock() + timedelta(seconds=self._wander_gap())
        self.request(self._idle_category, PRIORITY_IDLE, once=False)

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
