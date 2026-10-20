from pathlib import Path

from PIL import Image

from tools_cli.gif_pipeline import process_gif, resize_frame


def make_gif(path: Path, size=(600, 600), frames=20, bg=(255, 255, 255), subject=(30, 130, 210)):
    imgs = []
    for i in range(frames):
        im = Image.new("RGB", size, bg)
        for x in range(120, 480):
            for y in range(120, 480):
                if (x + i) % 4 != 0:
                    im.putpixel((x, y), subject)
        imgs.append(im)
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=40, loop=0)


def test_resize_frame_caps_long_side_keeps_ratio():
    assert resize_frame(Image.new("RGB", (640, 320)), 320).size == (320, 160)
    assert resize_frame(Image.new("RGB", (320, 640)), 320).size == (160, 320)


def test_process_gif_easy_becomes_transparent_and_capped(tmp_path):
    src = tmp_path / "in.gif"; make_gif(src)
    r = process_gif(src, tmp_path / "out.gif")
    assert (r["grade"], r["track"], r["has_alpha"]) == ("easy", "transparent", True)
    assert max(r["dst_size"]) <= 200 and r["fps"] <= 10
    out = Image.open(tmp_path / "out.gif")
    assert out.n_frames <= 13 and out.convert("RGBA").getpixel((0, 0))[3] == 0


def test_process_gif_gradient_becomes_card(tmp_path):
    src = tmp_path / "grad.gif"
    im = Image.new("RGB", (300, 300))
    for x in range(300):
        for y in range(300):
            im.putpixel((x, y), (x % 256, y % 256, (x * y) % 256))
    im.save(src, save_all=True, append_images=[im], duration=80)
    r = process_gif(src, tmp_path / "o.gif")
    assert r["track"] == "card" and r["has_alpha"] is False and (tmp_path / "o.gif").exists()


def test_process_gif_existing_alpha_stays_transparent(tmp_path):
    src = tmp_path / "a.gif"
    f = Image.new("RGBA", (300, 300), (255, 255, 255, 0))
    for x in range(100, 200):
        for y in range(100, 200):
            f.putpixel((x, y), (10, 200, 10, 255))
    f.save(src, save_all=True, append_images=[f], duration=100)
    r = process_gif(src, tmp_path / "ao.gif")
    assert r["track"] == "transparent" and r["has_alpha"] is True


def test_process_gif_single_frame_and_blank_image(tmp_path):
    single = tmp_path / "one.gif"; Image.new("RGB", (300, 300), (255, 255, 255)).save(single)
    r1 = process_gif(single, tmp_path / "one_o.gif")
    assert r1["frames"] == 1 and r1["track"] == "card"     # 整图背景色 → 不能输出全透明图
    assert (tmp_path / "one_o.gif").exists()


def test_process_gif_reports_bytes_and_sizes(tmp_path):
    src = tmp_path / "in.gif"; make_gif(src)
    r = process_gif(src, tmp_path / "out.gif")
    assert r["src_bytes"] > r["dst_bytes"] > 0
    assert r["src_size"] == (600, 600) and max(r["dst_size"]) <= 200
