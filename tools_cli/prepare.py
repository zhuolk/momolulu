"""素材准备 CLI：把 `raw/` 里的 GIF 去背/压缩到 `processed/`，并维护索引与分类。

用法::

    python tools_cli/prepare.py                       # 增量处理
    python tools_cli/prepare.py --rebuild             # 清空输出后全量重建
    python tools_cli/prepare.py --sample 20 --tol 48  # 抽样试跑、放宽容差
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

if __package__ in (None, ""):  # 允许 `python tools_cli/prepare.py` 直接运行
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet.catalog import add_unassigned, load_categories, save_categories  # noqa: E402
from tools_cli.gif_pipeline import (  # noqa: E402
    COLORS,
    EDGE_MIN,
    MAX_BYTES,
    MAX_FPS,
    MAX_SIDE,
    TOL,
    process_gif,
)

INDEX_VERSION = 1
_NAME_RE = re.compile(r"^lulu_(\d+)\.gif$", re.IGNORECASE)
_REPORT_NAME = "prepare_report.json"


def md5_of(path: Path) -> str:
    """分块计算文件 MD5，用于内容级去重。"""
    digest = hashlib.md5()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_index(path: Path) -> dict:
    """读取素材索引；文件缺失、损坏或结构不符时返回空索引。"""
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError, TypeError):
        return {"version": INDEX_VERSION, "entries": {}}
    if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
        return {"version": INDEX_VERSION, "entries": {}}
    return {"version": INDEX_VERSION, "entries": data["entries"]}


def save_index(path: Path, index: dict) -> None:
    """原子写入素材索引。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(index, fp, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def next_index_number(processed_dir: Path) -> int:
    """下一个可用编号 = 现有 `lulu_NNN.gif` 的最大编号 + 1。"""
    numbers = [
        int(match.group(1))
        for match in (_NAME_RE.match(p.name) for p in Path(processed_dir).glob("*.gif"))
        if match
    ]
    return max(numbers) + 1 if numbers else 1


def _process_one(task: tuple[str, str, dict]) -> dict:
    """子进程入口：处理单个 GIF，失败时把错误信息作为结果返回。"""
    src, dst, options = task
    try:
        report = process_gif(Path(src), Path(dst), **options)
    except Exception as exc:  # 单个坏文件不应中断整批
        return {"src": Path(src).name, "error": f"{type(exc).__name__}: {exc}"}
    report["src"] = Path(src).name
    return report


def _print_summary(report: dict, processed_dir: Path) -> None:
    before = report["total_bytes_before"] / 1e6
    after = report["total_bytes_after"] / 1e6
    print(
        f"处理完成：成功 {report['processed']}，跳过重复 {report['skipped_duplicate']}，"
        f"失败 {len(report['failed'])}"
    )
    print(f"轨道分布：透明 {report['easy']}，卡片 {report['card']}")
    print(f"体积：{before:.1f}MB → {after:.1f}MB，输出目录 {processed_dir}")
    if report["failed"]:
        print("失败明细（最多 10 条）：")
        for item in report["failed"][:10]:
            print(f"  - {item['file']}: {item['error']}")
    if report["largest"]:
        print("最大输出文件（最多 5 条）：")
        for name, size in report["largest"][:5]:
            print(f"  - {name}: {size / 1024:.0f}KB")


def run_prepare(
    raw_dir: Path,
    processed_dir: Path,
    categories_path: Path,
    index_path: Path,
    *,
    rebuild: bool = False,
    tol: int = TOL,
    edge_min: float = EDGE_MIN,
    max_side: int = MAX_SIDE,
    max_fps: int = MAX_FPS,
    colors: int = COLORS,
    max_bytes: int = MAX_BYTES,
    sample: int | None = None,
    workers: int = 4,
) -> dict:
    """处理 raw 目录下的 GIF 并把结果登记到分类索引；返回统计报告。"""
    raw_dir = Path(raw_dir)
    processed_dir = Path(processed_dir)
    categories_path = Path(categories_path)
    index_path = Path(index_path)
    processed_dir.mkdir(parents=True, exist_ok=True)

    if rebuild:
        for stale in processed_dir.glob("*.gif"):
            stale.unlink()

    index = (
        {"version": INDEX_VERSION, "entries": {}} if rebuild else load_index(index_path)
    )
    categories = load_categories(categories_path)
    if rebuild:
        unassigned = categories["categories"].setdefault(
            "unassigned", {"files": [], "track": "auto"}
        )
        unassigned["files"] = []
        unassigned["track"] = "auto"

    sources = sorted(raw_dir.glob("*.gif"))
    if sample:
        sources = sources[:sample]

    report = {
        "processed": 0,
        "skipped_duplicate": 0,
        "failed": [],
        "easy": 0,
        "card": 0,
        "total_bytes_before": 0,
        "total_bytes_after": 0,
        "largest": [],
    }

    seen = set(index["entries"])
    counter = next_index_number(processed_dir)
    options = {
        "tol": tol,
        "edge_min": edge_min,
        "max_side": max_side,
        "max_fps": max_fps,
        "colors": colors,
        "max_bytes": max_bytes,
    }
    tasks: list[tuple[str, str, dict]] = []
    pending: list[tuple[str, str, str, Path]] = []  # (源名, 目标名, md5, 目标路径)
    for src in sources:
        digest = md5_of(src)
        if digest in seen:
            report["skipped_duplicate"] += 1
            continue
        seen.add(digest)
        dst = processed_dir / f"lulu_{counter:03d}.gif"
        counter += 1
        tasks.append((str(src), str(dst), options))
        pending.append((src.name, dst.name, digest, dst))

    if workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_process_one, tasks))
    else:
        results = [_process_one(task) for task in tasks]

    largest: list[tuple[str, int]] = []
    names: list[str] = []
    tracks: dict[str, str] = {}
    for (src_name, dst_name, digest, dst), result in zip(pending, results):
        if "error" in result:
            if dst.exists():
                dst.unlink()
            report["failed"].append({"file": src_name, "error": result["error"]})
            continue
        report["processed"] += 1
        report["easy" if result["track"] == "transparent" else "card"] += 1
        report["total_bytes_before"] += result["src_bytes"]
        report["total_bytes_after"] += result["dst_bytes"]
        largest.append((dst_name, result["dst_bytes"]))
        index["entries"][digest] = {"name": dst_name, "track": result["track"]}
        names.append(dst_name)
        tracks[dst_name] = result["track"]

    report["largest"] = sorted(largest, key=lambda item: item[1], reverse=True)[:10]

    if names:
        add_unassigned(categories, names, tracks)
        save_categories(categories_path, categories)
    save_index(index_path, index)

    with open(processed_dir.parent / _REPORT_NAME, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    _print_summary(report, processed_dir)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 raw 目录下的 GIF 处理到 processed 目录并维护索引与分类"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--rebuild", action="store_true", help="清空输出目录并全量重建")
    group.add_argument("--incremental", action="store_true", help="增量处理（默认）")
    parser.add_argument("--raw", type=Path, default=Path("assets/raw"), help="原始素材目录")
    parser.add_argument("--out", type=Path, default=Path("assets/processed"), help="输出目录")
    parser.add_argument(
        "--categories", type=Path, default=Path("assets/categories.json"), help="分类索引文件"
    )
    parser.add_argument("--sample", type=int, default=None, help="只处理前 N 个文件")
    parser.add_argument("--tol", type=int, default=TOL, help="背景色容差")
    parser.add_argument("--edge-min", type=float, default=EDGE_MIN, help="边界清除比例阈值")
    parser.add_argument("--max-side", type=int, default=MAX_SIDE, help="输出长边像素上限")
    parser.add_argument("--fps", type=int, default=MAX_FPS, help="输出帧率上限")
    parser.add_argument("--colors", type=int, default=COLORS, help="调色板颜色数")
    parser.add_argument("--max-kb", type=int, default=MAX_BYTES // 1024, help="单文件体积上限（KB）")
    parser.add_argument("--workers", type=int, default=4, help="并行进程数")
    args = parser.parse_args(argv)

    report = run_prepare(
        args.raw,
        args.out,
        args.categories,
        args.categories.parent / ".index.json",
        rebuild=args.rebuild,
        tol=args.tol,
        edge_min=args.edge_min,
        max_side=args.max_side,
        max_fps=args.fps,
        colors=args.colors,
        max_bytes=args.max_kb * 1024,
        sample=args.sample,
        workers=args.workers,
    )
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
