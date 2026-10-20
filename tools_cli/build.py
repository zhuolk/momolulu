"""打包 CLI：用 PyInstaller 把桌宠打成 onedir 可执行程序，并把素材外置到产物目录。

素材（`assets/`）与 `config.json` 不打进 exe，而是随产物目录平级存放，
这样换素材只需替换 `assets/`，无需重新打包。

用法::

    python tools_cli/build.py                 # 输出到 <root>/dist/
    python tools_cli/build.py --out D:/dist   # 自定义输出目录
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):  # 允许 `python tools_cli/build.py` 直接运行
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet.config import DEFAULTS  # noqa: E402

APP_NAME = "momolulu"
ENTRY = "main.py"


def build_args(project_root: Path, out_dir: Path, name: str = APP_NAME) -> list[str]:
    """拼出 PyInstaller 命令行参数；不传任何 `--add-data`（素材外置）。"""
    project_root = Path(project_root)
    out_dir = Path(out_dir)
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onedir",
        "--noconfirm",  # 重复打包时直接覆盖旧产物，不交互提问
        "--name",
        name,
        "--distpath",
        str(out_dir),
        "--workpath",
        str(out_dir / "_build"),
        "--specpath",
        str(out_dir),
        str(project_root / ENTRY),
    ]


def stage_assets(project_root: Path, dist_dir: Path, name: str = APP_NAME) -> None:
    """把 `assets/` 与默认 `config.json` 复制到产物目录（已存在的配置不覆盖）。

    `assets/raw/` 是素材采集原件、运行期不需要，跳过以免产物白白翻倍。
    """
    app_dir = Path(dist_dir) / name
    source = Path(project_root) / "assets"
    if source.is_dir():
        shutil.copytree(
            source,
            app_dir / "assets",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("raw"),
        )
    config_path = app_dir / "config.json"
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(DEFAULTS, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _dir_size_mb(path: Path) -> float:
    total = sum(item.stat().st_size for item in Path(path).rglob("*") if item.is_file())
    return total / 1e6


def run_build(
    project_root: Path, out_dir: Path | None = None, name: str = APP_NAME
) -> int:
    """执行打包并外置素材；返回进程退出码（0 成功，1 失败）。"""
    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print("缺少 PyInstaller，请先执行：python -m pip install pyinstaller")
        return 1

    project_root = Path(project_root)
    out_dir = Path(out_dir) if out_dir is not None else project_root / "dist"
    args = build_args(project_root, out_dir, name)
    print("执行：" + " ".join(args))
    PyInstaller.__main__.run(args[3:])
    stage_assets(project_root, out_dir, name)
    app_dir = out_dir / name
    print(f"产物目录：{app_dir}（{_dir_size_mb(app_dir):.1f}MB）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="打包桌宠并把素材外置到产物目录")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="源码根目录（含 main.py）",
    )
    parser.add_argument("--out", type=Path, default=None, help="输出目录（默认 <root>/dist）")
    args = parser.parse_args(argv)
    return run_build(args.root, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
