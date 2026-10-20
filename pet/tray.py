"""系统托盘：图标 + 上下文菜单（每次弹出前按当前状态重建）+ 气泡通知。

菜单**不走** `QSystemTrayIcon.setContextMenu`：那条路会把菜单交给平台原生实现，而菜单
内容每次弹出都要重建（勾选态会变），原生菜单与新建的菜单项对不上，Windows 上表现为
「只剩一项、文字错乱」。改为自己接 `activated(Context)` 弹出普通 Qt 菜单，与右键噜噜
的菜单走同一条渲染路径。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image
from PyQt5.QtCore import QObject
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtWidgets import QMenu, QSystemTrayIcon

ICON_SIZE = 64
TOOLTIP = "噜噜"
TRAY_ASSET = "lulu_002.gif"  # 托盘图标固定取这张素材的首帧


def find_transparent_asset(processed_dir: Path, catalog_data: dict) -> Path | None:
    """找出第一个「实测轨道为 transparent 且文件存在」的素材。"""
    tracks = catalog_data.get("tracks", {}) if isinstance(catalog_data, dict) else {}
    for name, track in tracks.items():
        path = Path(processed_dir) / name
        if track == "transparent" and path.exists():
            return path
    return None


def ensure_tray_icon(processed_dir: Path, catalog_data: dict, out_path: Path) -> Path:
    """生成 64×64 托盘 PNG：已存在直接复用；否则按 `TRAY_ASSET` → transparent 素材 → 桔子依次兜底。"""
    out_path = Path(out_path)
    if out_path.exists():
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    source = Path(processed_dir) / TRAY_ASSET
    if not source.exists():
        source = find_transparent_asset(processed_dir, catalog_data)
    if source is not None:
        with Image.open(source) as image:
            image.seek(0)
            frame = image.convert("RGBA").resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
        frame.save(out_path, "PNG")
        return out_path

    from pet.sprite import Sprite  # 延迟导入，仅有回退路径才需要 Qt 绘图

    Sprite.draw_orange(ICON_SIZE).save(str(out_path), "PNG")
    return out_path


class Tray(QObject):
    """`QSystemTrayIcon` 包装；无托盘环境下 `show()` 返回 False 且不抛异常。"""

    def __init__(self, app, icon: QIcon, menu_factory: Callable[[], QMenu]):
        super().__init__()
        self._app = app
        self._menu_factory = menu_factory
        self._menu: QMenu | None = None

        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(TOOLTIP)
        self._tray.activated.connect(self._on_activated)

    @property
    def available(self) -> bool:
        return bool(QSystemTrayIcon.isSystemTrayAvailable())

    @property
    def menu(self) -> QMenu | None:
        """当前弹出的菜单（未弹出时为 `None`）。"""
        return self._menu

    def show(self) -> bool:
        if not self.available:
            return False
        self._tray.show()
        return True

    def hide(self) -> None:
        self._tray.hide()

    def notify(self, title: str, text: str) -> None:
        self._tray.showMessage(title, text)

    def set_tooltip(self, text: str) -> None:
        """更新悬停提示文本（空字符串回落默认文案）。"""
        self._tray.setToolTip(text or TOOLTIP)

    def popup_menu(self) -> bool:
        """在鼠标位置弹出按当前状态新建的菜单。"""
        menu = self._menu_factory()
        if menu is None:
            return False
        self._menu = menu
        menu.aboutToHide.connect(self._forget_menu)
        menu.popup(QCursor.pos())
        return True

    # ------------------------------------------------------------ 内部

    def _on_activated(self, reason) -> None:
        """右键（`Context`）才弹菜单；左键双击等不做处理。"""
        if reason == QSystemTrayIcon.Context:
            self.popup_menu()

    def _forget_menu(self) -> None:
        """菜单关闭后释放，避免每次右键堆一个 QMenu。"""
        menu, self._menu = self._menu, None
        if menu is not None:
            menu.deleteLater()
