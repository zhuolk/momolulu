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
