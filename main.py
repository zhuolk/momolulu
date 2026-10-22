"""启动入口：装配配置、素材索引、桌宠窗口、气泡提示、托盘菜单与实用模块。"""

from __future__ import annotations

import logging
import random
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMenu

import modules.health_reminder  # noqa: F401  导入即注册进 MODULE_CLASSES
import modules.hourly_chime  # noqa: F401  导入即注册进 MODULE_CLASSES
import modules.meal_reminder  # noqa: F401  导入即注册进 MODULE_CLASSES
import modules.pomodoro  # noqa: F401  导入即把 Pomodoro 注册进 MODULE_CLASSES
from modules.base import ModuleContext, build_modules
from pet.autostart import default_command, set_enabled, sync
from pet.behavior import PRIORITY_MODULE, STROLL, WANDER, Behavior
from pet.catalog import load_categories, pick
from pet.config import load_config, save_config
from pet.edge_hide import EdgeHider
from pet.sprite import Sprite
from pet.stroll import Stroller
from pet.tray import Tray, ensure_tray_icon
from pet.update_runner import AssetUpdateThread, ProgramUpdateThread, UpdateCheckThread
from pet.updater import LATEST_URL
from pet.version import VERSION
from pet.wander import Wanderer
from pet.winutil import is_foreground_fullscreen, should_hide_pet
from ui.menu import MENU_LABELS, MenuState, build_menu
from ui.settings_dialog import SettingsDialog
from ui.toast import Toast
from ui.update_prompt import UpdatePrompt

_DEFAULT_MARGIN = 40
_SAVE_DELAY_MS = 500
_TICK_MS = 100
_FS_CHECK_MS = 1000
_MODULE_TICK_MS = 1000
_TOAST_MS = 6000
_UPDATE_CHECK_DELAY_MS = 5000
_ASSET_TOAST = "噜噜换新衣服啦"

CLICK_LINES = ("噜噜~", "摸摸头", "咕噜咕噜", "噜噜在这儿")
FAST_CLICK_LINE = "噜噜生气啦！"

# 模块通知的备用分类（缺该类素材时退一级）
CATEGORY_FALLBACK = {"drink": "eat"}

# 菜单开关 → 配置文件里的模块键（喝水与久坐共用 health_reminder）
MODULE_KEYS = {
    "pomodoro": "pomodoro",
    "water": "health_reminder",
    "sit": "health_reminder",
    "meal": "meal_reminder",
    "hourly": "hourly_chime",
}

# 菜单开关 → 所属模块内的子开关字段（未列出的开关直接控制模块 enabled）
SUB_SWITCH_KEYS = {
    "water": "water_enabled",
    "sit": "sit_enabled",
}


def app_root() -> Path:
    """资源根目录：打包后取 exe 所在目录（素材外置），脚本模式取源码目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bottom_right(screen: tuple[int, int, int, int], size: tuple[int, int], margin: int = 0):
    """屏幕右下角内缩 margin 的窗口左上角坐标。"""
    sx, sy, sw, sh = screen
    return int(sx + sw - size[0] - margin), int(sy + sh - size[1] - margin)


def clamp_to_screen(
    pos: tuple[int, int],
    size: tuple[int, int],
    screens: list[tuple[int, int, int, int]],
) -> tuple[int, int]:
    """把窗口左上角夹进屏幕范围内。

    窗口完整落在任一屏幕内则原样返回；否则夹进「包含窗口左上角」的那块屏幕；
    左上角落在所有屏幕之外时，落到主屏（`screens[0]`）的右下角。`screens` 为空时原样返回。
    """
    x, y = int(pos[0]), int(pos[1])
    if not screens:
        return x, y
    w, h = int(size[0]), int(size[1])

    for sx, sy, sw, sh in screens:
        if sx <= x and sy <= y and x + w <= sx + sw and y + h <= sy + sh:
            return x, y

    for sx, sy, sw, sh in screens:
        if sx <= x < sx + sw and sy <= y < sy + sh:
            return min(max(x, sx), sx + sw - w), min(max(y, sy), sy + sh - h)

    return _bottom_right(screens[0], size)


class PetApp:
    """应用装配：配置 → 素材索引 → 桌宠窗口 → 位置持久化。"""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else app_root()
        self.config_path = self.root / "config.json"
        self.config = load_config(self.config_path)
        self.processed_dir = self.root / "assets" / "processed"
        self.catalog = load_categories(self.root / "assets" / "categories.json")

        app = QApplication.instance()
        if app is None:
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            app = QApplication(sys.argv)
        self.app = app

        self.sprite = Sprite(self.catalog, self.processed_dir, self.config)
        self.behavior = Behavior(self.sprite, self.config)
        self.edge_hider = EdgeHider(self.sprite, self.config, self._screens)
        self.wanderer = Wanderer(self.sprite, self._screens)
        self.stroller = Stroller(
            self.sprite,
            self._screens,
            on_finished=self.behavior.on_stroll_finished,
            bounds_provider=self._work_areas,
        )
        self.toast = Toast()

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self._flush_position)

        self._tick_timer = QTimer()
        self._tick_timer.setInterval(_TICK_MS)
        self._tick_timer.timeout.connect(self._on_tick)

        self._fs_timer = QTimer()
        self._fs_timer.setInterval(_FS_CHECK_MS)
        self._fs_timer.timeout.connect(self._check_fullscreen)

        self._module_timer = QTimer()
        self._module_timer.setInterval(_MODULE_TICK_MS)
        self._module_timer.timeout.connect(self._on_module_tick)

        self._menu: QMenu | None = None
        self.clock = datetime.now
        self.modules: dict = {}
        self._autostart_command = default_command(self.root / "main.py")
        self._autostart = sync(bool(self.config.get("autostart", False)), self._autostart_command)
        self._drag_active = False
        self._hidden_by_fullscreen = False
        self._shutdown_done = False
        self._wire_signals()
        self._start_ui()
        self._start_tray()
        self._init_modules()
        self._update_info: dict | None = None
        self._update_thread = None
        self._program_thread = None
        self._asset_thread = None
        self._update_prompt = UpdatePrompt()
        self._update_prompt.accepted.connect(self._update_now)
        self._update_prompt.declined.connect(self._dismiss_update_prompt)
        self._schedule_update_check()

    # ------------------------------------------------------------ 信号接线

    def _wire_signals(self) -> None:
        self.sprite.drag_moved.connect(self._on_drag_moved)
        self.sprite.drag_finished.connect(self._on_drag_finished)
        self.sprite.clicked.connect(self.behavior.on_user_click)
        self.sprite.clicked.connect(self._on_clicked)
        self.sprite.fast_clicked.connect(self.behavior.on_fast_click)
        self.sprite.fast_clicked.connect(self._on_fast_clicked)
        self.sprite.play_finished.connect(self.behavior.on_play_finished)
        self.sprite.right_clicked.connect(self._on_right_clicked)
        self.sprite.moved.connect(self._follow_toast)
        self.app.screenAdded.connect(self._on_screens_changed)
        self.app.screenRemoved.connect(self._on_screens_changed)

    # ------------------------------------------------------------ 气泡提示

    def _pet_anchor(self) -> tuple[int, int]:
        """气泡锚点：桌宠顶边中点（气泡浮在其上方）。"""
        return (
            self.sprite.x() + self.sprite.width() // 2,
            self.sprite.y(),
        )

    def _show_toast(self, text: str, kind: str = "info", duration_ms: int = _TOAST_MS) -> None:
        self.toast.show_message(text, duration_ms=duration_ms, anchor=self._pet_anchor(), kind=kind)

    def _follow_toast(self) -> None:
        """噜噜位置变了（拖拽 / 自己走动 / 贴边滑出 / 屏幕变化）就让气泡跟着走。

        气泡是独立顶层窗，不跟随就会钉在原地。
        """
        if self.toast.isVisible():
            self.toast.move_above_anchor(*self._pet_anchor())

    def _on_clicked(self) -> None:
        self._show_toast(random.choice(CLICK_LINES))

    def _on_fast_clicked(self) -> None:
        self._show_toast(FAST_CLICK_LINE, kind="warn")

    def _on_right_clicked(self, global_pos: QPoint) -> None:
        self._menu = self._build_menu()
        self._menu.popup(global_pos)

    # ------------------------------------------------------------ 托盘与菜单

    def _module_flags(self) -> dict:
        modules = self.config.get("modules", {})
        flags = {}
        for key, cfg_key in MODULE_KEYS.items():
            node = modules.get(cfg_key, {})
            sub = SUB_SWITCH_KEYS.get(key)
            if sub is not None:  # 喝水 / 久坐各自显示自己的子开关
                flags[key] = bool(node.get(sub, True))
            else:
                flags[key] = bool(node.get("enabled", False))
        return flags

    def _menu_state(self) -> MenuState:
        pomodoro = self.modules.get("pomodoro")
        info = self._update_info
        pending = info.get("version") if isinstance(info, dict) and info.get("package") else None
        return MenuState(
            visible=self.sprite.isVisible(),
            passthrough=bool(self.config.get("pet", {}).get("passthrough", False)),
            autostart=self._autostart,
            modules=self._module_flags(),
            pomodoro_running=bool(getattr(pomodoro, "running", False)),
            update_version=pending,
        )

    def _build_menu(self) -> QMenu:
        return build_menu(None, self._menu_state(), self._menu_handlers())

    def _menu_handlers(self) -> dict:
        return {
            "toggle_visible": self._toggle_visible,
            "toggle_passthrough": self._toggle_passthrough,
            "toggle_module": self._toggle_module,
            "pomodoro": self._pomodoro,
            "stroll": self._start_stroll,
            "open_settings": self._open_settings,
            "toggle_autostart": self._toggle_autostart,
            "update_now": self._update_now,
            "quit": self._quit,
        }

    def _start_tray(self) -> None:
        icon_path = ensure_tray_icon(
            self.processed_dir, self.catalog, self.root / "assets" / "tray_icon.png"
        )
        self.tray = Tray(self.app, QIcon(str(icon_path)), self._build_menu)
        self.tray.show()

    def _toggle_visible(self) -> None:
        # 用户手动切换显示状态后收回「全屏隐藏」的自动还原权
        self._hidden_by_fullscreen = False
        if self.sprite.isVisible():
            self.sprite.hide()
            self.toast.hide()
        else:
            self.sprite.show()

    def _toggle_passthrough(self) -> None:
        on = not bool(self.config["pet"].get("passthrough", False))
        self.config["pet"]["passthrough"] = on
        self.sprite.set_passthrough(on)
        save_config(self.config_path, self.config)
        if on:
            self._show_toast("穿透模式：鼠标可以穿过噜噜", kind="warn")
        else:
            self._show_toast("交互模式：可以拖拽噜噜")

    def _toggle_module(self, key: str, on: bool) -> None:
        cfg_key = MODULE_KEYS.get(key)
        if cfg_key is None:
            return
        module = self.modules.get(cfg_key)
        sub = SUB_SWITCH_KEYS.get(key)
        if sub is not None:
            node = self.config["modules"][cfg_key]
            node[sub] = bool(on)
            # 模块整体开关跟随两个子开关：任一开启即启用
            want = bool(node.get("water_enabled", True)) or bool(node.get("sit_enabled", True))
            if module is not None and module.enabled != want:
                module.set_enabled(want)  # 内部会落盘
            else:
                self._save_config()
            self._show_toast(f"{MENU_LABELS[key]}：{'已开启' if on else '已关闭'}")
            return
        if module is not None:
            module.set_enabled(bool(on))
        else:  # 该模块尚未落地（阶段 5 逐个接入）时至少把开关写进配置
            self.config["modules"][cfg_key]["enabled"] = bool(on)
            self._save_config()
        self._show_toast(f"{MENU_LABELS[key]}：{'已开启' if on else '已关闭'}")

    def _pomodoro(self, action: str) -> None:
        module = self.modules.get("pomodoro")
        if module is None:
            return
        if action == "toggle":
            module.toggle()
        elif action == "skip":
            module.skip()
        elif action == "reset":
            module.reset()

    def _start_stroll(self) -> None:
        """搞搞震 ▸ 散步：瞬移到当前屏的右下角，沿屏幕边缘逆时针走一圈。"""
        if self.stroller.active:
            return
        if not self.behavior.request("stroll", PRIORITY_MODULE, once=False):
            self._show_toast("散步素材缺失", kind="warn")
            return
        # 贴边缩回时窗口大半在屏外，得先靠露在屏内的桔子条认屏幕，再退出贴边隐藏
        started = self.stroller.start()
        self.edge_hider.detach()
        if not started:
            self.behavior.on_stroll_finished()
            return
        self._show_toast("噜噜去散步啦")

    def _open_settings(self) -> None:
        """打开设置面板；保存后立即生效。"""
        dialog = SettingsDialog(self.config, self.sprite)
        dialog.config_saved.connect(self._apply_settings)
        dialog.exec_()

    def _apply_settings(self, new_config: dict) -> None:
        """把面板返回的配置原地写回（保持其他组件持有的引用不失效）。"""
        self.config.clear()
        self.config.update(new_config)
        self._save_config()
        for name, module in self.modules.items():
            node = self.config["modules"].get(name, {})
            if name == "health_reminder":  # 整体开关跟随两个子开关
                want = bool(node.get("water_enabled", True)) or bool(node.get("sit_enabled", True))
            else:
                want = bool(node.get("enabled", module.default_enabled))
            if module.enabled != want:
                module.set_enabled(want)
        pet = self.config.get("pet", {})
        self.sprite.set_always_on_top(bool(pet.get("always_on_top", True)))
        self.sprite.reload()  # 缩放可能已改变，重建影片缓存
        self._autostart = sync(bool(self.config.get("autostart", False)), self._autostart_command)
        self._show_toast("设置已保存")

    def _toggle_autostart(self) -> None:
        want = not self._autostart
        if not set_enabled(want, self._autostart_command):
            self._show_toast("开机自启设置失败（可能被安全软件拦截）", kind="warn")
            return
        self._autostart = want
        self.config["autostart"] = want
        save_config(self.config_path, self.config)
        self._show_toast(f"开机自启：{'已开启' if want else '已关闭'}")

    def _quit(self) -> None:
        if getattr(self, "tray", None) is not None:
            self.tray.hide()
        self.shutdown()
        self.app.quit()

    def _on_tick(self) -> None:
        self.behavior.tick(datetime.now())
        state = self.behavior.state
        if state == STROLL:
            self.stroller.tick()
        else:  # 走完一圈或被拖拽/其他行为抢走：停下并恢复直立
            self.stroller.stop()
        self.wanderer.tick(state == WANDER)

    # ------------------------------------------------------------ 全屏隐藏与多屏

    def _check_fullscreen(self) -> None:
        """前台全屏（视频 / 游戏 / F11）时自动收起噜噜，退出全屏后还原。"""
        enabled = bool(self.config.get("pet", {}).get("hide_on_fullscreen", True))
        if should_hide_pet(is_foreground_fullscreen(), enabled):
            if self.sprite.isVisible():
                self._hidden_by_fullscreen = True
                self.sprite.hide()
                self.toast.hide()
            return
        if self._hidden_by_fullscreen:
            self._hidden_by_fullscreen = False
            self.sprite.show()

    def _on_screens_changed(self, *_args) -> None:
        """屏幕增删后把噜噜夹回可见范围；贴边隐藏状态下按新屏幕重新缩回。"""
        screens = self._screens()
        if not screens:
            return
        if self.edge_hider.is_hidden:
            self.edge_hider.retract()
        else:
            pos = clamp_to_screen(
                (self.sprite.x(), self.sprite.y()),
                (self.sprite.width(), self.sprite.height()),
                screens,
            )
            self.sprite.move_to(*pos)
        self._remember_position()
        self._save_timer.start()

    # ------------------------------------------------------------ 实用模块

    def _init_modules(self) -> None:
        """建模块上下文与模块实例，并启动模块心跳（1s）。"""
        ctx = ModuleContext(
            self._module_notify,
            self._set_tray_text,
            self.config,
            self._save_config,
        )
        self.modules = build_modules(ctx)
        self._module_timer.start()

    def _save_config(self) -> None:
        save_config(self.config_path, self.config)

    def _module_notify(
        self, text: str, category: str = "happy", duration_ms: int = _TOAST_MS
    ) -> None:
        """模块通知：弹气泡 + 让噜噜播对应分类的动图（缺素材时退一级）。"""
        self._show_toast(text, duration_ms=duration_ms)
        if self.behavior.request(category, PRIORITY_MODULE, once=True, max_ms=duration_ms):
            return
        fallback = CATEGORY_FALLBACK.get(category)
        if fallback:
            self.behavior.request(fallback, PRIORITY_MODULE, once=True, max_ms=duration_ms)

    def _set_tray_text(self, text: str) -> None:
        if getattr(self, "tray", None) is not None:
            self.tray.set_tooltip(text)

    def _on_module_tick(self) -> None:
        now = self.clock()
        for module in self.modules.values():
            if module.enabled:
                module.tick(now)

    # ------------------------------------------------------------ 自动更新

    def _schedule_update_check(self) -> None:
        """启动 5 秒后检查一次更新；脚本模式下不检查（源码目录不是可替换的安装目录）。"""
        if not getattr(sys, "frozen", False):
            return
        QTimer.singleShot(_UPDATE_CHECK_DELAY_MS, self._start_update_check)

    def _start_update_check(self) -> None:
        thread = UpdateCheckThread(VERSION, self.root / "assets", latest_url=LATEST_URL)
        thread.checked.connect(self._on_update_checked)
        self._update_thread = thread
        thread.start()

    def _on_update_checked(self, info) -> None:
        if not isinstance(info, dict):
            return
        if info.get("asset_changes"):
            self._apply_asset_changes(info)
        if info.get("package"):
            self._update_info = info
            self._prompt_update(info)

    def _apply_asset_changes(self, info: dict) -> None:
        """素材热更：先释放影片缓存（否则 GIF 被 QMovie 占着覆盖会失败），下载交给后台线程。"""
        self.sprite.release_movies()
        thread = AssetUpdateThread(
            info["asset_changes"], info["assets_base"], self.root / "assets"
        )
        thread.done.connect(self._on_assets_updated)
        self._asset_thread = thread
        thread.start()

    def _on_assets_updated(self, done) -> None:
        """素材下载完成（主线程）：原地换索引并提示一句。"""
        if not done:
            return
        fresh = load_categories(self.root / "assets" / "categories.json")
        self.catalog.clear()
        self.catalog.update(fresh)
        self.sprite.reload()
        self._show_toast(_ASSET_TOAST)

    def _prompt_update(self, info: dict) -> None:
        self._update_prompt.show_version(
            info.get("version", ""), info.get("notes", ""), anchor=self._pet_anchor()
        )

    def _dismiss_update_prompt(self) -> None:
        """点「稍后」只关窗；`_update_info` 保留，托盘菜单入口还在。"""
        self._update_prompt.hide()

    def _update_now(self) -> None:
        info = self._update_info
        if not info or not info.get("package"):
            return
        self._update_prompt.show_version(
            info.get("version", ""), info.get("notes", ""), anchor=self._pet_anchor()
        )
        self._update_prompt.set_busy(True)
        thread = ProgramUpdateThread(info, self.root, Path(tempfile.gettempdir()) / "momolulu-update")
        thread.staged.connect(self._on_program_staged)
        thread.progressed.connect(self._on_program_progress)
        self._program_thread = thread
        thread.start()

    def _on_program_progress(self, percent: int) -> None:
        self._update_prompt.set_download_progress(percent)

    def _on_program_staged(self, bat) -> None:
        if bat is None:
            self._update_prompt.set_busy(False, "更新失败，已保留当前版本")
            return
        try:
            subprocess.Popen(
                ["cmd", "/c", str(bat)],
                creationflags=subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        except OSError:
            self._update_prompt.set_busy(False, "更新失败，已保留当前版本")
            return
        self._quit()

    # ------------------------------------------------------------ 启动与位置

    def _screens(self) -> list[tuple[int, int, int, int]]:
        return [tuple(screen.geometry().getRect()) for screen in self.app.screens()]

    def _work_areas(self) -> list[tuple[int, int, int, int]]:
        """每块屏的工作区矩形（扣掉任务栏等系统保留区），与 `_screens()` 同序。

        散步贴着它走，否则底边那段会落到任务栏所在的那条带里被压住看不见。
        """
        return [tuple(screen.availableGeometry().getRect()) for screen in self.app.screens()]

    def _start_ui(self) -> None:
        self.behavior.start()
        size = (self.sprite.width(), self.sprite.height())
        screens = self._screens()
        saved = self.config.get("pet", {}).get("pos")
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            pos = clamp_to_screen((saved[0], saved[1]), size, screens)
        elif screens:
            pos = _bottom_right(screens[0], size, _DEFAULT_MARGIN)
        else:
            pos = (0, 0)
        self.sprite.move_to(*pos)
        self.sprite.show()
        self.sprite.set_passthrough(bool(self.config.get("pet", {}).get("passthrough", False)))
        self.sprite.set_always_on_top(bool(self.config.get("pet", {}).get("always_on_top", True)))
        self.edge_hider.restore_from_config()
        self._tick_timer.start()
        self._fs_timer.start()
        if pick(self.catalog, "idle", self.processed_dir) is None:
            print("assets/processed 为空，请先运行 tools_cli/prepare.py")

    def _remember_position(self) -> None:
        self.config["pet"]["pos"] = [int(self.sprite.x()), int(self.sprite.y())]

    def _flush_position(self) -> None:
        self._remember_position()
        save_config(self.config_path, self.config)

    # ------------------------------------------------------------ 拖拽接线

    def _on_drag_moved(self, global_pos: QPoint) -> None:
        if not self._drag_active:
            self._drag_active = True
            self.behavior.on_drag_started()
        self.sprite.move_to(
            global_pos.x() - self.sprite.width() // 2,
            global_pos.y() - self.sprite.height() // 2,
        )

    def _on_drag_finished(self, global_pos: QPoint) -> None:
        if self._drag_active:
            self._drag_active = False
            self.behavior.on_drag_finished()
        self.edge_hider.maybe_hide((self.sprite.x(), self.sprite.y()))
        self._remember_position()
        self._save_timer.start()

    # ------------------------------------------------------------ 生命周期

    def shutdown(self) -> None:
        """停定时器、断信号、落盘并退出事件循环；重复调用安全。"""
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self._tick_timer.stop()
        self._fs_timer.stop()
        self._module_timer.stop()
        self.behavior.stop()
        self._save_timer.stop()
        self.toast.hide()
        self._update_prompt.hide()
        for signal, slot in (
            (self.sprite.drag_moved, self._on_drag_moved),
            (self.sprite.drag_finished, self._on_drag_finished),
            (self.sprite.clicked, self.behavior.on_user_click),
            (self.sprite.clicked, self._on_clicked),
            (self.sprite.fast_clicked, self.behavior.on_fast_click),
            (self.sprite.fast_clicked, self._on_fast_clicked),
            (self.sprite.play_finished, self.behavior.on_play_finished),
            (self.sprite.right_clicked, self._on_right_clicked),
            (self.sprite.moved, self._follow_toast),
            (self.app.screenAdded, self._on_screens_changed),
            (self.app.screenRemoved, self._on_screens_changed),
        ):
            try:
                signal.disconnect(slot)
            except TypeError:
                pass
        self._flush_position()
        self.app.quit()

    def run(self) -> int:
        return self.app.exec_()


def main() -> int:
    try:
        logging.basicConfig(
            filename=app_root() / "momolulu.log",
            level=logging.WARNING,
            encoding="utf-8",
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except Exception:  # noqa: BLE001 - 日志不可写绝不能影响噜噜运行
        pass
    return PetApp().run()


if __name__ == "__main__":
    sys.exit(main())
