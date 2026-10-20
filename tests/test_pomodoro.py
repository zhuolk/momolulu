import copy
from datetime import datetime, timedelta

from modules.base import ModuleContext
from modules.pomodoro import Pomodoro
from pet.config import DEFAULTS


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 20, 9, 0, 0)

    def __call__(self):
        return self.now

    def adv(self, **kw):
        self.now += timedelta(**kw)


def make(focus=25, brk=5):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["pomodoro"].update({"enabled": True, "focus_min": focus, "break_min": brk})
    notes = []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), lambda s: None, cfg, lambda: None)
    clock = Clock()
    m = Pomodoro(ctx, clock=clock)
    m.enable()
    return m, notes, clock, cfg


def test_starts_idle_and_does_not_notify_before_time():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=24)
    m.tick(clock())
    assert m.phase == "focus" and notes == []
    assert m.remaining_seconds(clock()) == 60


def test_focus_end_notifies_once_and_enters_break():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=25)
    m.tick(clock())
    assert m.phase == "break" and notes == [("专注完成，休息 5 分钟", "happy")]
    clock.adv(minutes=1)
    m.tick(clock())
    assert len(notes) == 1


def test_break_end_notifies_and_enters_focus():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=25)
    m.tick(clock())  # 专注结束 → 进入休息
    clock.adv(minutes=5)
    m.tick(clock())  # 休息结束 → 回到专注
    assert m.phase == "focus" and notes[-1] == ("休息结束，继续专注", "idle")


def test_pause_freezes_remaining_time():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=10)
    m.pause()
    before = m.remaining_seconds(clock())
    clock.adv(minutes=30)
    m.tick(clock())
    assert m.remaining_seconds(clock()) == before and notes == []


def test_skip_jumps_to_next_phase_without_notification():
    m, notes, clock, _ = make()
    m.start()
    m.skip()
    assert m.phase == "break" and notes == []


def test_reset_returns_to_idle():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=10)
    m.reset()
    assert m.phase == "idle" and m.remaining_seconds(clock()) == 25 * 60


def test_disable_stops_ticking():
    m, notes, clock, _ = make()
    m.start()
    m.set_enabled(False)
    clock.adv(minutes=60)
    m.tick(clock())
    assert notes == []


def test_toggle_starts_and_pauses():
    m, notes, clock, _ = make()
    m.toggle()
    assert m.phase == "focus"
    m.toggle()
    assert m.phase == "focus"
    clock.adv(minutes=26)
    m.tick(clock())
    assert notes == []
