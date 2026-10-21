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
