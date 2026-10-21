import json
import threading
from pathlib import Path

from pet.download import md5_bytes, UpdateError
from pet.updater import check_for_update
from pet.update_runner import AssetUpdateThread, UpdateCheckThread

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


def test_check_is_silent_on_non_update_error(tmp_path):
    # check_for_update 用 `except Exception` 兜底：非 UpdateError 的意外异常也必须静默降级。
    # 这里刻意用与 UpdateError 无继承关系的具体异常，收窄成 `except UpdateError` 时会立刻暴露。
    def boom_runtime(url):
        raise RuntimeError("意外异常，且不是 UpdateError")

    assert check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=boom_runtime) is None

    def boom_value(url):
        raise ValueError("同样不是 UpdateError")

    assert check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=boom_value) is None

    def boom_type(url):
        raise TypeError("也不是 UpdateError")

    assert check_for_update("0.1.0", tmp_path, latest_url=URL, fetch=boom_type) is None


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


def test_update_check_thread_passes_latest_url_through(qapp, tmp_path):
    other_url = "https://raw.githubusercontent.com/zhuolk/momolulu/main/update/other.json"
    payload = _payload("0.2.0", {"categories.json": md5_bytes(b"x")})
    seen = []

    def fetch(url):
        seen.append(url)
        return payload

    thread = UpdateCheckThread("0.1.0", tmp_path, latest_url=other_url, fetch=fetch)
    got = []
    thread.checked.connect(got.append)

    thread.start()
    assert thread.wait(5000) is True
    for _ in range(50):
        if got:
            break
        qapp.processEvents()

    assert seen == [other_url]
    assert len(got) == 1 and got[0]["version"] == "0.2.0"


def test_asset_update_thread_writes_files_and_emits_paths(qapp, tmp_path):
    changes = {"processed/lulu_002.gif": md5_bytes(b"new")}
    thread = AssetUpdateThread(changes, BASE, tmp_path, fetch=lambda url: b"new")
    got = []
    thread.done.connect(got.append)

    thread.start()
    assert thread.wait(5000) is True
    for _ in range(50):
        if got:
            break
        qapp.processEvents()

    assert got == [["processed/lulu_002.gif"]]
    assert (tmp_path / "processed" / "lulu_002.gif").read_bytes() == b"new"
    assert not list(tmp_path.rglob("*.tmp"))


def test_asset_update_thread_emits_empty_on_fetch_failure(qapp, tmp_path):
    changes = {"processed/lulu_002.gif": md5_bytes(b"new")}

    def boom_update_error(url):
        raise UpdateError("断网")

    def boom_runtime(url):
        raise RuntimeError("意外")

    for fetch in (boom_update_error, boom_runtime):
        thread = AssetUpdateThread(changes, BASE, tmp_path, fetch=fetch)
        got = []
        thread.done.connect(got.append)

        thread.start()
        assert thread.wait(5000) is True
        for _ in range(50):
            if got:
                break
            qapp.processEvents()

        assert got == [[]]
        assert not list(tmp_path.rglob("*.tmp"))


def test_asset_update_thread_runs_off_main_thread(qapp, tmp_path):
    # I-1 的正牌守卫：下载必须真的跑在非主线程，否则界面会被网络卡顿冻住。
    main_ident = threading.get_ident()
    changes = {"processed/lulu_002.gif": md5_bytes(b"new")}
    seen = []

    def fetch(url):
        seen.append(threading.get_ident())
        return b"new"

    thread = AssetUpdateThread(changes, BASE, tmp_path, fetch=fetch)
    got = []
    thread.done.connect(got.append)

    thread.start()
    assert thread.wait(5000) is True
    for _ in range(50):
        if got:
            break
        qapp.processEvents()

    assert seen and all(ident != main_ident for ident in seen)


def test_asset_update_thread_is_silent_when_diff_raises(qapp, tmp_path, monkeypatch):
    # 线程用 `except Exception` 兜底：非 UpdateError 的意外异常也必须静默降级、不发崩溃。
    # 收窄成 `except UpdateError` 时本用例会立刻变红。
    def boom(*args, **kwargs):
        raise RuntimeError("意外异常，且不是 UpdateError")

    monkeypatch.setattr("pet.update_runner.apply_asset_update", boom)
    thread = AssetUpdateThread({"processed/x.gif": "0" * 32}, BASE, tmp_path)
    got = []
    thread.done.connect(got.append)

    thread.start()
    assert thread.wait(5000) is True
    for _ in range(50):
        if got:
            break
        qapp.processEvents()

    assert got == [[]]
