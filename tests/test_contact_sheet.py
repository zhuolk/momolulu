from PIL import Image

from tools_cli.contact_sheet import build_all, build_sheet


def make(tmp_path, n, size=(200, 200)):
    fs = []
    for i in range(n):
        p = tmp_path / f"lulu_{i + 1:03d}.gif"
        Image.new("RGB", size, (i * 7 % 255, 100, 150)).save(p)
        fs.append(p)
    return fs


def test_sheet_grid_size_and_count(tmp_path):
    fs = make(tmp_path, 7)
    assert build_sheet(fs, tmp_path / "s.png", cols=10, rows=6, cell=150) == 7
    w, h = Image.open(tmp_path / "s.png").size
    assert w >= 10 * 150 and h >= 1 * 150


def test_sheet_handles_non_square_and_skips_broken(tmp_path):
    a, b = tmp_path / "a.gif", tmp_path / "b.gif"
    Image.new("RGB", (640, 200), (1, 2, 3)).save(a)
    Image.new("RGB", (20, 640), (9, 9, 9)).save(b)
    broken = tmp_path / "bad.gif"; broken.write_text("nope")
    assert build_sheet([a, b, broken], tmp_path / "s.png", cell=120) == 2


def test_build_all_pages_of_60(tmp_path):
    make(tmp_path, 65)
    out = tmp_path / "out"; out.mkdir()
    pages = build_all(tmp_path, out)
    assert [p.name for p in pages] == ["contact_sheet_01.png", "contact_sheet_02.png"]
