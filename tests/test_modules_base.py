import copy
from datetime import datetime

from modules.base import MODULE_CLASSES, Module, ModuleContext, build_modules
from pet.config import DEFAULTS


class Dummy(Module):
    name = "dummy"
    title = "假模块"

    def enable(self):
        self.events.append("enable")

    def disable(self):
        self.events.append("disable")

    def tick(self, now):
        self.events.append(("tick", now))


def make_ctx(cfg=None):
    cfg = cfg if cfg is not None else copy.deepcopy(DEFAULTS)
    notes, tray, saved = [], [], []
    cfg.setdefault("modules", {})["dummy"] = {"enabled": False}
    ctx = ModuleContext(
        lambda text, category, duration_ms: notes.append((text, category, duration_ms)),
        tray.append,
        cfg,
        lambda: saved.append(True),
    )
    return ctx, notes, tray, saved, cfg


def test_ctx_notify_forwards_text_category_and_duration():
    ctx, notes, tray, _, _ = make_ctx()
    ctx.notify("该喝水啦")
    ctx.notify("专注完成", category="happy", duration_ms=1234)
    assert notes == [("该喝水啦", "happy", 6000), ("专注完成", "happy", 1234)]


def test_ctx_set_tray_text_and_save():
    ctx, _, tray, saved, _ = make_ctx()
    ctx.set_tray_text("CPU 12%")
    ctx.save()
    assert tray == ["CPU 12%"] and saved == [True]


def test_set_enabled_toggles_calls_and_persists_flag():
    ctx, _, _, saved, cfg = make_ctx()
    m = Dummy(ctx)
    assert m.enabled is False
    m.set_enabled(True)
    assert m.enabled is True and "enable" in m.events and cfg["modules"]["dummy"]["enabled"] is True
    m.set_enabled(False)
    assert m.enabled is False and "disable" in m.events and cfg["modules"]["dummy"]["enabled"] is False
    assert saved == [True, True]


def test_disabled_module_tick_does_not_notify():
    ctx, notes, _, _, _ = make_ctx()
    m = Dummy(ctx)
    m.tick(datetime(2026, 10, 20, 12, 0))
    assert notes == [] and ("tick", datetime(2026, 10, 20, 12, 0)) in m.events


def test_enable_is_idempotent():
    ctx, _, _, _, _ = make_ctx()
    m = Dummy(ctx)
    m.set_enabled(True)
    m.set_enabled(True)
    assert m.events.count("enable") == 1


def test_build_modules_respects_config_enabled_flag():
    ctx, _, _, _, cfg = make_ctx()
    cfg["modules"]["dummy"]["enabled"] = True
    MODULE_CLASSES.append(Dummy)
    try:
        mods = build_modules(ctx)
        # 阶段 5 逐个接入的真实模块也会注册进 MODULE_CLASSES，这里只断言本假模块
        assert "dummy" in mods and mods["dummy"].enabled is True
    finally:
        MODULE_CLASSES.remove(Dummy)


def test_build_modules_leaves_disabled_module_off():
    ctx, _, _, _, _ = make_ctx()
    MODULE_CLASSES.append(Dummy)
    try:
        mods = build_modules(ctx)
        assert mods["dummy"].enabled is False
    finally:
        MODULE_CLASSES.remove(Dummy)


def test_sub_switches_default_is_empty():
    ctx, _, _, _, _ = make_ctx()
    assert Dummy(ctx).sub_switches() == ()
