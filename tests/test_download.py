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
