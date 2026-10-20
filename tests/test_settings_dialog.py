import copy
from ui.settings_dialog import SettingsDialog
from pet.config import DEFAULTS


def test_widgets_initialised_from_config(qapp):
    d = SettingsDialog(copy.deepcopy(DEFAULTS))
    assert d.values()["pet"]["scale"] == DEFAULTS["pet"]["scale"]
    assert d.values()["modules"]["pomodoro"]["focus_min"] == 25
    assert d.values()["modules"]["meal_reminder"]["times"] == ["12:00", "18:30"]


def test_editing_values_roundtrips(qapp):
    cfg = copy.deepcopy(DEFAULTS)
    d = SettingsDialog(cfg)
    d.set_field("pet.scale", 1.5)
    d.set_field("modules.pomodoro.focus_min", 50)
    d.set_field("modules.meal_reminder.times", ["08:00", "20:00"])
    out = d.values()
    assert out["pet"]["scale"] == 1.5
    assert out["modules"]["pomodoro"]["focus_min"] == 50
    assert out["modules"]["meal_reminder"]["times"] == ["08:00", "20:00"]


def test_invalid_scale_is_rejected_on_accept(qapp):
    d = SettingsDialog(copy.deepcopy(DEFAULTS))
    d.set_field("pet.scale", 9.9)
    assert d.accept() is False
    assert d.error_text != ""


def test_valid_accept_emits_signal_with_validated_config(qapp):
    d = SettingsDialog(copy.deepcopy(DEFAULTS))
    got = []
    d.config_saved.connect(got.append)
    d.set_field("modules.hourly_chime.enabled", True)
    assert d.accept() is True
    assert got[0]["modules"]["hourly_chime"]["enabled"] is True


def test_input_config_is_not_mutated(qapp):
    cfg = copy.deepcopy(DEFAULTS)
    d = SettingsDialog(cfg)
    d.set_field("pet.scale", 1.8)
    d.values()
    assert cfg["pet"]["scale"] == DEFAULTS["pet"]["scale"]
