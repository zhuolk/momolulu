from PIL import Image
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMenu, QSystemTrayIcon

from pet.catalog import default_categories, set_track
from pet.tray import Tray, ensure_tray_icon
from ui.menu import MenuState, build_menu


class Handlers:
    """回调做成实例属性，这样 `h.__dict__` 就是可直接交给 `build_menu` 的 dict。"""

    def __init__(self):
        self.calls = []
        self.toggle_visible = lambda: self.calls.append(("visible",))
        self.toggle_passthrough = lambda: self.calls.append(("passthrough",))
        self.toggle_module = lambda key, on: self.calls.append(("module", key, on))
        self.pomodoro = lambda action: self.calls.append(("pomodoro", action))
        self.open_settings = lambda: self.calls.append(("settings",))
        self.toggle_autostart = lambda: self.calls.append(("autostart",))
        self.quit = lambda: self.calls.append(("quit",))
        self.update_now = lambda: self.calls.append(("update_now",))


MODS = {"pomodoro": False, "water": True, "sit": True, "meal": True, "hourly": False}


def actions(menu):
    return {a.text().replace("&", ""): a for a in menu.actions()}


def submenu_of(menu):
    return [a for a in menu.actions() if a.menu()][0].menu()


def test_menu_top_level_items_and_mode_pair(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    t = actions(m)
    for name in ("显示 / 隐藏噜噜", "设置…", "开机自启", "退出"):
        assert name in t
    assert "交互模式" in t and "穿透模式" in t
    assert t["交互模式"].isChecked() is True and t["穿透模式"].isChecked() is False


def test_passthrough_state_reflected(qapp):
    m = build_menu(None, MenuState(True, True, False, MODS, False), Handlers().__dict__)
    t = actions(m)
    assert t["穿透模式"].isChecked() is True and t["交互模式"].isChecked() is False


def test_module_switches_are_checkable_and_match_state(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    sub = actions(submenu_of(m))
    for label in ("番茄钟", "喝水提醒", "久坐提醒", "吃饭提醒", "整点报时"):
        assert sub[label].isCheckable() is True
    assert sub["喝水提醒"].isChecked() is True and sub["番茄钟"].isChecked() is False


def test_toggle_module_reports_new_state(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, False), h.__dict__)
    pom = actions(submenu_of(m))["番茄钟"]
    pom.setChecked(True)
    pom.trigger()
    assert ("module", "pomodoro", True) in h.calls
    sit = actions(submenu_of(m))["久坐提醒"]
    sit.setChecked(False)
    sit.trigger()
    assert ("module", "sit", False) in h.calls


def test_pomodoro_sub_actions_present(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, True), h.__dict__)
    sub = actions(submenu_of(m))
    for label in ("开始 / 暂停", "跳过", "重置"):
        assert label in sub
    sub["跳过"].trigger()
    assert ("pomodoro", "skip") in h.calls


def test_quit_and_autostart_handlers(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, False), h.__dict__)
    actions(m)["退出"].trigger()
    actions(m)["开机自启"].trigger()
    assert ("quit",) in h.calls and ("autostart",) in h.calls


def test_ensure_tray_icon_from_transparent_asset_then_reuse(tmp_path):
    Image.new("RGB", (200, 200), (30, 130, 210)).save(tmp_path / "lulu_001.gif")
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif"]
    set_track(d, "lulu_001.gif", "transparent")
    out = ensure_tray_icon(tmp_path, d, tmp_path / "tray_icon.png")
    assert out.exists() and Image.open(out).size == (64, 64)
    out.write_bytes(b"cached")
    assert ensure_tray_icon(tmp_path, d, out).read_bytes() == b"cached"


def test_ensure_tray_icon_falls_back_to_drawn_orange(qapp, tmp_path):
    p = ensure_tray_icon(tmp_path, default_categories(), tmp_path / "tray_icon.png")
    assert p.exists() and Image.open(p).size == (64, 64)


def make_tray(qapp):
    """托盘包装 + 记录每次工厂调用，用于验证「右键才弹、每次重建」。"""
    built = []

    def factory():
        menu = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
        built.append(menu)
        return menu

    return Tray(qapp, QIcon(), factory), built


def test_tray_does_not_use_native_context_menu(qapp):
    """菜单每次弹出都要重建，交给原生菜单会失同步（只剩一项 / 文字错乱）。"""
    tray, built = make_tray(qapp)
    assert tray.menu is None and built == []
    assert tray._tray.contextMenu() is None


def test_tray_pops_menu_on_context_activation_only(qapp):
    tray, built = make_tray(qapp)
    tray._tray.activated.emit(QSystemTrayIcon.Trigger)  # 左键：不弹菜单
    assert tray.menu is None and built == []
    tray._tray.activated.emit(QSystemTrayIcon.Context)  # 右键：按当前状态新建菜单
    assert tray.menu is not None and len(built) == 1
    assert actions(tray.menu)["退出"] is not None


def test_tray_popup_menu_returns_false_without_factory_result(qapp):
    tray = Tray(qapp, QIcon(), lambda: None)
    assert tray.popup_menu() is False and tray.menu is None


def test_update_item_absent_without_new_version(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    assert not [t for t in actions(m) if t.startswith("立即更新到")]


def test_update_item_present_and_triggers_handler(qapp):
    h = Handlers()
    m = build_menu(
        None, MenuState(True, False, False, MODS, False, update_version="0.2.0"), h.__dict__
    )
    t = actions(m)
    assert "立即更新到 0.2.0" in t
    t["立即更新到 0.2.0"].trigger()
    assert ("update_now",) in h.calls


def test_update_item_sits_before_settings(qapp):
    m = build_menu(
        None, MenuState(True, False, False, MODS, False, update_version="0.2.0"), Handlers().__dict__
    )
    order = [a.text().replace("&", "") for a in m.actions()]
    assert order.index("立即更新到 0.2.0") < order.index("设置…")


def test_existing_five_arg_calls_still_work(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    assert "设置…" in actions(m)
