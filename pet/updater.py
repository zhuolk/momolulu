"""自动更新的纯逻辑：版本比较、latest.json 解析、素材差异、bat 生成。

这一层不做任何网络 IO —— 取字节的能力一律由调用方以 `fetch` / `download` 注入，
所以单测完全离线、可以精确构造成功与失败。
"""

from __future__ import annotations

import json
import re

LATEST_URL = "https://raw.githubusercontent.com/zhuolk/momolulu/main/update/latest.json"

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_ZERO = (0, 0, 0)


def parse_version(text: object) -> tuple[int, int, int] | None:
    """严格解析 `x.y.z`；其余一律返回 None。"""
    if not isinstance(text, str):
        return None
    match = _SEMVER_RE.match(text.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def compare_versions(a: object, b: object) -> int:
    """比较两个版本号，返回 -1 / 0 / 1；无法解析的一侧按 `0.0.0` 处理。"""
    left = parse_version(a) or _ZERO
    right = parse_version(b) or _ZERO
    if left == right:
        return 0
    return 1 if left > right else -1


def update_available(local: str, remote: object) -> bool:
    """远端版本是否严格高于本地。"""
    return parse_version(remote) is not None and compare_versions(remote, local) > 0


def _package(raw: object) -> dict | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("package 不是对象")
    url, sha256, size = raw.get("url"), raw.get("sha256"), raw.get("size")
    if not isinstance(url, str) or not url:
        raise ValueError("package.url 非法")
    if not isinstance(sha256, str) or not sha256:
        raise ValueError("package.sha256 非法")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("package.size 非法")
    return {"url": url, "sha256": sha256, "size": size}


def _assets(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("assets 不是对象")
    base, files = raw.get("base"), raw.get("files")
    if not isinstance(base, str) or not base:
        raise ValueError("assets.base 非法")
    if not isinstance(files, dict) or not files:
        raise ValueError("assets.files 非法")
    clean: dict[str, str] = {}
    for name, digest in files.items():
        if not isinstance(name, str) or not isinstance(digest, str) or not digest:
            raise ValueError("assets.files 条目非法")
        clean[name] = digest
    return {"base": base, "files": clean}


def parse_latest(raw: bytes | str) -> dict | None:
    """解析远端 `latest.json`；任何问题都返回 None（放弃本次更新，不抛异常）。"""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        package = _package(data.get("package"))
        assets = _assets(data.get("assets"))
    except ValueError:
        return None
    version = data.get("version")
    notes = data.get("notes")
    return {
        "version": version if isinstance(version, str) else "",
        "notes": notes if isinstance(notes, str) else "",
        "package": package,
        "assets": assets,
    }
