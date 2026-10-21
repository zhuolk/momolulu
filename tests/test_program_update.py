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


def test_prepare_program_update_rejects_temp_root_inside_install(tmp_path):
    # 加固 A：bat 落点必须在安装目录之外，否则 bat 执行目录交换时会搬走自己。
    zip_path = _make_zip(tmp_path / "src.zip", {"momolulu.exe": b"exe"})
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        dest.write_bytes(zip_path.read_bytes())
        return dest

    inside = install / "tmp"
    with pytest.raises(UpdateError):
        prepare_program_update(_info(zip_path), install, inside, download=download)

    assert not (inside / "momolulu.new").exists()
    assert not (inside / "updater.bat").exists()


def test_prepare_program_update_wraps_bat_encode_error(tmp_path, monkeypatch):
    # 加固 B：write_updater_bat 的 mbcs 编码异常必须被包成 UpdateError，且清掉暂存目录。
    zip_path = _make_zip(tmp_path / "src.zip", {"momolulu.exe": b"exe"})
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        dest.write_bytes(zip_path.read_bytes())
        return dest

    def boom(path, text):
        raise UnicodeEncodeError("mbcs", "噜", 0, 1, "illegal multibyte sequence")

    monkeypatch.setattr("pet.updater.write_updater_bat", boom)

    with pytest.raises(UpdateError):
        prepare_program_update(_info(zip_path), install, tmp_path / "temp", download=download)
    assert not (tmp_path / "temp" / "momolulu.new").exists()


def test_prepare_program_update_removes_version_work_dir_on_failure(tmp_path):
    # 加固 C：失败时 <temp_root>/<version> 工作目录（含下载残留的 zip）也要清掉。
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
    assert not (tmp_path / "temp" / "0.2.0").exists()


def test_prepare_program_update_rejects_empty_package(tmp_path):
    # package 缺字段时必须按公开契约抛 UpdateError，不能漏出 KeyError。
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)
    (install / "momolulu.exe").write_bytes(b"old")

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        dest.write_bytes(b"payload")
        return dest

    info = {"version": "0.2.0", "notes": "", "package": {}, "assets": {}}
    with pytest.raises(UpdateError):
        prepare_program_update(info, install, tmp_path / "temp", download=download)

    assert (install / "momolulu.exe").read_bytes() == b"old"          # 安装目录未被触碰
    assert not (tmp_path / "temp" / "momolulu.new").exists()
    assert not (tmp_path / "temp" / "updater.bat").exists()


def test_prepare_program_update_rejects_package_with_null_url(tmp_path):
    # package.url 为 None（其余键缺失）同样必须抛 UpdateError。
    install = tmp_path / "app" / "momolulu"
    install.mkdir(parents=True)
    (install / "momolulu.exe").write_bytes(b"old")

    def download(url: str, dest: Path, timeout: float = 5.0) -> Path:
        dest.write_bytes(b"payload")
        return dest

    info = {"version": "0.2.0", "notes": "", "package": {"url": None}, "assets": {}}
    with pytest.raises(UpdateError):
        prepare_program_update(info, install, tmp_path / "temp", download=download)

    assert (install / "momolulu.exe").read_bytes() == b"old"          # 安装目录未被触碰
    assert not (tmp_path / "temp" / "momolulu.new").exists()
    assert not (tmp_path / "temp" / "updater.bat").exists()

