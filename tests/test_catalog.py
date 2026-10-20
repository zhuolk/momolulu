import json, random
from pathlib import Path
from pet.catalog import (CATEGORIES, FALLBACK, default_categories, load_categories, save_categories,
                         existing_files, add_unassigned, set_track, pick)


def prep(tmp_path, files=("lulu_001.gif",)):
    for n in files:
        (tmp_path / n).write_bytes(b"GIF89a")
    return tmp_path


def test_default_structure_and_fallback_chain():
    d = default_categories()
    assert set(CATEGORIES) | {"unassigned"} <= set(d["categories"]) and d["version"] == 2
    for c in CATEGORIES:
        assert FALLBACK[c][0] == c and FALLBACK[c][-1] == "unassigned"
    assert FALLBACK["drink"] == ("drink", "eat", "idle", "unassigned")


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
