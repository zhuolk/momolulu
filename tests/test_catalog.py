import json, random
from pathlib import Path
from pet.catalog import (CATEGORIES, FALLBACK, default_categories, load_categories, save_categories,
                         existing_files, add_unassigned, set_track, loops_of, set_loop, pick,
                         assign_file, forget_file, missing_files)


def prep(tmp_path, files=("lulu_001.gif",)):
    for n in files:
        (tmp_path / n).write_bytes(b"GIF89a")
    return tmp_path


def test_default_structure_and_fallback_chain():
    d = default_categories()
    assert set(CATEGORIES) | {"unassigned"} <= set(d["categories"]) and d["version"] == 3
    for c in CATEGORIES:
        assert FALLBACK[c][0] == c and FALLBACK[c][-1] == "unassigned"
    assert FALLBACK["drink"] == ("drink", "eat", "idle", "unassigned")


def test_new_categories_fall_back_to_the_closest_old_one():
    """新增分类缺素材时按语义就近降级，不要直接掉到 unassigned。"""
    assert set(CATEGORIES) >= {"showup", "awake", "move", "think", "sport", "cry", "anxious", "surprise"}
    assert FALLBACK["cry"][:2] == ("cry", "sad")
    assert FALLBACK["move"][:2] == ("move", "walk")
    assert FALLBACK["anxious"][:2] == ("anxious", "angry")
    assert FALLBACK["surprise"][:2] == ("surprise", "happy")


def test_load_missing_corrupt_or_wrong_shape_returns_default(tmp_path):
    assert load_categories(tmp_path / "nope.json") == default_categories()
    bad = tmp_path / "bad.json"; bad.write_text("{ not json", encoding="utf-8")
    assert load_categories(bad) == default_categories()
    wrong = tmp_path / "wrong.json"; wrong.write_text(json.dumps({"version": 2, "categories": "oops"}), encoding="utf-8")
    assert load_categories(wrong) == default_categories()


def test_save_reload_roundtrip_and_missing_categories_backfilled(tmp_path):
    p = tmp_path / "c.json"
    save_categories(p, {"version": 2, "categories": {"idle": {"files": ["lulu_001.gif"], "track": "auto"}}})
    d = load_categories(p)
    assert d["categories"]["idle"]["files"] == ["lulu_001.gif"]
    assert set(CATEGORIES) <= set(d["categories"])


def test_existing_files_filters_ghosts(tmp_path):
    prep(tmp_path)
    assert existing_files(["lulu_001.gif", "ghost.gif"], tmp_path) == ["lulu_001.gif"]


def test_pick_returns_none_when_no_assets_at_all(tmp_path):
    d = default_categories()
    assert pick(d, "idle", prep(tmp_path, files=())) is None


def test_pick_falls_back_category_to_idle_to_unassigned(tmp_path):
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif"]
    assert pick(d, "drink", prep(tmp_path)).name == "lulu_001.gif"
    d2 = default_categories()
    d2["categories"]["unassigned"]["files"] = ["lulu_001.gif"]
    assert pick(d2, "sleep", prep(tmp_path)).name == "lulu_001.gif"


def test_pick_ignores_missing_index_entries_but_uses_rest(tmp_path):
    """Review Focus #2"""
    d = default_categories()
    d["categories"]["idle"]["files"] = ["ghost.gif", "lulu_001.gif"]
    assert pick(d, "idle", prep(tmp_path)).name == "lulu_001.gif"
    d["categories"]["idle"]["files"] = ["ghost_a.gif", "ghost_b.gif"]
    assert pick(d, "idle", prep(tmp_path)) is None


def test_pick_prefers_requested_track(tmp_path):
    prep(tmp_path, ("lulu_001.gif", "lulu_002.gif"))
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif", "lulu_002.gif"]
    set_track(d, "lulu_001.gif", "card"); set_track(d, "lulu_002.gif", "transparent")
    for _ in range(20):
        assert pick(d, "idle", tmp_path, track="transparent").name == "lulu_002.gif"
    assert pick(d, "idle", tmp_path, track="card").name == "lulu_001.gif"


def test_pick_is_deterministic_with_seeded_rng(tmp_path):
    prep(tmp_path, ("lulu_001.gif", "lulu_002.gif"))
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif", "lulu_002.gif"]
    a = pick(d, "idle", tmp_path, rng=random.Random(7))
    b = pick(d, "idle", tmp_path, rng=random.Random(7))
    assert a.name == b.name


def test_add_unassigned_avoids_duplicates():
    d = default_categories()
    add_unassigned(d, ["lulu_001.gif"], {"lulu_001.gif": "transparent"})
    add_unassigned(d, ["lulu_001.gif"], {"lulu_001.gif": "transparent"})
    assert d["categories"]["unassigned"]["files"] == ["lulu_001.gif"]


def test_loops_defaults_to_loopable_and_survives_roundtrip(tmp_path):
    """没登记的素材算可循环；标了「只播一次」的要能存下来再读回来。"""
    d = default_categories()
    assert loops_of(d, "lulu_001.gif") is True
    set_loop(d, "lulu_001.gif", False)
    assert loops_of(d, "lulu_001.gif") is False

    p = tmp_path / "c.json"
    save_categories(p, d)
    assert loops_of(load_categories(p), "lulu_001.gif") is False


def test_load_categories_ignores_non_boolean_loop_values(tmp_path):
    p = tmp_path / "c.json"
    save_categories(p, {"version": 3, "categories": {}, "loops": {"lulu_001.gif": "no"}})
    assert loops_of(load_categories(p), "lulu_001.gif") is True


def test_assign_file_moves_between_categories_and_refreshes_track(tmp_path):
    """归位要摘干净原分类；混轨时分类聚合轨道回落 auto。"""
    prep(tmp_path, ("lulu_001.gif", "lulu_002.gif"))
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif", "lulu_002.gif"]
    set_track(d, "lulu_001.gif", "transparent")
    set_track(d, "lulu_002.gif", "transparent")
    assert d["categories"]["idle"]["track"] == "transparent"

    assign_file(d, "lulu_001.gif", "sleep")
    set_track(d, "lulu_002.gif", "card")
    assert d["categories"]["idle"]["files"] == ["lulu_002.gif"]
    assert d["categories"]["idle"]["track"] == "card"  # 剩一张就取其轨道
    assert d["categories"]["sleep"]["files"] == ["lulu_001.gif"]

    assign_file(d, "lulu_002.gif", "sleep")
    assert d["categories"]["sleep"]["track"] == "auto"  # 混轨


def test_assign_file_can_take_several_categories_at_once():
    d = default_categories()
    assign_file(d, "lulu_003.gif", ["eat", "drink"])
    assert d["categories"]["eat"]["files"] == ["lulu_003.gif"]
    assert d["categories"]["drink"]["files"] == ["lulu_003.gif"]


def test_forget_file_drops_category_track_and_loop(tmp_path):
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif"]
    set_track(d, "lulu_001.gif", "transparent")
    set_loop(d, "lulu_001.gif", False)

    forget_file(d, "lulu_001.gif")
    assert d["categories"]["idle"]["files"] == [] and d["categories"]["idle"]["track"] == "auto"
    assert "lulu_001.gif" not in d["tracks"] and "lulu_001.gif" not in d["loops"]


def test_missing_files_lists_only_ghosts(tmp_path):
    prep(tmp_path, ("lulu_001.gif",))
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif", "ghost.gif"]
    set_track(d, "ghost2.gif", "card")
    set_loop(d, "ghost3.gif", True)
    assert missing_files(d, tmp_path) == ["ghost.gif", "ghost2.gif", "ghost3.gif"]
