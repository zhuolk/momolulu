"""整体冒烟：`PetApp` 能在离屏环境下正常启动、驱动模块、退出，且不留残留。"""

from pathlib import Path

from PIL import Image
from PyQt5.QtCore import QPoint, QTimer
from PyQt5.QtWidgets import QApplication

import main as pet_main
from main import PetApp
from pet.behavior import PRIORITY_AUTO, WANDER
from pet.catalog import default_categories, save_categories
from pet.config import DEFAULTS, save_config
from pet.wander import WALK_SPEED_PX
from ui.toast import ANCHOR_GAP


def build_root(tmp_path: Path) -> Path:
    (tmp_path / "assets" / "processed").mkdir(parents=True)
    for i in range(1, 4):
        Image.new("RGB", (200, 200), (30 * i, 130, 210)).save(
            tmp_path / "assets" / "processed" / f"lulu_{i:03d}.gif"
        )
    data = default_categories()
    data["categories"]["idle"]["files"] = ["lulu_001.gif", "lulu_002.gif"]
    data["categories"]["happy"]["files"] = ["lulu_003.gif"]
    data["categories"]["walk"]["files"] = ["lulu_001.gif"]
    save_categories(tmp_path / "assets" / "categories.json", data)
    save_config(tmp_path / "config.json", DEFAULTS)
    return tmp_path


def test_app_starts_and_quits_cleanly(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    QTimer.singleShot(300, app.shutdown)
    assert app.run() == 0


def test_app_starts_without_assets(qapp, tmp_path):
    """空素材目录也必须能启动（显示占位图，不崩）"""
    (tmp_path / "assets" / "processed").mkdir(parents=True)
    save_config(tmp_path / "config.json", DEFAULTS)
    app = PetApp(root=tmp_path)
    QTimer.singleShot(200, app.shutdown)
    assert app.run() == 0


def test_shutdown_is_reentrant(qapp, tmp_path):
    """重复调用 `shutdown()` 不报错（`_quit()` 会先关托盘再关应用）。"""
    app = PetApp(root=build_root(tmp_path))
    app.shutdown()
    app.shutdown()


def test_all_modules_can_be_toggled_without_error(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    for module in app.modules.values():
        module.set_enabled(True)
        module.tick(app.clock())
        module.set_enabled(False)
    assert all(not module.enabled for module in app.modules.values())
    app.shutdown()


def test_passthrough_and_edge_hide_survive_toggle(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    app.sprite.set_passthrough(True)
    app.sprite.set_passthrough(False)
    assert app.edge_hider.maybe_hide((4, 400)) is True
    assert app.edge_hider.is_hidden is True
    # 鼠标划过桔子不再自动弹出；把桔子拖离边缘松手才恢复显示
    geo = QApplication.primaryScreen().geometry()
    centre = (geo.x() + geo.width() // 2 - app.sprite.width() // 2, geo.y() + geo.height() // 2)
    assert app.edge_hider.maybe_hide(centre) is False
    assert app.edge_hider.is_hidden is False
    app.shutdown()


def test_toast_follows_pet_while_dragging(qapp, tmp_path):
    """拖拽噜噜时气泡要跟着一起走（气泡是独立顶层窗，不会自己跟随）。"""
    app = PetApp(root=build_root(tmp_path))
    app._show_toast("跟着走")
    assert app.toast.isVisible() is True
    before = app.toast.pos()

    geo = QApplication.primaryScreen().geometry()
    app._on_drag_moved(QPoint(geo.x() + 200, geo.y() + 200))

    anchor = app._pet_anchor()
    assert app.toast.pos() != before
    assert app.toast.x() + app.toast.width() // 2 == anchor[0]
    assert app.toast.y() + app.toast.height() + ANCHOR_GAP == anchor[1]
    app.shutdown()


def test_toast_follows_pet_while_walking(qapp, tmp_path):
    """噜噜自己走动时气泡也要跟着走。"""
    app = PetApp(root=build_root(tmp_path))
    app._show_toast("走着")
    before = app.toast.pos()
    x_before = app.sprite.x()

    assert app.behavior.request("walk", PRIORITY_AUTO) is True
    assert app.behavior.state == WANDER
    app._on_tick()

    assert app.sprite.x() == x_before + WALK_SPEED_PX  # 噜噜自己挪了一格
    assert app.toast.pos() != before                   # 气泡跟着挪
    app.shutdown()


def test_double_click_does_not_open_settings(qapp, tmp_path, monkeypatch):
    """双击噜噜不再弹设置面板，设置只从右键菜单进。"""
    opened = []

    class _FakeSignal:
        def connect(self, *args):
            pass

    class _FakeDialog:
        def __init__(self, *args, **kwargs):
            opened.append(True)
            self.config_saved = _FakeSignal()

        def exec_(self):
            return 0

    app = PetApp(root=build_root(tmp_path))
    monkeypatch.setattr(pet_main, "SettingsDialog", _FakeDialog)

    app.sprite.double_clicked.emit()
    assert opened == []

    app._menu_handlers()["open_settings"]()  # 右键菜单的入口仍在
    assert opened == [True]
    app.shutdown()
