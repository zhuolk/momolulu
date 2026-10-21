import json
import zipfile
from pathlib import Path

from tools_cli.build import asset_manifest, build_zip, stage_assets, write_latest_json


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


def test_stage_assets_skips_raw_and_dev_only_files(tmp_path):
    root = tmp_path / "proj"
    assets = root / "assets"
    (assets / "processed").mkdir(parents=True)
    (assets / "processed" / "lulu_001.gif").write_bytes(b"gif")
    (assets / "categories.json").write_text("{}", encoding="utf-8")
    (assets / "raw").mkdir()
    (assets / "raw" / "origin.gif").write_bytes(b"raw-origin")
    for name in (".index.json", "id_map.csv", "prepare_report.json", "contact_sheet_01.png"):
        (assets / name).write_bytes(b"dev")

    stage_assets(root, tmp_path / "dist")

    staged = tmp_path / "dist" / "momolulu" / "assets"
    got = sorted(p.relative_to(staged).as_posix() for p in staged.rglob("*") if p.is_file())
    assert got == ["categories.json", "processed/lulu_001.gif"]


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
