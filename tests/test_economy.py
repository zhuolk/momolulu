import copy
from datetime import datetime, timedelta

from modules.base import ModuleContext
from modules.economy import FOOD_BY_KEY, FOODS, Economy
from pet.config import DEFAULTS


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 14, 9, 0, 0)

    def __call__(self):
        return self.now

    def adv(self, **kw):
        self.now += timedelta(**kw)


def make(**overrides):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["economy"].update(overrides)
    notes, saved = [], []
    ctx = ModuleContext(
        lambda text, category, duration_ms: notes.append((text, category)),
        lambda text: None,
        cfg,
        lambda: saved.append(True),
    )
    clock = Clock()
    module = Economy(ctx, clock=clock)
    module.enable()
    return module, notes, saved, clock, cfg


def test_starts_from_configured_coins(qapp):
    m, *_ = make()
    assert m.coins == 0.0
    assert m.working is False and m.earned == 0

    m2, *_ = make(coins=50)
    assert m2.coins == 50.0


def test_working_earns_coins_per_minute(qapp):
    m, _, _, clock, _ = make()
    m.start_work()
    clock.adv(minutes=2)
    m.tick(clock())
    assert m.coins == 2.0  # 1 币 / 分钟


def test_idle_time_earns_nothing(qapp):
    m, _, _, clock, _ = make()
    clock.adv(minutes=10)
    m.tick(clock())
    assert m.coins == 0.0


def test_earned_counts_only_the_current_shift(qapp):
    m, _, _, clock, _ = make()
    m.start_work()
    clock.adv(minutes=3)
    m.tick(clock())
    assert m.earned == 3

    m.stop_work()
    assert m.earned == 0  # 下班后不再显示这一班的进账

    m.start_work()  # 新的一班从头算
    clock.adv(minutes=1)
    m.tick(clock())
    assert (m.coins, m.earned) == (4.0, 1)


def test_spend_deducts_and_refuses_when_short(qapp):
    m, _, _, _, _ = make(coins=30)
    assert m.spend(10) is True and m.coins == 20.0
    assert m.spend(25) is False and m.coins == 20.0  # 余额不足不扣


def test_focus_links_to_working(qapp):
    m, *_ = make()
    m.set_focus(True)
    assert m.working is True
    m.set_focus(False)
    assert m.working is False


def test_manual_and_focus_are_independent_sources(qapp):
    """手动上班与番茄钟专注是「或」的关系，任一方还在就仍算在上班。"""
    m, *_ = make()
    m.start_work()
    m.set_focus(True)
    m.set_focus(False)
    assert m.working is True  # 手动那一份还在
    m.stop_work()
    assert m.working is False


def test_status_text_shows_shift_earnings(qapp):
    m, _, _, clock, _ = make(coins=7)
    assert m.status_text() == "噜噜币 7"
    m.start_work()
    clock.adv(minutes=2)
    m.tick(clock())
    assert m.status_text() == "上班中 · 已赚 2 噜噜币"


def test_income_rate_is_configurable(qapp):
    m, _, _, clock, _ = make(income_per_minute=3)
    m.start_work()
    clock.adv(minutes=2)
    m.tick(clock())
    assert m.coins == 6.0


def test_sync_config_writes_coins_back(qapp):
    """设置面板整份覆盖配置后，靠 `sync_config` 把当下的币补回去。"""
    m, _, _, clock, cfg = make(coins=5)
    m.start_work()
    clock.adv(minutes=1)
    m.tick(clock())
    cfg["modules"]["economy"]["coins"] = -999  # 模拟被面板打开时的旧快照顶掉
    m.sync_config()
    assert cfg["modules"]["economy"]["coins"] == 6.0


def test_food_bonuses_grow_with_price(qapp):
    """越贵的食物补的饱腹与心情越多（用户要求）。"""
    by_price = sorted((price, satiety, mood) for _key, _l, price, satiety, mood in FOODS)
    prices = [price for price, _, _ in by_price]
    satieties = [satiety for _, satiety, _ in by_price]
    moods = [mood for _, _, mood in by_price]
    assert prices == sorted(prices)
    assert satieties == sorted(satieties) and len(set(satieties)) == len(satieties)
    assert moods == sorted(moods) and len(set(moods)) == len(moods)
    assert set(FOOD_BY_KEY) == {key for key, *_ in FOODS}
