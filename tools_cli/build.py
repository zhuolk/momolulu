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
import zipfile
from pathlib import Path

if __package__ in (None, ""):  # 允许 `python tools_cli/build.py` 直接运行
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet.config import DEFAULTS  # noqa: E402
from pet.download import md5_file, sha256_file  # noqa: E402
from pet.version import VERSION  # noqa: E402

APP_NAME = "momolulu"
ENTRY = "main.py"
REPO = "zhuolk/momolulu"

# 开发期文件：`prepare.py` / `contact_sheet.py` 的产物，运行期一个都不读，不外发。
_DEV_ONLY = (".index.json", "id_map.csv", "prepare_report.json", "contact_sheet_*.png")


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

    只带运行期需要的文件：`assets/raw/` 是素材采集原件，`_DEV_ONLY` 是准备/校对
    脚本的产物，两者运行期都不读，跳过以免产物白白变大。
    """
    app_dir = Path(dist_dir) / name
    source = Path(project_root) / "assets"
    if source.is_dir():
        shutil.copytree(
            source,
            app_dir / "assets",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("raw", *_DEV_ONLY),
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


def _assets_base(repo: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/main/assets/"


def asset_manifest(assets_dir: Path) -> dict[str, str]:
    """运行期需要的素材清单：`processed/*.gif` 与 `categories.json`，键相对 `assets/`。"""
    assets_dir = Path(assets_dir)
    names = sorted(p.name for p in (assets_dir / "processed").glob("*.gif"))
    rels = [f"processed/{name}" for name in names]
    if (assets_dir / "categories.json").is_file():
        rels.append("categories.json")
    return {rel: md5_file(assets_dir / rel) for rel in rels}


def build_zip(app_dir: Path, out_zip: Path) -> Path:
    """把产物目录打成一个 zip（zip 根为目录名）；`config.json` 必须排除。

    它是每台机器运行期生成/修改的，`stage_assets()` 往产物里塞的是默认值，
    打进去会在整目录交换后覆盖用户的缩放 / 位置 / 模块开关。
    """
    app_dir = Path(app_dir)
    out_zip = Path(out_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(app_dir.rglob("*")):
            if not item.is_file() or item.name == "config.json":
                continue
            zf.write(item, Path(app_dir.name) / item.relative_to(app_dir))
    return out_zip


def write_latest_json(
    out_path: Path,
    version: str,
    notes: str,
    zip_path: Path,
    assets_dir: Path | None = None,
    repo: str = REPO,
) -> Path:
    """生成 `update/latest.json` 的内容；程序端读它决定要不要更新。"""
    zip_path = Path(zip_path)
    payload = {
        "version": version,
        "notes": notes,
        "package": {
            "url": f"https://github.com/{repo}/releases/download/v{version}/{zip_path.name}",
            "sha256": sha256_file(zip_path),
            "size": zip_path.stat().st_size,
        },
        "assets": {
            "base": _assets_base(repo),
            "files": asset_manifest(assets_dir) if assets_dir is not None else {},
        },
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


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
    zip_path = build_zip(app_dir, out_dir / f"{name}-{VERSION}.zip")
    latest = write_latest_json(
        out_dir / "latest.json", VERSION, "", zip_path, assets_dir=project_root / "assets"
    )
    print(f"整包：{zip_path}（{zip_path.stat().st_size / 1e6:.1f}MB）")
    print(f"清单：{latest}")
    print("发布：")
    print(f"  1. gh release create v{VERSION} \"{zip_path}\"")
    print(f"  2. 把 {latest} 覆盖到仓库 update/latest.json 后 git push")
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
