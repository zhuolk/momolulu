import os
from pathlib import Path

from PIL import Image
from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent, QPixmap

from pet.catalog import add_unassigned, default_categories
from pet.config import DEFAULTS
from pet.sprite import Sprite, placeholder_pixmap, render_frame


def make_gif(path: Path, frames=4, size=(320, 320)):
    imgs = [Image.new("RGB", size, (255, 255, 255)) for _ in range(frames)]
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=100, loop=0)


def catalog_with(tmp_path, names=("lulu_001.gif",), track="transparent", category="idle"):
    d = default_categories()
    for n in names:
        make_gif(tmp_path / n)
    d["categories"][category]["files"] = list(names)
    add_unassigned(d, list(names), {n: track for n in names})
    return d


def press(s, pos, button=Qt.LeftButton):
    s.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPoint(*pos), button, button, Qt.NoModifier))


def release(s, pos, button=Qt.LeftButton):
    s.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPoint(*pos), button, button, Qt.NoModifier))


def move(s, pos):
    s.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPoint(*pos), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))


def test_window_flags_and_attributes(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    assert s.windowFlags() & Qt.FramelessWindowHint and s.windowFlags() & Qt.WindowStaysOnTopHint
    assert s.testAttribute(Qt.WA_TranslucentBackground) and s.testAttribute(Qt.WA_ShowWithoutActivating)


def test_play_missing_assets_returns_false_and_shows_placeholder(qapp, tmp_path):
    """Review Focus #1"""
    s = Sprite(default_categories(), tmp_path, DEFAULTS)
    assert s.play("idle") is False and s.current_frame_pixmap() is not None


def test_play_existing_asset_returns_true(qapp, tmp_path):
    assert Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS).play("idle") is True


def test_movie_cache_bounded_and_switches_assets(qapp, tmp_path):
    names = tuple(f"lulu_{i:03d}.gif" for i in range(1, 9))
    s = Sprite(catalog_with(tmp_path, names=names), tmp_path, DEFAULTS)
    for _ in range(20):
        s.play("idle")
    assert s.movie_cache_size() <= 3


def test_freeze_unfreeze_and_passthrough(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    s.play("idle"); s.freeze()
    assert s.is_frozen() is True
    s.unfreeze(); assert s.is_frozen() is False
    s.set_passthrough(True); assert s.windowFlags() & Qt.WindowTransparentForInput
    s.set_passthrough(False); assert not (s.windowFlags() & Qt.WindowTransparentForInput)


def test_passthrough_toggle_keeps_window_visible(qapp, tmp_path):
    """切穿透不能让噜噜消失：`setWindowFlags` 会重建原生窗口并隐藏它，必须重新 show。"""
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    s.show()
    assert s.isVisible() is True
    s.set_passthrough(True)
    assert s.isVisible() is True
    s.set_passthrough(False)
    assert s.isVisible() is True
    s.hide()


def test_always_on_top_toggle_keeps_window_visible(qapp, tmp_path):
    """同一类缺陷：改窗口标志后不能因为 `isVisible()` 已变 False 而漏掉 show。"""
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    s.show()
    s.set_always_on_top(False)
    assert s.isVisible() is True
    s.set_always_on_top(True)
    assert s.isVisible() is True
    s.hide()


def test_passthrough_does_not_resurrect_hidden_window(qapp, tmp_path):
    """本就隐藏着的窗口，切穿透不应把它弹出来。"""
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    s.hide()
    s.set_passthrough(True)
    assert s.isVisible() is False


def test_render_frame_transparent_keeps_alpha(qapp):
    frame = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    frame.putpixel((40, 40), (255, 0, 0, 255))
    img = render_frame(frame, "transparent").toImage()
    assert img.pixelColor(0, 0).alpha() == 0 and img.pixelColor(40, 40).alpha() > 0


def test_render_frame_card_adds_shadow_margin(qapp):
    pm = render_frame(Image.new("RGBA", (80, 80), (200, 40, 40, 255)), "card")
    assert isinstance(pm, QPixmap) and pm.width() > 80


def test_placeholder_and_orange_are_valid(qapp):
    assert placeholder_pixmap(120).width() == 120
    assert Sprite.draw_orange(48).width() == 48


def test_strip_mode_paints_orange_on_visible_side(qapp, tmp_path):
    """贴边缩回时，屏内那一侧必须画桔子，且不再画素材切片。"""
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    s.play("idle")
    assert s.strip_side is None

    s.set_strip("left")  # 左侧隐藏：屏内可见的是窗口右缘
    assert s.strip_side == "left"
    image = s.grab().toImage()
    assert image.pixelColor(image.width() - 10, image.height() // 2).alpha() > 0
    assert image.pixelColor(10, image.height() // 2).alpha() == 0

    s.set_strip("right")  # 右侧隐藏：屏内可见的是窗口左缘
    image = s.grab().toImage()
    assert image.pixelColor(10, image.height() // 2).alpha() > 0
    assert image.pixelColor(image.width() - 10, image.height() // 2).alpha() == 0

    s.set_strip(None)  # 恢复正常渲染
    assert s.strip_side is None
    image = s.grab().toImage()
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() > 0


def test_move_to_emits_moved_only_when_position_changes(qapp, tmp_path):
    """位置真的变了才发 `moved`（气泡按它跟随），原地重设不重复触发。"""
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    got = []
    s.moved.connect(lambda: got.append((s.x(), s.y())))

    s.move_to(300, 400)
    s.move_to(300, 400)
    s.move_to(301, 400)

    assert got == [(300, 400), (301, 400)]


def test_flip_paints_mirrored_frame(qapp, tmp_path):
    """向左走动时窗口水平镜像渲染，否则看起来是倒着走。"""
    frame = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    for x in range(40):
        for y in range(80):
            frame.putpixel((x, y), (255, 0, 0, 255))  # 只有左半有像素
    frame.save(tmp_path / "lulu_001.gif", save_all=True, append_images=[frame], duration=100, loop=0)

    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif"]
    add_unassigned(d, ["lulu_001.gif"], {"lulu_001.gif": "transparent"})
    s = Sprite(d, tmp_path, DEFAULTS)
    assert s.play("idle") is True

    plain = s.grab().toImage()
    width = plain.width()
    assert plain.pixelColor(2, width // 2).alpha() > 0
    assert plain.pixelColor(width - 3, width // 2).alpha() == 0

    s.set_flip(True)
    flipped = s.grab().toImage()
    assert flipped.pixelColor(2, width // 2).alpha() == 0
    assert flipped.pixelColor(width - 3, width // 2).alpha() > 0


def test_click_and_right_click_emit_signals(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    got = []
    s.clicked.connect(lambda: got.append("click"))
    s.right_clicked.connect(lambda p: got.append("right"))
    press(s, (30, 30)); release(s, (30, 30))
    press(s, (30, 30), Qt.RightButton); release(s, (30, 30), Qt.RightButton)
    assert got == ["click", "right"]


def test_small_move_is_click_large_move_is_drag(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    got = []
    s.clicked.connect(lambda: got.append("click"))
    s.drag_finished.connect(lambda p: got.append("drag"))
    press(s, (10, 10))
    move(s, (12, 12))
    release(s, (12, 12))
    press(s, (10, 10))
    move(s, (40, 40))
    release(s, (40, 40))
    assert got == ["click", "drag"]


def test_five_quick_clicks_emit_fast_click(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    got = []
    s.fast_clicked.connect(lambda: got.append("fast"))
    for _ in range(5):
        press(s, (10, 10)); release(s, (10, 10))
    assert got == ["fast"]


def test_release_movies_clears_cache_without_replay(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    assert s.play("idle") is True
    assert s.movie_cache_size() == 1

    replayed = []
    s.asset_missing.connect(lambda: replayed.append("missing"))
    s.release_movies()

    assert s.movie_cache_size() == 0
    assert replayed == []                    # 没有重播：不触发 asset_missing、也没有新缓存


def test_release_movies_then_reload_plays_again(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    s.play("idle")
    s.release_movies()
    s.reload()
    assert s.movie_cache_size() == 1


def test_release_movies_releases_file_handle(qapp, tmp_path):
    """句柄真实释放的守卫：`release_movies()` 后同一路径必须可被 `os.replace` 覆盖。

    若实现回退为 `deleteLater()`，析构被推迟到下一次事件循环，文件句柄仍被占用，
    这里的 `os.replace` 会抛 `PermissionError`，本用例即失败。
    """
    gif_path = tmp_path / "lulu_001.gif"
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    assert s.play("idle") is True
    assert s.movie_cache_size() == 1

    s.release_movies()

    replacement = tmp_path / "replacement.gif"
    make_gif(replacement, size=(64, 64))
    expected = replacement.read_bytes()
    os.replace(replacement, gif_path)          # 不抛异常即句柄已释放
    assert gif_path.read_bytes() == expected   # 内容确已换成新文件
