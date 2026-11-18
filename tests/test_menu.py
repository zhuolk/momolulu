from PIL import Image
from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMenu, QSystemTrayIcon, QWidgetAction

from pet.catalog import default_categories, set_track
from pet.tray import Tray, ensure_tray_icon
from ui.menu import MenuState, build_menu
from ui.status_card import StatusHeader


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
        self.stroll = lambda: self.calls.append(("stroll",))
        self.bubble = lambda: self.calls.append(("bubble",))
        self.music = lambda: self.calls.append(("music",))
        self.toggle_work = lambda on: self.calls.append(("work", on))
        self.toggle_bricklay = lambda on: self.calls.append(("bricklay", on))
        self.soothe = lambda: self.calls.append(("soothe",))
        self.buy_food = lambda key: self.calls.append(("buy_food", key))


MODS = {"pomodoro": False, "water": True, "sit": True, "meal": True, "hourly": False}
# (key, 文案, 价格, 是否买得起)
FOODS_STATE = (("watermelon", "西瓜", 5, False), ("hamburger", "汉堡", 30, True))


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


def test_tray_emits_clicked_on_trigger_only(qapp):
    """左键单击发 `clicked`（用来弹状态卡），右键不发。"""
    tray, _ = make_tray(qapp)
    hits = []
    tray.clicked.connect(lambda: hits.append(True))
    tray._tray.activated.emit(QSystemTrayIcon.Trigger)
    assert hits == [True]
    tray._tray.activated.emit(QSystemTrayIcon.Context)
    assert hits == [True]


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


def test_interact_submenu_holds_stroll_and_bubble(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    assert "搞搞震" in actions(m)
    interact = actions(actions(m)["搞搞震"].menu())
    assert "散步" in interact and "吹泡泡" in interact


def test_interact_submenu_sits_after_tools_before_settings(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    order = [a.text().replace("&", "") for a in m.actions()]
    assert order.index("实用工具") < order.index("搞搞震") < order.index("设置…")


def test_stroll_triggers_handler(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, False), h.__dict__)
    actions(actions(m)["搞搞震"].menu())["散步"].trigger()
    assert ("stroll",) in h.calls


def test_bubble_and_music_trigger_handlers(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, False), h.__dict__)
    actions(actions(m)["搞搞震"].menu())["吹泡泡"].trigger()
    assert ("bubble",) in h.calls

    h2 = Handlers()
    m2 = build_menu(None, MenuState(True, False, False, MODS, False), h2.__dict__)
    actions(actions(m2)["搞搞震"].menu())["听歌"].trigger()
    assert ("music",) in h2.calls


def test_activity_locks_other_menu_entries(qapp):
    for activity, available in (
        ("work", {"打工"}), ("sleep", {"睡觉"}), ("food", set()), ("play", set())
    ):
        m = build_menu(None, MenuState(True, False, False, MODS, False, activity=activity), {})
        items = actions(m)
        assert {k for k in ("搞搞震", "睡觉", "干饭", "打工") if items[k].isEnabled()} == available


def test_food_items_show_price_and_disable_unaffordable(qapp):
    m = build_menu(
        None, MenuState(True, False, False, MODS, False, foods=FOODS_STATE), Handlers().__dict__
    )
    feed = actions(actions(m)["干饭"].menu())
    assert feed["汉堡（30 噜噜币）"].isEnabled() is True
    assert feed["西瓜（5 噜噜币）"].isEnabled() is False  # 买不起就置灰


def test_buy_food_reports_the_key(qapp):
    h = Handlers()
    m = build_menu(
        None, MenuState(True, False, False, MODS, False, foods=FOODS_STATE), h.__dict__
    )
    actions(actions(m)["干饭"].menu())["汉堡（30 噜噜币）"].trigger()
    assert ("buy_food", "hamburger") in h.calls


def test_soothe_triggers_handler(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, False), h.__dict__)
    assert actions(m)["睡觉"].menu() is None
    actions(m)["睡觉"].trigger()
    assert ("soothe",) in h.calls


def work_menu(menu):
    return actions(menu)["打工"].menu()


def test_work_submenu_holds_clock_in_and_bricklay(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    work = actions(work_menu(m))
    assert "上班" in work and "搬砖" in work


def test_work_item_reflects_state_and_reports_change(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, False, working=True), h.__dict__)
    clock_in = actions(work_menu(m))["上班"]
    assert not actions(work_menu(m))["搬砖"].isEnabled()
    assert clock_in.isCheckable() is True and clock_in.isChecked() is True
    clock_in.trigger()
    assert ("work", False) in h.calls


def test_bricklay_item_reflects_state_and_reports_change(qapp):
    h = Handlers()
    m = build_menu(
        None, MenuState(True, False, False, MODS, False, bricklaying=True), h.__dict__
    )
    bricklay = actions(work_menu(m))["搬砖"]
    assert not actions(work_menu(m))["上班"].isEnabled()
    assert bricklay.isCheckable() is True and bricklay.isChecked() is True
    bricklay.trigger()
    assert ("bricklay", False) in h.calls


def test_care_submenu_sits_after_interact_before_settings(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    order = [a.text().replace("&", "") for a in m.actions()]
    assert "照顾噜噜" not in order
    assert order.index("搞搞震") < order.index("睡觉") < order.index("干饭") < order.index("打工")


# ---------------------------------------------------------------- 顶部数值摘要

VITALS = (72.5, 48.0, 91.0, 42.7, 0)


def header_of(menu):
    """取菜单顶部的数值摘要条；没有则返回 None。"""
    for action in menu.actions():
        widget = action.defaultWidget() if isinstance(action, QWidgetAction) else None
        if isinstance(widget, StatusHeader):
            return widget
    return None


def test_menu_shows_vitals_header(qapp):
    m = build_menu(
        None, MenuState(True, False, False, MODS, False, vitals=VITALS), Handlers().__dict__
    )
    header = header_of(m)
    assert header is not None
    assert header._values() == [72.5, 48.0, 91.0]
    assert header.note_text() == "42"


def test_vitals_header_sits_on_top(qapp):
    m = build_menu(
        None, MenuState(True, False, False, MODS, False, vitals=VITALS), Handlers().__dict__
    )
    assert isinstance(m.actions()[0].defaultWidget(), StatusHeader)


def test_menu_without_vitals_has_no_header(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    assert header_of(m) is None


def test_vitals_header_follows_work_state(qapp):
    m = build_menu(
        None,
        MenuState(True, False, False, MODS, False, working=True, vitals=(50, 50, 50, 10, 15)),
        Handlers().__dict__,
    )
    assert header_of(m).note_text() == "上班中 · 已赚 15"


def test_menu_applies_card_style_sheet(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    sheet = m.styleSheet()
    assert "QMenu::item" in sheet
    assert "QMenu::item:selected" in sheet


def test_menu_cuts_rounded_corners(qapp):
    """圆角靠窗口 mask 切——QSS 里写 `border-radius` 会写坏堆，见 `ui.theme.menu_style`。"""
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    m.resize(200, 120)
    m.round_corners()
    mask = m.mask()
    assert not mask.isEmpty()
    assert mask.boundingRect().width() == 200
    assert not mask.contains(QPoint(0, 0))       # 左上角被切掉
    assert mask.contains(QPoint(100, 60))        # 中间照常
