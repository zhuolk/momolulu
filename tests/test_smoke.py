"""整体冒烟：`PetApp` 能在离屏环境下正常启动、驱动模块、退出，且不留残留。"""

from datetime import datetime, timedelta
from pathlib import Path

import copy

from PIL import Image
from PyQt5.QtCore import QPoint, QTimer
from PyQt5.QtWidgets import QApplication

import main as pet_main
from main import PetApp
from pet.behavior import PRIORITY_AUTO, STROLL, WANDER
from pet.catalog import default_categories, save_categories
from pet.config import DEFAULTS, load_config, save_config
from pet.stroll import STROLL_SPEED_PX
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
    data["categories"]["stroll"]["files"] = ["lulu_002.gif"]
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


def test_stroll_from_menu_walks_along_work_area_edge(qapp, tmp_path):
    """搞搞震 ▸ 散步：先从菜单入口瞬移到工作区右下角（让开任务栏）再沿右边向上走。"""
    app = PetApp(root=build_root(tmp_path))
    area = QApplication.primaryScreen().availableGeometry()
    app._menu_handlers()["stroll"]()

    assert app.behavior.state == STROLL
    assert app.stroller.active is True
    assert app.sprite.x() == area.x() + area.width() - app.sprite.width()
    assert app.sprite.y() == area.y() + area.height() - app.sprite.height()

    app._on_tick()  # 走一帧：沿工作区右边向上
    assert app.sprite.x() == area.x() + area.width() - app.sprite.width()
    assert app.sprite.y() == area.y() + area.height() - app.sprite.height() - STROLL_SPEED_PX
    app.shutdown()


def test_leaving_edge_hide_plays_showup_again(qapp, tmp_path):
    """从贴边隐藏里露面时再播一次 `showup`；缩回桔子条不算露面。"""
    app = PetApp(root=build_root(tmp_path))
    calls = []
    app.behavior.play_showup = lambda: calls.append(True) or True

    app.edge_hider.maybe_hide((4, 400))
    assert calls == []

    geo = QApplication.primaryScreen().geometry()
    centre = (geo.x() + geo.width() // 2, geo.y() + geo.height() // 2)
    app.edge_hider.maybe_hide(centre)
    assert calls == [True]
    app.shutdown()


def test_pomodoro_focus_switches_the_idle_asset_to_think(qapp, tmp_path):
    """番茄钟专注期间待机素材换成 `think`，退出专注再换回 `idle`。"""
    app = PetApp(root=build_root(tmp_path))
    app.behavior.tick(datetime.now() + timedelta(seconds=9))  # 让启动时的 `showup` 收尾
    assert app.behavior.state == "IDLE"

    pomodoro = app.modules["pomodoro"]
    pomodoro.set_enabled(True)
    pomodoro.toggle()  # 待机 → 开始专注

    app._on_module_tick()
    assert app.behavior.state == "THINK"

    pomodoro.reset()
    app._on_module_tick()
    assert app.behavior.state == "IDLE"
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


def test_click_and_fast_click_do_not_toast(qapp, tmp_path):
    """点击 / 连点只让噜噜做反应，不再冒泡；气泡只留给模块的到点提醒。"""
    app = PetApp(root=build_root(tmp_path))
    app.sprite.clicked.emit()
    app.sprite.fast_clicked.emit()
    assert app.toast.isVisible() is False
    app.shutdown()


def test_module_notify_still_toasts(qapp, tmp_path):
    """保留的那条路径：模块到点提醒照旧冒泡。"""
    app = PetApp(root=build_root(tmp_path))
    app._module_notify("该喝水啦", "drink")
    assert app.toast.isVisible() is True
    assert app.toast.current_text == "该喝水啦"
    app.shutdown()


# ---------------------------------------------------------------- 生活系统接线


def test_status_line_combines_vitals_and_coins(qapp, tmp_path):
    """托盘悬停由宿主把两个模块的片段拼起来，谁也不会覆盖谁。"""
    app = PetApp(root=build_root(tmp_path))
    seen = []
    app._set_tray_text = seen.append
    app._update_status()
    assert seen == ["心情 80 · 活力 80 · 饱腹 80 · 噜噜币 0"]
    app.shutdown()


def test_buy_food_spends_coins_and_feeds_the_pet(qapp, tmp_path):
    root = build_root(tmp_path)
    cfg = load_config(root / "config.json")
    cfg["modules"]["economy"]["coins"] = 100
    cfg["modules"]["vitals"].update({"satiety": 50, "mood": 50})
    save_config(root / "config.json", cfg)

    app = PetApp(root=root)
    app._menu_handlers()["buy_food"]("burger")

    assert app.modules["economy"].coins == 70      # 100 - 30
    assert app.modules["vitals"].satiety == 80     # 50 + 30
    assert app.modules["vitals"].mood == 80
    app.shutdown()


def test_buy_food_without_coins_changes_nothing(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    before = app.modules["vitals"].satiety
    app._menu_handlers()["buy_food"]("ice_cream")
    assert app.modules["economy"].coins == 0
    assert app.modules["vitals"].satiety == before
    app.shutdown()


def test_work_toggle_drives_economy_and_working_decay(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    handlers = app._menu_handlers()

    handlers["toggle_work"](True)
    assert app.modules["economy"].working is True
    assert app.modules["vitals"]._working is True  # 上班时心情 / 活力衰减加倍

    handlers["toggle_work"](False)
    assert app.modules["economy"].working is False
    assert app.modules["vitals"]._working is False
    app.shutdown()


def test_soothe_puts_the_pet_to_sleep(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    app._menu_handlers()["soothe"]()
    assert app.behavior.state == "SLEEP"
    assert app.modules["vitals"]._sleeping is True  # 睡着时活力改为回升
    app.shutdown()


def test_apply_settings_keeps_runtime_vitals(qapp, tmp_path):
    """设置面板保存会整份覆盖配置，靠 `sync_config` 把运行时数值补回去。"""
    app = PetApp(root=build_root(tmp_path))
    stale = copy.deepcopy(app.config)  # 面板打开时的旧快照
    app.modules["vitals"].feed(satiety=10, mood=10)  # 80 → 90

    app._apply_settings(stale)

    assert app.config["modules"]["vitals"]["satiety"] == 90
    assert app.config["modules"]["vitals"]["mood"] == 90
    app.shutdown()


# ---------------------------------------------------------------- 状态卡接线


def test_show_status_card_pops_with_live_numbers(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    app._show_status_card()
    assert app.status_card.isVisible() is True
    assert app.status_card.note_text() == "噜噜币 0"
    app.shutdown()


def test_show_status_card_noop_without_both_modules(qapp, tmp_path):
    """数值 / 经济模块缺一就不弹（避免画一张空卡）。"""
    app = PetApp(root=build_root(tmp_path))
    saved = app.modules
    app.modules = {"vitals": saved["vitals"]}  # 抽掉 economy
    assert app._fill_status_card() is False
    app._show_status_card()
    assert app.status_card.isVisible() is False
    app.modules = saved
    app.shutdown()


def test_status_card_refreshes_while_visible(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    app._show_status_card()
    assert app.status_card.note_text() == "噜噜币 0"

    app.modules["economy"]._coins = 55
    app._update_status()  # 心跳每秒都会调它
    assert app.status_card.note_text() == "噜噜币 55"
    app.shutdown()


def test_hiding_pet_hides_status_card(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    app._show_status_card()
    app._toggle_visible()
    assert app.status_card.isVisible() is False
    app.shutdown()
