import copy
from datetime import datetime, timedelta
from modules.base import ModuleContext
from modules.meal_reminder import MealReminder
from pet.config import DEFAULTS


class Clock:
    def __init__(self, now=datetime(2026, 10, 20, 11, 59, 0)): self.now = now
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)
    def set(self, **kw): self.now = self.now.replace(**kw)


def make(times=("12:00", "18:30")):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["meal_reminder"].update({"enabled": True, "times": list(times)})
    notes = []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), lambda s: None, cfg, lambda: None)
    clock = Clock()
    m = MealReminder(ctx, clock=clock)
    m.enable()
    return m, notes, clock, cfg


def test_fires_at_noon_once(qapp):
    m, notes, clock, _ = make()
    clock.set(hour=12, minute=0, second=0)
    m.tick(clock())
    assert notes == [("12:00 到啦，该吃饭咯", "eat")]
    clock.set(minute=1)
    m.tick(clock())
    assert len(notes) == 1


def test_fires_at_evening_time(qapp):
    m, notes, clock, _ = make()
    clock.set(hour=18, minute=30, second=0)
    m.tick(clock())
    assert [n[0] for n in notes] == ["18:30 到啦，该吃饭咯"]


def test_does_not_backfill_missed_time(qapp):
    m, notes, clock, _ = make()
    clock.set(hour=13, minute=30)
    m.tick(clock())
    assert notes == []


def test_fires_again_next_day_and_across_midnight(qapp):
    """Review Focus #5"""
    m, notes, clock, _ = make()
    clock.set(hour=12, minute=0, second=0); m.tick(clock())
    clock.adv(days=1); clock.set(hour=12, minute=0, second=0); m.tick(clock())
    assert len(notes) == 2 and notes[0][0] == notes[1][0]
    assert ("2026-10-20", "12:00") in m.fired_keys and ("2026-10-21", "12:00") in m.fired_keys


def test_clock_rollback_does_not_refire_same_key(qapp):
    """Review Focus #5：时钟回拨后再次经过同一时刻，不得重复触发"""
    m, notes, clock, _ = make()
    clock.set(hour=12, minute=0, second=0); m.tick(clock())
    before = len(notes)
    clock.set(hour=11, minute=58); m.tick(clock())
    clock.set(hour=12, minute=0); m.tick(clock())
    assert len(notes) == before


def test_configurable_times_are_respected(qapp):
    m, notes, clock, _ = make(times=("08:00",))
    clock.set(hour=12, minute=0); m.tick(clock())
    assert notes == []
    clock.set(hour=8, minute=0, second=0); m.tick(clock())
    assert [n[0] for n in notes] == ["08:00 到啦，该吃饭咯"]


def test_disable_silences(qapp):
    m, notes, clock, _ = make()
    m.set_enabled(False)
    clock.set(hour=12, minute=0, second=0); m.tick(clock())
    assert notes == []
