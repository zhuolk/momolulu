import copy
from datetime import datetime, timedelta
from modules.base import ModuleContext
from modules.hourly_chime import HourlyChime
from pet.config import DEFAULTS


class Clock:
    def __init__(self, now=datetime(2026, 10, 20, 13, 59, 30)): self.now = now
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)
    def set(self, **kw): self.now = self.now.replace(**kw)


def make():
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["hourly_chime"].update({"enabled": True})
    notes = []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), lambda s: None, cfg, lambda: None)
    clock = Clock()
    m = HourlyChime(ctx, clock=clock)
    m.enable()
    return m, notes, clock


def test_fires_on_the_hour_once(qapp):
    m, notes, clock = make()
    clock.set(hour=14, minute=0, second=10)
    m.tick(clock())
    assert notes == [("现在是 14:00", "idle")]
    clock.set(second=40); m.tick(clock())
    assert len(notes) == 1


def test_does_not_fire_mid_hour(qapp):
    m, notes, clock = make()
    clock.set(hour=14, minute=30)
    m.tick(clock())
    assert notes == []


def test_fires_each_hour_and_next_day(qapp):
    """Review Focus #5"""
    m, notes, clock = make()
    clock.set(hour=14, minute=0, second=0); m.tick(clock())
    clock.set(hour=15, minute=0, second=0); m.tick(clock())
    clock.adv(days=1); clock.set(hour=14, minute=0, second=0); m.tick(clock())
    assert [n[0] for n in notes] == ["现在是 14:00", "现在是 15:00", "现在是 14:00"]


def test_clock_rollback_does_not_refire(qapp):
    m, notes, clock = make()
    clock.set(hour=14, minute=0, second=5); m.tick(clock())
    clock.set(hour=13, minute=59, second=50); m.tick(clock())
    clock.set(hour=14, minute=0, second=5); m.tick(clock())
    assert len(notes) == 1


def test_disable_silences(qapp):
    m, notes, clock = make()
    m.set_enabled(False)
    clock.set(hour=14, minute=0, second=5); m.tick(clock())
    assert notes == []
