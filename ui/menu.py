"""右键 / 托盘菜单构建：只负责「按状态搭菜单」，状态变化通过 handlers 回传。

`build_menu` 不修改任何状态；checkable 项一律连 `toggled`（`trigger()` 会二次翻转勾选态，
只有 `toggled` 能稳定拿到用户改变后的值），非 checkable 项连 `triggered`。

菜单顶部放一条与状态卡同款的数值摘要（`StatusHeader`），整体样式表取自 `ui/theme.py`。
"""

from __future__ import annotations

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainterPath, QRegion
from PyQt5.QtWidgets import QActionGroup, QMenu, QMessageBox, QWidgetAction

from ui.status_card import StatusHeader
from ui.theme import RADIUS, menu_style

MENU_KEYS = ("pomodoro", "water", "sit", "meal", "hourly")
MENU_LABELS = {
    "pomodoro": "番茄钟",
    "water": "喝水提醒",
    "sit": "久坐提醒",
    "meal": "吃饭提醒",
    "hourly": "整点报时",
}
POMODORO_ACTIONS = (("toggle", "开始 / 暂停"), ("skip", "跳过"), ("reset", "重置"))

ABOUT_TITLE = "关于噜噜"
ABOUT_TEXT = "噜噜\n素材来自网络，仅供个人学习使用。"


class CardMenu(QMenu):
    """与状态卡同款圆角的菜单。

    QSS 里写 `border-radius` 会写坏 `QStyleSheetStyle` 的堆（见 `ui.theme.menu_style`），
    所以圆角改用窗口 mask 切——尺寸一变就重切一次。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._masked = None

    def round_corners(self) -> None:
        """按当前尺寸重切圆角；尺寸没变就跳过（`resizeEvent` 会频繁触发）。"""
        size = self.size()
        if size == self._masked:
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), RADIUS, RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        self._masked = size

    def resizeEvent(self, event):  # noqa: N802 - Qt 命名
        super().resizeEvent(event)
        self.round_corners()


class MenuState:
    """菜单需要展示的全部状态快照。"""

    def __init__(
        self,
        visible: bool,
        passthrough: bool,
        autostart: bool,
        modules: dict,
        pomodoro_running: bool,
        update_version: str | None = None,
        working: bool = False,
        foods: tuple = (),
        vitals: tuple | None = None,
    ):
        self.visible = bool(visible)
        self.passthrough = bool(passthrough)
        self.autostart = bool(autostart)
        self.modules = dict(modules)
        self.pomodoro_running = bool(pomodoro_running)
        self.update_version = update_version or None
        self.working = bool(working)
        # (key, 文案, 价格, 是否买得起)
        self.foods = tuple(foods)
        # (心情, 活力, 饱腹, 噜噜币, 本班进账)，为 None 时不显示顶部摘要条
        self.vitals = tuple(vitals) if vitals is not None else None


def build_header(state: MenuState) -> StatusHeader | None:
    """按 `state.vitals` 造顶部数值摘要条；没有数值时返回 None。"""
    if not state.vitals:
        return None
    mood, energy, satiety, coins, earned = state.vitals
    header = StatusHeader()
    header.set_state(mood, energy, satiety, coins, state.working, earned)
    return header


# ------------------------------------------------------------------ 回调适配


def _call(handlers, key: str, *args) -> None:
    fn = handlers.get(key) if isinstance(handlers, dict) else getattr(handlers, key, None)
    if fn is not None:
        fn(*args)


def _slot(handlers, key: str, *args):
    """忽略 Qt 传入的 checked 参数，直接以固定参数调用 handler。"""

    def run(*_ignored):
        _call(handlers, key, *args)

    return run


def _slot_checked(handlers, key: str):
    """仅在「被勾选」时调用（`QActionGroup` 互斥，取消勾选的一侧不发通知）。"""

    def run(on: bool = False):
        if on:
            _call(handlers, key)

    return run


def _slot_module(handlers, key: str):
    """把触发后的勾选态原样回传（`toggle_module(key, on)`）。"""

    def run(on: bool = False):
        _call(handlers, "toggle_module", key, bool(on))

    return run


# ------------------------------------------------------------------ 菜单构建


def build_menu(parent, state: MenuState, handlers) -> QMenu:
    menu = CardMenu(parent)
    menu.setStyleSheet(menu_style())

    header = build_header(state)
    if header is not None:
        holder = QWidgetAction(menu)
        holder.setDefaultWidget(header)
        menu.addAction(holder)
        menu.addSeparator()

    visible = menu.addAction("显示 / 隐藏噜噜")
    visible.setCheckable(True)
    visible.setChecked(state.visible)
    visible.toggled.connect(_slot(handlers, "toggle_visible"))

    mode_group = QActionGroup(menu)
    mode_group.setExclusive(True)
    interactive = menu.addAction("交互模式")
    passthrough = menu.addAction("穿透模式")
    for action in (interactive, passthrough):
        action.setCheckable(True)
        mode_group.addAction(action)
    (passthrough if state.passthrough else interactive).setChecked(True)
    for action in (interactive, passthrough):
        action.toggled.connect(_slot_checked(handlers, "toggle_passthrough"))

    menu.addSeparator()

    tools = menu.addMenu("实用工具")
    for key in MENU_KEYS:
        action = tools.addAction(MENU_LABELS[key])
        action.setCheckable(True)
        action.setChecked(bool(state.modules.get(key, False)))
        action.toggled.connect(_slot_module(handlers, key))
    tools.addSeparator()
    for action_id, label in POMODORO_ACTIONS:
        tools.addAction(label).triggered.connect(_slot(handlers, "pomodoro", action_id))

    menu.addSeparator()

    interact = menu.addMenu("搞搞震")
    interact.addAction("散步").triggered.connect(_slot(handlers, "stroll"))

    menu.addSeparator()

    care = menu.addMenu("照顾噜噜")
    care.addAction("看看状态").triggered.connect(_slot(handlers, "show_status"))
    feed = care.addMenu("喂食")
    for key, label, price, affordable in state.foods:
        action = feed.addAction(f"{label}（{price} 噜噜币）")
        action.setEnabled(bool(affordable))
        action.triggered.connect(_slot(handlers, "buy_food", key))
    care.addAction("哄睡").triggered.connect(_slot(handlers, "soothe"))
    work = care.addAction("上班 / 下班")
    work.setCheckable(True)
    work.setChecked(state.working)
    work.toggled.connect(lambda on: _call(handlers, "toggle_work", bool(on)))

    menu.addSeparator()

    if state.update_version:
        update = menu.addAction(f"立即更新到 {state.update_version}")
        update.triggered.connect(_slot(handlers, "update_now"))
        menu.addSeparator()

    settings = menu.addAction("设置…")
    settings.triggered.connect(_slot(handlers, "open_settings"))

    autostart = menu.addAction("开机自启")
    autostart.setCheckable(True)
    autostart.setChecked(state.autostart)
    autostart.toggled.connect(_slot(handlers, "toggle_autostart"))

    about = menu.addAction("关于")
    about.triggered.connect(lambda *_: QMessageBox.about(parent, ABOUT_TITLE, ABOUT_TEXT))

    quit_action = menu.addAction("退出")
    quit_action.triggered.connect(_slot(handlers, "quit"))

    return menu
