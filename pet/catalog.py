"""分类索引与素材回退链（无 Qt 依赖）。

`categories.json` 的结构::

    {
      "version": 2,
      "categories": {"idle": {"files": [...], "track": "auto"}, ..., "unassigned": {...}},
      "tracks": {"lulu_001.gif": "transparent"}
    }

`categories[cat]["track"]` 是该分类的聚合轨道（分类内文件轨道一致时为其值，混杂时为
"auto"）；`tracks` 保存每个文件的实测轨道，供按轨挑选素材。
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

CATEGORIES: tuple[str, ...] = (
    "idle",
    "walk",
    "stroll",
    "sleep",
    "eat",
    "drink",
    "happy",
    "angry",
    "sad",
    "bath",
)
UNASSIGNED = "unassigned"
VERSION = 2

# 回退链：找不到目标分类时逐级降级，最后落到 unassigned
FALLBACK: dict[str, tuple[str, ...]] = {name: (name, "idle", UNASSIGNED) for name in CATEGORIES}
FALLBACK["drink"] = ("drink", "eat", "idle", UNASSIGNED)
FALLBACK[UNASSIGNED] = (UNASSIGNED,)


def default_categories() -> dict:
    """返回空的分类索引结构。"""
    categories = {name: {"files": [], "track": "auto"} for name in CATEGORIES}
    categories[UNASSIGNED] = {"files": [], "track": "auto"}
    return {"version": VERSION, "categories": categories, "tracks": {}}


def _is_valid(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    categories = data.get("categories")
    if not isinstance(categories, dict):
        return False
    for entry in categories.values():
        if not isinstance(entry, dict) or not isinstance(entry.get("files"), list):
            return False
    tracks = data.get("tracks", {})
    return isinstance(tracks, dict)


def load_categories(path: Path) -> dict:
    """读取分类索引；文件缺失、损坏或结构不符时返回默认结构（并补齐缺失分类）。"""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError, TypeError):
        return default_categories()
    if not _is_valid(data):
        return default_categories()

    merged = default_categories()
    merged["tracks"].update({k: v for k, v in data.get("tracks", {}).items() if isinstance(v, str)})
    for name, entry in data["categories"].items():
        target = merged["categories"].setdefault(name, {"files": [], "track": "auto"})
        target["files"] = list(entry["files"])
        track = entry.get("track")
        target["track"] = track if isinstance(track, str) else "auto"
    return merged


def save_categories(path: Path, data: dict) -> None:
    """原子写入分类索引（先写临时文件再替换）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def existing_files(names: list[str], processed_dir: Path) -> list[str]:
    """按原顺序过滤掉磁盘上不存在的文件名，并去重。"""
    processed_dir = Path(processed_dir)
    out: list[str] = []
    for name in names:
        if name in out:
            continue
        if (processed_dir / name).is_file():
            out.append(name)
    return out


def track_of(data: dict, name: str) -> str:
    """取文件的实测轨道；无记录时返回 "auto"。"""
    return data.get("tracks", {}).get(name, "auto")


def set_track(data: dict, name: str, track: str) -> None:
    """记录文件轨道，并刷新其所属分类的聚合轨道。"""
    data.setdefault("tracks", {})[name] = track
    tracks = data["tracks"]
    for entry in data.get("categories", {}).values():
        files = entry.get("files") or []
        if name not in files:
            continue
        kinds = {tracks.get(f, "auto") for f in files}
        entry["track"] = kinds.pop() if len(kinds) == 1 else "auto"


def add_unassigned(data: dict, names: list[str], tracks: dict[str, str]) -> None:
    """把新素材登记到 unassigned（去重），并记录各自轨道。"""
    entry = data.setdefault("categories", {}).setdefault(
        UNASSIGNED, {"files": [], "track": "auto"}
    )
    for name in names:
        if name not in entry["files"]:
            entry["files"].append(name)
    for name in names:
        if name in tracks:
            set_track(data, name, tracks[name])


def _filter_track(data: dict, names: list[str], track: str | None) -> list[str]:
    if track is None:
        return names
    matched = [n for n in names if track_of(data, n) == track]
    return matched or names  # 符合轨道的为空时忽略轨道条件，宁可有素材


def _catalog_is_empty(data: dict) -> bool:
    return not any(entry.get("files") for entry in data.get("categories", {}).values())


def pick(
    data: dict,
    category: str,
    processed_dir: Path,
    track: str | None = None,
    rng: random.Random | None = None,
) -> Path | None:
    """沿回退链选一个已存在的素材；全链为空返回 None。

    索引整体为空（如 categories.json 丢失）时退化为扫描 processed_dir 兜底。
    """
    processed_dir = Path(processed_dir)
    rng = rng or random.Random()
    categories = data.get("categories", {})

    for name in FALLBACK.get(category, (category, "idle", UNASSIGNED)):
        entry = categories.get(name) or {}
        candidates = existing_files(list(entry.get("files") or []), processed_dir)
        candidates = _filter_track(data, candidates, track)
        if candidates:
            return processed_dir / rng.choice(sorted(candidates))

    if _catalog_is_empty(data):
        candidates = _filter_track(data, sorted(p.name for p in processed_dir.glob("*.gif")), track)
        if candidates:
            return processed_dir / rng.choice(sorted(candidates))
    return None
