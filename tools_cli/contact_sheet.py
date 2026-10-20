"""生成缩略图接触表：把 `processed/` 里的 GIF 首页排成网格 PNG，便于人工分类。

用法::

    python tools_cli/contact_sheet.py                       # 输出到 assets/
    python tools_cli/contact_sheet.py --cols 8 --cell 180   # 调整网格密度
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

BG = (245, 245, 245)
LINE = (221, 221, 221)
TEXT = (60, 60, 60)


def build_sheet(
    files: list[Path],
    out_path: Path,
    *,
    cols: int = 10,
    rows: int = 6,
    cell: int = 150,
) -> int:
    """把 files 的首页缩略图排成 cols×rows 接触表并保存，返回成功收录的文件数。"""
    canvas = Image.new("RGB", (cols * cell, rows * cell), BG)
    draw = ImageDraw.Draw(canvas)
    for i in range(1, cols):
        x = i * cell
        draw.line([(x, 0), (x, rows * cell)], fill=LINE, width=1)
    for j in range(1, rows):
        y = j * cell
        draw.line([(0, y), (cols * cell, y)], fill=LINE, width=1)

    font = ImageFont.load_default()
    box = (cell - 16, cell - 24)
    count = 0
    for path in files:
        if count >= cols * rows:
            break
        try:
            with Image.open(path) as im:
                im.seek(0)
                frame = im.convert("RGBA")
        except Exception:  # 坏文件跳过，不中断整页
            continue
        thumb = ImageOps.contain(frame, box, Image.LANCZOS)
        x0 = (count % cols) * cell
        y0 = (count // cols) * cell
        canvas.paste(thumb, (x0 + (cell - thumb.width) // 2, y0 + 8), thumb)
        draw.text((x0 + 6, y0 + cell - 14), path.name, fill=TEXT, font=font)
        count += 1

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return count


def build_all(
    processed_dir: Path,
    out_dir: Path,
    *,
    cols: int = 10,
    rows: int = 6,
    cell: int = 150,
) -> list[Path]:
    """按文件名排序后每页 cols*rows 张（默认 60），生成 `contact_sheet_NN.png`。"""
    files = sorted(Path(processed_dir).glob("*.gif"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_page = max(1, cols * rows)
    pages: list[Path] = []
    for index in range(0, len(files), per_page):
        page = out_dir / f"contact_sheet_{index // per_page + 1:02d}.png"
        build_sheet(files[index : index + per_page], page, cols=cols, rows=rows, cell=cell)
        pages.append(page)
    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 processed 目录下的 GIF 排成缩略图接触表")
    parser.add_argument("--processed", type=Path, default=Path("assets/processed"), help="素材目录")
    parser.add_argument("--out", type=Path, default=Path("assets"), help="接触表输出目录")
    parser.add_argument("--cols", type=int, default=10, help="每行格数")
    parser.add_argument("--rows", type=int, default=6, help="每页行数")
    parser.add_argument("--cell", type=int, default=150, help="单格像素边长")
    args = parser.parse_args(argv)

    pages = build_all(args.processed, args.out, cols=args.cols, rows=args.rows, cell=args.cell)
    print(f"生成接触表 {len(pages)} 页，输出目录 {args.out}")
    for page in pages:
        print(f"  - {page.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
