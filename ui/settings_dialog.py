"""设置面板：把 `config.json` 的主要字段暴露成控件，保存前做校验。

设计要点：
- 内部持有一份 `config` 的深拷贝，控件改动即时写回该副本；
- `values()` 返回副本的深拷贝，调用方写盘即可（不会污染入参）；
- `accept()` 先经 `pet.config.validate` 规范化，再检查语义范围（如缩放 0.5–2.0），
  任一不合法则写入 `error_text` 并拒绝关闭。
"""

from __future__ import annotations

import copy
import re

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pet.config import validate

# 语义范围约束（超出即拒绝保存）；`pet.config.validate` 只保证类型与正数
RANGES: dict[str, tuple[float, float]] = {"pet.scale": (0.5, 2.0)}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def parse_times(text: str) -> list[str]:
    """把 "12:00, 18:30" 之类的输入解析成合法时刻列表。"""
    parts = [p.strip() for p in str(text).replace("，", ",").replace(";", ",").split(",")]
    return [p for p in parts if _TIME_RE.match(p)]


def _get(cfg: dict, path: str, default=None):
    node = cfg
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def _assign(cfg: dict, path: str, value) -> None:
    keys = path.split(".")
    node = cfg
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    node[keys[-1]] = value


class SettingsDialog(QDialog):
    """噜噜设置面板；`config_saved` 在保存成功时携带校验后的配置。"""

    config_saved = pyqtSignal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("噜噜设置")
        self._cfg = copy.deepcopy(config)
        self._setters: dict[str, object] = {}
        self.error_text = ""

        self._tabs = QTabWidget(self)
        self._pet_page = QWidget(self)
        self._tool_page = QWidget(self)
        self._tabs.addTab(self._pet_page, "噜噜")
        self._tabs.addTab(self._tool_page, "工具")

        self._build_pet_page()
        self._build_tool_page()

        self._error_label = QLabel("", self)
        self._error_label.setStyleSheet("color: #c0392b;")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(self._error_label)
        layout.addWidget(buttons)
        self._sync_widgets()

    # ------------------------------------------------------------ 控件搭建

    def _build_pet_page(self) -> None:
        form = QFormLayout(self._pet_page)
        self._add_double(form, "显示缩放", "pet.scale", 0.1, 10.0, step=0.1, decimals=2)
        self._add_check(form, "始终置顶", "pet.always_on_top")
        self._add_check(form, "全屏时自动隐藏", "pet.hide_on_fullscreen")
        self._add_check(form, "开机自启", "autostart")

    def _build_tool_page(self) -> None:
        form = QFormLayout(self._tool_page)
        form.addRow(QLabel("番茄钟"))
        self._add_check(form, "启用", "modules.pomodoro.enabled")
        self._add_int(form, "专注时长（分钟）", "modules.pomodoro.focus_min", 1, 999)
        self._add_int(form, "休息时长（分钟）", "modules.pomodoro.break_min", 1, 999)

        form.addRow(QLabel("喝水 / 久坐"))
        self._add_check(form, "喝水提醒", "modules.health_reminder.water_enabled")
        self._add_int(form, "喝水的间隔（分钟）", "modules.health_reminder.water_min", 1, 999)
        self._add_check(form, "久坐提醒", "modules.health_reminder.sit_enabled")
        self._add_int(form, "久坐的间隔（分钟）", "modules.health_reminder.sit_min", 1, 999)
        self._add_int(form, "稍后提醒（分钟）", "modules.health_reminder.snooze_min", 1, 999)

        form.addRow(QLabel("吃饭提醒"))
        self._add_check(form, "启用", "modules.meal_reminder.enabled")
        self._add_times(form, "提醒时刻（逗号分隔）", "modules.meal_reminder.times")

        form.addRow(QLabel("整点报时"))
        self._add_check(form, "启用", "modules.hourly_chime.enabled")

    def _add_check(self, form: QFormLayout, label: str, path: str) -> None:
        box = QCheckBox(self)
        box.stateChanged.connect(lambda _state, p=path, w=box: _assign(self._cfg, p, w.isChecked()))
        self._setters[path] = lambda value, w=box: w.setChecked(bool(value))
        form.addRow(label, box)

    def _add_int(
        self, form: QFormLayout, label: str, path: str, minimum: int, maximum: int
    ) -> None:
        spin = QSpinBox(self)
        spin.setRange(minimum, maximum)
        spin.valueChanged.connect(lambda value, p=path: _assign(self._cfg, p, int(value)))
        self._setters[path] = lambda value, w=spin: w.setValue(int(value))
        form.addRow(label, spin)

    def _add_double(
        self,
        form: QFormLayout,
        label: str,
        path: str,
        minimum: float,
        maximum: float,
        step: float = 0.1,
        decimals: int = 1,
    ) -> None:
        spin = QDoubleSpinBox(self)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.valueChanged.connect(lambda value, p=path: _assign(self._cfg, p, float(value)))
        self._setters[path] = lambda value, w=spin: w.setValue(float(value))
        form.addRow(label, spin)

    def _add_times(self, form: QFormLayout, label: str, path: str) -> None:
        edit = QLineEdit(self)
        edit.textChanged.connect(lambda text, p=path: _assign(self._cfg, p, parse_times(text)))
        self._setters[path] = lambda value, w=edit: w.setText(
            ", ".join(value) if isinstance(value, (list, tuple)) else str(value)
        )
        form.addRow(label, edit)

    # ------------------------------------------------------------ 读写

    def set_field(self, path: str, value) -> None:
        """按点号路径写入配置副本，并同步对应控件。"""
        _assign(self._cfg, path, copy.deepcopy(value))
        setter = self._setters.get(path)
        if setter is not None:
            setter(value)

    def values(self) -> dict:
        """返回当前配置副本（深拷贝，可直接写回 `config.json`）。"""
        return copy.deepcopy(self._cfg)

    # ------------------------------------------------------------ 保存

    def accept(self) -> bool:
        """校验通过则发 `config_saved` 并关闭；否则写 `error_text` 并留在面板。"""
        validated = validate(self._cfg)
        error = self._range_error(validated)
        self.error_text = error
        self._error_label.setText(error)
        if error:
            return False
        self._cfg = validated
        self._sync_widgets()
        self.config_saved.emit(self.values())
        super().accept()
        return True

    # ------------------------------------------------------------ 内部

    def _range_error(self, cfg: dict) -> str:
        for path, (low, high) in RANGES.items():
            value = _get(cfg, path)
            if not isinstance(value, (int, float)) or not low <= float(value) <= high:
                return f"{path} 需要在 {low} ~ {high} 之间（当前 {value}）"
        return ""

    def _sync_widgets(self) -> None:
        for path, setter in self._setters.items():
            value = _get(self._cfg, path)
            if value is not None:
                setter(value)
