"""素材整理 CLI：清单驱动的分类 / 循环打标、悬空引用清理、清单模板生成。"""

from pathlib import Path

import pytest

from pet.catalog import default_categories, load_categories, loops_of, save_categories, set_loop, set_track
from tools_cli.assign import (
    main,
    parse_loop,
    prune_index,
    read_manifest,
    run_assign,
    write_template,
)
from tools_cli.prepare import load_index, save_index


def make_gif(path: Path) -> None:
    path.write_bytes(b"GIF89a")


def setup_assets(tmp_path, names=("lulu_001.gif", "lulu_002.gif"), category="idle"):
    processed = tmp_path / "processed"
    processed.mkdir()
    for name in names:
        make_gif(processed / name)
    data = default_categories()
    data["categories"][category]["files"] = list(names)
    for name in names:
        set_track(data, name, "transparent")
    cats = tmp_path / "categories.json"
    save_categories(cats, data)
    return processed, cats


def write_manifest(path: Path, rows) -> Path:
    lines = "\n".join(",".join(str(c) for c in row) for row in rows)
    path.write_text("file,category,loop\n" + lines + "\n", encoding="utf-8")
    return path


def test_parse_loop_accepts_common_spellings_and_blank():
    for text in ("true", "TRUE", "yes", "1", "on"):
        assert parse_loop(text) is True
    for text in ("false", "no", "0", "off"):
        assert parse_loop(text) is False
    assert parse_loop("") is None and parse_loop("   ") is None


def test_parse_loop_rejects_garbage():
    with pytest.raises(ValueError):
        parse_loop("看情况")


def test_read_manifest_rejects_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,kind\nlulu_001.gif,idle\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_manifest(bad)


def test_assign_puts_file_in_category_and_sets_loop(tmp_path):
    processed, cats = setup_assets(tmp_path)
    manifest = write_manifest(tmp_path / "a.csv", [("lulu_001.gif", "sleep", "false")])
    report = run_assign(cats, processed, manifest=manifest)

    d = load_categories(cats)
    assert d["categories"]["sleep"]["files"] == ["lulu_001.gif"]
    assert loops_of(d, "lulu_001.gif") is False
    assert report["assigned"] == 1 and report["loops"] == 1 and report["skipped"] == []


def test_assign_pulls_file_out_of_its_old_category(tmp_path):
    processed, cats = setup_assets(tmp_path)
    manifest = write_manifest(tmp_path / "a.csv", [("lulu_001.gif", "happy", "true")])
    run_assign(cats, processed, manifest=manifest)

    d = load_categories(cats)
    assert d["categories"]["happy"]["files"] == ["lulu_001.gif"]
    assert d["categories"]["idle"]["files"] == ["lulu_002.gif"]  # 没被清单点名的还在原地


def test_assign_keeps_extra_categories_when_listed_twice(tmp_path):
    """一张图想同时归两个分类（如吃 / 喝共用），写两行即可。"""
    processed, cats = setup_assets(tmp_path)
    manifest = write_manifest(
        tmp_path / "a.csv",
        [("lulu_001.gif", "eat", "false"), ("lulu_001.gif", "drink", "false")],
    )
    run_assign(cats, processed, manifest=manifest)

    d = load_categories(cats)
    assert d["categories"]["eat"]["files"] == ["lulu_001.gif"]
    assert d["categories"]["drink"]["files"] == ["lulu_001.gif"]
    assert d["categories"]["idle"]["files"] == ["lulu_002.gif"]
    assert loops_of(d, "lulu_001.gif") is False


def test_assign_leaves_unlisted_files_alone(tmp_path):
    processed, cats = setup_assets(tmp_path)
    data = load_categories(cats)
    set_loop(data, "lulu_002.gif", False)  # 没被清单点名的图，现况要原样保留
    save_categories(cats, data)

    manifest = write_manifest(tmp_path / "a.csv", [("lulu_001.gif", "walk", "true")])
    run_assign(cats, processed, manifest=manifest)

    d = load_categories(cats)
    assert d["categories"]["idle"]["files"] == ["lulu_002.gif"]
    assert loops_of(d, "lulu_002.gif") is False


def test_assign_skips_unknown_category_and_missing_file(tmp_path):
    processed, cats = setup_assets(tmp_path)
    manifest = write_manifest(
        tmp_path / "a.csv",
        [("lulu_001.gif", "flying", "true"), ("lulu_999.gif", "idle", "true")],
    )
    report = run_assign(cats, processed, manifest=manifest)

    assert report["assigned"] == 0
    assert [item["file"] for item in report["skipped"]] == ["lulu_001.gif", "lulu_999.gif"]
    d = load_categories(cats)
    assert d["categories"]["idle"]["files"] == ["lulu_001.gif", "lulu_002.gif"]


def test_blank_loop_column_leaves_existing_flag_alone(tmp_path):
    processed, cats = setup_assets(tmp_path)
    data = load_categories(cats)
    set_loop(data, "lulu_001.gif", False)
    save_categories(cats, data)

    manifest = write_manifest(tmp_path / "a.csv", [("lulu_001.gif", "idle", "")])
    report = run_assign(cats, processed, manifest=manifest)

    assert report["loops"] == 0
    assert loops_of(load_categories(cats), "lulu_001.gif") is False


def test_prune_forgets_deleted_assets(tmp_path):
    processed, cats = setup_assets(tmp_path)
    (processed / "lulu_002.gif").unlink()
    report = run_assign(cats, processed, prune=True)

    d = load_categories(cats)
    assert report["pruned"] == 1
    assert d["categories"]["idle"]["files"] == ["lulu_001.gif"]
    assert "lulu_002.gif" not in d["tracks"] and "lulu_002.gif" not in d["loops"]


def test_prune_cleans_material_index(tmp_path):
    processed, cats = setup_assets(tmp_path)
    index_path = tmp_path / ".index.json"
    save_index(index_path, {"version": 1, "entries": {"aaa": {"name": "lulu_001.gif", "track": "transparent"}, "bbb": {"name": "lulu_002.gif", "track": "card"}}})
    (processed / "lulu_002.gif").unlink()

    assert prune_index(index_path, processed) == 1
    assert sorted(load_index(index_path)["entries"]) == ["aaa"]
    assert prune_index(index_path, processed) == 0  # 幂等：再跑一次没有可摘的


def test_template_lists_current_state(tmp_path):
    processed, cats = setup_assets(tmp_path)
    data = load_categories(cats)
    set_loop(data, "lulu_002.gif", False)
    save_categories(cats, data)

    out = tmp_path / "assign.csv"
    assert write_template(out, processed, cats) == 2

    rows = [line.split(",") for line in out.read_text(encoding="utf-8").strip().splitlines()]
    assert rows[0] == ["file", "category", "loop"]
    assert rows[1:] == [["lulu_001.gif", "idle", "true"], ["lulu_002.gif", "idle", "false"]]


def test_cli_requires_a_manifest_or_prune(tmp_path):
    processed, cats = setup_assets(tmp_path)
    with pytest.raises(SystemExit):
        main(["--categories", str(cats), "--processed", str(processed)])


def test_cli_template_then_assign_roundtrip(tmp_path):
    processed, cats = setup_assets(tmp_path)
    manifest = tmp_path / "assign.csv"
    assert main(["--template", str(manifest), "--categories", str(cats), "--processed", str(processed)]) == 0

    text = manifest.read_text(encoding="utf-8").replace("lulu_001.gif,idle,true", "lulu_001.gif,walk,false")
    manifest.write_text(text, encoding="utf-8")
    assert main([str(manifest), "--categories", str(cats), "--processed", str(processed)]) == 0

    d = load_categories(cats)
    assert d["categories"]["walk"]["files"] == ["lulu_001.gif"]
    assert loops_of(d, "lulu_001.gif") is False
