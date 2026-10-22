import hashlib
from pathlib import Path

import pytest

from pet.download import (
    UpdateError,
    check_redirect,
    download_file,
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
        self.urls.append(getattr(url, "full_url", url))
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


class ChunkedResponse:
    """按块产出字节，模拟 download_file 的流式 read(size)。"""

    def __init__(self, chunks: list[bytes], headers: dict | None = None):
        self._chunks = list(chunks)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ChunkedOpener:
    def __init__(self, chunks: list[bytes], headers: dict | None = None):
        self.chunks = chunks
        self.headers = headers or {}
        self.urls = []

    def open(self, url, timeout=None):
        self.urls.append(getattr(url, "full_url", url))
        return ChunkedResponse(self.chunks, self.headers)


def test_download_file_writes_all_bytes_and_returns_path(tmp_path):
    opener = ChunkedOpener([b"aa", b"bb", b"cc"])
    dest = tmp_path / "pkg.zip"
    result = download_file("https://github.com/x", dest, opener=opener)
    assert isinstance(dest, Path)
    assert result == dest
    assert dest.read_bytes() == b"aa" + b"bb" + b"cc"


def test_download_file_removes_dest_and_leaves_no_residue_on_failure(tmp_path):
    class Boom:
        def open(self, url, timeout=None):
            raise OSError("断网了")

    dest = tmp_path / "pkg.zip"
    dest.write_bytes(b"stale")
    with pytest.raises(UpdateError):
        download_file("https://github.com/x", dest, opener=Boom())
    assert list(tmp_path.iterdir()) == []


def test_download_file_rejects_non_whitelisted_url_without_touching_network(tmp_path):
    opener = ChunkedOpener([b"nope"])
    with pytest.raises(UpdateError):
        download_file("http://raw.githubusercontent.com/x", tmp_path / "pkg.zip", opener=opener)
    assert opener.urls == []


def test_download_file_reports_progress_with_total(tmp_path):
    opener = ChunkedOpener([b"aa", b"bb", b"cc"], headers={"Content-Length": "6"})
    seen = []

    download_file(
        "https://github.com/x",
        tmp_path / "pkg.zip",
        opener=opener,
        progress=lambda done, total: seen.append((done, total)),
    )

    assert seen == [(2, 6), (4, 6), (6, 6)]


def test_download_file_progress_total_is_zero_without_content_length(tmp_path):
    # 拿不到 Content-Length（分块传输、代理改写）时必须传 0 表示总量未知，不能瞎猜。
    for headers in ({}, {"Content-Length": ""}, {"Content-Length": "abc"}, {"Content-Length": "-1"}):
        opener = ChunkedOpener([b"aa", b"bb"], headers=headers)
        seen = []
        download_file(
            "https://github.com/x",
            tmp_path / "pkg.zip",
            opener=opener,
            progress=lambda done, total: seen.append((done, total)),
        )
        assert seen == [(2, 0), (4, 0)], headers


def test_download_file_without_progress_callback_still_works(tmp_path):
    opener = ChunkedOpener([b"aa", b"bb"], headers={"Content-Length": "4"})
    dest = download_file("https://github.com/x", tmp_path / "pkg.zip", opener=opener)
    assert dest.read_bytes() == b"aabb"
