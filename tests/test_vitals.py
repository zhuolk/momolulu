import copy
from datetime import datetime, timedelta

from modules.base import ModuleContext
from modules.vitals import Vitals
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
    cfg["modules"]["vitals"].update(overrides)
    notes, saved = [], []
    ctx = ModuleContext(
        lambda text, category, duration_ms: notes.append((text, category)),
        lambda text: None,
        cfg,
        lambda: saved.append(True),
    )
    clock = Clock()
    module = Vitals(ctx, clock=clock)
    module.enable()
    return module, notes, saved, clock, cfg


def test_starts_from_configured_values(qapp):
    m, *_ = make()
    assert (m.mood, m.energy, m.satiety) == (80.0, 80.0, 80.0)


def test_decays_by_the_hour_while_online(qapp):
    m, _, _, clock, _ = make()
    clock.adv(hours=1)
    m.tick(clock())
    assert m.mood == 74.0      # 80 - 6
    assert m.energy == 72.0    # 80 - 8
    assert m.satiety == 70.0   # 80 - 10


def test_working_doubles_mood_and_energy_decay(qapp):
    m, _, _, clock, _ = make()
    m.set_working(True)
    clock.adv(hours=1)
    m.tick(clock())
    assert m.mood == 68.0      # 80 - 6*2
    assert m.energy == 64.0    # 80 - 8*2
    assert m.satiety == 70.0   # 饱腹不受上班影响


def test_sleeping_recovers_energy_instead_of_draining_it(qapp):
    m, _, _, clock, _ = make(energy=40)
    m.set_sleeping(True)
    clock.adv(hours=1)
    m.tick(clock())
    assert m.energy == 70.0    # 40 + 30
    assert m.mood == 74.0      # 睡觉不影响其它两项


def test_values_clamp_at_zero_and_hundred(qapp):
    m, _, _, clock, _ = make(mood=3, energy=95)
    m.set_sleeping(True)
    clock.adv(hours=5)
    m.tick(clock())
    assert m.mood == 0.0                       # 不会变负数
    assert m.energy == 100.0                   # 封顶 100
    assert 0.0 <= m.satiety <= 100.0


def test_offline_time_is_not_deducted(qapp):
    """停用（相当于噜噜没在跑）期间不衰减。"""
    m, _, _, clock, _ = make()
    m.set_enabled(False)
    clock.adv(hours=5)
    m.tick(clock())
    assert m.mood == 80.0 and m.energy == 80.0 and m.satiety == 80.0


def test_feed_raises_satiety_and_mood_capped_at_hundred(qapp):
    m, _, _, clock, _ = make(satiety=20, mood=95)
    m.feed(satiety=10, mood=10)
    assert m.satiety == 30.0
    assert m.mood == 100.0


def test_low_threshold_notifies_once_until_it_recovers(qapp):
    m, notes, _, clock, _ = make(mood=5)
    mood_text = "噜噜心情好低落，来陪我玩会儿吧"

    clock.adv(hours=1)
    m.tick(clock())
    assert [n[0] for n in notes] == [mood_text]

    clock.adv(hours=1)
    m.tick(clock())
    assert len([n for n in notes if n[0] == mood_text]) == 1  # 还在低值区，不反复刷屏

    m.feed(satiety=0, mood=60)  # 补到警戒线以上 → 重新武装
    clock.adv(hours=20)
    m.tick(clock())
    assert len([n for n in notes if n[0] == mood_text]) == 2


def test_values_are_written_back_to_config(qapp):
    m, _, saved, clock, cfg = make()
    clock.adv(hours=1)
    m.tick(clock())
    assert cfg["modules"]["vitals"]["mood"] == 74
    assert cfg["modules"]["vitals"]["energy"] == 72
    assert saved  # 60 秒节流：这一跳已经超时，应落盘一次


def test_action_weights_are_neutral_when_everything_is_fine(qapp):
    m, *_ = make()
    assert m.action_weights() is None


def test_action_weights_favour_negative_moods_when_low(qapp):
    m, *_ = make(mood=5, satiety=5, energy=5)
    weights = m.action_weights()
    assert weights is not None
    assert weights["sad"] > 1.0 and weights["cry"] > 1.0
    assert weights["anxious"] > 1.0
    assert weights["walk"] < 1.0  # 没力气就不爱走动


def test_status_text_rounds_values(qapp):
    m, *_ = make()
    assert m.status_text() == "心情 80 · 活力 80 · 饱腹 80"
