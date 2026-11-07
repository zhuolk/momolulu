"""素材整理 CLI：按清单批量设置分类与「是否可循环」，并清理悬空引用。

用法::

    python tools_cli/assign.py --template assets/assign.csv   # 生成待填清单（列出现况）
    python tools_cli/assign.py assets/assign.csv              # 按清单分类 + 打循环标
    python tools_cli/assign.py --prune                        # 清掉悬空引用（磁盘上已删的素材）

清单是带表头的 CSV，三列 `file,category,loop`::

    file,category,loop
    lulu_001.gif,idle,true
    lulu_003.gif,eat,false
    lulu_003.gif,drink,false      # 一张图想同时归两个分类就写多行

`category` 必须是已知分类；`loop` 留空表示不动这张图的循环设置。
清单里出现过的文件会**先摘出原分类再按清单归位**，所以清单就是它们的最终归属；
没出现在清单里的文件完全不受影响。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if __package__ in (None, ""):  # 允许 `python tools_cli/assign.py` 直接运行
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet.catalog import (  # noqa: E402
    CATEGORIES,
    UNASSIGNED,
    assign_file,
    forget_file,
    load_categories,
    loops_of,
    missing_files,
    save_categories,
    set_loop,
)
from tools_cli.prepare import load_index, save_index  # noqa: E402

KNOWN = CATEGORIES + (UNASSIGNED,)
_TRUE = {"true", "1", "yes", "y", "on"}
_FALSE = {"false", "0", "no", "n", "off"}


def parse_loop(text: str) -> bool | None:
    """解析清单里的 `loop` 列：留空返回 None（不改动），其余按 true / false 解析。"""
    value = (text or "").strip().lower()
    if not value:
        return None
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"无法识别的 loop 取值 {text!r}（用 true / false，留空表示不修改）")


def read_manifest(path: Path) -> list[tuple[str, str, bool | None]]:
    """读清单，返回 (文件名, 分类, 是否可循环 or None)；缺列或空文件直接报错。"""
    path = Path(path)
    with open(path, encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        fields = {(name or "").strip().lower() for name in reader.fieldnames or ()}
        if not {"file", "category"} <= fields:
            raise ValueError(
                f"清单 {path} 必须含 file 与 category 两列，实际为 {reader.fieldnames}"
            )
        rows: list[tuple[str, str, bool | None]] = []
        for line in reader:
            item = {(k or "").strip().lower(): (v or "").strip() for k, v in line.items()}
            name, category = item.get("file", ""), item.get("category", "")
            if not name and not category:
                continue  # 跳过空行
            rows.append((name, category, parse_loop(item.get("loop", ""))))
    return rows


def prune_index(index_path: Path, processed_dir: Path) -> int:
    """把素材索引里指向已删除素材的条目摘掉，返回摘除条数。"""
    index_path = Path(index_path)
    if not index_path.is_file():
        return 0
    index = load_index(index_path)
    gone = [
        digest
        for digest, entry in index["entries"].items()
        if not (processed_dir / str(entry.get("name") or "")).is_file()
    ]
    for digest in gone:
        del index["entries"][digest]
    if gone:
        save_index(index_path, index)
    return len(gone)


def write_template(path: Path, processed_dir: Path, categories_path: Path) -> int:
    """生成待填清单：把 `processed/` 里每个文件的现况铺成 CSV，返回素材个数。"""
    processed_dir, path = Path(processed_dir), Path(path)
    data = load_categories(categories_path)
    home: dict[str, list[str]] = {}
    for category, entry in (data.get("categories") or {}).items():
        for name in entry.get("files") or []:
            home.setdefault(name, []).append(category)

    files = sorted(p.name for p in processed_dir.glob("*.gif"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["file", "category", "loop"])
        for name in files:
            loop = "true" if loops_of(data, name) else "false"
            for category in home.get(name) or [UNASSIGNED]:
                writer.writerow([name, category, loop])
    return len(files)


def run_assign(
    categories_path: Path,
    processed_dir: Path,
    *,
    manifest: Path | None = None,
    prune: bool = False,
    index_path: Path | None = None,
) -> dict:
    """按清单归位素材、打循环标，并按需清理悬空引用；返回统计报告。"""
    categories_path, processed_dir = Path(categories_path), Path(processed_dir)
    data = load_categories(categories_path)
    report = {"assigned": 0, "loops": 0, "pruned": 0, "pruned_index": 0, "skipped": []}

    if prune:
        for name in missing_files(data, processed_dir):
            forget_file(data, name)
            report["pruned"] += 1
        if index_path is not None:
            report["pruned_index"] = prune_index(index_path, processed_dir)

    if manifest is not None:
        wanted: dict[str, set[str]] = {}
        loops: dict[str, bool] = {}
        for name, category, loop in read_manifest(manifest):
            if category not in KNOWN:
                report["skipped"].append({"file": name, "error": f"未知分类 {category!r}"})
                continue
            if not (processed_dir / name).is_file():
                report["skipped"].append({"file": name, "error": "processed/ 里没有这个文件"})
                continue
            wanted.setdefault(name, set()).add(category)
            if loop is not None:
                loops[name] = loop
        for name, categories in wanted.items():
            assign_file(data, name, sorted(categories))
            report["assigned"] += 1
        for name, loop in loops.items():
            set_loop(data, name, loop)
            report["loops"] += 1

    save_categories(categories_path, data)
    return report


def _print_report(report: dict) -> None:
    print(
        f"归位 {report['assigned']} 个素材，改写循环标记 {report['loops']} 个，"
        f"清理悬空引用 {report['pruned']} 个（索引 {report['pruned_index']} 条）"
    )
    for item in report["skipped"]:
        print(f"  - 跳过 {item['file']}：{item['error']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="按清单批量设置素材分类与是否可循环，并清理悬空引用"
    )
    parser.add_argument("manifest", nargs="?", type=Path, help="清单 CSV（file,category,loop）")
    parser.add_argument("--template", type=Path, help="生成待填清单到该路径后退出")
    parser.add_argument("--prune", action="store_true", help="摘掉指向已删除素材的悬空引用")
    parser.add_argument(
        "--processed", type=Path, default=Path("assets/processed"), help="素材目录"
    )
    parser.add_argument(
        "--categories", type=Path, default=Path("assets/categories.json"), help="分类索引文件"
    )
    args = parser.parse_args(argv)

    if args.template:
        count = write_template(args.template, args.processed, args.categories)
        print(f"已生成清单模板 {args.template}（{count} 个素材），填好再跑本脚本")
        return 0
    if args.manifest is None and not args.prune:
        parser.error("要么给一份清单 CSV，要么加 --prune（--help 看用法）")

    report = run_assign(
        args.categories,
        args.processed,
        manifest=args.manifest,
        prune=args.prune,
        index_path=args.categories.parent / ".index.json",
    )
    _print_report(report)
    return 1 if report["skipped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
