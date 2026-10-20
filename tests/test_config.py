import json

from pet.config import DEFAULTS, get, load_config, save_config, validate


def test_defaults_match_spec():
    assert set(DEFAULTS) == {"version", "pet", "modules"}
    assert set(DEFAULTS["modules"]) == {
        "pomodoro",
        "health_reminder",
        "meal_reminder",
        "hourly_chime",
    }
    assert DEFAULTS["modules"]["meal_reminder"]["times"] == ["12:00", "18:30"]
    assert DEFAULTS["pet"]["state_intervals"] == {"idle_to_wander": [30, 120], "idle_to_sleep": 900}
    assert DEFAULTS["modules"]["health_reminder"]["enabled"] is True
    assert DEFAULTS["modules"]["pomodoro"]["enabled"] is False


def test_load_missing_returns_defaults(tmp_path):
    assert load_config(tmp_path / "c.json") == DEFAULTS


def test_load_corrupt_backs_up_and_returns_defaults(tmp_path):
    p = tmp_path / "c.json"; p.write_text("{ broken")
    assert load_config(p) == DEFAULTS and (tmp_path / "c.json.bad").exists()


def test_deep_merge_keeps_user_values_and_fills_gaps(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"version": 1, "pet": {"scale": 2.0}, "modules": {"pomodoro": {"focus_min": 50}}}))
    cfg = load_config(p)
    assert cfg["pet"]["scale"] == 2.0 and cfg["pet"]["always_on_top"] is True
    assert cfg["modules"]["pomodoro"]["focus_min"] == 50 and cfg["modules"]["pomodoro"]["break_min"] == 5


def test_validate_fixes_invalid_types_and_negatives():
    """Review Focus #3"""
    cfg = {"version": 1,
           "pet": {"scale": "big", "state_intervals": {"idle_to_wander": [30, 120], "idle_to_sleep": -5}},
           "modules": {"pomodoro": {"enabled": "yes", "focus_min": -3, "break_min": "x"},
                       "meal_reminder": {"times": "12:00"}, "health_reminder": {}, "hourly_chime": {}}}
    out = validate(cfg)
    assert out["pet"]["scale"] == DEFAULTS["pet"]["scale"]
    assert out["pet"]["state_intervals"]["idle_to_sleep"] == 900
    assert out["modules"]["pomodoro"] == {"enabled": False, "focus_min": 25, "break_min": 5}
    assert out["modules"]["meal_reminder"]["times"] == ["12:00", "18:30"]


def test_validate_keeps_valid_values_and_rejects_bad_times():
    cfg = json.loads(json.dumps(DEFAULTS))
    cfg["modules"]["meal_reminder"]["times"] = ["08:00", "20:15"]
    assert validate(cfg)["modules"]["meal_reminder"]["times"] == ["08:00", "20:15"]
    cfg["modules"]["meal_reminder"]["times"] = ["25:99", "abc"]
    assert validate(cfg)["modules"]["meal_reminder"]["times"] == ["12:00", "18:30"]


def test_validate_does_not_mutate_input_and_keeps_unknown_keys():
    cfg = json.loads(json.dumps(DEFAULTS))
    cfg["modules"]["pomodoro"]["focus_min"] = -1
    cfg["pet"]["my_custom"] = 42
    out = validate(cfg)
    assert cfg["modules"]["pomodoro"]["focus_min"] == -1
    assert out["pet"]["my_custom"] == 42


def test_save_load_roundtrip_and_no_temp_left(tmp_path):
    p = tmp_path / "c.json"
    cfg = json.loads(json.dumps(DEFAULTS)); cfg["pet"]["scale"] = 1.5
    save_config(p, cfg)
    assert load_config(p)["pet"]["scale"] == 1.5
    assert [f.name for f in tmp_path.iterdir()] == ["c.json"]


def test_get_dotted():
    assert get(DEFAULTS, "modules.pomodoro.focus_min") == 25
    assert get(DEFAULTS, "modules.nope.x", "fallback") == "fallback"
