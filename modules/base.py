"""实用模块框架：统一的 enable / disable / tick 生命周期与宿主交互上下文。"""

from __future__ import annotations

from datetime import datetime
from typing import Callable


class ModuleContext:
    """模块与宿主（桌宠 UI）之间的唯一交互通道。"""

    def __init__(
        self,
        notify: Callable[[str, str, int], None],
        set_tray_text: Callable[[str], None],
        config: dict,
        save: Callable[[], None],
    ):
        self._notify = notify
        self._set_tray_text = set_tray_text
        self._config = config
        self._save = save

    @property
    def config(self) -> dict:
        """运行时配置 dict 的引用（模块可直接读写）。"""
        return self._config

    def notify(self, text: str, category: str = "happy", duration_ms: int = 6000) -> None:
        """弹气泡提示；`category` 决定用哪类素材呈现（如 `eat` / `drink`）。"""
        self._notify(text, category, duration_ms)

    def set_tray_text(self, text: str) -> None:
        """更新托盘悬停文本。"""
        self._set_tray_text(text)

    def save(self) -> None:
        """立即把配置落盘。"""
        self._save()


class Module:
    """模块基类：注册名 / 标题 / 默认开关 + 统一生命周期。"""

    name: str = ""
    title: str = ""
    default_enabled: bool = False

    def __init__(self, ctx: ModuleContext):
        self.ctx = ctx
        self._enabled = False
        self.events: list = []  # 轻量事件日志，便于调试与测试

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        """模块被启用时调用（子类覆写）。"""

    def disable(self) -> None:
        """模块被停用时调用（子类覆写）。"""

    def tick(self, now: datetime) -> None:
        """宿主定时驱动（子类覆写）。"""

    def set_enabled(self, on: bool) -> None:
        """切换开关：幂等（状态未变则直接返回）、写配置并落盘。"""
        on = bool(on)
        if on == self._enabled:
            return
        self._enabled = on
        node = self.ctx.config.setdefault("modules", {}).setdefault(self.name, {})
        node["enabled"] = on
        if on:
            self.enable()
        else:
            self.disable()
        self.ctx.save()

    def sub_switches(self) -> tuple[str, ...]:
        """该模块暴露的子开关名（默认无，子开关模块覆写）。"""
        return ()

    # ------------------------------------------------------------ 内部

    def _enable_from_config(self) -> None:
        """启动时按配置启用：只置位并调 `enable()`，不写配置、不落盘。"""
        self._enabled = True
        self.enable()


MODULE_CLASSES: list[type[Module]] = []


def config_enabled(config: dict, name: str, default: bool = False) -> bool:
    """读 `modules.<name>.enabled`；缺失或类型不对时回落 `default`。"""
    node = config.get("modules", {}).get(name, {})
    if isinstance(node, dict) and isinstance(node.get("enabled"), bool):
        return node["enabled"]
    return bool(default)


def build_modules(ctx: ModuleContext) -> dict[str, Module]:
    """实例化已注册模块，并按配置打开启用的那些（不重复落盘）。"""
    modules: dict[str, Module] = {}
    for cls in MODULE_CLASSES:
        module = cls(ctx)
        modules[cls.name] = module
        if config_enabled(ctx.config, cls.name, cls.default_enabled):
            module._enable_from_config()
    return modules
