from pathlib import Path
from tools_cli.build import build_args


def test_build_args_uses_onedir_noconsole_and_entry(tmp_path):
    args = build_args(tmp_path, tmp_path / "dist")
    assert "--noconsole" in args and "--onedir" in args
    assert "--onefile" not in args
    assert args[args.index("--name") + 1] == "momolulu"
    assert str(tmp_path / "main.py") in args


def test_build_args_does_not_bundle_assets(tmp_path):
    """素材外置：不把 assets 打进 exe（不传 --add-data / --add-binary）。"""
    args = build_args(tmp_path, tmp_path / "dist")
    assert "--add-data" not in args
    assert "--add-binary" not in args
    assert not any(Path(a).name == "assets" for a in args)


def test_build_args_uses_out_dir(tmp_path):
    out = tmp_path / "dist"
    args = build_args(tmp_path, out)
    assert args[args.index("--distpath") + 1] == str(out)
