from pathlib import Path
from PIL import Image
from tools_cli.prepare import md5_of, load_index, save_index, next_index_number, run_prepare
from pet.catalog import load_categories


def make_gif(path: Path, color=(30, 130, 210), frames=6):
    # 主体必须 >= 画布 25%，否则被清除比例 > 0.75 会被判为 hard（见 spec §5.1-5）
    imgs = []
    for _ in range(frames):
        im = Image.new("RGB", (400, 400), (255, 255, 255))
        for x in range(80, 320):
            for y in range(80, 320):
                im.putpixel((x, y), color)
        imgs.append(im)
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=60, loop=0)


def dirs(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "processed"
    raw.mkdir(); out.mkdir()
    return raw, out, tmp_path / "categories.json", tmp_path / ".index.json"


def test_next_index_number_counts_from_max(tmp_path):
    assert next_index_number(tmp_path) == 1
    for n in (3, 10, 7):
        (tmp_path / f"lulu_{n:03d}.gif").write_bytes(b"GIF89a")
    assert next_index_number(tmp_path) == 11


def test_run_prepare_processes_and_registers_unassigned(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "a.gif"); make_gif(raw / "b.gif", color=(200, 30, 30))
    rep = run_prepare(raw, out, cats, idx)
    assert rep["processed"] == 2 and rep["failed"] == [] and rep["easy"] == 2
    assert sorted(p.name for p in out.glob("*.gif")) == ["lulu_001.gif", "lulu_002.gif"]
    d = load_categories(cats)
    assert sorted(d["categories"]["unassigned"]["files"]) == ["lulu_001.gif", "lulu_002.gif"]
    assert d["categories"]["unassigned"]["track"] == "transparent"


def test_run_prepare_skips_content_duplicates(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "a.gif")
    (raw / "b.gif").write_bytes((raw / "a.gif").read_bytes())
    rep = run_prepare(raw, out, cats, idx)
    assert rep["processed"] == 1 and rep["skipped_duplicate"] == 1


def test_run_prepare_incremental_appends_without_overwriting(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "a.gif")
    run_prepare(raw, out, cats, idx)
    make_gif(raw / "b.gif", color=(10, 200, 10))
    rep = run_prepare(raw, out, cats, idx)
    assert rep["processed"] == 1
    assert sorted(p.name for p in out.glob("*.gif")) == ["lulu_001.gif", "lulu_002.gif"]


def test_run_prepare_rebuild_clears_stale_output(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "a.gif")
    run_prepare(raw, out, cats, idx)
    (out / "stale.gif").write_bytes(b"GIF89a")
    rep = run_prepare(raw, out, cats, idx, rebuild=True)
    assert rep["processed"] == 1 and not (out / "stale.gif").exists()


def test_run_prepare_records_broken_file_and_continues(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "good.gif"); (raw / "broken.gif").write_text("not a gif")
    rep = run_prepare(raw, out, cats, idx)
    assert rep["processed"] == 1 and [f["file"] for f in rep["failed"]] == ["broken.gif"]


def test_run_prepare_sample_limits_and_reports_sizes(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    for i in range(4):
        make_gif(raw / f"{i}.gif", color=(i * 40, 100, 100))
    rep = run_prepare(raw, out, cats, idx, sample=2)
    assert rep["processed"] == 2
    # 这里不断言 before > after：合成素材只有纯色块，源图本身已被 PIL 的帧内增量压到 ~1.4KB，
    # 低于 GIF 的调色板+文件头地板（~2KB），输出必然更大。真实素材的压缩比由 Task 4 Step 5 验证。
    assert rep["total_bytes_before"] > 0 and rep["total_bytes_after"] > 0
    sizes = [size for _, size in rep["largest"]]
    assert len(sizes) == 2 and sizes == sorted(sizes, reverse=True)
    assert rep["largest"][0][0].startswith("lulu_")


def test_index_roundtrip_and_corrupt_recovery(tmp_path):
    p = tmp_path / "x.gif"; p.write_bytes(b"GIF89a")
    idx = {"version": 1, "entries": {md5_of(p): {"name": "lulu_001.gif", "track": "card"}}}
    save_index(tmp_path / ".index.json", idx)
    assert load_index(tmp_path / ".index.json") == idx
    (tmp_path / ".index.json").write_text("{oops")
    assert load_index(tmp_path / ".index.json") == {"version": 1, "entries": {}}
