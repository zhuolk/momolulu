# 噜噜自动更新 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让发出去的噜噜在启动时检查 GitHub，素材静默热更、程序更新弹窗确认后整目录交换并自动重启。

**Architecture:** 网络层与纯逻辑层分离。`pet/download.py` 只负责「按安全边界取字节」，`pet/updater.py` 全是可注入 `fetch` 的纯函数（解析、版本比较、素材差异、bat 生成、更新编排），`pet/update_runner.py` 把同步逻辑包进 `QThread` 以免阻塞 UI。更新源是一个 URL 常量 + 一个可注入的 `fetch`，换源只改一处。

**Tech Stack:** Python 3.10.4 / PyQt5 5.15.11 / Pillow / PyInstaller 6.15.0（`--onedir`）/ pytest。网络只用标准库 `urllib.request`。

**Spec:** [2026-10-21-auto-update-design.md](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/docs/superpowers/specs/2026-10-21-auto-update-design.md)

## Global Constraints

- 网络实现只用标准库 `urllib.request`，**不引入 `requests`**（spec §10）
- 只允许 `https://`；**起始 URL 的主机**必须在白名单 `("raw.githubusercontent.com", "github.com")`；重定向只校验协议仍是 https，最多 5 跳，不做逐跳主机白名单（spec §8）
- **不内嵌任何 GitHub 凭据**（spec §2 反目标）
- 打 zip 时**必须排除 `config.json`**，由 `updater.bat` 从旧目录搬迁（spec §6.3）
- 所有更新相关异常**静默**处理：日志 + 放弃，绝不弹错误框、绝不影响噜噜继续运行（spec §7.1、§8）
- 未打包（脚本模式，`sys.frozen` 为假）时**不检查更新**（spec §9）
- 每个下载都校验 md5 / sha256；校验失败**目标文件保持不变**，且不留 `.tmp` 残留（spec §8、§11）
- 文案（逐字复制）：弹窗主句「有新版本，要现在更新吗」、弹窗按钮「现在更新」「稍后」、下载中「正在下载…」、下载失败「更新失败，已保留当前版本」、素材更新完成「噜噜换新衣服啦」、菜单项「立即更新到 {version}」
- 测试必须离线可跑：`fetch` / `download` 一律以参数注入假实现；`tests/conftest.py` 已设 `QT_QPA_PLATFORM=offscreen`，Qt 相关测试请求 `qapp` fixture
- 全部测试命令：`python -m pytest tests/<file>.py -q`（`pytest.ini` 已有 `testpaths = tests`、`addopts = -q`）
- 提交信息用中文 conventional commit（`feat:` / `fix:` / `test:` / `docs:`），不要用 heredoc 写多行信息（PowerShell 不支持），改用多个 `-m` 参数

## Review Focus

用户实际会撞上的五类输入 / 条件，按风险排序：

1. **远端 `latest.json` 的 `assets.files` 键含 `..` 或绝对路径** —— 用户期望更新只动 `assets/` 目录内；实现必须拒绝越界路径，否则素材更新会写到安装目录之外
2. **正在播放的那几张素材被 `QMovie` 持有文件句柄** —— 用户期望新素材立刻生效；Windows 上覆盖被占用文件会 `PermissionError`，不先释放缓存的话这几张永远更新不上（spec §7.2 第 2 步）
3. **安装目录含空格或中文（如 `C:\Users\张三\Desktop\momolulu`）** —— 用户期望更新后噜噜照常起来；`updater.bat` 里任一路径漏引号会静默失败，目录停在被改名的状态，噜噜再也起不来
4. **GitHub Release 下载 302 跳到 `objects.githubusercontent.com`** —— 用户期望 54MB 的包正常下完；若对每一跳都做主机白名单，下载会 100% 静默失败
5. **sha256 不匹配 / 解压失败** —— 用户期望坏包不会铺进安装目录；必须「先校验、后解压」，且失败时清理 `momolulu.new`

## File Structure

**新建**

| 文件 | 职责 |
| --- | --- |
| `pet/version.py` | 应用版本号单一真相源（`VERSION = "0.1.0"`） |
| `pet/download.py` | URL 安全校验 + 取字节 / 流式下载 + md5 / sha256（无 Qt、无业务） |
| `pet/updater.py` | 纯逻辑：版本比较、`latest.json` 解析、素材差异、素材应用、`updater.bat` 生成、程序更新编排、`check_for_update` 总入口 |
| `pet/update_runner.py` | 两个 `QThread`：`UpdateCheckThread`、`ProgramUpdateThread` |
| `ui/update_prompt.py` | `UpdatePrompt` 更新确认小窗（复用 `Toast` 画法，带按钮） |

**修改**

| 文件 | 改动 |
| --- | --- |
| `pet/sprite.py` | 从 `reload()` 抽出 `release_movies()`（释放影片缓存但不重播） |
| `ui/menu.py` | `MenuState` 加 `update_version`；`build_menu` 在「设置…」前插入「立即更新到 x.y.z」 |
| `main.py` | 启动 5s 后检查、应用素材热更、弹更新窗、托盘菜单「立即更新」入口 |
| `tools_cli/build.py` | 额外产出 `dist/momolulu-<version>.zip`（排除 `config.json`）与 `dist/latest.json` |
| `docs/handoff.md` | 补发布步骤 |
| `tests/test_menu.py` | 补菜单项用例 |

---

## Task 1: 版本号、版本比较与 `latest.json` 解析

**Files:**
- Create: `pet/version.py`
- Create: `pet/updater.py`
- Test: `tests/test_updater_meta.py`

**Interfaces:**
```python
# pet/version.py
VERSION = "0.1.0"

# pet/updater.py
LATEST_URL = "https://raw.githubusercontent.com/zhuolk/momolulu/main/update/latest.json"

def parse_version(text: object) -> tuple[int, int, int] | None
    # "1.2.3" -> (1,2,3)；"v1.2.3"/"1.2"/"abc"/None/123 -> None

def compare_versions(a: object, b: object) -> int
    # 返回 -1 / 0 / 1；任一侧解析失败按 (0,0,0) 处理，绝不抛异常

def update_available(local: str, remote: object) -> bool
    # remote 为 None 或解析失败 -> False；否则 compare_versions(remote, local) > 0

def parse_latest(raw: bytes | str) -> dict | None
    # 成功返回 {"version": str, "notes": str,
    #           "package": {"url": str, "sha256": str, "size": int} | None,
    #           "assets": {"base": str, "files": {相对路径: md5}}}
    # 任何缺失/类型错/畸形 JSON -> None（不抛异常）
```

`package` 允许缺失或为 `null`（表示这一版只更素材、不发程序包）；`assets` 必须存在且 `base` 是非空字符串、`files` 是非空 `{str: str}`。`notes` 缺失时补 `""`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_updater_meta.py`：

```python
import json

from pet.updater import compare_versions, parse_latest, parse_version, update_available
from pet.version import VERSION


def test_version_is_three_part_semver():
    assert parse_version(VERSION) is not None


def test_parse_version_accepts_and_rejects():
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("10.0.9") == (10, 0, 9)
    for bad in ("v1.2.3", "1.2", "abc", "", None, 123, "1.2.3.4"):
        assert parse_version(bad) is None


def test_compare_versions_orders_and_never_raises():
    assert compare_versions("0.2.0", "0.1.0") == 1
    assert compare_versions("0.1.0", "0.1.0") == 0
    assert compare_versions("0.1.0", "0.2.0") == -1
    assert compare_versions("0.10.0", "0.9.0") == 1
    assert compare_versions("abc", "0.1.0") == compare_versions("0.0.0", "0.1.0")
    assert compare_versions(None, None) == 0


def test_update_available():
    assert update_available("0.1.0", "0.2.0") is True
    assert update_available("0.1.0", "0.1.0") is False
    assert update_available("0.1.0", "0.0.9") is False
    assert update_available("0.1.0", None) is False
    assert update_available("0.1.0", "garbage") is False


def _latest(**over):
    data = {
        "version": "0.2.0",
        "notes": "新增两张素材",
        "package": {
            "url": "https://github.com/zhuolk/momolulu/releases/download/v0.2.0/momolulu-0.2.0.zip",
            "sha256": "a" * 64,
            "size": 1234,
        },
        "assets": {
            "base": "https://raw.githubusercontent.com/zhuolk/momolulu/main/assets/",
            "files": {"processed/lulu_001.gif": "b" * 32, "categories.json": "c" * 32},
        },
    }
    data.update(over)
    return data


def test_parse_latest_ok():
    got = parse_latest(json.dumps(_latest()).encode("utf-8"))
    assert got["version"] == "0.2.0"
    assert got["package"]["size"] == 1234
    assert got["assets"]["files"]["categories.json"] == "c" * 32


def test_parse_latest_allows_missing_package_and_extra_fields():
    got = parse_latest(json.dumps(_latest(package=None, extra="忽略我")))
    assert got["package"] is None
    got2 = parse_latest(json.dumps({"assets": _latest()["assets"]}))
    assert got2["version"] == "" and got2["notes"] == "" and got2["package"] is None


def test_parse_latest_safely_fails():
    for bad in (
        b"{not json",
        b"[]",
        b'{"assets": {}}',
        b'{"assets": {"base": "", "files": {"a.gif": "d"}}}',
        b'{"assets": {"base": "https://x/", "files": {}}}',
        json.dumps(_latest(assets={"base": "https://x/", "files": {"a.gif": 1}})).encode(),
        json.dumps(_latest(package={"url": 1, "sha256": "a", "size": "x"})).encode(),
    ):
        assert parse_latest(bad) is None
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_updater_meta.py -q
```

预期：`ModuleNotFoundError: No module named 'pet.version'` / `'pet.updater'`。

- [ ] **Step 3: 实现**

`pet/version.py`：

```python
"""应用版本号单一真相源：程序读它，`tools_cli/build.py` 也读它。"""

VERSION = "0.1.0"
```

`pet/updater.py`（本任务只写元信息部分，后续任务往下追加）：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_updater_meta.py -q
```

预期：全部通过。

- [ ] **Step 5: 提交**

```powershell
git add pet/version.py pet/updater.py tests/test_updater_meta.py
git commit -m "feat: 新增应用版本号与 latest.json 解析" -m "版本比较与解析全部走纯函数，非法输入安全失败返回 None。"
```

---

## Task 2: 下载与安全校验

**Files:**
- Create: `pet/download.py`
- Test: `tests/test_download.py`

**Interfaces:**
```python
# pet/download.py
ALLOWED_HOSTS = ("raw.githubusercontent.com", "github.com")
DEFAULT_TIMEOUT = 5.0
MAX_REDIRECTS = 5

class UpdateError(Exception): ...

def is_allowed_url(url: str) -> bool          # https + 主机在白名单（大小写不敏感）
def check_redirect(url: str) -> None          # 非 https 抛 UpdateError
def fetch_bytes(url: str, timeout: float = DEFAULT_TIMEOUT, opener=None) -> bytes
def download_file(url: str, dest: Path, timeout: float = DEFAULT_TIMEOUT, opener=None) -> Path
def md5_bytes(data: bytes) -> str
def md5_file(path: Path, chunk: int = 1 << 20) -> str
def sha256_file(path: Path, chunk: int = 1 << 20) -> str
```

`opener` 参数只为测试注入（默认 `_opener()` 返回一个带 `_HttpsOnlyRedirect` 的 `OpenerDirector`）。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_download.py`：

```python
import hashlib
from pathlib import Path

import pytest

from pet.download import (
    UpdateError,
    check_redirect,
    fetch_bytes,
    is_allowed_url,
    md5_bytes,
    md5_file,
    sha256_file,
)


def test_whitelist_accepts_only_https_and_known_hosts():
    assert is_allowed_url("https://raw.githubusercontent.com/zhuolk/momolulu/main/x") is True
    assert is_allowed_url("https://github.com/zhuolk/momolulu/releases/download/v1/x.zip") is True
    assert is_allowed_url("http://raw.githubusercontent.com/x") is False
    assert is_allowed_url("https://evil.com/x.zip") is False
    assert is_allowed_url("ftp://github.com/x") is False
    assert is_allowed_url("not a url") is False
    assert is_allowed_url("") is False


def test_redirect_must_stay_https():
    check_redirect("https://objects.githubusercontent.com/abc")  # 不抛
    with pytest.raises(UpdateError):
        check_redirect("http://objects.githubusercontent.com/abc")


def test_digest_helpers():
    assert md5_bytes(b"") == "d41d8cd98f00b204e9800998ecf8427e"
    blob = b"lulu" * 1000
    p = Path(__file__).parent / "_tmp_digest.bin"
    p.write_bytes(blob)
    try:
        assert md5_file(p) == hashlib.md5(blob).hexdigest()
        assert sha256_file(p) == hashlib.sha256(blob).hexdigest()
    finally:
        p.unlink(missing_ok=True)


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.urls = []

    def open(self, url, timeout=None):
        self.urls.append(url)
        return FakeResponse(self.payload)


def test_fetch_bytes_rejects_non_whitelisted_url_without_network():
    opener = FakeOpener(b"nope")
    with pytest.raises(UpdateError):
        fetch_bytes("http://raw.githubusercontent.com/x", opener=opener)
    with pytest.raises(UpdateError):
        fetch_bytes("https://evil.com/x", opener=opener)
    assert opener.urls == []


def test_fetch_bytes_returns_payload_for_allowed_url():
    opener = FakeOpener(b'{"a":1}')
    assert fetch_bytes("https://raw.githubusercontent.com/x", opener=opener) == b'{"a":1}'
    assert opener.urls == ["https://raw.githubusercontent.com/x"]


def test_fetch_bytes_wraps_oserror_as_update_error():
    class Boom:
        def open(self, url, timeout=None):
            raise OSError("断网了")

    with pytest.raises(UpdateError):
        fetch_bytes("https://github.com/x", opener=Boom())
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_download.py -q
```

预期：`ModuleNotFoundError: No module named 'pet.download'`。

- [ ] **Step 3: 实现**

创建 `pet/download.py`：

```python
"""取字节 + 安全边界：只允许 https，起始主机必须在白名单，重定向最多 5 跳且仍须 https。"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED_HOSTS = ("raw.githubusercontent.com", "github.com")
DEFAULT_TIMEOUT = 5.0
MAX_REDIRECTS = 5
USER_AGENT = "momolulu-updater"


class UpdateError(Exception):
    """更新流程中任何可预期的失败；上层一律静默处理。"""


def is_allowed_url(url: str) -> bool:
    """起始 URL 必须是 https，且主机在白名单内。"""
    if not isinstance(url, str) or not url:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme.lower() != "https":
        return False
    host = (parts.hostname or "").lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


def check_redirect(url: str) -> None:
    """重定向只校验协议：GitHub 的 Release 会跳到 objects.githubusercontent.com。"""
    if urlsplit(str(url)).scheme.lower() != "https":
        raise UpdateError(f"拒绝非 https 重定向：{url}")


class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        check_redirect(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener():
    return urllib.request.build_opener(_HttpsOnlyRedirect)


def _open(url: str, timeout: float, opener):
    if not is_allowed_url(url):
        raise UpdateError(f"不允许的更新地址：{url}")
    engine = opener if opener is not None else _opener()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return engine.open(request, timeout=timeout)
    except UpdateError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"请求失败：{url}（{exc}）") from exc


def fetch_bytes(url: str, timeout: float = DEFAULT_TIMEOUT, opener=None) -> bytes:
    """整体读回一个小文件（latest.json 等）。"""
    try:
        with _open(url, timeout, opener) as response:
            return response.read()
    except UpdateError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"读取失败：{url}（{exc}）") from exc


def download_file(url: str, dest: Path, timeout: float = DEFAULT_TIMEOUT, opener=None) -> Path:
    """流式下载到 dest（54MB 的整包不能整体读进内存）。"""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _open(url, timeout, opener) as response:
            with open(dest, "wb") as fp:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    fp.write(chunk)
    except UpdateError:
        dest.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        dest.unlink(missing_ok=True)
        raise UpdateError(f"下载失败：{url}（{exc}）") from exc
    return dest


def _digest(path: Path, name: str, chunk: int) -> str:
    digest = hashlib.new(name)
    with open(path, "rb") as fp:
        for block in iter(lambda: fp.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def md5_file(path: Path, chunk: int = 1 << 20) -> str:
    return _digest(Path(path), "md5", chunk)


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    return _digest(Path(path), "sha256", chunk)
```

`_open` 里 `engine.open(request, ...)` 用的是 `Request` 对象；`FakeOpener.open` 接受 `url` 位置参数即可（测试里签名 `open(self, url, timeout=None)`）。

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_download.py -q
```

- [ ] **Step 5: 提交**

```powershell
git add pet/download.py tests/test_download.py
git commit -m "feat: 新增下载层与 https 白名单校验" -m "起始地址限定 https 与白名单主机，重定向只校验协议并限 5 跳。"
```

---

## Task 3: 素材差异与静默热更

**Files:**
- Modify: `pet/updater.py`
- Test: `tests/test_asset_sync.py`

**Interfaces:**
```python
# 追加到 pet/updater.py
def safe_relpath(rel: str) -> Path | None
    # 拒绝绝对路径、盘符、".." 段；合法则返回 Path("a/b.gif")

def asset_diff(remote_files: dict[str, str], local_dir: Path) -> dict[str, str]
    # 只返回「本地缺失」或「md5 不同」的条目（键仍相对 assets/），本地多出的不在结果内

def apply_asset_update(changes: dict[str, str], base: str, local_dir: Path,
                       fetch) -> list[str]
    # 逐个 fetch(base + rel) -> 校验 md5 -> 写 <目标>.tmp -> os.replace
    # 单文件失败跳过，返回成功写入的相对路径列表；绝不抛异常
```

- [ ] **Step 1: 写失败测试**

创建 `tests/test_asset_sync.py`：

```python
from pathlib import Path

from pet.download import md5_bytes
from pet.updater import apply_asset_update, asset_diff, safe_relpath

BASE = "https://raw.githubusercontent.com/zhuolk/momolulu/main/assets/"


def _write(root: Path, rel: str, data: bytes) -> Path:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def test_safe_relpath_rejects_traversal():
    assert safe_relpath("processed/lulu_001.gif") == Path("processed/lulu_001.gif")
    assert safe_relpath("categories.json") == Path("categories.json")
    assert safe_relpath("../config.json") is None
    assert safe_relpath("processed/../../config.json") is None
    assert safe_relpath("/etc/passwd") is None
    assert safe_relpath("C:/Windows/x") is None
    assert safe_relpath("") is None


def test_asset_diff_four_cases(tmp_path):
    _write(tmp_path, "processed/lulu_001.gif", b"same")
    _write(tmp_path, "processed/lulu_002.gif", b"old")
    _write(tmp_path, "processed/lulu_009.gif", b"local-only")
    remote = {
        "processed/lulu_001.gif": md5_bytes(b"same"),    # 未变
        "processed/lulu_002.gif": md5_bytes(b"new"),      # 变更
        "processed/lulu_003.gif": md5_bytes(b"added"),    # 新增
        "../config.json": md5_bytes(b"evil"),             # 越界：忽略
    }
    assert asset_diff(remote, tmp_path) == {
        "processed/lulu_002.gif": md5_bytes(b"new"),
        "processed/lulu_003.gif": md5_bytes(b"added"),
    }


def test_asset_diff_empty_when_everything_matches(tmp_path):
    _write(tmp_path, "categories.json", b"{}")
    assert asset_diff({"categories.json": md5_bytes(b"{}")}, tmp_path) == {}


def test_apply_asset_update_writes_only_verified_files(tmp_path):
    changes = {
        "processed/lulu_002.gif": md5_bytes(b"new"),
        "processed/lulu_003.gif": md5_bytes(b"added"),
    }
    calls = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        if url.endswith("lulu_003.gif"):
            return b"corrupted"  # md5 对不上
        return b"new"

    done = apply_asset_update(changes, BASE, tmp_path, fetch)

    assert set(calls) == {BASE + "processed/lulu_002.gif", BASE + "processed/lulu_003.gif"}
    assert done == ["processed/lulu_002.gif"]
    assert (tmp_path / "processed/lulu_002.gif").read_bytes() == b"new"
    assert not (tmp_path / "processed/lulu_003.gif").exists()          # 校验失败不落盘
    assert not list(tmp_path.rglob("*.tmp"))                            # 不留临时文件


def test_apply_asset_update_keeps_old_file_when_checksum_mismatch(tmp_path):
    old = _write(tmp_path, "categories.json", b"good-old")
    done = apply_asset_update(
        {"categories.json": md5_bytes(b"brand-new")}, BASE, tmp_path, lambda url: b"tampered"
    )
    assert done == []
    assert old.read_bytes() == b"good-old"
    assert not list(tmp_path.rglob("*.tmp"))


def test_apply_asset_update_never_raises_on_fetch_error(tmp_path):
    def fetch(url: str) -> bytes:
        raise RuntimeError("boom")

    assert apply_asset_update({"a.gif": md5_bytes(b"x")}, BASE, tmp_path, fetch) == []
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_asset_sync.py -q
```

预期：`ImportError: cannot import name 'apply_asset_update'`。

- [ ] **Step 3: 实现**

追加到 `pet/updater.py`（新增 `import os`、`from pathlib import Path`、`from pet.download import UpdateError`）：

```python
def safe_relpath(rel: str) -> Path | None:
    """把 `assets/` 下的相对路径收敛成安全的 Path；越界一律 None。"""
    if not isinstance(rel, str) or not rel:
        return None
    text = rel.replace("\\", "/")
    if text.startswith("/") or ":" in text.split("/")[0]:
        return None
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return Path(*parts)


def _local_md5(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return md5_file(path)
    except OSError:
        return None


def asset_diff(remote_files: dict[str, str], local_dir: Path) -> dict[str, str]:
    """远端 md5 清单与本地实际文件的差异（只含新增与变更）。"""
    local_dir = Path(local_dir)
    changes: dict[str, str] = {}
    for rel, digest in remote_files.items():
        target = safe_relpath(rel)
        if target is None:
            continue
        if _local_md5(local_dir / target) != digest:
            changes[rel] = digest
    return changes


def apply_asset_update(changes: dict[str, str], base: str, local_dir: Path, fetch) -> list[str]:
    """把有差异的素材下下来逐个原子替换；单文件失败只跳过。"""
    local_dir = Path(local_dir)
    done: list[str] = []
    for rel, digest in changes.items():
        target = safe_relpath(rel)
        if target is None:
            continue
        dest = local_dir / target
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            data = fetch(base + rel)
            if md5_bytes(data) != digest:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            os.replace(tmp, dest)
        except Exception:  # noqa: BLE001 - 单个素材失败只跳过，绝不能拖垮整个更新
            continue
        finally:
            tmp.unlink(missing_ok=True)
        done.append(rel)
    return done
```

`asset_diff` 用到 `md5_file`、`md5_bytes`，从 `pet.download` 一并 import。

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_asset_sync.py -q
```

- [ ] **Step 5: 提交**

```powershell
git add pet/updater.py tests/test_asset_sync.py
git commit -m "feat: 素材差异计算与静默热更替换" -m "越界路径直接拒绝，md5 校验通过才原子替换，失败不留临时文件。"
```

---

## Task 4: `Sprite.release_movies()` —— 覆盖素材前释放文件句柄

**Files:**
- Modify: `pet/sprite.py`（`reload()` 在第 298 行；`_evict_movies` 在第 235 行）
- Test: `tests/test_sprite.py`

**Interfaces:**
```python
# pet/sprite.py
def release_movies(self) -> None:
    """停掉并销毁全部影片缓存，`_current_movie` 置空；不重播。"""
```

`reload()` 改为先 `release_movies()` 再按 `self._current_category` 重播，行为保持不变。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_sprite.py`：

```python
def test_release_movies_clears_cache_without_replay(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    assert s.play("idle") is True
    assert s.movie_cache_size() == 1

    replayed = []
    s.asset_missing.connect(lambda: replayed.append("missing"))
    s.release_movies()

    assert s.movie_cache_size() == 0
    assert replayed == []                    # 没有重播：不触发 asset_missing、也没有新缓存


def test_release_movies_then_reload_plays_again(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    s.play("idle")
    s.release_movies()
    s.reload()
    assert s.movie_cache_size() == 1
```

说明：`release_movies()` 后 `_current_movie is None` 由「缓存为空且未重播」共同覆盖；`release_movies()` 不重播是热更能生效的前提（先释放句柄，再覆盖文件）。

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_sprite.py -q
```

预期：`AttributeError: 'Sprite' object has no attribute 'release_movies'`。

- [ ] **Step 3: 实现**

把 [sprite.py](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/pet/sprite.py#L298-L307) 的 `reload()` 拆开：

```python
    def release_movies(self) -> None:
        """停掉并销毁全部影片缓存。

        素材热更前必须调用：`QMovie` 打开着 GIF 文件，Windows 上覆盖被占用的文件会
        `PermissionError`，不先释放的话正在播放的素材永远更新不上。
        """
        for movie in self._movies.values():
            movie.stop()
            movie.deleteLater()
        self._movies.clear()
        self._current_movie = None

    def reload(self) -> None:
        """清空影片缓存并按当前分类重新加载（缩放等渲染参数变化后调用）。"""
        category = self._current_category
        self.release_movies()
        if category is not None:
            self.play(category, once=False)
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_sprite.py -q
```

- [ ] **Step 5: 提交**

```powershell
git add pet/sprite.py tests/test_sprite.py
git commit -m "refactor: 从 reload 抽出 release_movies 以支持素材热更" -m "QMovie 持有 GIF 句柄，覆盖前必须先释放，否则 Windows 上 PermissionError。"
```

---

## Task 5: `updater.bat` 生成

**Files:**
- Modify: `pet/updater.py`
- Test: `tests/test_updater_bat.py`

**Interfaces:**
```python
# 追加到 pet/updater.py
def build_updater_bat(install_dir: Path, staged_dir: Path, backup_dir: Path,
                      exe_name: str = "momolulu.exe", retries: int = 30) -> str
    # 返回 bat 文本（CRLF 行尾）

def write_updater_bat(path: Path, text: str) -> Path
    # encoding="mbcs"（Windows 中文 ANSI 码页），保证含中文的路径能被 cmd 正确解析
```

- [ ] **Step 1: 写失败测试**

创建 `tests/test_updater_bat.py`：

```python
from pathlib import Path

from pet.updater import build_updater_bat, write_updater_bat


def _text(**over):
    args = {
        "install_dir": Path(r"C:\Users\zhang san\Desktop\momolulu"),
        "staged_dir": Path(r"C:\Users\zhang san\AppData\Local\Temp\momolulu-update\0.2.0\momolulu.new"),
        "backup_dir": Path(r"C:\Users\zhang san\Desktop\momolulu.old"),
        "exe_name": "momolulu.exe",
        "retries": 30,
    }
    args.update(over)
    return build_updater_bat(**args)


def test_bat_quotes_every_path():
    text = _text()
    assert 'set "TARGET=C:\\Users\\zhang san\\Desktop\\momolulu"' in text
    assert '"%TARGET%"' in text and '"%OLD%"' in text and '"%NEW%"' in text
    assert "momolulu.exe" in text


def test_bat_has_reorder_retry_and_rollback():
    text = _text()
    assert "move" in text and "rmdir" in text
    assert "config.json" in text                     # 从旧目录搬配置
    assert "tries" in text and "30" in text          # 重试上限来自 retries
    assert text.count(":retry") >= 1 and ":rollback" in text
    assert "\r\n" in text                            # cmd 需要 CRLF


def test_bat_uses_given_exe_name_and_retries():
    text = _text(exe_name="lulu.exe", retries=7)
    assert "lulu.exe" in text and "geq 7" in text


def test_write_updater_bat_roundtrip(tmp_path):
    out = write_updater_bat(tmp_path / "updater.bat", _text())
    assert out.exists()
    assert out.read_bytes().startswith(b"@echo off")
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_updater_bat.py -q
```

预期：`ImportError: cannot import name 'build_updater_bat'`。

- [ ] **Step 3: 实现**

追加到 `pet/updater.py`：

```python
_BAT_TEMPLATE = """@echo off
setlocal
set "TARGET={target}"
set "NEW={new}"
set "OLD={old}"
set "EXE={exe}"
set /a tries=0

rem 1. 重试把安装目录改名成备份目录：能改名成功就说明噜噜确实退干净了。
rem    （不对 PID 打转：onedir 的 exe 是 bootloader，父子进程谁持有目录句柄不确定）
:retry
rmdir /s /q "%OLD%" >nul 2>&1
move "%TARGET%" "%OLD%" >nul 2>&1
if not exist "%TARGET%" goto swapped
set /a tries+=1
if %tries% geq {retries} goto failed
ping -n 2 127.0.0.1 >nul
goto retry

rem 2. 把旧目录的 config.json 搬进新目录，保住用户的缩放 / 位置 / 模块开关
:swapped
if exist "%OLD%\\config.json" copy /y "%OLD%\\config.json" "%NEW%\\" >nul 2>&1
if exist "%TARGET%" rmdir /s /q "%TARGET%" >nul 2>&1

rem 3. 新目录顶替安装目录
move "%NEW%" "%TARGET%" >nul 2>&1
if exist "%TARGET%\\%EXE%" goto ok

rem 交换失败：把备份改回来再启动，绝不让噜噜留在跑不起来的状态
:rollback
rmdir /s /q "%TARGET%" >nul 2>&1
move "%OLD%" "%TARGET%" >nul 2>&1
start "" "%TARGET%\\%EXE%"
goto done

:ok
rem 4. 删掉备份（失败就留着，下次启动再清）
rmdir /s /q "%OLD%" >nul 2>&1
rem 5. 启动新版
start "" "%TARGET%\\%EXE%"
goto done

:failed
rem 改名一直没成功说明噜噜还活着，原目录完好，直接把它拉起来
start "" "%TARGET%\\%EXE%"

:done
endlocal
"""


def build_updater_bat(
    install_dir: Path,
    staged_dir: Path,
    backup_dir: Path,
    exe_name: str = "momolulu.exe",
    retries: int = 30,
) -> str:
    """生成目录交换脚本：等待噜噜退出 -> 搬 config.json -> 交换 -> 删备份 -> 启动新版。"""
    return _BAT_TEMPLATE.format(
        target=Path(install_dir),
        new=Path(staged_dir),
        old=Path(backup_dir),
        exe=exe_name,
        retries=int(retries),
    ).replace("\n", "\r\n")


def write_updater_bat(path: Path, text: str) -> Path:
    """用 Windows ANSI 码页写盘，含中文的安装路径才能被 cmd 正确解析。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="mbcs")
    return path
```

注意 `:rollback` 与 `:ok` 都必须能走到 `:done` 结束，不要在 `:rollback` 后掉进 `:ok`。

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_updater_bat.py -q
```

- [ ] **Step 5: 提交**

```powershell
git add pet/updater.py tests/test_updater_bat.py
git commit -m "feat: 生成 updater.bat 完成目录交换与回滚" -m "重试重命名判断进程是否退干净，config.json 从旧目录搬迁，失败回滚。"
```

---

## Task 6: 程序更新编排（下载 → 校验 → 解压 → 写 bat）

**Files:**
- Modify: `pet/updater.py`
- Test: `tests/test_program_update.py`

**Interfaces:**
```python
# 追加到 pet/updater.py
def prepare_program_update(info: dict, install_dir: Path, temp_root: Path,
                           download=None, retries: int = 30) -> Path
    # info 为 parse_latest 的返回值；download 默认 pet.download.download_file
    # 成功返回 updater.bat 的路径；任何失败抛 UpdateError，
    # 且保证安装目录未被触碰、momolulu.new 已清理、bat 未写出
```

解压布局：zip 根是 `momolulu/`，所以 `momolulu.new` 对应 `install_dir`，取 `staged_root/*/` 里唯一的那个顶层目录。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_program_update.py`：

```python
import hashlib
import zipfile
from pathlib import Path

import pytest

from pet.download import UpdateError
from pet.updater import prepare_program_update


def _make_zip(path: Path, entries: dict[str, bytes], root: str = "momolulu") -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for rel, data in entries.items():
            zf.writestr(f"{root}/{rel}", data)
    return path


def _info(zip_path: Path, *, sha256: str | None = None, size: int | None = None) -> dict:
    raw = zip_path.read_bytes()
    return {
        "version": "0.2.0",
        "notes": "",
        "package": {
            "url": "https://github.com/zhuolk/momolulu/releases/download/v0.2.0/momolulu-0.2.0.zip",
            "sha256": sha256 or hashlib.sha256(raw).hexdigest(),
            "size": size if size is not None else len(raw),
        },
        "assets": {"base": "https://raw.githubusercontent.com/x/", "files": {"categories.json": "d" * 32}},
    }


def test_prepare_program_update_stages_and_writes_bat(tmp_path):
    zip_path = _make_zip(tmp_path / "src.zip", {"momolulu.exe": b"exe", "_internal/x.txt": b"x"})
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)
    (install / "momolulu.exe").write_bytes(b"old")

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        dest.write_bytes(zip_path.read_bytes())
        return dest

    bat = prepare_program_update(
        _info(zip_path), install, tmp_path / "temp", download=download
    )

    assert bat.name == "updater.bat" and bat.exists()
    assert bat.read_bytes().startswith(b"@echo off")
    staged = tmp_path / "temp" / "momolulu.new"
    assert (staged / "momolulu.exe").read_bytes() == b"exe"
    assert (install / "momolulu.exe").read_bytes() == b"old"     # 安装目录未被触碰


def test_prepare_program_update_rejects_bad_sha256_without_extracting(tmp_path):
    zip_path = _make_zip(tmp_path / "src.zip", {"momolulu.exe": b"exe"})
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        dest.write_bytes(zip_path.read_bytes())
        return dest

    with pytest.raises(UpdateError):
        prepare_program_update(
            _info(zip_path, sha256="0" * 64), install, tmp_path / "temp", download=download
        )

    assert not (tmp_path / "temp" / "momolulu.new").exists()
    assert not (tmp_path / "temp" / "updater.bat").exists()


def test_prepare_program_update_rejects_size_mismatch(tmp_path):
    zip_path = _make_zip(tmp_path / "src.zip", {"momolulu.exe": b"exe"})
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        dest.write_bytes(zip_path.read_bytes())
        return dest

    with pytest.raises(UpdateError):
        prepare_program_update(
            _info(zip_path, size=len(zip_path.read_bytes()) + 1),
            install, tmp_path / "temp", download=download,
        )
    assert not (tmp_path / "temp" / "momolulu.new").exists()


def test_prepare_program_update_cleans_up_on_bad_zip(tmp_path):
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip at all")

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        dest.write_bytes(broken.read_bytes())
        return dest

    with pytest.raises(UpdateError):
        prepare_program_update(
            _info(broken), install, tmp_path / "temp", download=download
        )
    assert not (tmp_path / "temp" / "momolulu.new").exists()


def test_prepare_program_update_propagates_download_failure(tmp_path):
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        raise UpdateError("断网")

    info = _info(_make_zip(tmp_path / "src.zip", {"momolulu.exe": b"exe"}))
    with pytest.raises(UpdateError):
        prepare_program_update(info, install, tmp_path / "temp", download=download)
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_program_update.py -q
```

预期：`ImportError: cannot import name 'prepare_program_update'`。

- [ ] **Step 3: 实现**

追加到 `pet/updater.py`（新增 `import shutil`、`import zipfile`，`from pet.download import UpdateError, download_file, sha256_file`）：

```python
def _download_zip(info: dict, temp_root: Path, download) -> Path:
    package = info.get("package") or {}
    version = info.get("version") or "unknown"
    work = Path(temp_root) / version
    work.mkdir(parents=True, exist_ok=True)
    zip_path = work / f"momolulu-{version}.zip"
    engine = download if download is not None else download_file
    engine(package["url"], zip_path)
    if not zip_path.is_file():
        raise UpdateError("下载未产生文件")
    if zip_path.stat().st_size != package["size"]:
        raise UpdateError("整包大小与 latest.json 不符")
    if sha256_file(zip_path) != package["sha256"]:
        raise UpdateError("整包 sha256 校验失败")
    return zip_path


def _extract(zip_path: Path, staged_root: Path) -> Path:
    """解压并展平：zip 根是 `momolulu/`，处理后 `staged_root` 本身就是新的安装目录。"""
    staged_root = Path(staged_root)
    shutil.rmtree(staged_root, ignore_errors=True)
    staged_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(staged_root)
    top = list(staged_root.iterdir())
    if len(top) == 1 and top[0].is_dir():
        holder = staged_root / "_flatten"
        top[0].rename(holder)
        for child in list(holder.iterdir()):
            shutil.move(str(child), str(staged_root / child.name))
        holder.rmdir()
    if not (staged_root / "momolulu.exe").is_file():
        raise UpdateError("整包结构异常：找不到 momolulu.exe")
    return staged_root


def prepare_program_update(
    info: dict, install_dir: Path, temp_root: Path, download=None, retries: int = 30
) -> Path:
    """下载并校验整包、解压到暂存目录、写出 updater.bat；失败时不留任何中间产物。"""
    package = info.get("package")
    if not isinstance(package, dict):
        raise UpdateError("latest.json 未提供程序整包")
    install_dir = Path(install_dir).resolve()
    temp_root = Path(temp_root)
    staged_root = temp_root / "momolulu.new"

    try:
        downloaded = _download_zip(info, temp_root, download)
        staged = _extract(downloaded, staged_root)
        backup = install_dir.with_name(install_dir.name + ".old")
        text = build_updater_bat(install_dir, staged, backup, retries=retries)
        return write_updater_bat(temp_root / "updater.bat", text)
    except UpdateError:
        shutil.rmtree(staged_root, ignore_errors=True)
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        shutil.rmtree(staged_root, ignore_errors=True)
        raise UpdateError(f"准备更新失败：{exc}") from exc
```

说明：`_download_zip` 把 zip 落在 `<temp_root>/<version>/package.zip`，与 `momolulu.new` 分开，避免 `extractall` 把 zip 自己带进暂存目录。展平后 `momolulu.new` 就是新的安装目录，`updater.bat` 里 `NEW` 指向它。

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_program_update.py -q
```

- [ ] **Step 5: 提交**

```powershell
git add pet/updater.py tests/test_program_update.py
git commit -m "feat: 程序整包下载校验解压并写出更新脚本" -m "先校验大小与 sha256 再解压；任何失败都清掉暂存目录、不写 bat。"
```

---

## Task 7: `check_for_update` 总入口与检查线程

**Files:**
- Modify: `pet/updater.py`
- Create: `pet/update_runner.py`
- Test: `tests/test_update_runner.py`

**Interfaces:**
```python
# 追加到 pet/updater.py
def check_for_update(local_version: str, local_assets_dir: Path,
                     latest_url: str = LATEST_URL, fetch=fetch_bytes) -> dict | None
    # 返回 {"version": str, "notes": str, "package": dict | None,
    #        "assets_base": str, "asset_changes": dict[str, str]}
    # 远端不比本地新 -> package 置 None；素材也无差异 -> 返回 None
    # 任何异常（含 UpdateError）-> None

# pet/update_runner.py
class UpdateCheckThread(QThread):
    checked = pyqtSignal(object)      # 上面那个 dict，或 None
    def __init__(self, local_version, local_assets_dir, latest_url=LATEST_URL,
                 fetch=fetch_bytes, parent=None)

class ProgramUpdateThread(QThread):
    staged = pyqtSignal(object)       # 成功: bat 的 Path；失败: None
    def __init__(self, info, install_dir, temp_root, download=None, parent=None)
```

- [ ] **Step 1: 写失败测试**

创建 `tests/test_update_runner.py`：

```python
import json
from pathlib import Path

from pet.download import md5_bytes, UpdateError
from pet.updater import check_for_update
from pet.update_runner import UpdateCheckThread

URL = "https://raw.githubusercontent.com/zhuolk/momolulu/main/update/latest.json"
BASE = "https://raw.githubusercontent.com/zhuolk/momolulu/main/assets/"


def _payload(version: str, files: dict[str, str]) -> bytes:
    return json.dumps({
        "version": version,
        "notes": "新增两张素材",
        "package": {
            "url": "https://github.com/zhuolk/momolulu/releases/download/v0.2.0/x.zip",
            "sha256": "a" * 64,
            "size": 10,
        },
        "assets": {"base": BASE, "files": files},
    }).encode("utf-8")


def test_check_reports_new_version_and_asset_changes(tmp_path):
    (tmp_path / "categories.json").write_bytes(b"old")
    payload = _payload("0.2.0", {"categories.json": md5_bytes(b"new")})

    got = check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=lambda url: payload)

    assert got["version"] == "0.2.0"
    assert got["package"]["size"] == 10
    assert got["assets_base"] == BASE
    assert got["asset_changes"] == {"categories.json": md5_bytes(b"new")}


def test_check_drops_package_when_version_not_newer(tmp_path):
    payload = _payload("0.1.0", {"categories.json": md5_bytes(b"new")})
    got = check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=lambda url: payload)
    assert got["package"] is None           # 版本没变：只更素材，不弹窗
    assert got["asset_changes"]


def test_check_returns_none_when_nothing_to_do(tmp_path):
    (tmp_path / "categories.json").write_bytes(b"same")
    payload = _payload("0.1.0", {"categories.json": md5_bytes(b"same")})
    assert check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=lambda url: payload) is None


def test_check_is_silent_on_every_failure(tmp_path):
    def boom(url):
        raise UpdateError("断网")

    assert check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=boom) is None
    assert check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=lambda url: b"{}") is None
    assert check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=lambda url: b"oops") is None


def test_update_check_thread_emits_result(qapp, tmp_path):
    payload = _payload("0.2.0", {"categories.json": md5_bytes(b"x")})
    thread = UpdateCheckThread("0.1.0", tmp_path, latest_url=URL, fetch=lambda url: payload)
    got = []
    thread.checked.connect(got.append)

    thread.start()
    assert thread.wait(5000) is True
    for _ in range(50):
        if got:
            break
        qapp.processEvents()

    assert len(got) == 1 and got[0]["version"] == "0.2.0"
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_update_runner.py -q
```

预期：`ModuleNotFoundError: No module named 'pet.update_runner'`。

- [ ] **Step 3: 实现**

追加到 `pet/updater.py`：

```python
def check_for_update(
    local_version: str,
    local_assets_dir: Path,
    latest_url: str = LATEST_URL,
    fetch=fetch_bytes,
) -> dict | None:
    """取 latest.json、比对素材与版本，产出一份可执行的更新计划；任何问题都返回 None。"""
    try:
        parsed = parse_latest(fetch(latest_url))
    except Exception:  # noqa: BLE001 - 检查更新绝不允许影响噜噜运行
        return None
    if parsed is None:
        return None
    changes = asset_diff(parsed["assets"]["files"], Path(local_assets_dir))
    package = parsed["package"] if update_available(local_version, parsed["version"]) else None
    if package is None and not changes:
        return None
    return {
        "version": parsed["version"],
        "notes": parsed["notes"],
        "package": package,
        "assets_base": parsed["assets"]["base"],
        "asset_changes": changes,
    }
```

顶部 import 补齐：`from pet.download import UpdateError, fetch_bytes, md5_bytes, md5_file, sha256_file, download_file`。

创建 `pet/update_runner.py`：

```python
"""把同步的更新逻辑包进 QThread，保证检查与下载都不阻塞 UI。"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from pet.download import fetch_bytes
from pet.updater import LATEST_URL, check_for_update, prepare_program_update


class UpdateCheckThread(QThread):
    """启动后跑一次更新检查；结果通过 `checked` 回主线程。"""

    checked = pyqtSignal(object)

    def __init__(
        self,
        local_version: str,
        local_assets_dir: Path,
        latest_url: str = LATEST_URL,
        fetch=fetch_bytes,
        parent=None,
    ):
        super().__init__(parent)
        self._args = (local_version, Path(local_assets_dir), latest_url, fetch)

    def run(self) -> None:  # noqa: D102 - QThread
        try:
            self.checked.emit(check_for_update(*self._args))
        except Exception:  # 更新检查绝不允许拖垮主程序
            self.checked.emit(None)


class ProgramUpdateThread(QThread):
    """下载并暂存新版整包；成功发 bat 路径，失败发 None。"""

    staged = pyqtSignal(object)

    def __init__(self, info: dict, install_dir: Path, temp_root: Path, download=None, parent=None):
        super().__init__(parent)
        self._info = info
        self._install_dir = Path(install_dir)
        self._temp_root = Path(temp_root)
        self._download = download

    def run(self) -> None:  # noqa: D102 - QThread
        try:
            bat = prepare_program_update(
                self._info, self._install_dir, self._temp_root, download=self._download
            )
        except Exception:
            self.staged.emit(None)
            return
        self.staged.emit(bat)
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_update_runner.py -q
```

- [ ] **Step 5: 提交**

```powershell
git add pet/updater.py pet/update_runner.py tests/test_update_runner.py
git commit -m "feat: 更新检查总入口与后台检查线程" -m "检查与下载都在 QThread 里跑，异常一律静默降级为 None。"
```

---

## Task 8: 更新确认弹窗

**Files:**
- Create: `ui/update_prompt.py`
- Test: `tests/test_update_prompt.py`

**Interfaces:**
```python
# ui/update_prompt.py
PROMPT_WIDTH = 240
TITLE = "有新版本，要现在更新吗"
BUSY_TEXT = "正在下载…"

class UpdatePrompt(QWidget):
    accepted = pyqtSignal()          # 点「现在更新」
    declined = pyqtSignal()          # 点「稍后」

    def __init__(self, parent=None)
    def show_version(self, version: str, notes: str = "", anchor=None) -> None
        # 显示卡片，正文含版本号与 notes（notes 为空时只显示版本）
    def set_busy(self, busy: bool, text: str = BUSY_TEXT) -> None
        # busy 为真：两个按钮 disabled，状态文字显示 text
    def current_version(self) -> str
    @property
    def is_busy(self) -> bool
```

画法照 [toast.py](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/ui/toast.py) 的圆角卡片 + 投影 + `STYLES` 配色，但**不要** `Qt.WindowTransparentForInput`（否则按钮点不到）。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_update_prompt.py`：

```python
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPushButton

from ui.update_prompt import TITLE, UpdatePrompt


def buttons(prompt):
    return {b.text(): b for b in prompt.findChildren(QPushButton)}


def test_buttons_and_title(qapp):
    p = UpdatePrompt()
    assert set(buttons(p)) == {"现在更新", "稍后"}
    assert p._title.text() == TITLE


def test_prompt_is_clickable(qapp):
    p = UpdatePrompt()
    assert not (p.windowFlags() & Qt.WindowTransparentForInput)


def test_accept_and_decline_emit(qapp):
    p = UpdatePrompt()
    got = []
    p.accepted.connect(lambda: got.append("accept"))
    p.declined.connect(lambda: got.append("decline"))
    buttons(p)["现在更新"].click()
    assert got == ["accept"] and p.isVisible() is False
    p.show_version("0.2.0")
    buttons(p)["稍后"].click()
    assert got == ["accept", "decline"] and p.isVisible() is False


def test_show_version_puts_version_and_notes_in_text(qapp):
    p = UpdatePrompt()
    p.show_version("0.2.0", "新增两张素材")
    assert p.current_version() == "0.2.0"
    text = p.body_text()
    assert "0.2.0" in text and "新增两张素材" in text


def test_busy_disables_buttons_and_shows_status(qapp):
    p = UpdatePrompt()
    p.show_version("0.2.0")
    p.set_busy(True)
    assert p.is_busy is True
    assert all(not b.isEnabled() for b in buttons(p).values())
    assert "正在下载…" in p.body_text()
    p.set_busy(False, "更新失败，已保留当前版本")
    assert p.is_busy is False
    assert all(b.isEnabled() for b in buttons(p).values())
    assert "更新失败，已保留当前版本" in p.body_text()
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_update_prompt.py -q
```

预期：`ModuleNotFoundError: No module named 'ui.update_prompt'`。

- [ ] **Step 3: 实现**

创建 `ui/update_prompt.py`：

```python
"""更新确认小窗：复用 Toast 的圆角卡片画法，但可点击（不设 WindowTransparentForInput）。"""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.toast import PAD, SHADOW, STYLES, TOAST_RADIUS, _qcolor

PROMPT_WIDTH = 240
TITLE = "有新版本，要现在更新吗"
BUSY_TEXT = "正在下载…"


class UpdatePrompt(QWidget):
    """跟随噜噜的更新确认窗；点「现在更新」发 `accepted`，点「稍后」发 `declined`。"""

    accepted = pyqtSignal()
    declined = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._version = ""
        self._notes = ""
        self._status = ""
        self._busy = False

        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(PROMPT_WIDTH)

        self._title = QLabel(TITLE, self)
        font = self._title.font()
        font.setBold(True)
        self._title.setFont(font)

        self._body = QLabel("", self)
        self._body.setWordWrap(True)
        self._body.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self._later = QPushButton("稍后", self)
        self._now = QPushButton("现在更新", self)
        self._later.clicked.connect(self._decline)
        self._now.clicked.connect(self._accept)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._later)
        row.addWidget(self._now)

        column = QVBoxLayout(self)
        column.setContentsMargins(SHADOW + PAD, SHADOW + PAD, SHADOW + PAD, SHADOW + PAD)
        column.addWidget(self._title)
        column.addWidget(self._body)
        column.addLayout(row)

        self._refresh()

    # ------------------------------------------------------------ 对外接口

    @property
    def is_busy(self) -> bool:
        return self._busy

    def current_version(self) -> str:
        return self._version

    def body_text(self) -> str:
        return self._body.text()

    def show_version(self, version: str, notes: str = "", anchor=None) -> None:
        self._version = str(version)
        self._notes = str(notes or "")
        self._busy = False
        self._status = ""
        self._refresh()
        self.show()
        self.raise_()
        if anchor is not None:
            self._move_near_anchor(int(anchor[0]), int(anchor[1]))

    def set_busy(self, busy: bool, text: str = "") -> None:
        """置忙时按钮失效并显示进度；传 `text` 可同时给出结果文案（如失败原因）。"""
        self._busy = bool(busy)
        self._status = str(text) if text else (BUSY_TEXT if self._busy else "")
        self._refresh()

    # ------------------------------------------------------------ 内部实现

    def _accept(self) -> None:
        if self._busy:
            return
        self.hide()
        self.accepted.emit()

    def _decline(self) -> None:
        if self._busy:
            return
        self.hide()
        self.declined.emit()

    def _refresh(self) -> None:
        lines = [f"新版本 {self._version}"] if self._version else []
        if self._notes:
            lines.append(self._notes)
        if self._status:
            lines.append(self._status)
        self._body.setText("\n".join(lines))
        for button in (self._now, self._later):
            button.setEnabled(not self._busy)
        self._body.setStyleSheet(f"color: {STYLES['info']['text']};")
        self._title.setStyleSheet(f"color: {STYLES['info']['text']};")
        self.adjustSize()

    def _move_near_anchor(self, anchor_x: int, anchor_y: int) -> None:
        x = anchor_x - self.width() // 2
        y = anchor_y - self.height() - 8
        screen = QApplication.screenAt(QPoint(anchor_x, anchor_y))
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left(), min(x, area.right() - self.width() + 1))
            y = max(area.top(), min(y, area.bottom() - self.height() + 1))
        self.move(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        style = STYLES["info"]
        card = QRectF(SHADOW, SHADOW, self.width() - 2 * SHADOW, self.height() - 2 * SHADOW)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        for step in range(SHADOW, 0, -1):
            ratio = (SHADOW - step) / SHADOW
            alpha = int(60 * ratio * ratio / 3)
            if alpha <= 0:
                continue
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(
                card.adjusted(-step + 2, -step + 5, step, step),
                TOAST_RADIUS + step,
                TOAST_RADIUS + step,
            )
        painter.setBrush(_qcolor(style["bg"]))
        painter.drawRoundedRect(card, TOAST_RADIUS, TOAST_RADIUS)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(_qcolor(style["border"]), 1))
        painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), TOAST_RADIUS, TOAST_RADIUS)
        painter.end()
```

补齐 import：`from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal`（`QRect` 未用到就删掉）。`STATUS_INTERVAL_MS` 未使用也删掉——只保留真正用到的常量。

字段渲染固定 `STYLES["info"]`；无需 `kind` 参数（spec 只要求一个确认弹窗）。

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_update_prompt.py -q
```

- [ ] **Step 5: 提交**

```powershell
git add ui/update_prompt.py tests/test_update_prompt.py
git commit -m "feat: 新增更新确认弹窗" -m "复用 Toast 卡片画法但可点击，支持下载中置灰与失败提示。"
```

---

## Task 9: 托盘菜单「立即更新到 x.y.z」

**Files:**
- Modify: `ui/menu.py`
- Modify: `tests/test_menu.py`

**Interfaces:**
```python
# ui/menu.py
class MenuState:
    def __init__(self, visible, passthrough, autostart, modules, pomodoro_running,
                 update_version: str | None = None)
        ...
        self.update_version = update_version or None

# build_menu：当 state.update_version 非空时，在「设置…」之前插入一项
#   文案 f"立即更新到 {state.update_version}"，触发 handlers["update_now"]
```

- [ ] **Step 1: 写失败测试**

在 `tests/test_menu.py` 的 `Handlers.__init__` 里补一行：

```python
        self.update_now = lambda: self.calls.append(("update_now",))
```

追加用例：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_menu.py -q
```

预期：`TypeError: __init__() got an unexpected keyword argument 'update_version'`。

- [ ] **Step 3: 实现**

改 [menu.py](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/ui/menu.py#L25-L40)：

```python
    def __init__(
        self,
        visible: bool,
        passthrough: bool,
        autostart: bool,
        modules: dict,
        pomodoro_running: bool,
        update_version: str | None = None,
    ):
        self.visible = bool(visible)
        self.passthrough = bool(passthrough)
        self.autostart = bool(autostart)
        self.modules = dict(modules)
        self.pomodoro_running = bool(pomodoro_running)
        self.update_version = update_version or None
```

在 [build_menu](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/ui/menu.py#L114-L117) 里「设置…」之前插入：

```python
    menu.addSeparator()

    if state.update_version:
        update = menu.addAction(f"立即更新到 {state.update_version}")
        update.triggered.connect(_slot(handlers, "update_now"))
        menu.addSeparator()

    settings = menu.addAction("设置…")
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_menu.py -q
```

- [ ] **Step 5: 提交**

```powershell
git add ui/menu.py tests/test_menu.py
git commit -m "feat: 托盘菜单新增立即更新入口" -m "发现新版时在设置之前插入菜单项，点稍后也能随时手动更新。"
```

---

## Task 10: `main.py` 接线（启动检查 → 素材热更 → 弹窗 → 手动更新）

**Files:**
- Modify: `main.py`

**Interfaces:**
```python
# main.py 新增常量
_UPDATE_CHECK_DELAY_MS = 5000

# PetApp 新增成员与方法
self._update_info: dict | None = None
self._update_prompt = UpdatePrompt()
self._update_thread = None
self._program_thread = None

def _schedule_update_check(self) -> None      # 非 frozen 直接 return
def _start_update_check(self) -> None         # 起 UpdateCheckThread
def _on_update_checked(self, info) -> None    # 应用素材差异 + 决定是否弹窗
def _apply_asset_changes(self, info: dict) -> None
def _prompt_update(self, info: dict) -> None
def _dismiss_update_prompt(self) -> None
def _update_now(self) -> None                 # 菜单项与弹窗「现在更新」共用
def _on_program_staged(self, bat) -> None
```

接线点：
- `__init__` 末尾（`_init_modules()` 之后）调 `self._schedule_update_check()`
- `_menu_state()` 传 `update_version`：有 `self._update_info` 且 `package` 非空时用 `info["version"]`，否则 `None`
- `_menu_handlers()` 加 `"update_now": self._update_now`
- `shutdown()` 里 `self._update_prompt.hide()`

- [ ] **Step 1: 实现接线**

`main.py` 顶部 import 补：

```python
import subprocess
import tempfile

from pet.download import fetch_bytes
from pet.update_runner import ProgramUpdateThread, UpdateCheckThread
from pet.updater import LATEST_URL, apply_asset_update
from pet.version import VERSION
from ui.update_prompt import UpdatePrompt
```

常量区加 `_UPDATE_CHECK_DELAY_MS = 5000`、`_ASSET_TOAST = "噜噜换新衣服啦"`。

`__init__` 中 `self._init_modules()` 之后加：

```python
        self._update_info: dict | None = None
        self._update_thread = None
        self._program_thread = None
        self._update_prompt = UpdatePrompt()
        self._update_prompt.accepted.connect(self._update_now)
        self._update_prompt.declined.connect(self._dismiss_update_prompt)
        self._schedule_update_check()
```

新增方法（放在「实用模块」与「启动与位置」之间）：

```python
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
        """素材热更：先释放影片缓存（否则 GIF 被 QMovie 占着覆盖会失败），再原地换索引。"""
        self.sprite.release_movies()
        done = apply_asset_update(
            info["asset_changes"], info["assets_base"], self.root / "assets", fetch_bytes
        )
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
        self._program_thread = thread
        thread.start()

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
```

并在 `_menu_state()` 里传版本：

```python
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
```

`_menu_handlers()` 的 dict 里加 `"update_now": self._update_now,`。

`shutdown()` 在 `self.toast.hide()` 之后加：

```python
        self._update_prompt.hide()
```

- [ ] **Step 2: 静态检查**

```powershell
python -c "import main; print('ok')"
```

预期打印 `ok`（无 import 错误、无语法错误）。

- [ ] **Step 3: 跑全量回归**

```powershell
python -m pytest -q
```

预期：全部通过，且 `tests/test_menu.py`、`tests/test_sprite.py`、`tests/test_smoke.py` 无回归。

- [ ] **Step 4: 手工集成验收（对应 spec §11 的 1 / 2 / 5）**

按 spec §11 把更新源指向本地 `python -m http.server`（临时把 `LATEST_URL` 指过去，验完改回），新增一张素材、版本不变：

1. 启动噜噜，5 秒后不弹窗，`assets/processed/` 里出现新素材，弹出「噜噜换新衣服啦」
2. 把 `latest.json` 的 `version` 调高，重启噜噜 → 弹窗「有新版本，要现在更新吗」；点「稍后」→ 噜噜照常跑，右键菜单出现「立即更新到 x.y.z」
3. 断网后重启噜噜 → 没有任何提示，噜噜照常跑

- [ ] **Step 5: 提交**

```powershell
git add main.py
git commit -m "feat: 启动时检查更新并接线素材热更与更新弹窗" -m "检查与下载都在后台线程，素材静默生效，程序更新需用户确认。"
```

---

## Task 11: `build.py` 产出整包 zip 与 `latest.json`

**Files:**
- Modify: `tools_cli/build.py`
- Modify: `docs/handoff.md`
- Test: `tests/test_build_package.py`

**Interfaces:**
```python
# tools_cli/build.py
def asset_manifest(assets_dir: Path) -> dict[str, str]
    # 遍历 assets/processed/*.gif 与 assets/categories.json，键相对 assets/，值为 md5

def build_zip(app_dir: Path, out_zip: Path) -> Path
    # zip 根为 app_dir.name；必须排除 config.json

def write_latest_json(out_path: Path, version: str, notes: str, zip_path: Path,
                      repo: str = "zhuolk/momolulu") -> Path
    # url = https://github.com/<repo>/releases/download/v<version>/<zip 文件名>
    # 同时写入 sha256 与 size

def run_build(project_root, out_dir=None, name=APP_NAME) -> int
    # 末尾追加：build_zip + write_latest_json，并打印上传命令
```

`latest.json` 结构（逐字段对齐 spec §6.2）：

```json
{
  "version": "0.2.0",
  "notes": "新增两张素材，修复穿透后消失",
  "package": {"url": "...", "sha256": "...", "size": 56341000},
  "assets": {"base": "https://raw.githubusercontent.com/zhuolk/momolulu/main/assets/", "files": {}}
}
```

- [ ] **Step 1: 写失败测试**

创建 `tests/test_build_package.py`：

```python
import json
import zipfile
from pathlib import Path

from tools_cli.build import asset_manifest, build_zip, write_latest_json


def _fake_app(tmp_path: Path) -> Path:
    app = tmp_path / "dist" / "momolulu"
    (app / "_internal").mkdir(parents=True)
    (app / "momolulu.exe").write_bytes(b"exe")
    (app / "_internal" / "python310.dll").write_bytes(b"dll")
    (app / "config.json").write_text("{}", encoding="utf-8")
    return app


def test_build_zip_excludes_config_json(tmp_path):
    app = _fake_app(tmp_path)
    out = build_zip(app, tmp_path / "dist" / "momolulu-0.1.0.zip")
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert "momolulu/momolulu.exe" in names
    assert "momolulu/_internal/python310.dll" in names
    assert "momolulu/config.json" not in names


def test_asset_manifest_keys_are_relative_to_assets(tmp_path):
    (tmp_path / "processed").mkdir()
    (tmp_path / "processed" / "lulu_001.gif").write_bytes(b"gif")
    (tmp_path / "categories.json").write_text("{}", encoding="utf-8")
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "big.gif").write_bytes(b"raw-origin")

    manifest = asset_manifest(tmp_path)

    assert set(manifest) == {"processed/lulu_001.gif", "categories.json"}
    assert all(len(digest) == 32 for digest in manifest.values())


def test_write_latest_json_fields(tmp_path):
    app = _fake_app(tmp_path)
    zip_path = build_zip(app, tmp_path / "dist" / "momolulu-0.1.0.zip")
    assets = tmp_path / "assets"
    (assets / "processed").mkdir(parents=True)
    (assets / "processed" / "lulu_001.gif").write_bytes(b"gif")
    (assets / "categories.json").write_text("{}", encoding="utf-8")

    out = write_latest_json(
        tmp_path / "dist" / "latest.json", "0.1.0", "初版", zip_path, assets_dir=assets
    )
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["version"] == "0.1.0"
    assert data["notes"] == "初版"
    assert data["package"]["url"].endswith("/v0.1.0/momolulu-0.1.0.zip")
    assert data["package"]["url"].startswith("https://github.com/zhuolk/momolulu/releases/download/")
    assert data["package"]["size"] == zip_path.stat().st_size
    assert len(data["package"]["sha256"]) == 64
    assert data["assets"]["base"] == "https://raw.githubusercontent.com/zhuolk/momolulu/main/assets/"
    assert data["assets"]["files"]["processed/lulu_001.gif"]
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
python -m pytest tests/test_build_package.py -q
```

预期：`ImportError: cannot import name 'asset_manifest'`。

- [ ] **Step 3: 实现**

在 [build.py](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/tools_cli/build.py) 的 import 区补 `import zipfile`，并新增：

```python
from pet.download import md5_file, sha256_file
from pet.version import VERSION

REPO = "zhuolk/momolulu"


def _assets_base(repo: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/main/assets/"


def asset_manifest(assets_dir: Path) -> dict[str, str]:
    """运行期需要的素材清单：`processed/*.gif` 与 `categories.json`，键相对 `assets/`。"""
    assets_dir = Path(assets_dir)
    names = sorted(p.name for p in (assets_dir / "processed").glob("*.gif"))
    rels = [f"processed/{name}" for name in names]
    if (assets_dir / "categories.json").is_file():
        rels.append("categories.json")
    return {rel: md5_file(assets_dir / rel) for rel in rels}


def build_zip(app_dir: Path, out_zip: Path) -> Path:
    """把产物目录打成一个 zip（zip 根为目录名）；`config.json` 必须排除。

    它是每台机器运行期生成/修改的，`stage_assets()` 往产物里塞的是默认值，
    打进去会在整目录交换后覆盖用户的缩放 / 位置 / 模块开关。
    """
    app_dir = Path(app_dir)
    out_zip = Path(out_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(app_dir.rglob("*")):
            if not item.is_file() or item.name == "config.json":
                continue
            zf.write(item, Path(app_dir.name) / item.relative_to(app_dir))
    return out_zip


def write_latest_json(
    out_path: Path,
    version: str,
    notes: str,
    zip_path: Path,
    assets_dir: Path | None = None,
    repo: str = REPO,
) -> Path:
    """生成 `update/latest.json` 的内容；程序端读它决定要不要更新。"""
    zip_path = Path(zip_path)
    payload = {
        "version": version,
        "notes": notes,
        "package": {
            "url": f"https://github.com/{repo}/releases/download/v{version}/{zip_path.name}",
            "sha256": sha256_file(zip_path),
            "size": zip_path.stat().st_size,
        },
        "assets": {
            "base": _assets_base(repo),
            "files": asset_manifest(assets_dir) if assets_dir is not None else {},
        },
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
```

`run_build()` 末尾（`print` 产物目录之后）追加：

```python
    zip_path = build_zip(app_dir, out_dir / f"{name}-{VERSION}.zip")
    latest = write_latest_json(
        out_dir / "latest.json", VERSION, "", zip_path, assets_dir=project_root / "assets"
    )
    print(f"整包：{zip_path}（{zip_path.stat().st_size / 1e6:.1f}MB）")
    print(f"清单：{latest}")
    print("发布：")
    print(f"  1. gh release create v{VERSION} \"{zip_path}\"")
    print(f"  2. 把 {latest} 覆盖到仓库 update/latest.json 后 git push")
```

`notes` 目前由调用方填；`run_build` 里留空字符串即可（发版时手写一行说明）。

- [ ] **Step 4: 跑测试确认通过**

```powershell
python -m pytest tests/test_build_package.py -q
```

- [ ] **Step 5: 补发布步骤到 `docs/handoff.md`**

在 `docs/handoff.md` 末尾追加一节：

```markdown
## 发版（自动更新源）

1. 改 `pet/version.py` 里的 `VERSION`
2. `python tools_cli/build.py`
3. `gh release create v<version> dist/momolulu-<version>.zip`
4. 把 `dist/latest.json` 覆盖到仓库的 `update/latest.json`，`git push`
5. 素材有变动时 `assets/` 已在 git 里，push 完即生效

注意 `raw.githubusercontent.com` 有几分钟 CDN 缓存，push 完对方不一定立刻看到。
```

- [ ] **Step 6: 提交**

```powershell
git add tools_cli/build.py tests/test_build_package.py docs/handoff.md
git commit -m "feat: 打包时产出整包 zip 与 latest.json" -m "zip 排除 config.json 以免覆盖用户设置，并打印发版命令。"
```

---

## 收尾：首次发布（手工）

代码全部就位后走一次真实发布，让仓库里出现 `update/latest.json`：

- [ ] `python tools_cli/build.py`
- [ ] `gh release create v0.1.0 dist/momolulu-0.1.0.zip`
- [ ] 把 `dist/latest.json` 复制到 `update/latest.json`，提交并推送
- [ ] 在另一台机器上解压 `dist/momolulu-0.1.0.zip` 双击运行，确认无更新提示（版本已追平）
- [ ] 把 `pet/version.py` 改成 `0.2.0`、`run_build` 一次、上传 Release、覆盖 `update/latest.json` 并推送，确认老版本启动后会弹更新窗

## 备注：`latest.json` 与 Release 的对应关系

`update/latest.json` 里的 `package.url` 指向 `releases/download/v<version>/momolulu-<version>.zip`，所以**先传 Release、再覆盖 latest.json**。反过来做会让对方在几分钟内下载到 404（`UpdateError` → 静默放弃，下次启动再试，不会坏）。
