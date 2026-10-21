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
