"""运行时配置读写：默认值 + 深合并 + 类型校验 + 原子写入。

配置文件为程序目录下的 `config.json`，与 spec §10 一一对应。
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

DEFAULTS: dict = {
    "version": 2,
    "pet": {
        "scale": 0.5,
        "pos": None,
        "edge_hide": None,
        "always_on_top": True,
        "passthrough": False,
        "hide_on_fullscreen": True,
        "state_intervals": {
            "idle_to_wander": [3300, 3900],
            "idle_to_sleep": 900,
        },
    },
    "modules": {
        "pomodoro": {"enabled": False, "focus_min": 25, "break_min": 5},
        "health_reminder": {"enabled": True, "water_enabled": True, "sit_enabled": True,
                            "water_min": 45, "sit_min": 60, "snooze_min": 10},
        "meal_reminder": {"enabled": True, "times": ["12:00", "18:30"]},
        "hourly_chime": {"enabled": False},
        # 生活数值：0~100，只按「在线时间」衰减（进程没跑的那段不扣）
        "vitals": {
            "enabled": True,
            "mood": 80,
            "energy": 80,
            "satiety": 80,
            "mood_decay_per_hour": 6,
            "energy_decay_per_hour": 8,
            "satiety_decay_per_hour": 10,
            "energy_sleep_recover_per_hour": 30,
            "work_decay_multiplier": 2,
            "warn_threshold": 30,
            "low_threshold": 10,
        },
        # 噜噜币与上班收入
        "economy": {
            "enabled": True,
            "coins": 0,
            "income_per_minute": 1,
        },
    },
}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _valid_pair(value: object) -> bool:
    """二维整数坐标（允许负值，多屏可能为负）。"""
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(_is_int(v) for v in value)
    )


def _valid_pos(value: object) -> bool:
    return value is None or _valid_pair(value)


def _valid_edge_hide(value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict):
        return False
    return value.get("side") in ("left", "right") and _is_int(value.get("y"))


def _valid_interval(value: object) -> bool:
    return _valid_pair(value) and all(v > 0 for v in value)


def _valid_times(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(v, str) and _TIME_RE.match(v) for v in value)
    )


def _valid_level(value: object) -> bool:
    """生活数值：允许 0（见底）到 100 之间的任意数。"""
    return _is_number(value) and 0 <= float(value) <= 100


def _valid_coins(value: object) -> bool:
    """噜噜币：允许 0，不允许负数。"""
    return _is_number(value) and float(value) >= 0


# 需要特殊校验的路径（点号分隔），其余按默认值的类型与正数规则校验
# 注意：`_valid_scalar` 对整数默认值要求 `> 0`，所以「可以是 0」的字段必须走这里
_SPECIAL = {
    "pet.pos": _valid_pos,
    "pet.edge_hide": _valid_edge_hide,
    "pet.state_intervals.idle_to_wander": _valid_interval,
    "modules.meal_reminder.times": _valid_times,
    "modules.vitals.mood": _valid_level,
    "modules.vitals.energy": _valid_level,
    "modules.vitals.satiety": _valid_level,
    "modules.economy.coins": _valid_coins,
}


def _valid_scalar(value: object, default: object) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if _is_int(default):
        return _is_int(value) and value > 0
    if isinstance(default, float):
        return _is_number(value) and value > 0
    if isinstance(default, str):
        return isinstance(value, str)
    return True


def _merge_validate(value: object, default: object, path: str) -> object:
    """按 default 的结构递归补全 value 并逐字段校验；未知键原样保留。"""
    if isinstance(default, dict):
        source = value if isinstance(value, dict) else {}
        out: dict = {k: copy.deepcopy(v) for k, v in source.items()}
        for key, sub_default in default.items():
            child = f"{path}.{key}" if path else key
            if key in source:
                out[key] = _merge_validate(source[key], sub_default, child)
            else:
                out[key] = copy.deepcopy(sub_default)
        return out
    checker = _SPECIAL.get(path)
    if checker is not None:
        return copy.deepcopy(value) if checker(value) else copy.deepcopy(default)
    return copy.deepcopy(value) if _valid_scalar(value, default) else copy.deepcopy(default)


def validate(cfg: dict) -> dict:
    """返回校验后的新 dict（深拷贝，绝不修改入参）；损坏字段回落默认值。"""
    return _merge_validate(cfg, DEFAULTS, "")


def _migrate(cfg: dict) -> dict:
    """把旧版本配置升到当前版本（就地改传入的 dict，调用方保证那是刚解析出的新对象）。

    只处理「默认值变了、老用户跟着变」这一种迁移：**仍停留在旧默认值的字段**才更新，
    用户自己调过的值不动；升完写上当前版本号，避免重复迁移。
    """
    version = cfg.get("version")
    if _is_int(version) and version >= DEFAULTS["version"]:
        return cfg
    # v1 → v2：待机小动作间隔由 [30, 120] 秒（约 1 分多钟）改为约 1 小时。
    pet = cfg.get("pet")
    intervals = pet.get("state_intervals") if isinstance(pet, dict) else None
    if isinstance(intervals, dict) and intervals.get("idle_to_wander") == [30, 120]:
        intervals["idle_to_wander"] = copy.deepcopy(
            DEFAULTS["pet"]["state_intervals"]["idle_to_wander"]
        )
    cfg["version"] = DEFAULTS["version"]
    return cfg


def load_config(path: Path) -> dict:
    """读取配置并做深合并 + 校验；文件缺失返回默认，损坏则备份为 `.bad` 后返回默认。"""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except FileNotFoundError:
        return copy.deepcopy(DEFAULTS)
    except (OSError, ValueError, TypeError):
        try:
            os.replace(path, path.with_name(path.name + ".bad"))
        except OSError:
            pass
        return copy.deepcopy(DEFAULTS)
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULTS)
    return validate(_migrate(data))


def save_config(path: Path, cfg: dict) -> None:
    """原子写入配置（先写 `.tmp` 再 `os.replace`）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(cfg, fp, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get(cfg: dict, dotted: str, default=None):
    """按点号路径取值，任一层缺失即返回 default。"""
    node = cfg
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node
