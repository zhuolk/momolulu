"""噜噜币与上班：上班按分钟攒币，币用来在商店买食物。

模块只负责「攒币 / 扣币」；食物补的是心情与饱腹（属于数值模块的职责），
两者的耦合留在 `main.py` 牵线，模块之间不互相引用。

上班来源有两处，任一为真即算在上班：菜单手动开关（`start_work` / `stop_work`）
与番茄钟专注联动（`set_focus`）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from modules.base import MODULE_CLASSES, Module, ModuleContext
from pet.config import get

# key, 名称, 价格（噜噜币）, 饱腹 +, 心情 +
FOODS = (
    ("ice_cream", "冰淇淋", 10, 10, 10),
    ("cake", "蛋糕", 20, 20, 20),
    ("burger", "汉堡", 30, 30, 30),
)
FOOD_BY_KEY = {item[0]: item for item in FOODS}

_SAVE_INTERVAL_SECONDS = 60


class Economy(Module):
    """噜噜币账户 + 上班计薪；币只按「在线时间」进账。"""

    name = "economy"
    title = "噜噜币"
    default_enabled = True

    def __init__(self, ctx: ModuleContext, clock: Callable[[], datetime] = datetime.now):
        super().__init__(ctx)
        self._clock = clock
        self._coins = self._read_coins()
        self._manual_work = False
        self._focus = False
        self._last = clock()
        self._last_save = clock()
        self._was_working = False
        self._shift_start_coins = self._coins

    # ------------------------------------------------------------ 只读属性

    @property
    def coins(self) -> float:
        return self._coins

    @property
    def working(self) -> bool:
        return self._manual_work or self._focus

    @property
    def earned(self) -> int:
        """当前这一班已赚的币（没上班时为 0）。"""
        if not self.working:
            return 0
        return max(0, int(self._coins - self._shift_start_coins))

    def status_text(self) -> str:
        """托盘悬停里显示的一行。"""
        if self.working:
            return f"上班中 · 已赚 {self.earned} 噜噜币"
        return f"噜噜币 {int(self._coins)}"

    # ------------------------------------------------------------ 控制

    def start_work(self) -> None:
        self._manual_work = True
        self._refresh_shift()

    def stop_work(self) -> None:
        self._manual_work = False
        self._refresh_shift()

    def set_focus(self, on: bool) -> None:
        """番茄钟专注联动上班（幂等）。"""
        on = bool(on)
        if on == self._focus:
            return
        self._focus = on
        self._refresh_shift()

    def spend(self, amount: float) -> bool:
        """扣币；余额不足返回 False 且不扣。"""
        amount = float(amount)
        if amount < 0 or self._coins < amount:
            return False
        self._coins -= amount
        self._persist(force=True)
        return True

    # ------------------------------------------------------------ 生命周期

    def enable(self) -> None:
        self._enabled = True
        self._last = self._clock()  # 别把停用期间的那段算成上班时间

    def disable(self) -> None:
        self._enabled = False
        self._persist(force=True)

    def tick(self, now: datetime) -> None:
        if not self._enabled:
            return
        self._refresh_shift()
        elapsed = (now - self._last).total_seconds()
        self._last = now
        if not self.working or elapsed <= 0:
            return
        self._coins += elapsed / 60.0 * self._rate()
        self._persist()

    def sync_config(self) -> None:
        self._write_config()

    # ------------------------------------------------------------ 内部

    def _refresh_shift(self) -> None:
        """进出上班的沿：记下这一班的起始币数，并立即落盘。"""
        now_working = self.working
        if now_working == self._was_working:
            return
        self._was_working = now_working
        if now_working:
            self._shift_start_coins = self._coins
        self._persist(force=True)

    def _rate(self) -> float:
        value = get(self.ctx.config, "modules.economy.income_per_minute", 1)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0.0, float(value))
        return 1.0

    def _read_coins(self) -> float:
        value = get(self.ctx.config, "modules.economy.coins", 0)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0.0, float(value))
        return 0.0

    def _write_config(self) -> None:
        node = self.ctx.config.setdefault("modules", {}).setdefault("economy", {})
        node["coins"] = round(self._coins, 2)

    def _persist(self, force: bool = False) -> None:
        self._write_config()
        now = self._clock()
        if not force and (now - self._last_save).total_seconds() < _SAVE_INTERVAL_SECONDS:
            return
        self._last_save = now
        self.ctx.save()


MODULE_CLASSES.append(Economy)
