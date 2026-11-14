"""生活数值：心情 / 活力 / 饱腹。

只按「在线时间」衰减：每次 `tick` 用「距上次 tick 的秒数」折算，进程没跑的那段时间不算，
所以关掉噜噜期间数值不会被扣（持久化只为下次启动接着用）。

衰减速率与当下状态相关：
- 上班中（`set_working`）：心情 / 活力衰减翻倍；
- 睡觉中（`set_sleeping`）：活力不再往下掉，改为回升。

数值一变就写回 `ctx.config`（`modules.vitals`），落盘按 60 秒节流，免得每秒写盘。
跌破 `low_threshold` 时冒一次泡，回到 `warn_threshold` 以上才重新武装，避免反复刷屏。
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from modules.base import MODULE_CLASSES, Module, ModuleContext
from pet.config import get

# 待机小动作分类（与 `pet.behavior._AUTO_ACTIONS` 一致）：低数值时给负面情绪加权
_AUTO_ACTIONS = ("walk", "sad", "bath", "cry", "anxious", "surprise")

_SAVE_INTERVAL_SECONDS = 60

# 字段名 → (衰减速率配置键, 偏低时的文案, 通知分类)
_LEVELS = (
    ("mood", "mood_decay_per_hour", "噜噜心情好低落，来陪我玩会儿吧", "cry"),
    ("energy", "energy_decay_per_hour", "噜噜累坏了，想眯一会儿", "sleep"),
    ("satiety", "satiety_decay_per_hour", "噜噜饿扁啦，想吃东西", "eat"),
)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


class Vitals(Module):
    """心情 / 活力 / 饱腹三件套；数值由宿主每隔一秒 `tick` 一次。"""

    name = "vitals"
    title = "心情·活力·饱腹"
    default_enabled = True

    def __init__(self, ctx: ModuleContext, clock: Callable[[], datetime] = datetime.now):
        super().__init__(ctx)
        self._clock = clock
        self._mood = self._level("mood", 80.0)
        self._energy = self._level("energy", 80.0)
        self._satiety = self._level("satiety", 80.0)
        self._sleeping = False
        self._working = False
        self._warned: set[str] = set()
        self._last = clock()
        self._last_save = clock()

    # ------------------------------------------------------------ 只读属性

    @property
    def mood(self) -> float:
        return self._mood

    @property
    def energy(self) -> float:
        return self._energy

    @property
    def satiety(self) -> float:
        return self._satiety

    def status_text(self) -> str:
        """托盘悬停里显示的一行数值。"""
        return (
            f"心情 {int(self._mood)} · 活力 {int(self._energy)} · 饱腹 {int(self._satiety)}"
        )

    # ------------------------------------------------------------ 外部状态

    def set_working(self, on: bool) -> None:
        """上班中：心情 / 活力衰减加倍。"""
        self._working = bool(on)

    def set_sleeping(self, on: bool) -> None:
        """睡觉中：活力改为回升。"""
        self._sleeping = bool(on)

    # ------------------------------------------------------------ 软影响

    def action_weights(self) -> dict[str, float] | None:
        """按当前数值给待机小动作加权；状态良好时返回 None（维持等概率）。"""
        warn = self._number("warn_threshold", 30.0)
        if self._mood >= warn and self._satiety >= warn and self._energy >= warn:
            return None
        weights = {name: 1.0 for name in _AUTO_ACTIONS}
        if self._mood < warn:
            weights["sad"] *= 3.0
            weights["cry"] *= 3.0
        if self._satiety < warn:
            weights["anxious"] *= 3.0
            weights["cry"] *= 2.0
        if self._energy < warn:
            weights["walk"] *= 0.3
            weights["surprise"] *= 0.5
        return weights

    # ------------------------------------------------------------ 恢复

    def feed(self, satiety: float, mood: float) -> None:
        """吃东西：补饱腹与心情（封顶 100），并立即落盘。"""
        self._satiety = _clamp(self._satiety + float(satiety))
        self._mood = _clamp(self._mood + float(mood))
        self._check_thresholds()
        self._persist(force=True)

    # ------------------------------------------------------------ 生命周期

    def enable(self) -> None:
        self._enabled = True
        self._last = self._clock()  # 别把停用期间的那段算进衰减

    def disable(self) -> None:
        self._enabled = False
        self._persist(force=True)

    def tick(self, now: datetime) -> None:
        if not self._enabled:
            return
        elapsed = (now - self._last).total_seconds()
        self._last = now
        if elapsed <= 0:
            return
        hours = elapsed / 3600.0
        mult = self._work_multiplier() if self._working else 1.0

        self._mood = _clamp(self._mood - self._number("mood_decay_per_hour", 6.0) * hours * mult)
        if self._sleeping:
            self._energy = _clamp(
                self._energy + self._number("energy_sleep_recover_per_hour", 30.0) * hours
            )
        else:
            self._energy = _clamp(
                self._energy - self._number("energy_decay_per_hour", 8.0) * hours * mult
            )
        self._satiety = _clamp(self._satiety - self._number("satiety_decay_per_hour", 10.0) * hours)

        self._check_thresholds()
        self._persist()

    def sync_config(self) -> None:
        self._write_config()

    # ------------------------------------------------------------ 内部

    def _check_thresholds(self) -> None:
        """跌破低阈值冒一次泡；回到警戒线以上才重新武装。"""
        low = self._number("low_threshold", 10.0)
        warn = self._number("warn_threshold", 30.0)
        for field, _key, text, category in _LEVELS:
            value = getattr(self, f"_{field}")
            if value < low and field not in self._warned:
                self._warned.add(field)
                self.ctx.notify(text, category)
            elif value >= warn and field in self._warned:
                self._warned.discard(field)

    def _work_multiplier(self) -> float:
        value = self._number("work_decay_multiplier", 2.0)
        return value if value >= 1.0 else 1.0

    def _write_config(self) -> None:
        node = self.ctx.config.setdefault("modules", {}).setdefault("vitals", {})
        node["mood"] = round(self._mood, 2)
        node["energy"] = round(self._energy, 2)
        node["satiety"] = round(self._satiety, 2)

    def _persist(self, force: bool = False) -> None:
        self._write_config()
        now = self._clock()
        if not force and (now - self._last_save).total_seconds() < _SAVE_INTERVAL_SECONDS:
            return
        self._last_save = now
        self.ctx.save()

    def _level(self, key: str, default: float) -> float:
        return _clamp(self._number(key, default))

    def _number(self, key: str, default: float) -> float:
        value = get(self.ctx.config, f"modules.vitals.{key}", default)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return float(default)


MODULE_CLASSES.append(Vitals)
