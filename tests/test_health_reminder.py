import copy
from datetime import datetime, timedelta
from modules.base import ModuleContext
from modules.health_reminder import HealthReminder
from pet.config import DEFAULTS


class Clock:
    def __init__(self): self.now = datetime(2026, 10, 20, 9, 0, 0)
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)


def make(water=45, sit=60, snooze=10, water_on=True, sit_on=True):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["health_reminder"].update({"enabled": True, "water_min": water, "sit_min": sit,
                                              "snooze_min": snooze, "water_enabled": water_on,
                                              "sit_enabled": sit_on})
    notes = []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), lambda s: None, cfg, lambda: None)
    clock = Clock()
    m = HealthReminder(ctx, clock=clock)
    m.enable()
    return m, notes, clock, cfg


def test_water_fires_after_interval_and_not_again(qapp):
    m, notes, clock, _ = make()
    clock.adv(minutes=44); m.tick(clock())
    assert notes == []
    clock.adv(minutes=1); m.tick(clock())
    assert notes == [("该喝水啦", "drink")]
    m.tick(clock())
    assert len(notes) == 1


def test_sit_fires_independently_with_its_own_interval(qapp):
    m, notes, clock, _ = make(water=45, sit=60)
    clock.adv(minutes=60); m.tick(clock())
    assert ("起来动一动吧", "happy") in notes and ("该喝水啦", "drink") in notes


def test_water_sub_switch_off_silences_only_water(qapp):
    m, notes, clock, _ = make(water_on=False, sit_on=True)
    clock.adv(minutes=90); m.tick(clock())
    assert ("该喝水啦", "drink") not in notes and ("起来动一动吧", "happy") in notes


def test_sit_sub_switch_off_silences_only_sit(qapp):
    m, notes, clock, _ = make(water_on=True, sit_on=False)
    clock.adv(minutes=90); m.tick(clock())
    assert ("起来动一动吧", "happy") not in notes and ("该喝水啦", "drink") in notes


def test_snooze_postpones_next_reminder(qapp):
    m, notes, clock, _ = make(snooze=10)
    clock.adv(minutes=45); m.tick(clock())
    assert len(notes) == 1
    m.snooze("water")
    clock.adv(minutes=9); m.tick(clock())
    assert len(notes) == 1
    clock.adv(minutes=2); m.tick(clock())
    assert len(notes) == 2


def test_repeated_tick_does_not_refire_within_interval(qapp):
    m, notes, clock, _ = make()
    clock.adv(minutes=45); m.tick(clock())
    for _ in range(60):
        m.tick(clock())
    assert len([n for n in notes if n[0] == "该喝水啦"]) == 1


def test_next_at_reflects_snooze(qapp):
    m, notes, clock, _ = make(snooze=10)
    m.snooze("water")
    assert (m.next_at("water") - clock()).total_seconds() == 10 * 60


def test_disable_silences_everything(qapp):
    m, notes, clock, _ = make()
    m.set_enabled(False)
    clock.adv(minutes=200); m.tick(clock())
    assert notes == []
