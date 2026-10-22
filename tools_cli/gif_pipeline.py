"""GIF 去背、分级、压缩与批处理流水线（无 Qt 依赖）。

去背流程：四角/四边中位数采样背景色 → 从边界对近背景色像素做 4 连通 flood fill
→ 清空连通区域 → 对清空掩膜向内收缩 1px（消除 GIF 1-bit 透明的白边）。
"""

from __future__ import annotations

import collections
from pathlib import Path

from PIL import Image

TOL = 32
EDGE_MIN = 0.70
MAX_BYTES = 300 * 1024
# 200px：桌宠实际显示 120–200px（spec §5.1），200px 正好等于显示上限，不损失清晰度；
# 本批素材为 255 色、逐帧整帧变化的高熵视频截图，实测 240/12fps/128 色单文件仍可达
# 0.6~1.7MB，故取「平衡档」200px/10fps/96 色。
MAX_SIDE = 200
MAX_FPS = 10
COLORS = 96
COLOR_FALLBACKS = (64, 32, 16)
_DEFAULT_FRAME_MS = 40

_BLOCK = 5
# 掩膜取值只有 0（保留）和 1（清除）：translate 成 alpha，1 → 0、0 → 255
_ALPHA_TABLE = bytes.maketrans(b"\x00\x01", b"\xff\x00")
_NEIGHBORS = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def _median(values: list[int]) -> int:
    values.sort()
    n = len(values)
    if n % 2:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) // 2


def _block_median(im: Image.Image, x0: int, y0: int, size: int = _BLOCK) -> tuple[int, int, int]:
    """以 (x0, y0) 为左上角取最长 size×size 的块，逐通道取中位数（自动裁剪进图内）。"""
    w, h = im.size
    x0 = max(0, min(x0, w - 1))
    y0 = max(0, min(y0, h - 1))
    x1 = max(min(x0 + size, w), x0 + 1)
    y1 = max(min(y0 + size, h), y0 + 1)
    px = im.load()
    rs: list[int] = []
    gs: list[int] = []
    bs: list[int] = []
    for x in range(x0, x1):
        for y in range(y0, y1):
            r, g, b = px[x, y][:3]
            rs.append(r)
            gs.append(g)
            bs.append(b)
    return (_median(rs), _median(gs), _median(bs))


def _max_diff(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def _consistent(cands: list[tuple[int, int, int]], tol: int) -> bool:
    return all(_max_diff(a, b) <= tol for a in cands for b in cands)


def _mode(cands: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return collections.Counter(cands).most_common(1)[0][0]


def sample_background(im: Image.Image, tol: int = TOL) -> tuple[int, int, int] | None:
    """采样背景色；四角不一致时退化为四边中点，仍无一致候选（渐变底）返回 None。"""
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    corners = [
        _block_median(im, 0, 0),
        _block_median(im, w - _BLOCK, 0),
        _block_median(im, 0, h - _BLOCK),
        _block_median(im, w - _BLOCK, h - _BLOCK),
    ]
    if _consistent(corners, tol):
        return _mode(corners)
    mids = [
        _block_median(im, 0, (h - _BLOCK) // 2),
        _block_median(im, w - _BLOCK, (h - _BLOCK) // 2),
        _block_median(im, (w - _BLOCK) // 2, 0),
        _block_median(im, (w - _BLOCK) // 2, h - _BLOCK),
    ]
    if _consistent(mids, tol):
        return _mode(mids)
    return None


def _flood_mask(im: Image.Image, bg: tuple[int, int, int], tol: int) -> bytearray:
    """从四条边界出发的 4 连通扫描线 flood fill，返回 1 表示需清除的掩膜。"""
    w, h = im.size
    px = im.load()
    mask = bytearray(w * h)
    r0, g0, b0 = bg

    def matches(x: int, y: int) -> bool:
        r, g, b = px[x, y][:3]
        return abs(r - r0) <= tol and abs(g - g0) <= tol and abs(b - b0) <= tol

    stack: list[tuple[int, int]] = []
    for x in range(w):
        stack.append((x, 0))
        stack.append((x, h - 1))
    for y in range(h):
        stack.append((0, y))
        stack.append((w - 1, y))

    while stack:
        x, y = stack.pop()
        row = y * w
        if mask[row + x] or not matches(x, y):
            continue
        xl = x
        while xl > 0 and not mask[row + xl - 1] and matches(xl - 1, y):
            xl -= 1
        xr = x
        while xr < w - 1 and not mask[row + xr + 1] and matches(xr + 1, y):
            xr += 1
        length = xr - xl + 1
        mask[row + xl:row + xl + length] = b"\x01" * length
        for ny in (y - 1, y + 1):
            if not 0 <= ny < h:
                continue
            nrow = ny * w
            in_run = False
            for xx in range(xl, xr + 1):
                if not mask[nrow + xx] and matches(xx, ny):
                    if not in_run:
                        stack.append((xx, ny))
                        in_run = True
                else:
                    in_run = False
    return mask


def _erode_mask(mask: bytearray, w: int, h: int) -> bytearray:
    """清空掩膜向内收缩 1px：边界上的清空像素恢复为不透明（用原掩膜判定邻域）。"""
    out = bytearray(mask)
    for y in range(h):
        row = y * w
        for x in range(w):
            if not mask[row + x]:
                continue
            for dx, dy in _NEIGHBORS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and not mask[ny * w + nx]:
                    out[row + x] = 0
                    break
    return out


def remove_background(
    im: Image.Image, bg: tuple[int, int, int], tol: int = TOL, erode: int = 1
) -> Image.Image:
    """清除与边界连通的近背景色区域，输出 RGBA；erode 为清空掩膜向内收缩的像素数。"""
    rgb = im.convert("RGB")
    w, h = rgb.size
    mask = _flood_mask(rgb, bg, tol)
    for _ in range(max(0, erode)):
        mask = _erode_mask(mask, w, h)
    keep = bytes(mask.translate(_ALPHA_TABLE))
    out = im.convert("RGBA")
    if "A" in im.getbands():
        keep = bytes(map(min, out.getchannel("A").tobytes(), keep))
    out.putalpha(Image.frombytes("L", (w, h), keep))
    return out


def grade(cleaned_ratio: float, edge_ratio: float, edge_min: float = EDGE_MIN) -> str:
    """按 spec §5.1：先按整体清除比例排除极端情况，再看边界清除比例分级。"""
    if cleaned_ratio < 0.05 or cleaned_ratio > 0.75:
        return "hard"
    if edge_ratio >= edge_min:
        return "easy"
    if edge_ratio >= 0.35:
        return "medium"
    return "hard"


def analyze_frame(
    im: Image.Image, bg: tuple[int, int, int], tol: int = TOL
) -> tuple[float, float]:
    """返回 (清除像素占比, 边界被清除像素占比)。"""
    rgb = im.convert("RGB") if im.mode != "RGB" else im
    w, h = rgb.size
    mask = _flood_mask(rgb, bg, tol)
    total = w * h
    cleared = sum(mask)
    border = bytearray(w * h)
    for x in range(w):
        border[x] = 1
        border[(h - 1) * w + x] = 1
    for y in range(h):
        border[y * w] = 1
        border[y * w + w - 1] = 1
    edge_total = sum(border)
    edge_cleared = sum(1 for i in range(total) if border[i] and mask[i])
    return cleared / total, edge_cleared / edge_total


# ---------------------------------------------------------------- 压缩与批处理


def resize_frame(im: Image.Image, max_side: int = MAX_SIDE) -> Image.Image:
    """长边缩放到 max_side 以内（保持比例），短边不动。"""
    out = im.copy()
    out.thumbnail((max_side, max_side), Image.LANCZOS)
    return out


def _resample(
    frames: list[Image.Image], durations: list[int], max_fps: int
) -> tuple[list[Image.Image], list[int]]:
    """按帧时长累加抽帧，使每帧间隔 >= 1000/max_fps 毫秒（保留每组最后一帧）。"""
    min_ms = 1000.0 / max_fps
    out_frames: list[Image.Image] = []
    out_durations: list[int] = []
    acc = 0
    last: Image.Image | None = None
    for frame, duration in zip(frames, durations):
        last = frame
        acc += max(1, int(duration))
        if acc >= min_ms:
            out_frames.append(last)
            out_durations.append(int(round(acc)))
            acc = 0
    if last is not None and acc:
        if out_frames:
            out_durations[-1] += int(round(acc))  # 残余并入上一帧，保持总时长
        else:
            out_frames.append(last)
            out_durations.append(int(round(acc)))
    return out_frames, out_durations


def _to_palette_frame(frame: Image.Image, colors: int, quantum_alpha: bool) -> Image.Image:
    """转 P 模式；quantum_alpha 为真时把 alpha<128 的像素改为保留索引 colors-1。

    注意 palette 必须在合成前取出：`Image.composite` 的结果会带回被合成层的默认调色板。
    """
    rgba = frame.convert("RGBA")
    base = rgba.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=colors - 1)
    palette = (base.getpalette() or [])[: (colors - 1) * 3]
    palette += [0, 0, 0] * (colors - len(palette) // 3)
    out = base
    if quantum_alpha:
        index = colors - 1
        # mask 为 255 的像素取 base（不透明），为 0 的像素取保留索引层（透明）
        mask = rgba.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
        out = Image.composite(base, Image.new("P", base.size, index), mask)
    out.putpalette(palette)
    if quantum_alpha:
        out.info["transparency"] = colors - 1
    return out


def compress_gif(
    frames: list[Image.Image],
    durations: list[int],
    out_path: Path,
    max_fps: int = MAX_FPS,
    colors: int = COLORS,
) -> None:
    """抽帧到 max_fps 以内、量化到 colors 色并写成 GIF（保留透明通道的专用索引）。"""
    frames, durations = _resample(frames, durations, max_fps)
    has_alpha = any(f.getchannel("A").getextrema()[0] < 255 for f in frames)
    pal_frames = [_to_palette_frame(f, colors, has_alpha) for f in frames]
    kwargs = dict(
        save_all=True,
        append_images=pal_frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=False,
    )
    if has_alpha:
        kwargs["transparency"] = colors - 1
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pal_frames[0].save(out_path, **kwargs)


def _load_frames(im: Image.Image) -> tuple[list[Image.Image], list[int]]:
    frames: list[Image.Image] = []
    durations: list[int] = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        frames.append(im.convert("RGBA"))
        durations.append(int(im.info.get("duration") or _DEFAULT_FRAME_MS))
    return frames, durations


def _sample_indices(n: int, count: int = 5) -> list[int]:
    if n <= count:
        return list(range(n))
    step = (n - 1) / (count - 1)
    return sorted({int(round(i * step)) for i in range(count)})


def process_gif(
    src: Path,
    dst: Path,
    *,
    max_side: int = MAX_SIDE,
    max_fps: int = MAX_FPS,
    colors: int = COLORS,
    max_bytes: int = MAX_BYTES,
    tol: int = TOL,
    edge_min: float = EDGE_MIN,
) -> dict:
    """处理单个 GIF：缩放 → 抽帧 → 压缩 → 返回统计。

    素材一律要求**预先去背**（自带 alpha）；漏去背的素材直接抛 `ValueError`，
    既不兜底套卡片轨、也不静默出片。`tol` / `edge_min` 是去背参数，
    保留给本模块的 `remove_background` / `grade` 等去背函数使用。
    """
    src = Path(src)
    dst = Path(dst)
    im = Image.open(src)
    src_bytes = src.stat().st_size
    src_size = (im.size[0], im.size[1])
    src_frames, durations = _load_frames(im)
    first_alpha = src_frames[0].getchannel("A").getextrema()[0] < 255
    has_src_alpha = first_alpha or im.info.get("transparency") is not None
    if not has_src_alpha:
        raise ValueError(f"{src.name}：素材没有 alpha 通道（未去背），请先去背再放进 raw/")

    track, level = "transparent", "easy"
    out_frames = src_frames
    cleaned_ratio = 0.0
    edge_ratio = 0.0

    resized = [resize_frame(f, max_side) for f in out_frames]
    resample_frames, resample_durations = _resample(resized, durations, max_fps)
    if len(resample_frames) <= 1:
        fps = 0
    else:
        mean_ms = sum(resample_durations) / len(resample_durations)
        fps = int(round(1000.0 / mean_ms))

    compress_gif(resized, durations, dst, max_fps=max_fps, colors=colors)
    if dst.stat().st_size > max_bytes:
        for fallback in COLOR_FALLBACKS:
            if fallback >= colors:
                continue
            compress_gif(resized, durations, dst, max_fps=max_fps, colors=fallback)
            if dst.stat().st_size <= max_bytes:
                break

    with Image.open(dst) as out:
        dst_size = (out.size[0], out.size[1])
        dst_frames = getattr(out, "n_frames", 1)

    return {
        "file": dst.name,
        "track": track,
        "grade": level,
        "cleaned_ratio": round(cleaned_ratio, 4),
        "edge_ratio": round(edge_ratio, 4),
        "src_bytes": src_bytes,
        "dst_bytes": dst.stat().st_size,
        "src_size": src_size,
        "dst_size": dst_size,
        "frames": dst_frames,
        "fps": fps,
        "has_alpha": track == "transparent",
    }
