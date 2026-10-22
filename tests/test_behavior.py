from datetime import datetime, timedelta
from pet.behavior import Behavior, PRIORITY_AUTO, PRIORITY_MODULE, PRIORITY_USER
from pet.config import DEFAULTS


class FakeSprite:
    def __init__(self): self.played = []; self.frozen = False
    def play(self, category, once=False): self.played.append((category, once)); return True
    def freeze(self): self.frozen = True
    def unfreeze(self): self.frozen = False


class Clock:
    def __init__(self): self.now = datetime(2026, 10, 20, 9, 0, 0)
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)


def make():
    clock, sp = Clock(), FakeSprite()
    b = Behavior(sp, DEFAULTS, clock=clock)
    b.start()
    return b, sp, clock


def test_starts_in_idle_playing_idle(qapp):
    b, sp, _ = make()
    assert b.state == "IDLE" and sp.played[-1] == ("idle", False)


def test_module_event_overrides_auto_and_blocks_lower(qapp):
    b, sp, _ = make()
    b.request("walk", PRIORITY_AUTO)
    assert b.request("eat", PRIORITY_MODULE) is True and b.state == "EAT"
    assert b.request("walk", PRIORITY_AUTO) is False and b.state == "EAT"


def test_user_overrides_auto_but_not_module(qapp):
    b, sp, _ = make()
    b.request("sleep", PRIORITY_AUTO)
    assert b.request("happy", PRIORITY_USER) is True and b.state == "HAPPY"
    b.request("eat", PRIORITY_MODULE)
    assert b.request("happy", PRIORITY_USER) is False and b.state == "EAT"


def test_event_state_returns_to_idle_on_finish_or_timeout(qapp):
    b, sp, clock = make()
    b.request("eat", PRIORITY_MODULE, once=True)
    b.on_play_finished("eat")
    assert b.state == "IDLE"
    b.request("eat", PRIORITY_MODULE, once=True, max_ms=3000)
    clock.adv(seconds=4); b.tick(clock())
    assert b.state == "IDLE"


def test_drag_freezes_animation_beats_module_and_restores(qapp):
    b, sp, _ = make()
    b.request("eat", PRIORITY_MODULE)
    b.on_drag_started()
    assert b.state == "DRAGGED" and sp.frozen is True
    b.request("walk", PRIORITY_AUTO)
    assert b.state == "DRAGGED"
    b.on_drag_finished()
    assert b.state == "IDLE" and sp.frozen is False


def test_click_plays_happy_once_and_fast_click_plays_angry(qapp):
    b, sp, _ = make()
    b.on_user_click()
    assert b.state == "HAPPY" and sp.played[-1] == ("happy", True)
    b.on_fast_click()
    assert b.state == "ANGRY"


def test_auto_wander_after_interval_and_user_activity_resets_sleep_timer(qapp):
    b, sp, clock = make()
    b.force_wander_chance(1.0)
    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_wander"][1] + 1)
    b.tick(clock())
    assert b.state in ("WANDER", "SAD", "BATH")   # 待机小动作：走 / 难过 / 洗澡
    b.on_user_click(); b.on_play_finished("happy")
    clock.adv(seconds=800); b.tick(clock())
    assert b.state != "SLEEP"      # 用户操作重置了睡眠计时：800s < 900s 不应入睡


def test_sleep_after_long_idle(qapp):
    b, sp, clock = make()
    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_sleep"] + 1)
    b.tick(clock())
    assert b.state in ("SLEEP", "WANDER", "SAD", "BATH")


def test_stop_freezes_transitions(qapp):
    b, sp, clock = make()
    b.stop(); b.force_wander_chance(1.0)
    clock.adv(seconds=9999); b.tick(clock())
    assert b.state == "IDLE"


def test_stroll_is_a_sustained_module_state(qapp):
    """散步是持续（`once=False`）的模块级状态：待机随机动作不能把它抢回 idle。"""
    b, sp, clock = make()
    assert b.request("stroll", PRIORITY_MODULE, once=False) is True
    assert b.state == "STROLL"
    b.force_wander_chance(1.0)
    clock.adv(seconds=9999); b.tick(clock())
    assert b.state == "STROLL"


def test_stroll_finished_returns_to_idle(qapp):
    b, sp, _ = make()
    b.request("stroll", PRIORITY_MODULE, once=False)
    b.on_stroll_finished()
    assert b.state == "IDLE" and sp.played[-1] == ("idle", False)


def test_stroll_finished_ignored_when_other_state_took_over(qapp):
    """被拖拽抢走后，散步的收尾回调不该把状态从别处拽回待机。"""
    b, sp, _ = make()
    b.request("stroll", PRIORITY_MODULE, once=False)
    b.on_drag_started()
    b.on_stroll_finished()
    assert b.state == "DRAGGED"
