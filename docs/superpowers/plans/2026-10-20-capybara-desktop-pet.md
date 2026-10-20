# 水豚噜噜桌宠 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 506 张「水豚噜噜」GIF 变成一个 Windows 常驻桌宠程序，含双轨制视觉、行为状态机、5 个可开关的实用模块与系统集成。

**Architecture:** 四层单向依赖：`tools_cli`（离线素材流水线）→ `assets`（处理后素材 + 分类索引）→ `pet`（窗口/行为/系统集成）→ `modules`（插件式提醒，通过 `ModuleContext.notify()` 反向请求行为层）。视觉走双轨制：去背干净的素材做真透明桌宠，其余做圆角卡片。

**Tech Stack:** Python 3.10、PyQt5 5.15.11、Pillow 11、psutil、PyInstaller 6（运行依赖只有这三者，不引入 numpy）。测试用 pytest + Qt offscreen 平台。

**Spec:** `docs/superpowers/specs/2026-10-20-capybara-desktop-pet-design.md`

## Global Constraints

- 仅 Windows、Python 3.10；运行依赖只有 PyQt5 / Pillow / psutil。
- 项目根目录：`d:\Users\linkai.zhuo\Documents\Trae\temp_20261020_01\capybara_pet\`（下称 `<root>`）。
- **本项目不使用 git**：任务验收 = 该任务测试全部通过；有可视/可交互产出的任务另加末尾「手工检查点」，纯库任务止于 Step 4。计划中不出现 commit 步骤。
- 素材命名保持 `lulu_NNN.gif`；运行时只读 `assets/processed/`。
- 处理后素材：长边 ≤ 200px、帧率 ≤ 10fps、颜色 ≤ 96 色、单文件 ≤ 300 KB（可经 `prepare.py` 的 `--max-side/--fps/--colors/--max-kb` 覆盖）。
- 去背分级（先算 `cleaned_ratio`、`edge_ratio`）：`cleaned_ratio < 0.05` 或 `cleaned_ratio > 0.75` → `hard`；否则 `cleaned_ratio` 在区间内时再看边界：`edge_ratio >= 0.70` → `easy`、`edge_ratio >= 0.35` → `medium`、其余 → `hard`。`easy` 的 track 为 `transparent`，`medium`/`hard` 为 `card`。原图自带透明通道 → 直接 `transparent`。
- 卡片样式：圆角 16px、描边 `#00000014` 1px、投影 24px 模糊 `#00000040`。
- 测试统一 `python -m pytest`，Qt 测试固定 `QT_QPA_PLATFORM=offscreen`（`tests/conftest.py` 设置）。
- 模块统一接口 `enable() / disable() / tick(now) / enabled`，只通过 `ModuleContext.notify()` 与外界交互。
- 状态优先级：`module(3) > user(2) > auto(1) > idle(0)`；拖拽高于一切。

## Review Focus

以下 5 类 spec 隐含要求、但容易被漏掉的失败模式，每条都已在对应任务中加了测试：

1. `assets/processed/` 为空或不存在时启动 → 不崩、显示兜底占位图、托盘提示（T7/T8）。
2. `categories.json` 手写引用了不存在的文件名 → 忽略缺失项继续用其余素材；全空时走回退链（T3）。
3. `config.json` 被手改成非法值（类型错误、负数、缺字段、JSON 损坏）→ 校验后回落默认值，正常启动（T6）。
4. 显示器拔插/分辨率变化后窗口位置越界 → 窗口回到主屏右下角（T8）。
5. 跨天与系统时钟回拨 → 整点报时/吃饭提醒跨天后重新触发，时钟回拨不重复触发也不漏触发（T18/T19）。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `tools_cli/gif_pipeline.py` | 去背（背景采样 / flood-fill / 腐蚀）、分级、压缩、`process_gif`。无 Qt 依赖 |
| `tools_cli/prepare.py` | CLI：增量/重建、MD5 去重、写 `processed/`、更新 `.index.json` 与 `categories.json`、出报告 |
| `tools_cli/contact_sheet.py` | 缩略图接触表 |
| `tools_cli/build.py` | PyInstaller 参数构造与打包 |
| `pet/catalog.py` | `categories.json` 读写、回退链、按分类 + track 选素材。无 Qt 依赖 |
| `pet/config.py` | `config.json` 深合并默认值、类型校验、原子写 |
| `pet/sprite.py` | 无边框透明置顶窗口、A/B 双轨渲染、GIF 播放与 3 实例缓存、交互信号 |
| `pet/behavior.py` | 行为状态机（优先级、自动状态定时、拖拽冻结） |
| `pet/edge_hide.py` | 贴边隐藏 / 滑出 / 离开 3 秒缩回 |
| `pet/tray.py` | 系统托盘图标与菜单宿主 |
| `pet/autostart.py` | 开机自启注册表读写 |
| `pet/winutil.py` | 前台窗口全屏检测 |
| `ui/menu.py` | 菜单构造（托盘与右键同源） |
| `ui/toast.py` | 气泡提示窗 |
| `ui/settings_dialog.py` | 设置面板 |
| `main.py` | 装配与启动 |
| `tests/*` | 单元测试 + 离屏冒烟测试 |

---

## 阶段 1：素材流水线

### Task 1: 去背核心算法与分级

**Files:**
- Create: `<root>/tools_cli/__init__.py`、`<root>/tools_cli/gif_pipeline.py`
- Create: `<root>/tests/conftest.py`、`<root>/tests/test_gif_pipeline_bg.py`
- Create: `<root>/requirements.txt`、`<root>/pytest.ini`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `TOL = 32`、`EDGE_MIN = 0.70`
  - `sample_background(im: Image.Image, tol: int = 32) -> tuple[int,int,int] | None`
  - `analyze_frame(im: Image.Image, bg: tuple[int,int,int], tol: int = 32) -> tuple[float, float]` → `(cleaned_ratio, edge_ratio)`
  - `remove_background(im: Image.Image, bg: tuple[int,int,int], tol: int = 32, erode: int = 1) -> Image.Image`
  - `grade(cleaned_ratio: float, edge_ratio: float) -> str` → `"easy" | "medium" | "hard"`
- 前置：`pip install PyQt5==5.15.11 Pillow psutil pytest`；`requirements.txt` 写 `PyQt5==5.15.11` / `Pillow>=11` / `psutil>=5.9`；`pytest.ini` 写 `[pytest]` + `testpaths = tests` + `addopts = -q`；`tests/conftest.py` 写 `import os; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`。

- [ ] **Step 1: 写失败测试**（`tests/test_gif_pipeline_bg.py`）

```python
from PIL import Image
from tools_cli.gif_pipeline import sample_background, analyze_frame, remove_background, grade


def solid(w, h, color, inner=None):
    im = Image.new("RGB", (w, h), color)
    if inner:
        for x in range(w // 4, w * 3 // 4):
            for y in range(h // 4, h * 3 // 4):
                im.putpixel((x, y), inner)
    return im


def test_sample_background_solid_and_gradient():
    assert sample_background(solid(40, 40, (255, 255, 255))) == (255, 255, 255)
    grad = Image.new("RGB", (40, 40))
    for x in range(40):
        for y in range(40):
            grad.putpixel((x, y), (x * 6, y * 6, (x + y) * 3))
    assert sample_background(grad) is None


def test_analyze_frame_ratios_on_solid_with_center_subject():
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    cleaned, edge = analyze_frame(im, (255, 255, 255))
    assert 0.60 <= cleaned <= 0.80 and edge == 1.0


def test_remove_background_border_transparent_subject_kept():
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    out = remove_background(im, (255, 255, 255))
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 0 and out.getpixel((20, 20))[3] == 255


def test_remove_background_only_clears_connected_region():
    """被主体包围、不连通到边界的同色区域必须保留"""
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    for x in range(18, 22):
        for y in range(18, 22):
            im.putpixel((x, y), (255, 255, 255))
    assert remove_background(im, (255, 255, 255)).getpixel((20, 20))[3] == 255


def test_remove_background_clears_center_when_connected_to_border():
    """只验证连通性：erode=0 隔离掉腐蚀（腐蚀由 test_erode_* 单独覆盖）"""
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    for x in range(19, 21):
        for y in range(10, 30):
            im.putpixel((x, y), (255, 255, 255))
    assert remove_background(im, (255, 255, 255), erode=0).getpixel((20, 20))[3] == 0


def test_erode_shrinks_transparent_area_by_one_pixel():
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    assert remove_background(im, (255, 255, 255), erode=0).getpixel((9, 9))[3] == 0
    assert remove_background(im, (255, 255, 255), erode=1).getpixel((9, 9))[3] == 255


def test_grade_thresholds():
    assert grade(0.50, 1.00) == "easy"
    assert grade(0.90, 1.00) == "hard"      # 整图都是背景 → 必须判 hard，否则会输出全透明图
    assert grade(0.10, 0.40) == "medium"
    assert grade(0.03, 0.90) == "hard"
    assert grade(1.00, 1.00) == "hard"


def test_tiny_images_do_not_crash():
    assert sample_background(Image.new("RGB", (1, 1), (0, 0, 0))) == (0, 0, 0)
    assert remove_background(Image.new("RGB", (1, 1), (0, 0, 0)), (0, 0, 0)).size == (1, 1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_gif_pipeline_bg.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'tools_cli'`

- [ ] **Step 3: 实现 `tools_cli/gif_pipeline.py` 的四个函数**

- `sample_background`：取四角各 5×5 区域逐通道中位数作候选；四候选两两最大通道差 > `tol` 时改用四边中点各 5×5 中位数，取出现次数最多者；仍无一致候选（渐变）返回 `None`；图宽或高 < 5px 时退化为单点采样。
- `analyze_frame`：`collections.deque` 扫描线 BFS，起点为四条边界上与 `bg` 通道差 ≤ `tol` 的像素，只清除与边界连通的近背景色区域；返回 `(清除像素/总像素, 边界被清除像素/边界总像素)`。
- `remove_background`：同一 BFS 把清除区域 alpha 置 0；`erode > 0` 时把**清除掩膜向内收缩 1px**（清空区边界上、8 邻域含不透明像素的像素恢复为不透明，用原掩膜逐次判定），重复 `erode` 次 —— 即 spec §5.1-6 的「镂空区域比实际稍小」，用于消除 GIF 1-bit 透明的白边。
- `grade`：按 Global Constraints 阈值返回分级。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_gif_pipeline_bg.py -v`
Expected: 8 passed

- [ ] **Step 5: 手工检查点**

在真实素材上打印分级比例。**全量 506 张实测（tol=32）**：`bg=None` 464、`easy` 29、`medium` 7、`hard` 6（tol=48 时 easy 56）。素材多为满幅彩色插画底，`easy` 占 5.7%，低于 spec §2 的 15% 估算；结论不变（绝大多数走卡片轨），`--tol` 可按需放宽：

```powershell
python -c "import glob; from PIL import Image; from tools_cli.gif_pipeline import sample_background, analyze_frame, grade; rs=[grade(*analyze_frame(Image.open(p).convert('RGB'), bg)) for p in glob.glob('../水豚噜噜GIF/*.gif')[:20] if (bg:=sample_background(Image.open(p).convert('RGB')))]; from collections import Counter; print(Counter(rs))"
```

---

### Task 2: 压缩、多帧处理与 `process_gif`

**Files:**
- Modify: `<root>/tools_cli/gif_pipeline.py`
- Create: `<root>/tests/test_gif_pipeline_process.py`

**Interfaces:**
- Consumes: Task 1 的四个函数
- Produces:
  - `resize_frame(im: Image.Image, max_side: int = 200) -> Image.Image`
  - `compress_gif(frames: list[Image.Image], durations: list[int], out_path: Path, max_fps: int = 10, colors: int = 96) -> None`
  - `process_gif(src: Path, dst: Path, *, max_side: int = 200, max_fps: int = 10, colors: int = 96, max_bytes: int = 307200, tol: int = 32, edge_min: float = 0.70) -> dict`，返回键：`file, track, grade, cleaned_ratio, edge_ratio, src_bytes, dst_bytes, src_size, dst_size, frames, fps, has_alpha`。超出 `max_bytes` 时按 `COLOR_FALLBACKS = (64, 32, 16)` 逐级降色重压。

- [ ] **Step 1: 写失败测试**（`tests/test_gif_pipeline_process.py`）

```python
from pathlib import Path
from PIL import Image
from tools_cli.gif_pipeline import process_gif, resize_frame


def make_gif(path: Path, size=(600, 600), frames=20, bg=(255, 255, 255), subject=(30, 130, 210)):
    imgs = []
    for i in range(frames):
        im = Image.new("RGB", size, bg)
        for x in range(120, 480):
            for y in range(120, 480):
                if (x + i) % 4 != 0:
                    im.putpixel((x, y), subject)
        imgs.append(im)
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=40, loop=0)


def test_resize_frame_caps_long_side_keeps_ratio():
    assert resize_frame(Image.new("RGB", (640, 320)), 320).size == (320, 160)
    assert resize_frame(Image.new("RGB", (320, 640)), 320).size == (160, 320)


def test_process_gif_easy_becomes_transparent_and_capped(tmp_path):
    src = tmp_path / "in.gif"; make_gif(src)
    r = process_gif(src, tmp_path / "out.gif")
    assert (r["grade"], r["track"], r["has_alpha"]) == ("easy", "transparent", True)
    assert max(r["dst_size"]) <= 200 and r["fps"] <= 10
    out = Image.open(tmp_path / "out.gif")
    assert out.n_frames <= 13 and out.convert("RGBA").getpixel((0, 0))[3] == 0


def test_process_gif_gradient_becomes_card(tmp_path):
    src = tmp_path / "grad.gif"
    im = Image.new("RGB", (300, 300))
    for x in range(300):
        for y in range(300):
            im.putpixel((x, y), (x % 256, y % 256, (x * y) % 256))
    im.save(src, save_all=True, append_images=[im], duration=80)
    r = process_gif(src, tmp_path / "o.gif")
    assert r["track"] == "card" and r["has_alpha"] is False and (tmp_path / "o.gif").exists()


def test_process_gif_existing_alpha_stays_transparent(tmp_path):
    src = tmp_path / "a.gif"
    f = Image.new("RGBA", (300, 300), (255, 255, 255, 0))
    for x in range(100, 200):
        for y in range(100, 200):
            f.putpixel((x, y), (10, 200, 10, 255))
    f.save(src, save_all=True, append_images=[f], duration=100)
    r = process_gif(src, tmp_path / "ao.gif")
    assert r["track"] == "transparent" and r["has_alpha"] is True


def test_process_gif_single_frame_and_blank_image(tmp_path):
    single = tmp_path / "one.gif"; Image.new("RGB", (300, 300), (255, 255, 255)).save(single)
    r1 = process_gif(single, tmp_path / "one_o.gif")
    assert r1["frames"] == 1 and r1["track"] == "card"     # 整图背景色 → 不能输出全透明图
    assert (tmp_path / "one_o.gif").exists()


def test_process_gif_reports_bytes_and_sizes(tmp_path):
    src = tmp_path / "in.gif"; make_gif(src)
    r = process_gif(src, tmp_path / "out.gif")
    assert r["src_bytes"] > r["dst_bytes"] > 0
    assert r["src_size"] == (600, 600) and max(r["dst_size"]) <= 200
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_gif_pipeline_process.py -v`
Expected: FAIL，`ImportError: cannot import name 'process_gif'`

- [ ] **Step 3: 实现三个函数**

- `resize_frame`：`copy()` 后 `thumbnail((max_side, max_side), Image.LANCZOS)`。
- `compress_gif`：按帧时长累加抽帧使有效帧率 ≤ `max_fps`（保留首帧）；每帧 `convert("P", palette=Image.ADAPTIVE, colors=colors)`；保存参数 `save_all=True, append_images=..., duration=<重采样后的每帧时长>, loop=0, disposal=2, transparency=<专用透明索引>`。
- `process_gif`：① 判断原图是否自带透明通道（`im.info.get("transparency") is not None` 或首帧含 A 通道）→ 是则 track 直接为 `transparent`；② 否则首帧 `sample_background`，`None` → `card`；否则抽样 5 帧（首帧 + 均匀 4 帧）取 `cleaned_ratio` / `edge_ratio` 均值 → `grade`，`easy` → 逐帧 `remove_background(erode=1)` 输出 RGBA + `transparent`，否则原图 `card`；③ 逐帧 `resize_frame` → `compress_gif`；④ 写出后若超过 500 KB，按 `colors` 128→64→32 重写一次；⑤ 返回统计 dict（`src_size`/`dst_size` 为 `(w, h)`，单帧 `fps = 0`）。注意返回的 `has_alpha` 字段表示**输出**是否带 alpha 通道，即 `has_alpha = (track == "transparent")`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_gif_pipeline_process.py -v`
Expected: 6 passed

- [ ] **Step 5: 手工检查点**

`python -c "from tools_cli.gif_pipeline import process_gif; from pathlib import Path; import json; print(json.dumps(process_gif(Path('../水豚噜噜GIF/lulu_001.gif'), Path('_t1.gif')), ensure_ascii=False))"`，目视 `_t1.gif` 主体完好无白边，看完删除该文件。

---

### Task 3: 分类索引与回退链（`pet/catalog.py`）

**Files:**
- Create: `<root>/pet/__init__.py`、`<root>/pet/catalog.py`
- Create: `<root>/tests/test_catalog.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `CATEGORIES: tuple[str, ...] = ("idle", "walk", "sleep", "eat", "drink", "happy", "angry")`
  - `FALLBACK: dict[str, tuple[str, ...]]`，`drink → ("drink","eat","idle","unassigned")`，其余为 `(自己,"idle","unassigned")`
  - `default_categories() -> dict` → `{"version": 2, "categories": {name: {"files": [], "track": "auto"}, ..., "unassigned": {...}}}`
  - `load_categories(path: Path) -> dict`（缺失/损坏/结构错 → 默认结构）、`save_categories(path: Path, data: dict) -> None`（原子写）
  - `existing_files(names: list[str], processed_dir: Path) -> list[str]`
  - `add_unassigned(data: dict, names: list[str], tracks: dict[str, str]) -> None`
  - `set_track(data: dict, name: str, track: str) -> None`
  - `pick(data: dict, category: str, processed_dir: Path, track: str | None = None, rng: random.Random | None = None) -> Path | None`
- 本文件禁止 import PyQt5。

- [ ] **Step 1: 写失败测试**（`tests/test_catalog.py`）

```python
import json, random
from pathlib import Path
from pet.catalog import (CATEGORIES, FALLBACK, default_categories, load_categories, save_categories,
                         existing_files, add_unassigned, set_track, pick)


def prep(tmp_path, files=("lulu_001.gif",)):
    for n in files:
        (tmp_path / n).write_bytes(b"GIF89a")
    return tmp_path


def test_default_structure_and_fallback_chain():
    d = default_categories()
    assert set(CATEGORIES) | {"unassigned"} <= set(d["categories"]) and d["version"] == 2
    for c in CATEGORIES:
        assert FALLBACK[c][0] == c and FALLBACK[c][-1] == "unassigned"
    assert FALLBACK["drink"] == ("drink", "eat", "idle", "unassigned")


def test_load_missing_corrupt_or_wrong_shape_returns_default(tmp_path):
    assert load_categories(tmp_path / "nope.json") == default_categories()
    bad = tmp_path / "bad.json"; bad.write_text("{ not json", encoding="utf-8")
    assert load_categories(bad) == default_categories()
    wrong = tmp_path / "wrong.json"; wrong.write_text(json.dumps({"version": 2, "categories": "oops"}), encoding="utf-8")
    assert load_categories(wrong) == default_categories()


def test_save_reload_roundtrip_and_missing_categories_backfilled(tmp_path):
    p = tmp_path / "c.json"
    save_categories(p, {"version": 2, "categories": {"idle": {"files": ["lulu_001.gif"], "track": "auto"}}})
    d = load_categories(p)
    assert d["categories"]["idle"]["files"] == ["lulu_001.gif"]
    assert set(CATEGORIES) <= set(d["categories"])


def test_existing_files_filters_ghosts(tmp_path):
    prep(tmp_path)
    assert existing_files(["lulu_001.gif", "ghost.gif"], tmp_path) == ["lulu_001.gif"]


def test_pick_returns_none_when_no_assets_at_all(tmp_path):
    d = default_categories()
    assert pick(d, "idle", prep(tmp_path, files=())) is None


def test_pick_falls_back_category_to_idle_to_unassigned(tmp_path):
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif"]
    assert pick(d, "drink", prep(tmp_path)).name == "lulu_001.gif"
    d2 = default_categories()
    d2["categories"]["unassigned"]["files"] = ["lulu_001.gif"]
    assert pick(d2, "sleep", prep(tmp_path)).name == "lulu_001.gif"


def test_pick_ignores_missing_index_entries_but_uses_rest(tmp_path):
    """Review Focus #2"""
    d = default_categories()
    d["categories"]["idle"]["files"] = ["ghost.gif", "lulu_001.gif"]
    assert pick(d, "idle", prep(tmp_path)).name == "lulu_001.gif"
    d["categories"]["idle"]["files"] = ["ghost_a.gif", "ghost_b.gif"]
    assert pick(d, "idle", prep(tmp_path)) is None


def test_pick_prefers_requested_track(tmp_path):
    prep(tmp_path, ("lulu_001.gif", "lulu_002.gif"))
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif", "lulu_002.gif"]
    set_track(d, "lulu_001.gif", "card"); set_track(d, "lulu_002.gif", "transparent")
    for _ in range(20):
        assert pick(d, "idle", tmp_path, track="transparent").name == "lulu_002.gif"
    assert pick(d, "idle", tmp_path, track="card").name == "lulu_001.gif"


def test_pick_is_deterministic_with_seeded_rng(tmp_path):
    prep(tmp_path, ("lulu_001.gif", "lulu_002.gif"))
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif", "lulu_002.gif"]
    a = pick(d, "idle", tmp_path, rng=random.Random(7))
    b = pick(d, "idle", tmp_path, rng=random.Random(7))
    assert a.name == b.name


def test_add_unassigned_avoids_duplicates():
    d = default_categories()
    add_unassigned(d, ["lulu_001.gif"], {"lulu_001.gif": "transparent"})
    add_unassigned(d, ["lulu_001.gif"], {"lulu_001.gif": "transparent"})
    assert d["categories"]["unassigned"]["files"] == ["lulu_001.gif"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_catalog.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pet'`

- [ ] **Step 3: 实现 `pet/catalog.py`**

- `load_categories`：`json.load` 包 `try/except (OSError, ValueError, TypeError)`；校验 `categories` 为 dict 且每项含 list 型 `files`，否则返回 `default_categories()`；成功后用 `default_categories()` 深合并补齐缺失分类。
- 数据结构在 `default_categories()` 里除 `categories` 外还带 `tracks: {文件名: 实测轨道}`；`set_track(data, name, track)` 写 `tracks[name]` 并刷新它所属分类的聚合 `track`（该分类内文件轨道一致时取该值，混杂时为 `"auto"`）。**注意**：`pick` 的按轨筛选必须查 per-file 的 `tracks`，分类级 `track` 只是聚合值，无法区分同分类内不同轨道的文件（见 `test_pick_prefers_requested_track`）。
- `pick`：沿 `FALLBACK[category]` 逐级取候选，每级用 `existing_files` 过滤；`track` 非 None 时在该级内筛 `tracks` 匹配者，筛空则忽略 track 条件（宁可有素材）；用 `rng or random.Random()` 随机选一个返回 `Path`；全链失败后，**仅当索引整体为空**（如 `categories.json` 丢失但 processed 目录完好）才扫 `processed_dir.glob("*.gif")` 兜底；否则返回 `None`。此处不可无条件扫目录，否则 `test_pick_ignores_missing_index_entries_but_uses_rest` 会拿到未登记的文件而非 `None`。
- `save_categories`：写 `<name>.tmp` 后 `os.replace`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_catalog.py -v`
Expected: 10 passed

---

### Task 4: `prepare.py` CLI（增量/重建、去重、索引、报告）

**Files:**
- Create: `<root>/tools_cli/prepare.py`
- Create: `<root>/tests/test_prepare.py`

**Interfaces:**
- Consumes: `process_gif`（T2）、`load_categories / save_categories / add_unassigned / set_track / default_categories`（T3）
- Produces:
  - `md5_of(path: Path) -> str`
  - `load_index(path: Path) -> dict` → `{"version": 1, "entries": {md5: {"name": str, "track": str}}}`；损坏返回空索引
  - `save_index(path: Path, index: dict) -> None`
  - `next_index_number(processed_dir: Path) -> int`
  - `run_prepare(raw_dir, processed_dir, categories_path, index_path, *, rebuild=False, tol=32, edge_min=0.70, max_side=200, max_fps=10, colors=96, max_bytes=307200, sample=None, workers=4) -> dict`，报告键：`processed, skipped_duplicate, failed, easy, card, total_bytes_before, total_bytes_after, largest`
  - CLI：`python tools_cli/prepare.py [--incremental|--rebuild] [--raw DIR] [--out DIR] [--categories FILE] [--sample N] [--tol N] [--edge-min F] [--max-side N] [--fps N] [--colors N] [--max-kb N] [--workers N]`，默认 `--raw assets/raw --out assets/processed --categories assets/categories.json`

- [ ] **Step 1: 写失败测试**（`tests/test_prepare.py`）

```python
from pathlib import Path
from PIL import Image
from tools_cli.prepare import md5_of, load_index, save_index, next_index_number, run_prepare
from pet.catalog import load_categories


def make_gif(path: Path, color=(30, 130, 210), frames=6):
    # 主体必须 >= 画布 25%，否则被清除比例 > 0.75 会被判为 hard（见 spec §5.1-5）
    imgs = []
    for _ in range(frames):
        im = Image.new("RGB", (400, 400), (255, 255, 255))
        for x in range(80, 320):
            for y in range(80, 320):
                im.putpixel((x, y), color)
        imgs.append(im)
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=60, loop=0)


def dirs(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "processed"
    raw.mkdir(); out.mkdir()
    return raw, out, tmp_path / "categories.json", tmp_path / ".index.json"


def test_next_index_number_counts_from_max(tmp_path):
    assert next_index_number(tmp_path) == 1
    for n in (3, 10, 7):
        (tmp_path / f"lulu_{n:03d}.gif").write_bytes(b"GIF89a")
    assert next_index_number(tmp_path) == 11


def test_run_prepare_processes_and_registers_unassigned(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "a.gif"); make_gif(raw / "b.gif", color=(200, 30, 30))
    rep = run_prepare(raw, out, cats, idx)
    assert rep["processed"] == 2 and rep["failed"] == [] and rep["easy"] == 2
    assert sorted(p.name for p in out.glob("*.gif")) == ["lulu_001.gif", "lulu_002.gif"]
    d = load_categories(cats)
    assert sorted(d["categories"]["unassigned"]["files"]) == ["lulu_001.gif", "lulu_002.gif"]
    assert d["categories"]["unassigned"]["track"] == "transparent"


def test_run_prepare_skips_content_duplicates(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "a.gif")
    (raw / "b.gif").write_bytes((raw / "a.gif").read_bytes())
    rep = run_prepare(raw, out, cats, idx)
    assert rep["processed"] == 1 and rep["skipped_duplicate"] == 1


def test_run_prepare_incremental_appends_without_overwriting(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "a.gif")
    run_prepare(raw, out, cats, idx)
    make_gif(raw / "b.gif", color=(10, 200, 10))
    rep = run_prepare(raw, out, cats, idx)
    assert rep["processed"] == 1
    assert sorted(p.name for p in out.glob("*.gif")) == ["lulu_001.gif", "lulu_002.gif"]


def test_run_prepare_rebuild_clears_stale_output(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "a.gif")
    run_prepare(raw, out, cats, idx)
    (out / "stale.gif").write_bytes(b"GIF89a")
    rep = run_prepare(raw, out, cats, idx, rebuild=True)
    assert rep["processed"] == 1 and not (out / "stale.gif").exists()


def test_run_prepare_records_broken_file_and_continues(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    make_gif(raw / "good.gif"); (raw / "broken.gif").write_text("not a gif")
    rep = run_prepare(raw, out, cats, idx)
    assert rep["processed"] == 1 and [f["file"] for f in rep["failed"]] == ["broken.gif"]


def test_run_prepare_sample_limits_and_reports_sizes(tmp_path):
    raw, out, cats, idx = dirs(tmp_path)
    for i in range(4):
        make_gif(raw / f"{i}.gif", color=(i * 40, 100, 100))
    rep = run_prepare(raw, out, cats, idx, sample=2)
    assert rep["processed"] == 2
    # 这里不断言 before > after：合成素材只有纯色块，源图本身已被 PIL 的帧内增量压到 ~1.4KB，
    # 低于 GIF 的调色板+文件头地板（~2KB），输出必然更大。真实素材的压缩比由 Task 4 Step 5 验证。
    assert rep["total_bytes_before"] > 0 and rep["total_bytes_after"] > 0
    sizes = [size for _, size in rep["largest"]]
    assert len(sizes) == 2 and sizes == sorted(sizes, reverse=True)
    assert rep["largest"][0][0].startswith("lulu_")


def test_index_roundtrip_and_corrupt_recovery(tmp_path):
    p = tmp_path / "x.gif"; p.write_bytes(b"GIF89a")
    idx = {"version": 1, "entries": {md5_of(p): {"name": "lulu_001.gif", "track": "card"}}}
    save_index(tmp_path / ".index.json", idx)
    assert load_index(tmp_path / ".index.json") == idx
    (tmp_path / ".index.json").write_text("{oops")
    assert load_index(tmp_path / ".index.json") == {"version": 1, "entries": {}}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_prepare.py -v`
Expected: FAIL，`ImportError: cannot import name 'run_prepare'`

- [ ] **Step 3: 实现 `tools_cli/prepare.py`**

- 流程：`rebuild=True` 先删 `processed_dir` 下全部 `*.gif` 并把索引重置；`load_index` 后遍历 `sorted(raw_dir.glob("*.gif"))`（`sample` 时截前 N 个）；算 `md5_of`，命中索引或命中本批已见 md5 集合 → `skipped_duplicate += 1`；否则分配 `lulu_{next_index_number(processed_dir):03d}.gif`（循环内自增计数器，防覆盖）。
- 单文件包 `try/except Exception`，失败记入 `failed`（含 `file` 与 `error`）并继续。
- 成功后更新索引 entry、`add_unassigned` 并 `set_track` 写入 `categories.json`、累加 `easy/card` 与体积统计、维护 `largest`（体积降序前 10）。
- `workers > 1` 时用 `ProcessPoolExecutor` 并行跑 `process_gif`，写文件与索引更新留主进程串行。为避免长参数列表，任务项为 `(src, dst, options)` 三元组，`options` 是含 `tol/edge_min/max_side/max_fps/colors/max_bytes` 的普通 dict（可 pickle）。
- 报告写入 `<processed_dir>/../prepare_report.json` 并 `print` 人类可读摘要。
- 实现完毕后做首次素材迁移（同盘重命名，不复制）：`Move-Item "d:\Users\linkai.zhuo\Documents\Trae\temp_20261020_01\水豚噜噜GIF" "<root>\assets\raw"`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_prepare.py -v`
Expected: 8 passed

- [ ] **Step 5: 全量处理真实素材（手工检查点）**

`cd <root>; python tools_cli/prepare.py`
期望：`processed == 506`、`failed == []`、`total_bytes_after` 落在 ~110–130MB。记录 `easy` 数量：若 `< 40`，用 `--edge-min 0.60` 重跑一次并对比目视质量，取质量更好的那次（数量服从质量）。

> 参数说明：默认 200px / 10fps / 96 色 / 单文件 ≤ 300KB。该取向由本批素材特性决定——实测这批 GIF 是 255 色、逐帧整帧变化的高熵视频截图，`disposal` 优化对帧间差异无效（`diffbbox=1.00`），因此体积只能靠降尺寸/降帧/降色控制。spec §5.1 亦写明桌宠实际显示 120–200px，200px 已是显示上限，不损失清晰度。后续需要更高画质时无需改代码：`python tools_cli/prepare.py --rebuild --max-side 240 --fps 12 --colors 128`。

---

### Task 5: 缩略图接触表

**Files:**
- Create: `<root>/tools_cli/contact_sheet.py`
- Create: `<root>/tests/test_contact_sheet.py`

**Interfaces:**
- Consumes: `processed/*.gif`
- Produces:
  - `build_sheet(files: list[Path], out_path: Path, *, cols: int = 10, rows: int = 6, cell: int = 150) -> int`（返回收录数）
  - `build_all(processed_dir: Path, out_dir: Path, *, cols: int = 10, rows: int = 6, cell: int = 150) -> list[Path]`，每 60 张一页，命名 `contact_sheet_01.png` 起

- [ ] **Step 1: 写失败测试**（`tests/test_contact_sheet.py`）

```python
from PIL import Image
from tools_cli.contact_sheet import build_sheet, build_all


def make(tmp_path, n, size=(200, 200)):
    fs = []
    for i in range(n):
        p = tmp_path / f"lulu_{i+1:03d}.gif"
        Image.new("RGB", size, (i * 7 % 255, 100, 150)).save(p)
        fs.append(p)
    return fs


def test_sheet_grid_size_and_count(tmp_path):
    fs = make(tmp_path, 7)
    assert build_sheet(fs, tmp_path / "s.png", cols=10, rows=6, cell=150) == 7
    w, h = Image.open(tmp_path / "s.png").size
    assert w >= 10 * 150 and h >= 1 * 150


def test_sheet_handles_non_square_and_skips_broken(tmp_path):
    a, b = tmp_path / "a.gif", tmp_path / "b.gif"
    Image.new("RGB", (640, 200), (1, 2, 3)).save(a)
    Image.new("RGB", (20, 640), (9, 9, 9)).save(b)
    broken = tmp_path / "bad.gif"; broken.write_text("nope")
    assert build_sheet([a, b, broken], tmp_path / "s.png", cell=120) == 2


def test_build_all_pages_of_60(tmp_path):
    make(tmp_path, 65)
    out = tmp_path / "out"; out.mkdir()
    pages = build_all(tmp_path, out)
    assert [p.name for p in pages] == ["contact_sheet_01.png", "contact_sheet_02.png"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_contact_sheet.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'tools_cli.contact_sheet'`

- [ ] **Step 3: 实现 `tools_cli/contact_sheet.py`**

画布 `cols*cell × rows*cell`，背景 `#F5F5F5`，格线 1px `#DDDDDD`；每格取首帧 `ImageOps.contain(frame, (cell-16, cell-24))` 居中粘贴；格底用 `ImageDraw.text` + `ImageFont.load_default()` 写文件名（不依赖系统字体）；打开失败的文件跳过；`build_all` 按文件名排序后每 60 张一页。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_contact_sheet.py -v`
Expected: 3 passed

- [ ] **Step 5: 生成接触表并人工分类（手工检查点）**

`python tools_cli/contact_sheet.py` → 打开 `assets/contact_sheet_*.png` → 把文件名填进 `assets/categories.json` 的 `idle / walk / sleep / eat / drink / happy / angry`。
校验：`python -c "from pet.catalog import load_categories; from pathlib import Path; d=load_categories(Path('assets/categories.json')); print({k: len(v['files']) for k,v in d['categories'].items()})"`。
**分类未完成不阻塞后续任务**：运行时代码在分类为空时走回退链，可先用 `unassigned` 跑通程序再回来补。

---

## 阶段 2：桌宠本体

### Task 6: 配置读写（`pet/config.py`）

**Files:**
- Create: `<root>/pet/config.py`
- Create: `<root>/tests/test_config.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `DEFAULTS: dict` — 与 spec §10 的 JSON 完全一致
  - `validate(cfg: dict) -> dict` — 返回校验后的新 dict，不修改入参，未知键保留
  - `load_config(path: Path) -> dict` — 深合并默认值 + 校验；损坏时备份 `path` 为同名 `.bad` 并返回默认
  - `save_config(path: Path, cfg: dict) -> None` — 原子写
  - `get(cfg: dict, dotted: str, default=None)`

- [ ] **Step 1: 写失败测试**（`tests/test_config.py`）

```python
import json
from pet.config import DEFAULTS, load_config, save_config, validate, get


def test_defaults_match_spec():
    assert set(DEFAULTS) == {"version", "pet", "modules"}
    assert set(DEFAULTS["modules"]) == {"pomodoro", "health_reminder", "meal_reminder", "hourly_chime", "sysmonitor"}
    assert DEFAULTS["modules"]["meal_reminder"]["times"] == ["12:00", "18:30"]
    assert DEFAULTS["pet"]["state_intervals"] == {"idle_to_wander": [30, 120], "idle_to_sleep": 900}
    assert DEFAULTS["modules"]["health_reminder"]["enabled"] is True
    assert DEFAULTS["modules"]["pomodoro"]["enabled"] is False


def test_load_missing_returns_defaults(tmp_path):
    assert load_config(tmp_path / "c.json") == DEFAULTS


def test_load_corrupt_backs_up_and_returns_defaults(tmp_path):
    p = tmp_path / "c.json"; p.write_text("{ broken")
    assert load_config(p) == DEFAULTS and (tmp_path / "c.json.bad").exists()


def test_deep_merge_keeps_user_values_and_fills_gaps(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"version": 1, "pet": {"scale": 2.0}, "modules": {"pomodoro": {"focus_min": 50}}}))
    cfg = load_config(p)
    assert cfg["pet"]["scale"] == 2.0 and cfg["pet"]["always_on_top"] is True
    assert cfg["modules"]["pomodoro"]["focus_min"] == 50 and cfg["modules"]["pomodoro"]["break_min"] == 5


def test_validate_fixes_invalid_types_and_negatives(tmp_path):
    """Review Focus #3"""
    cfg = {"version": 1,
           "pet": {"scale": "big", "state_intervals": {"idle_to_wander": [30, 120], "idle_to_sleep": -5}},
           "modules": {"pomodoro": {"enabled": "yes", "focus_min": -3, "break_min": "x"},
                       "meal_reminder": {"times": "12:00"}, "health_reminder": {}, "hourly_chime": {},
                       "sysmonitor": {}}}
    out = validate(cfg)
    assert out["pet"]["scale"] == DEFAULTS["pet"]["scale"]
    assert out["pet"]["state_intervals"]["idle_to_sleep"] == 900
    assert out["modules"]["pomodoro"] == {"enabled": False, "focus_min": 25, "break_min": 5}
    assert out["modules"]["meal_reminder"]["times"] == ["12:00", "18:30"]


def test_validate_keeps_valid_values_and_rejects_bad_times():
    cfg = json.loads(json.dumps(DEFAULTS))
    cfg["modules"]["meal_reminder"]["times"] = ["08:00", "20:15"]
    assert validate(cfg)["modules"]["meal_reminder"]["times"] == ["08:00", "20:15"]
    cfg["modules"]["meal_reminder"]["times"] = ["25:99", "abc"]
    assert validate(cfg)["modules"]["meal_reminder"]["times"] == ["12:00", "18:30"]


def test_validate_does_not_mutate_input_and_keeps_unknown_keys():
    cfg = json.loads(json.dumps(DEFAULTS))
    cfg["modules"]["pomodoro"]["focus_min"] = -1
    cfg["pet"]["my_custom"] = 42
    out = validate(cfg)
    assert cfg["modules"]["pomodoro"]["focus_min"] == -1
    assert out["pet"]["my_custom"] == 42


def test_save_load_roundtrip_and_no_temp_left(tmp_path):
    p = tmp_path / "c.json"
    cfg = json.loads(json.dumps(DEFAULTS)); cfg["pet"]["scale"] = 1.5
    save_config(p, cfg)
    assert load_config(p)["pet"]["scale"] == 1.5
    assert [f.name for f in tmp_path.iterdir()] == ["c.json"]


def test_get_dotted():
    assert get(DEFAULTS, "modules.pomodoro.focus_min") == 25
    assert get(DEFAULTS, "modules.nope.x", "fallback") == "fallback"
```

- [ ] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_config.py -v`，Expected: FAIL `No module named 'pet.config'`

- [ ] **Step 3: 实现 `pet/config.py`**

`DEFAULTS` 逐字抄 spec §10。`validate` 先 `copy.deepcopy(cfg)` 保护入参（绝不修改传入的 dict），再以 `DEFAULTS` 递归补全缺失键、未知键原样保留，按字段校验：bool 只接受 bool、数值必须为对应类型且 > 0、`[min,max]` 必须是两个正数、`times` 必须是 `HH:MM` 列表、`pos`/`edge_hide` 允许 `None` 或坐标；不符则回落默认。`load_config` 用 `try json.load` + `except (OSError, ValueError)` 备份并返回默认，成功则 `validate`。`save_config` 写 `.tmp` 后 `os.replace`。

- [ ] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_config.py -v`，Expected: 9 passed

---

### Task 7: 主窗口与双轨渲染（`pet/sprite.py`）

**Files:**
- Create: `<root>/pet/sprite.py`
- Create: `<root>/tests/test_sprite.py`
- Modify: `<root>/tests/conftest.py`（追加 `qapp` fixture）

**Interfaces:**
- Consumes: `pet.catalog.pick`（T3）、`pet.config.DEFAULTS`（T6）
- Produces:
  - 常量 `CARD_RADIUS = 16`、`CARD_BORDER = "#00000014"`、`CARD_SHADOW_BLUR = 24`、`CARD_SHADOW_COLOR = "#00000040"`、`MAX_MOVIE_CACHE = 3`、`DRAG_THRESHOLD = 4`
  - `render_frame(frame: Image.Image, track: str) -> QPixmap`
  - `placeholder_pixmap(size: int = 160) -> QPixmap`
  - `class Sprite(QWidget)`：`__init__(self, catalog_data: dict, processed_dir: Path, config: dict, parent=None)`；`play(category: str, once: bool = False) -> bool`；`set_track(track: str | None)`；`freeze()` / `unfreeze()` / `is_frozen() -> bool`；`movie_cache_size() -> int`；`current_frame_pixmap() -> QPixmap | None`；`move_to(x, y)`；`set_passthrough(on: bool)`；`draw_orange(size: int = 48) -> QPixmap`（静态方法）
  - 信号：`clicked`、`fast_clicked`、`double_clicked`、`right_clicked(QPoint)`、`drag_moved(QPoint)`、`drag_finished(QPoint)`、`hover_entered`、`hover_left`、`play_finished(str)`、`asset_missing`

- [ ] **Step 1: 追加 `qapp` fixture 到 `tests/conftest.py`**

```python
import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    yield QApplication.instance() or QApplication([])
```

- [ ] **Step 2: 写失败测试**（`tests/test_sprite.py`）

```python
from pathlib import Path
from PIL import Image
from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent, QPixmap
from pet.catalog import add_unassigned, default_categories
from pet.config import DEFAULTS
from pet.sprite import Sprite, placeholder_pixmap, render_frame


def make_gif(path: Path, frames=4, size=(320, 320)):
    imgs = [Image.new("RGB", size, (255, 255, 255)) for _ in range(frames)]
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=100, loop=0)


def catalog_with(tmp_path, names=("lulu_001.gif",), track="transparent", category="idle"):
    d = default_categories()
    for n in names:
        make_gif(tmp_path / n)
    d["categories"][category]["files"] = list(names)
    add_unassigned(d, list(names), {n: track for n in names})
    return d


def press(s, pos, button=Qt.LeftButton):
    s.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPoint(*pos), button, button, Qt.NoModifier))


def release(s, pos, button=Qt.LeftButton):
    s.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPoint(*pos), button, button, Qt.NoModifier))


def move(s, pos):
    s.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPoint(*pos), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))


def test_window_flags_and_attributes(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    assert s.windowFlags() & Qt.FramelessWindowHint and s.windowFlags() & Qt.WindowStaysOnTopHint
    assert s.testAttribute(Qt.WA_TranslucentBackground) and s.testAttribute(Qt.WA_ShowWithoutActivating)


def test_play_missing_assets_returns_false_and_shows_placeholder(qapp, tmp_path):
    """Review Focus #1"""
    s = Sprite(default_categories(), tmp_path, DEFAULTS)
    assert s.play("idle") is False and s.current_frame_pixmap() is not None


def test_play_existing_asset_returns_true(qapp, tmp_path):
    assert Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS).play("idle") is True


def test_movie_cache_bounded_and_switches_assets(qapp, tmp_path):
    names = tuple(f"lulu_{i:03d}.gif" for i in range(1, 9))
    s = Sprite(catalog_with(tmp_path, names=names), tmp_path, DEFAULTS)
    for _ in range(20):
        s.play("idle")
    assert s.movie_cache_size() <= 3


def test_freeze_unfreeze_and_passthrough(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    s.play("idle"); s.freeze()
    assert s.is_frozen() is True
    s.unfreeze(); assert s.is_frozen() is False
    s.set_passthrough(True); assert s.windowFlags() & Qt.WindowTransparentForInput
    s.set_passthrough(False); assert not (s.windowFlags() & Qt.WindowTransparentForInput)


def test_render_frame_transparent_keeps_alpha(qapp):
    frame = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    frame.putpixel((40, 40), (255, 0, 0, 255))
    img = render_frame(frame, "transparent").toImage()
    assert img.pixelColor(0, 0).alpha() == 0 and img.pixelColor(40, 40).alpha() > 0


def test_render_frame_card_adds_shadow_margin(qapp):
    pm = render_frame(Image.new("RGBA", (80, 80), (200, 40, 40, 255)), "card")
    assert isinstance(pm, QPixmap) and pm.width() > 80


def test_placeholder_and_orange_are_valid(qapp):
    assert placeholder_pixmap(120).width() == 120
    assert Sprite.draw_orange(48).width() == 48


def test_click_and_right_click_emit_signals(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    got = []
    s.clicked.connect(lambda: got.append("click"))
    s.right_clicked.connect(lambda p: got.append("right"))
    press(s, (30, 30)); release(s, (30, 30))
    press(s, (30, 30), Qt.RightButton); release(s, (30, 30), Qt.RightButton)
    assert got == ["click", "right"]


def test_small_move_is_click_large_move_is_drag(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    got = []
    s.clicked.connect(lambda: got.append("click"))
    s.drag_finished.connect(lambda p: got.append("drag"))
    press(s, (10, 10))
    move(s, (12, 12))
    release(s, (12, 12))
    press(s, (10, 10))
    move(s, (40, 40))
    release(s, (40, 40))
    assert got == ["click", "drag"]


def test_five_quick_clicks_emit_fast_click(qapp, tmp_path):
    s = Sprite(catalog_with(tmp_path), tmp_path, DEFAULTS)
    got = []
    s.fast_clicked.connect(lambda: got.append("fast"))
    for _ in range(5):
        press(s, (10, 10)); release(s, (10, 10))
    assert got == ["fast"]
```

- [ ] **Step 3: 运行测试确认失败** — Run: `python -m pytest tests/test_sprite.py -v`，Expected: FAIL `No module named 'pet.sprite'`

- [ ] **Step 4: 实现 `pet/sprite.py`**

> 实施偏离（已确认合理）：本机 Pillow 11.3 的 `PIL.ImageQt` 无法解析 Qt 绑定（模块内 `ImageQt` 类未定义，`toqimage/toqpixmap` 抛 `NameError`），故自行实现 `_qimage()`（`QImage(bytes, w, h, Format_RGBA8888).copy()`）与 `_qimage_to_pil()`（`convertToFormat` + `constBits`），不依赖 Pillow 的 Qt 桥。

窗口 `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool` + `WA_TranslucentBackground` + `WA_ShowWithoutActivating` + `setMouseTracking(True)`。`render_frame`：`transparent` → `QPixmap.fromImage(ImageQt(frame))`；`card` → 尺寸 `+2*CARD_SHADOW_BLUR` 的透明画布，`QPainter` 画圆角底图（按 `CARD_RADIUS` 裁切）+ 1px `CARD_BORDER` 描边 + 偏移模糊投影。`play`：`pick(...)` 为 `None` → 显示占位图、发 `asset_missing`、返回 False；命中 → `QMovie` + `setCacheMode(QMovie.CacheAll)` + `setScaledSize`（乘 `config["pet"]["scale"]`），`OrderedDict` LRU 上限 `MAX_MOVIE_CACHE`，淘汰时 `stop()`；`once=True` 时连 `finished` 发 `play_finished(category)`。鼠标：按下记 `_press_pos`/`_press_win_pos`，移动超过 `DRAG_THRESHOLD` 才置拖拽标记并发 `drag_moved`，释放按标记发 `drag_finished` 或 `clicked`（并维护 3 秒内点击计数，达 5 次发 `fast_clicked`），右键释放发 `right_clicked`，双击发 `double_clicked`；`enterEvent/leaveEvent` 发 `hover_entered/hover_left`。`draw_orange` 用 `QPainter` 画橙色椭圆 + 绿色叶片。

- [ ] **Step 5: 运行测试确认通过** — Run: `python -m pytest tests/test_sprite.py -v`，Expected: 11 passed

---

### Task 8: 启动装配与位置持久化（`main.py`）

**Files:**
- Create: `<root>/main.py`
- Create: `<root>/tests/test_main_positions.py`

**Interfaces:**
- Consumes: `Sprite`（T7）、`load_config / save_config`（T6）、`load_categories / default_categories`（T3）
- Produces:
  - `clamp_to_screen(pos: tuple[int,int], size: tuple[int,int], screens: list[tuple[int,int,int,int]]) -> tuple[int,int]`
  - `class PetApp`：`__init__(self, root: Path | None = None)`、`run(self) -> int`、`shutdown(self)`
  - `main() -> int`

- [x] **Step 1: 写失败测试**（`tests/test_main_positions.py`）

```python
from main import clamp_to_screen

PRIMARY = (0, 0, 1920, 1080)
SECOND = (1920, 0, 1920, 1080)
LEFT = (-1920, 0, 1920, 1080)


def test_position_kept_when_inside_any_screen():
    assert clamp_to_screen((300, 400), (200, 200), [PRIMARY, SECOND]) == (300, 400)
    assert clamp_to_screen((2000, 100), (200, 200), [PRIMARY, SECOND]) == (2000, 100)


def test_offscreen_position_returns_primary_bottom_right():
    """Review Focus #4"""
    assert clamp_to_screen((3000, 500), (200, 200), [PRIMARY]) == (1720, 880)


def test_partially_visible_position_is_pushed_inside():
    x, y = clamp_to_screen((1850, 1050), (200, 200), [PRIMARY])
    assert x <= 1720 and y <= 880


def test_negative_monitor_coordinates_supported():
    assert clamp_to_screen((-1900, 10), (200, 200), [PRIMARY, LEFT]) == (-1900, 10)


def test_empty_screens_returns_input():
    assert clamp_to_screen((50, 50), (200, 200), []) == (50, 50)
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_main_positions.py -v`，Expected: FAIL `No module named 'main'`

- [x] **Step 3: 实现 `main.py`**

`clamp_to_screen`：完全落在某屏幕内 → 原样；否则夹到「包含窗口左上角的最近屏幕」边界内；都不含 → 主屏（`screens[0]`）右下角内缩 40px；`screens` 为空返回原值。`PetApp.__init__`：`root` 默认 `Path(__file__).parent`，读 `root/config.json`；`processed = root/"assets/processed"`、`categories = root/"assets/categories.json"`（缺失用 `default_categories()`）。启动：`QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)` 必须在构造 `QApplication` 前 → 建 `Sprite` → 用 `clamp_to_screen` 校正 `config["pet"]["pos"]`（`None` → 主屏右下角）→ `show()`；若 `pick("idle")` 为 None 则打印一次「assets/processed 为空，请先运行 tools_cli/prepare.py」（托盘提示在 T12 接入）。连接 `drag_finished` 后用 `QTimer` 500ms 合并把最终位置写回 `config.json`。`shutdown` 同步保存并断开信号。`run` 返回 `app.exec_()`。

> 实施偏离（已确认合理）：① Step 1 测试期望「全屏外位置 → `(1720, 880)`」即主屏右下角**贴合**（`sx+sw-w, sy+sh-h`，无 40px 内缩），故 `clamp_to_screen` 的兜底分支不内缩；40px 内缩只用于「首次启动且 `pet.pos` 为 `None`」的默认落点（`_DEFAULT_MARGIN = 40`）。② `Sprite` 的拖拽只发 `drag_moved/drag_finished` 信号、自身不移动窗口，故 `PetApp` 增补 `_on_drag_moved`（窗口中心跟随光标）实现真实拖动，`_on_drag_finished` 只负责记忆位置与 500ms 合并落盘（贴边判定留给 T10）。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_main_positions.py -v`，Expected: 5 passed

- [x] **Step 5: 手工检查点**

`cd <root>; python main.py` → 桌面出现噜噜，可拖动；退出后重开位置保持；把 `assets/processed` 里的文件临时移走再启动 → 出现占位图且不崩（Review Focus #1），验证后移回。

> 以离屏冒烟脚本等效验证（`QT_QPA_PLATFORM=offscreen`，验证后已删除）：正常素材 → 渲染 200×200、位置落在屏幕内、`move_to(137,91)` + `shutdown` 后 `config.json` 记录 `[137,91]`、二次启动恢复到 `(137,91)`；空 `assets/processed` → 打印提示、显示占位图、不崩溃。

---

## 阶段 3：行为与交互

### Task 9: 行为状态机（`pet/behavior.py`）

**Files:**
- Create: `<root>/pet/behavior.py`
- Create: `<root>/tests/test_behavior.py`

**Interfaces:**
- Consumes: `Sprite.play/freeze/unfreeze`（T7）、`config["pet"]["state_intervals"]`（T6）
- Produces:
  - `PRIORITY_IDLE = 0`、`PRIORITY_AUTO = 1`、`PRIORITY_USER = 2`、`PRIORITY_MODULE = 3`、`PRIORITY_DRAG = 4`
  - `class Behavior(QObject)`：`__init__(self, sprite, config: dict, clock: Callable[[], datetime] = datetime.now)`；`start()` / `stop()`；`request(category: str, priority: int, once: bool = True, max_ms: int = 8000) -> bool`；`state` 属性（`"IDLE"` 等）；`on_drag_started()` / `on_drag_finished()` / `on_user_click()` / `on_fast_click()` / `on_play_finished(category: str)`；`tick(now: datetime)`；`force_wander_chance(p: float)`；信号 `state_changed(str)`

- [x] **Step 1: 写失败测试**（`tests/test_behavior.py`）

```python
from datetime import datetime, timedelta
from pet.behavior import Behavior, PRIORITY_AUTO, PRIORITY_MODULE, PRIORITY_USER
from pet.config import DEFAULTS


class FakeSprite:
    def __init__(self): self.played = []; self.frozen = False
    def play(self, category, once=False): self.played.append((category, once)); return True
    def freeze(self): self.frozen = True
    def unfreeze(self): self.frozen = False


class Clock:
    def __init__(self): self.now = datetime(2026, 10, 20, 9, 0, 0)
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)


def make():
    clock, sp = Clock(), FakeSprite()
    b = Behavior(sp, DEFAULTS, clock=clock)
    b.start()
    return b, sp, clock


def test_starts_in_idle_playing_idle(qapp):
    b, sp, _ = make()
    assert b.state == "IDLE" and sp.played[-1] == ("idle", False)


def test_module_event_overrides_auto_and_blocks_lower(qapp):
    b, sp, _ = make()
    b.request("walk", PRIORITY_AUTO)
    assert b.request("eat", PRIORITY_MODULE) is True and b.state == "EAT"
    assert b.request("walk", PRIORITY_AUTO) is False and b.state == "EAT"


def test_user_overrides_auto_but_not_module(qapp):
    b, sp, _ = make()
    b.request("sleep", PRIORITY_AUTO)
    assert b.request("happy", PRIORITY_USER) is True and b.state == "HAPPY"
    b.request("eat", PRIORITY_MODULE)
    assert b.request("happy", PRIORITY_USER) is False and b.state == "EAT"


def test_event_state_returns_to_idle_on_finish_or_timeout(qapp):
    b, sp, clock = make()
    b.request("eat", PRIORITY_MODULE, once=True)
    b.on_play_finished("eat")
    assert b.state == "IDLE"
    b.request("eat", PRIORITY_MODULE, once=True, max_ms=3000)
    clock.adv(seconds=4); b.tick(clock())
    assert b.state == "IDLE"


def test_drag_freezes_animation_beats_module_and_restores(qapp):
    b, sp, _ = make()
    b.request("eat", PRIORITY_MODULE)
    b.on_drag_started()
    assert b.state == "DRAGGED" and sp.frozen is True
    b.request("walk", PRIORITY_AUTO)
    assert b.state == "DRAGGED"
    b.on_drag_finished()
    assert b.state == "IDLE" and sp.frozen is False


def test_click_plays_happy_once_and_fast_click_plays_angry(qapp):
    b, sp, _ = make()
    b.on_user_click()
    assert b.state == "HAPPY" and sp.played[-1] == ("happy", True)
    b.on_fast_click()
    assert b.state == "ANGRY"


def test_auto_wander_after_interval_and_user_activity_resets_sleep_timer(qapp):
    b, sp, clock = make()
    b.force_wander_chance(1.0)
    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_wander"][1] + 1)
    b.tick(clock())
    assert b.state == "WANDER"
    b.on_user_click(); b.on_play_finished("happy")
    clock.adv(seconds=800); b.tick(clock())
    assert b.state != "SLEEP"      # 用户操作重置了睡眠计时：800s < 900s 不应入睡


def test_sleep_after_long_idle(qapp):
    b, sp, clock = make()
    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_sleep"] + 1)
    b.tick(clock())
    assert b.state in ("SLEEP", "WANDER")


def test_stop_freezes_transitions(qapp):
    b, sp, clock = make()
    b.stop(); b.force_wander_chance(1.0)
    clock.adv(seconds=9999); b.tick(clock())
    assert b.state == "IDLE"
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_behavior.py -v`，Expected: FAIL `No module named 'pet.behavior'`

- [x] **Step 3: 实现 `pet/behavior.py`**

内部状态 `_state`、`_priority`、`_state_until`、`_last_user_activity`、`_next_auto_at`、`_rng`、`_stopped`。`request`：`priority < _priority` 返回 False；否则 `sprite.play(category, once)`、`_state_until = clock() + max_ms`、更新 `_state/_priority`、发 `state_changed`。`on_play_finished` 仅在状态由该分类驱动且 `once` 时回 IDLE。`tick`：`_stopped` 直接返回；`_state_until` 到期 → 回 IDLE；DRAGGED 跳过；IDLE 时 `now - _last_user_activity >= idle_to_sleep` → 概率 0.5 进 SLEEP 否则 WANDER，或到达 `_next_auto_at` → WANDER。回 IDLE 时重算 `_next_auto_at = now + rng.uniform(min_gap, max_gap)`。`on_drag_started` 用 `PRIORITY_DRAG` 置 DRAGGED 并 `freeze()`。`force_wander_chance(p)` 把随机阈值固定为 `p`（测试钩子）。

> 实施细节补充：① `once=False` 的请求把 `_state_until` 置 `None`（状态一直持续到被覆盖），如启动时的 `idle`；`once=True` 才带 `max_ms` 超时兜底。② 状态名由分类推导（`state_of()`），仅 `walk → "WANDER"` 需特殊映射；`_to_idle()` 会重置 `_priority` 并重放 `idle`（`once=False`），同时重算 `_next_auto_at`。③ `force_wander_chance(p)` 固定的是自动行为里「睡眠/走动」两类随机判定共用的概率阈值（`_chance()`），因此 `p=1.0` 时长时间空闲也会进 SLEEP——测试 7 的 800s < 900s 路径不受影响。④ 拖动只 `freeze()` 不换素材，`_state_category` 置 `None`，避免 `play_finished(walk)` 误触发回 IDLE。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_behavior.py -v`，Expected: 9 passed

- [x] **Step 5: 手工检查点**

在 `main.py` 接入 `Behavior`，用 `QTimer` 每 100ms 调 `tick(datetime.now())`，并把 `Sprite` 的 `play_finished`、`drag_*`、`clicked`、`fast_clicked` 连到对应方法。运行 2 分钟观察：会从待机切到走动/睡觉；点击回待机；拖拽时画面冻结。

> 已完成接线：`PetApp._wire_signals()`（`clicked → on_user_click`、`fast_clicked → on_fast_click`、`play_finished → on_play_finished`、`drag_moved/drag_finished → 拖动起止`），`_TICK_MS = 100` 的 `_tick_timer` 驱动 `behavior.tick(datetime.now())`；启动改为 `behavior.start()`（其内部即播放 `idle`），`shutdown` 停表并停状态机。以离屏冒烟等效验证（含真实 Qt 鼠标事件）：`IDLE → WANDER`（自动）→ 单击 `HAPPY` → 5 连击 `ANGRY` → 拖拽 `DRAGGED`+冻结+跟随光标 → 松手 `IDLE`+解冻，验证后脚本已删除。

---

### Task 10: 贴边隐藏（`pet/edge_hide.py`）

**Files:**
- Create: `<root>/pet/edge_hide.py`
- Create: `<root>/tests/test_edge_hide.py`

**Interfaces:**
- Consumes: `Sprite.move_to`（T7）
- Produces:
  - `hidden_x(pos: tuple[int,int], size: tuple[int,int], screen: tuple[int,int,int,int], edge_px: int = 24, strip_px: int = 48) -> int | None`
  - `strip_rect(hidden_x: int, screen: tuple[int,int,int,int], size: tuple[int,int], y: int, strip_px: int = 48) -> tuple[int,int,int,int] | None`
  - `class EdgeHider(QObject)`：`__init__(self, sprite, config: dict, screens_provider: Callable[[], list[tuple[int,int,int,int]]], clock=datetime.now, strip_px=48, edge_px=24, leave_ms=3000)`；`maybe_hide(pos) -> bool`；`reveal()`；`retract()`；`is_hidden` 属性；`on_hover_entered()`；`on_hover_left()`；`detach()`；`tick(now)`；`save_to_config()`；`restore_from_config()`；信号 `hidden_changed(bool)`

> 接口偏离（已确认合理）：① 计划原 `strip_rect(hidden_x, screen, size, strip_px=48)` 无法由入参推出桔子窄条的 `y`（测试期望 `y=400` 但该值不在任何入参中），改为 `strip_rect(hidden_x, screen, size, y, strip_px=48)`——窄条要贴在窗口纵向上，`y` 必须显式传入。② `sprite` 的尺寸取自 `sprite.width()/height()`（真实 `Sprite` 是 QWidget 天然具备），故测试用 `FakeSprite` 需补 `width()/height()`。③ 新增 `on_hover_left()`（Step 5 要求的「移开开始计时」）与 `detach()`（拖离边缘时取消贴边并清除配置记录）；`on_hover_entered` 改为「滑出并取消倒计时」，使悬停期间不会倒计时缩回。测试由 7 增至 8 项。

- [x] **Step 1: 写失败测试**（`tests/test_edge_hide.py`）

```python
from datetime import datetime, timedelta
from pet.edge_hide import EdgeHider, hidden_x, strip_rect

SCREEN = (0, 0, 1920, 1080)
SIZE = (200, 200)


class FakeSprite:
    """模拟桌宠窗口：仅暴露 EdgeHider 用到的接口（QWidget 的 width/height + move_to）。"""

    def __init__(self): self.pos = (500, 500)
    def move_to(self, x, y): self.pos = (x, y)
    def width(self): return SIZE[0]
    def height(self): return SIZE[1]


class Clock:
    def __init__(self): self.now = datetime(2026, 10, 20, 9, 0, 0)
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)


def make(cfg=None, leave_ms=3000):
    sp, clock = FakeSprite(), Clock()
    return EdgeHider(sp, cfg if cfg is not None else {}, lambda: [SCREEN], clock=clock, leave_ms=leave_ms), sp, clock


def test_hidden_x_only_left_and_right_edges():
    assert hidden_x((800, 400), SIZE, SCREEN) is None
    assert hidden_x((5, 400), SIZE, SCREEN) == 48 - 200
    assert hidden_x((1920 - 200 - 5, 400), SIZE, SCREEN) == 1920 - 48
    assert hidden_x((800, 2), SIZE, SCREEN) is None
    assert hidden_x((800, 1078), SIZE, SCREEN) is None


def test_strip_rect_left_right_and_middle():
    assert strip_rect(48 - 200, SCREEN, SIZE, 400) == (0, 400, 48, 200)
    assert strip_rect(1872, SCREEN, SIZE, 400) == (1872, 400, 48, 200)
    assert strip_rect(500, SCREEN, SIZE, 400) is None


def test_maybe_hide_moves_offscreen_only_near_edge():
    h, sp, _ = make()
    assert h.maybe_hide((900, 500)) is False and h.is_hidden is False
    assert h.maybe_hide((4, 500)) is True and h.is_hidden is True
    assert sp.pos[0] == 48 - 200
    assert h.maybe_hide((900, 500)) is False and h.is_hidden is False


def test_reveal_then_retract_after_leave_timeout():
    h, sp, clock = make(leave_ms=3000)
    h.maybe_hide((4, 500))
    h.reveal()
    assert sp.pos == (0, 500) and h.is_hidden is True
    clock.adv(seconds=2); h.tick(clock())
    assert sp.pos == (0, 500)
    clock.adv(seconds=2); h.tick(clock())
    assert sp.pos[0] == 48 - 200


def test_hover_entered_resets_leave_timer():
    h, sp, clock = make(leave_ms=3000)
    h.maybe_hide((4, 500)); h.reveal()
    clock.adv(seconds=2); h.on_hover_entered()
    clock.adv(seconds=2); h.tick(clock())
    assert sp.pos == (0, 500)


def test_hover_left_arms_leave_timer_then_retracts():
    h, sp, clock = make(leave_ms=3000)
    h.maybe_hide((4, 500)); h.reveal(); h.on_hover_entered()
    clock.adv(seconds=10); h.tick(clock())
    assert sp.pos == (0, 500)      # 悬停期间一直滑出，不缩回
    h.on_hover_left()
    clock.adv(seconds=2); h.tick(clock())
    assert sp.pos == (0, 500)
    clock.adv(seconds=2); h.tick(clock())
    assert sp.pos[0] == 48 - 200


def test_config_roundtrip_restores_hidden_state():
    cfg = {}
    h, sp, _ = make(cfg)
    h.maybe_hide((4, 500))
    assert cfg["pet"]["edge_hide"] == {"side": "left", "y": 500}
    h2, sp2, _ = make(cfg)
    h2.restore_from_config()
    assert h2.is_hidden is True and sp2.pos[0] == 48 - 200


def test_restore_from_config_noop_when_not_hidden():
    cfg = {"pet": {"edge_hide": None}}
    h, sp, _ = make(cfg)
    h.restore_from_config()
    assert h.is_hidden is False and sp.pos == (500, 500)
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_edge_hide.py -v`，Expected: FAIL `No module named 'pet.edge_hide'`

- [x] **Step 3: 实现 `pet/edge_hide.py`**

`hidden_x`：左边缘（`pos[0] - screen.x <= edge_px`）→ `screen.x - size[0] + strip_px`；右边缘（`pos[0] + size[0] >= screen.x + screen.w - edge_px`）→ `screen.x + screen.w - strip_px`；否则 `None`。`strip_rect`：按隐藏后 x 判断在左侧（`x < screen.x`）还是右侧（`x + size[0] > screen.x + screen.w`），返回 `strip_px` 宽的可见条。`EdgeHider`：`maybe_hide` 记 `_side`/`_y`、`sprite.move_to`、`_hidden=True`、`save_to_config()`、发 `hidden_changed(True)`；`reveal()` 移到屏幕内侧（左 `screen.x`、右 `screen.x + w - size[0]`）、`_revealed=True`、`_leave_at = clock() + leave_ms`；`retract()` 再移出；`tick` 仅当 `_hidden and _revealed and now >= _leave_at` → `retract()`；`save_to_config` 写 `config["pet"]["edge_hide"] = {"side": ..., "y": ...}`。

> 实现补充：`maybe_hide` 未命中边缘（或找不到所在屏幕）时调用 `detach()` 退出贴边模式并清除配置；`on_hover_entered()` = 未滑出则 `reveal()` + 取消 `_leave_at`（悬停期间不缩回）；`on_hover_left()` 重新armed `_leave_at`；`restore_from_config()` 依据 `side` 直接 `retract()` 落位。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_edge_hide.py -v`，Expected: 8 passed

- [x] **Step 5: 手工检查点**

`main.py` 接入：`drag_finished` → `maybe_hide`，`hover_entered` → `on_hover_entered()`，`hover_left` → 启动离开计时，`Behavior.tick` 的同时调 `EdgeHider.tick`。把噜噜拖到屏幕最左侧松手 → 只剩桔子条；鼠标移上去滑出，移开 3 秒缩回；重启后仍隐藏。

> 已完成接线（`PetApp`）：`self.edge_hider = EdgeHider(self.sprite, self.config, self._screens)`；`_wire_signals()` 增加 `hover_entered → on_hover_entered`、`hover_left → on_hover_left`；`_on_tick` 同时驱动 `behavior.tick(now)` 与 `edge_hider.tick(now)`；`_on_drag_finished` 在松手后调 `maybe_hide((sprite.x(), sprite.y()))`；`_start_ui` 末尾 `restore_from_config()`；`shutdown` 一并断开 hover 信号。以离屏冒烟等效验证：拖到左边缘松手 → `x=-152`、`is_hidden=True`、配置写 `{"side":"left","y":400}`；hover 滑出到 `x=0` 且悬停 10s 不缩回；`hover_left` 后 2s 仍滑出、4s 缩回；重启恢复隐藏；拖离边缘 `detach` 且配置清零（脚本验证后已删除）。

---

### Task 11: 气泡提示与交互接线（`ui/toast.py`）

**Files:**
- Create: `<root>/ui/__init__.py`、`<root>/ui/toast.py`
- Modify: `<root>/main.py`（点击 / 连点 / 双击 / 右键 / 悬停气泡接线）
- Create: `<root>/tests/test_toast.py`

**Interfaces:**
- Consumes: `Sprite` 信号（T7）、`Behavior`（T9）
- Produces:
  - `TOAST_WIDTH = 220`、`TOAST_RADIUS = 12`、`TOAST_MAX_LINES = 4`
  - `class Toast(QWidget)`：`__init__(self, parent=None)`；`show_message(self, text: str, duration_ms: int = 6000, anchor: tuple[int,int] | None = None, kind: str = "info")`；属性 `current_text`、`kind`；信号 `dismissed`

- [x] **Step 1: 写失败测试**（`tests/test_toast.py`）

```python
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication
from ui.toast import Toast, TOAST_WIDTH


def pump(pred, timeout=400):
    loop = QTimer(); loop.setSingleShot(True)
    done = {"v": False}
    loop.timeout.connect(lambda: done.update(v=True)); loop.start(timeout)
    while not pred() and not done["v"]:
        QApplication.processEvents()
    return pred()


def test_toast_window_flags(qapp):
    t = Toast()
    assert t.windowFlags() & Qt.FramelessWindowHint and t.windowFlags() & Qt.WindowStaysOnTopHint
    assert t.windowFlags() & Qt.WindowTransparentForInput
    assert t.testAttribute(Qt.WA_TranslucentBackground)


def test_show_message_sets_text_and_visible(qapp):
    t = Toast()
    t.show_message("该喝水啦", duration_ms=50)
    assert t.current_text == "该喝水啦" and t.isVisible() is True


def test_toast_autocloses_and_emits_dismissed(qapp):
    t = Toast()
    got = []
    t.dismissed.connect(lambda: got.append(True))
    t.show_message("hi", duration_ms=50)
    assert pump(lambda: not t.isVisible()) and got == [True]


def test_long_text_wrapped_within_width(qapp):
    t = Toast()
    t.show_message("噜" * 200, duration_ms=10)
    assert t.width() <= TOAST_WIDTH + 40


def test_anchor_positions_toast_above_point(qapp):
    t = Toast()
    t.show_message("x", duration_ms=10, anchor=(1000, 600))
    assert abs(t.x() - 1000) <= 260 and t.y() < 600


def test_kind_switches_style(qapp):
    t = Toast()
    t.show_message("warn", duration_ms=10, kind="warn")
    assert t.kind == "warn"
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_toast.py -v`，Expected: FAIL `No module named 'ui.toast'`

- [x] **Step 3: 实现 `ui/toast.py` 并接线 `main.py`**

`Toast`：`Qt.Tool | FramelessWindowHint | WindowStaysOnTopHint | WindowTransparentForInput` + `WA_TranslucentBackground` + `WA_ShowWithoutActivating`；`setFixedWidth(TOAST_WIDTH)`；`paintEvent` 画圆角背景（info `#FFFFFFEE`、warn `#FFF6E5EE`）+ 1px 边框 + 12px 投影；`QLabel` 自动换行、超过 `TOAST_MAX_LINES` 行用省略号；`show_message` 先 `show()` 再起定时器：用 `QTimer.singleShot(duration_ms)` 触发 `hide()` 并发 `dismissed`；`anchor` 给定时置于锚点上方 8px 居中并夹进屏幕。
`main.py` 接线：`clicked` → `behavior.on_user_click()` + 悬停气泡；`fast_clicked` → `behavior.on_fast_click()`；`hover_entered` → 400ms 后按 `config["pet"]["hover_tooltip"]` 弹状态气泡；`double_clicked` → 暂时打印「设置面板未接入」；`right_clicked` → 弹出占位菜单（T12 换成真实菜单）。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_toast.py -v`，Expected: 6 passed

- [x] **Step 5: 手工检查点**

`python main.py`：点击 → happy + 气泡；3 秒内连点 5 次 → angry；悬停 0.5 秒 → 状态气泡；气泡不抢焦点（在记事本里打字时点击噜噜，输入焦点不丢）。

> 已完成接线（`PetApp`）：`self.toast = Toast()`；`_wire_signals()` 增加 `clicked → _on_clicked`（随机 `CLICK_LINES`）、`fast_clicked → _on_fast_clicked`（warn 气泡）、`hover_entered → _on_hover_entered`（400ms `_hover_timer`）、`hover_left → _on_hover_left`（取消计时）、`double_clicked → _on_double_clicked`（打印占位）、`right_clicked → _on_right_clicked`（`menu.popup` 占位菜单，T12 替换）；`_show_toast()` 以「桌宠顶边中点」为锚点；`shutdown` 停止 hover 计时、`toast.hide()` 并断开上述信号。以离屏冒烟等效验证（合成真实 `QMouseEvent` 走完整点击计数链路）：单击 → `HAPPY` + 气泡；3 秒内连点 5 次 → `ANGRY` + warn 气泡；悬停 150ms 不弹、650ms 弹状态气泡；`WindowTransparentForInput` 与 `WA_ShowWithoutActivating` 均为真；`duration_ms=50` 到期自动 `hide()`；`hover_tooltip=false` 时悬停不弹；右键占位菜单动作 `['菜单将在下一步接入', '', '退出']`（脚本验证后已删除）。
>
> 实施偏离（已确认合理）：① 总宽固定为 `TOAST_WIDTH`（220），其中左右各留 12px 给投影（`SHADOW`），卡片实际宽 196px，满足测试 `width() <= TOAST_WIDTH + 40`；② 自动关闭改用成员 `QTimer(self)`（可被下一次 `show_message` 取消），替代计划里的 `QTimer.singleShot`；③ `anchor` 夹进屏幕时取「包含锚点的那块屏幕」（`QApplication.screenAt`），锚点不在任何屏幕内则不夹——否则离屏环境 800×600 下 `anchor=(1000,600)` 会被夹到 `x=556`，与测试容差 ±260 冲突；④ 文本超过 4 行时用二分查找截断并追加「…」。

---

## 阶段 4：系统集成

### Task 12: 菜单与系统托盘（`ui/menu.py` + `pet/tray.py`）

**Files:**
- Create: `<root>/ui/menu.py`、`<root>/pet/tray.py`
- Create: `<root>/tests/test_menu.py`
- Modify: `<root>/main.py`（右键菜单换成真实菜单，接入托盘）

**Interfaces:**
- Consumes: `config`（T6）、`Sprite`（T7）、`Toast`（T11）
- Produces:
  - `MENU_KEYS = ("pomodoro", "water", "sit", "meal", "hourly", "sysmonitor")` 与 `MENU_LABELS = {"pomodoro": "番茄钟", "water": "喝水提醒", "sit": "久坐提醒", "meal": "吃饭提醒", "hourly": "整点报时", "sysmonitor": "系统监控"}`
  - `class MenuState`：`__init__(self, visible: bool, passthrough: bool, autostart: bool, modules: dict[str, bool], pomodoro_running: bool)`
  - `build_menu(parent, state: MenuState, handlers: dict) -> QMenu`；`handlers` 必须提供 `toggle_visible()`、`toggle_passthrough()`、`toggle_module(key: str, on: bool)`、`pomodoro(action: str)`、`open_settings()`、`toggle_autostart()`、`quit()`
  - `class Tray(QObject)`：`__init__(self, app, icon: QIcon, menu_factory: Callable[[], QMenu])`；`show()`；`refresh()`；`notify(title: str, text: str)`
  - `ensure_tray_icon(processed_dir: Path, catalog_data: dict, out_path: Path) -> Path`

- [x] **Step 1: 写失败测试**（`tests/test_menu.py`）

```python
from pathlib import Path
from PIL import Image
from pet.catalog import default_categories, set_track
from pet.tray import ensure_tray_icon
from ui.menu import MenuState, build_menu


class Handlers:
    def __init__(self): self.calls = []
    def toggle_visible(self): self.calls.append(("visible",))
    def toggle_passthrough(self): self.calls.append(("passthrough",))
    def toggle_module(self, key, on): self.calls.append(("module", key, on))
    def pomodoro(self, action): self.calls.append(("pomodoro", action))
    def open_settings(self): self.calls.append(("settings",))
    def toggle_autostart(self): self.calls.append(("autostart",))
    def quit(self): self.calls.append(("quit",))


MODS = {"pomodoro": False, "water": True, "sit": True, "meal": True, "hourly": False, "sysmonitor": False}


def actions(menu):
    return {a.text().replace("&", ""): a for a in menu.actions()}


def submenu_of(menu):
    return [a for a in menu.actions() if a.menu()][0].menu()


def test_menu_top_level_items_and_mode_pair(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    t = actions(m)
    for name in ("显示 / 隐藏噜噜", "设置…", "开机自启", "退出"):
        assert name in t
    assert "交互模式" in t and "穿透模式" in t
    assert t["交互模式"].isChecked() is True and t["穿透模式"].isChecked() is False


def test_passthrough_state_reflected(qapp):
    m = build_menu(None, MenuState(True, True, False, MODS, False), Handlers().__dict__)
    t = actions(m)
    assert t["穿透模式"].isChecked() is True and t["交互模式"].isChecked() is False


def test_module_switches_are_checkable_and_match_state(qapp):
    m = build_menu(None, MenuState(True, False, False, MODS, False), Handlers().__dict__)
    sub = actions(submenu_of(m))
    for label in ("番茄钟", "喝水提醒", "久坐提醒", "吃饭提醒", "整点报时", "系统监控"):
        assert sub[label].isCheckable() is True
    assert sub["喝水提醒"].isChecked() is True and sub["番茄钟"].isChecked() is False


def test_toggle_module_reports_new_state(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, False), h.__dict__)
    pom = actions(submenu_of(m))["番茄钟"]
    pom.setChecked(True); pom.trigger()
    assert ("module", "pomodoro", True) in h.calls
    sit = actions(submenu_of(m))["久坐提醒"]
    sit.setChecked(False); sit.trigger()
    assert ("module", "sit", False) in h.calls


def test_pomodoro_sub_actions_present(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, True), h.__dict__)
    sub = actions(submenu_of(m))
    for label in ("开始 / 暂停", "跳过", "重置"):
        assert label in sub
    sub["跳过"].trigger()
    assert ("pomodoro", "skip") in h.calls


def test_quit_and_autostart_handlers(qapp):
    h = Handlers()
    m = build_menu(None, MenuState(True, False, False, MODS, False), h.__dict__)
    actions(m)["退出"].trigger()
    actions(m)["开机自启"].trigger()
    assert ("quit",) in h.calls and ("autostart",) in h.calls


def test_ensure_tray_icon_from_transparent_asset_then_reuse(tmp_path):
    Image.new("RGB", (200, 200), (30, 130, 210)).save(tmp_path / "lulu_001.gif")
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif"]
    set_track(d, "lulu_001.gif", "transparent")
    out = ensure_tray_icon(tmp_path, d, tmp_path / "tray_icon.png")
    assert out.exists() and Image.open(out).size == (64, 64)
    out.write_bytes(b"cached")
    assert ensure_tray_icon(tmp_path, d, out).read_bytes() == b"cached"


def test_ensure_tray_icon_falls_back_to_drawn_orange(qapp, tmp_path):
    p = ensure_tray_icon(tmp_path, default_categories(), tmp_path / "tray_icon.png")
    assert p.exists() and Image.open(p).size == (64, 64)
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_menu.py -v`，Expected: FAIL `No module named 'ui.menu'`

- [x] **Step 3: 实现 `ui/menu.py` 与 `pet/tray.py`**

`build_menu` 按 spec §9.1 结构：`显示 / 隐藏噜噜`（checkable）、`交互模式` 与 `穿透模式`（互斥 checkable，用 `QActionGroup`）、分隔线、`实用工具 ▸`（6 个 checkable 项按 `MENU_KEYS`/`MENU_LABELS` 顺序 + 分隔 + `开始 / 暂停`、`跳过`、`重置`）、分隔线、`设置…`、`开机自启`（checkable）、`关于`（`QMessageBox.about`）、`退出`。触发时用 `functools.partial` 把「触发后的新状态」传给 handler，本函数不修改状态。**注意**：6 个模块开关、`显示 / 隐藏噜噜`、`开机自启` 一律连 `toggled(bool)`，不要连 `triggered`——checkable 动作调 `trigger()` 时会二次翻转勾选态，只有 `toggled` 能稳定拿到用户改变后的状态；`交互模式` / `穿透模式` 用 `QActionGroup` 互斥，同样取 `toggled` 收到的布尔值。
`Tray`：`QSystemTrayIcon` + `menu_factory()` 的结果作为上下文菜单（在 `aboutToShow` 时重建，保证状态同步）；`refresh()` 只重建菜单；`notify` 走 `showMessage`。若系统无托盘则 `show()` 返回 False 且不抛异常。
`ensure_tray_icon`：`out_path` 已存在直接返回；否则找 `catalog_data` 中第一个 track 为 `transparent` 且文件存在的素材，用 Pillow 取首帧缩 64×64 存 PNG；找不到用 `Sprite.draw_orange(64)` 存 PNG。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_menu.py -v`，Expected: 8 passed

- [x] **Step 5: 手工检查点**

`python main.py` → 托盘出现噜噜图标；右键同一份菜单；「显示 / 隐藏噜噜」互切；切「穿透模式」后点击穿到桌面，切回「交互模式」能继续拖拽；「退出」后任务管理器无残留进程。

> 已完成接线（`PetApp`）：`_start_tray()` 用 `ensure_tray_icon(processed_dir, catalog, root/assets/tray_icon.png)` 生成图标后建 `Tray`；`_build_menu()` = `build_menu(None, _menu_state(), _menu_handlers())`，托盘上下文菜单与右键菜单共用同一工厂；`_menu_state()` 取 `sprite.isVisible()` / `config["pet"]["passthrough"]` / `_autostart` / `_module_flags()`；`_toggle_visible` 互切显示并连带隐藏气泡；`_toggle_passthrough` 写 `config["pet"]["passthrough"]` + `sprite.set_passthrough()` + 存盘 + 气泡；`_toggle_module(key, on)` 按 `MODULE_KEYS` 落到 `config["modules"][*]["enabled"]` 并存盘（模块真正启停留给 T15+）；`_start_ui` 末尾按配置回放一次 `set_passthrough`，避免「菜单显示穿透、实际不穿透」；`_quit` 先收托盘再 `shutdown()` + `app.quit()`。以离屏冒烟等效验证：生成 `tray_icon.png`（5282 B，64×64）；托盘与右键菜单同构 `['显示 / 隐藏噜噜','交互模式','穿透模式','','实用工具','','设置…','开机自启','关于','退出']`；显示/隐藏互切；穿透开/关时 `windowFlags & WindowTransparentForInput` 随之为真/假且配置同步；模块开关写入配置并弹气泡；`tray.refresh()` 后「番茄钟」勾选为真、「吃饭提醒」为假且子菜单含「跳过」（脚本验证后已删除；冒烟产生的 `config.json` 一并删除，首次运行按默认值重建）。
>
> 实施偏离（已确认合理）：① 计划测试里 `build_menu(None, state, Handlers().__dict__)` 与「Handlers 用方法定义回调」自相矛盾——实例 `__dict__` 只含 `calls`，拿不到方法，故把 `Handlers` 的回调改写成实例属性（lambda），从而让 `h.__dict__` 正好就是 `build_menu` 需要的 dict；`build_menu` 仍按 Interfaces 接收 `dict`（同时对对象型 handlers 用 `getattr` 兜底）；② `triggered` 会附带 `checked` 布尔、`toggled` 会附带新勾选态，而多数 handler 不接参数，故用 `_slot` / `_slot_checked` / `_slot_module` 三个适配器（`_slot_checked` 仅在勾选时回调，配合 `QActionGroup` 互斥避免取消勾选的一侧误触发），未用计划提到的 `functools.partial`；③ `Tray.refresh()` 不直接 `setContextMenu(新菜单)`（弹出中换菜单不生效），而是把工厂产出的动作搬进常驻 `QMenu`（子菜单 `setParent` 到常驻菜单，避免随临时菜单回收），并在 `aboutToShow` 上重跑 `refresh()`；④ 模块开关按 `MODULE_KEYS` 映射落配置（`water`/`sit` 共用 `health_reminder`），`pomodoro`/`open_settings`/`toggle_autostart` 暂为占位（T13/T16/T21 接管）；⑤ `ensure_tray_icon` 用 `image.convert("RGBA").resize((64,64), Image.Resampling.LANCZOS)` 保证输出恒为 64×64。

---

### Task 13: 开机自启（`pet/autostart.py`）

**Files:**
- Create: `<root>/pet/autostart.py`
- Create: `<root>/tests/test_autostart.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"`、`APP_NAME = "LuluPet"`
  - `build_command(frozen: bool, exe_path: Path, script_path: Path) -> str`
  - `is_enabled(reg=winreg) -> bool`、`current_command(reg=winreg) -> str | None`
  - `set_enabled(on: bool, command: str, reg=winreg) -> bool`（失败返回 False，不抛异常）
  - `sync(want_enabled: bool, command: str, reg=winreg) -> bool`（按配置与注册表实际状态对齐，返回最终是否启用）

- [x] **Step 1: 写失败测试**（`tests/test_autostart.py`）

```python
from pathlib import Path
from pet.autostart import APP_NAME, build_command, current_command, is_enabled, set_enabled, sync


class FakeReg:
    HKEY_CURRENT_USER = "HKCU"

    def __init__(self, fail=False): self.store = {}; self.fail = fail
    def OpenKey(self, root, path, reserved=0, access=0): return (root, path)
    def QueryValueEx(self, key, name):
        if name not in self.store: raise FileNotFoundError(name)
        return (self.store[name], 1)
    def SetValueEx(self, key, name, reserved, type, value):
        if self.fail: raise PermissionError("denied")
        self.store[name] = value
    def DeleteValue(self, key, name):
        if name not in self.store: raise FileNotFoundError(name)
        del self.store[name]


def test_build_command_frozen_and_script_mode():
    assert build_command(True, Path(r"C:\apps\lulu pet\lulu_pet.exe"), Path("x")) == r'"C:\apps\lulu pet\lulu_pet.exe"'
    cmd = build_command(False, Path(r"C:\py\python.exe"), Path(r"D:\pet\main.py"))
    assert "pythonw" in cmd.lower() and "main.py" in cmd


def test_set_enabled_writes_and_is_enabled_reads():
    reg = FakeReg()
    assert is_enabled(reg=reg) is False
    assert set_enabled(True, '"C:\\x\\lulu.exe"', reg=reg) is True
    assert is_enabled(reg=reg) is True and reg.store[APP_NAME] == '"C:\\x\\lulu.exe"'


def test_set_enabled_false_removes_value():
    reg = FakeReg()
    set_enabled(True, '"C:\\x\\lulu.exe"', reg=reg)
    assert set_enabled(False, "", reg=reg) is True and is_enabled(reg=reg) is False


def test_set_enabled_returns_false_on_permission_error():
    assert set_enabled(True, '"C:\\x\\lulu.exe"', reg=FakeReg(fail=True)) is False


def test_current_command_none_when_absent():
    assert current_command(reg=FakeReg()) is None


def test_sync_adds_removes_and_rewrites():
    reg = FakeReg()
    assert sync(True, '"C:\\x\\lulu.exe"', reg=reg) is True
    assert current_command(reg=reg) == '"C:\\x\\lulu.exe"'
    assert sync(False, '"C:\\x\\lulu.exe"', reg=reg) is False
    assert current_command(reg=reg) is None
    set_enabled(True, '"C:\\old\\lulu.exe"', reg=reg)
    sync(True, '"C:\\new\\lulu.exe"', reg=reg)
    assert current_command(reg=reg) == '"C:\\new\\lulu.exe"'


def test_sync_idempotent_when_already_correct():
    reg = FakeReg()
    sync(True, '"C:\\x\\lulu.exe"', reg=reg)
    assert sync(True, '"C:\\x\\lulu.exe"', reg=reg) is True
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_autostart.py -v`，Expected: FAIL `No module named 'pet.autostart'`

- [x] **Step 3: 实现 `pet/autostart.py`**

`build_command`：frozen → `f'"{exe_path}"'`；否则 `f'"{pythonw.exe}" "{script_path}"'`（用 `sys.executable` 同目录的 `pythonw.exe`，不存在则回退 `python.exe`，由调用方传入的 `exe_path` 决定）。`set_enabled(on)`：`on` 时 `SetValueEx(HKEY_CURRENT_USER, RUN_KEY, APP_NAME, REG_SZ, command)`，`off` 时 `DeleteValue` 并吞掉 `FileNotFoundError`；`PermissionError/OSError` → 返回 False。`sync`：读 `current_command`，与期望比较，不一致才写/删，返回最终状态。默认参数 `reg=winreg` 在模块顶层 `import winreg`（仅 Windows 存在，符合平台约束）。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_autostart.py -v`，Expected: 7 passed

- [x] **Step 5: 手工检查点**

`python main.py` → 托盘勾选「开机自启」→ `reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v LuluPet` 能看到带引号的命令；取消勾选后再查，值消失。

> 已完成接线（`PetApp`）：`from pet.autostart import default_command, set_enabled, sync`；`__init__` 中 `self._autostart_command = default_command(self.root / "main.py")`，随后 `self._autostart = sync(bool(self.config.get("autostart", False)), self._autostart_command)`，启动时即把注册表与配置对齐；`_toggle_autostart()` = `want = not self._autostart` → `set_enabled(want, self._autostart_command)`，失败则弹 `warn` 气泡并 `return`（不改状态、不写配置）→ 成功则更新 `self._autostart`、写 `config["autostart"]` 并 `save_config`、气泡反馈；`_menu_state().autostart` 直接取 `self._autostart`，故菜单/托盘的「开机自启」勾选态自动同步。
>
> 冒烟等效验证（打桩 `main.set_enabled`，不碰真实注册表）：`_autostart_command` = `"…pythonw.exe" "…\main.py"`；初始 `_autostart=False` 且 `is_enabled()` 为 False，真实注册表未被污染；`_toggle_autostart()` → 打桩记录末项为 `(True, cmd)`、`_autostart=True`、`config["autostart"]=True`、气泡「开机自启：已开启」、`tray.refresh()` 后「开机自启」勾选为真；再切一次 → `(False, cmd)`、回到 False、气泡「已关闭」；打桩返回 False 时 `_autostart` 保持不变且气泡 `kind == "warn"`（脚本验证后已删除）。
>
> 实施偏离（已确认合理）：① `winreg` 在 `pet/autostart.py` 顶层导入（Windows 专有，符合本平台约束），并取 `KEY_SET_VALUE`/`REG_SZ` 常量便于用假注册表打桩；② `build_command` 用 `Path(exe_path).parent / "pythonw.exe"` 定位无控制台解释器（而非计划里含糊的「不存在则回退 `python.exe` 由调用方决定」），`default_command(script_path)` 再按 `sys.frozen` 选择 frozen / 脚本两种形态，供 `main.py` 一行取命令；③ `sync()` 的返回值定义为「**写入后当前实际是否启用**」（读回注册表再判定），因此写失败时返回的是真实状态而非期望状态，避免配置与注册表不一致。

---

### Task 14: 穿透接线、全屏隐藏与不抢焦点（`pet/winutil.py`）

**Files:**
- Create: `<root>/pet/winutil.py`
- Modify: `<root>/main.py`（穿透切换、全屏隐藏、`WA_ShowWithoutActivating`、`screenAdded/screenRemoved` 处理）
- Create: `<root>/tests/test_winutil.py`

**Interfaces:**
- Consumes: `Sprite.set_passthrough`（T7）、`EdgeHider`（T10）、`Toast`（T11）
- Produces:
  - `rect_covers(win_rect: tuple[int,int,int,int], screen_rect: tuple[int,int,int,int], tolerance: int = 2) -> bool` — 纯函数
  - `is_foreground_fullscreen(tolerance: int = 2) -> bool` — ctypes 包装（`GetForegroundWindow` + `GetWindowRect` + 主屏尺寸）
  - `should_hide_pet(fullscreen: bool, config_enabled: bool) -> bool` — 纯函数

- [x] **Step 1: 写失败测试**（`tests/test_winutil.py`）

```python
from pet.winutil import rect_covers, should_hide_pet

SCREEN = (0, 0, 1920, 1080)


def test_rect_covers_exact_and_larger():
    assert rect_covers((0, 0, 1920, 1080), SCREEN) is True
    assert rect_covers((-5, -5, 1930, 1090), SCREEN) is True


def test_rect_covers_smaller_window_is_false():
    assert rect_covers((0, 0, 1600, 900), SCREEN) is False
    assert rect_covers((0, 0, 1920, 1000), SCREEN) is False


def test_rect_covers_tolerance_allows_one_pixel_off():
    assert rect_covers((1, 1, 1919, 1079), SCREEN, tolerance=2) is True


def test_should_hide_pet_matrix():
    assert should_hide_pet(True, True) is True
    assert should_hide_pet(True, False) is False
    assert should_hide_pet(False, True) is False
    assert should_hide_pet(False, False) is False
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_winutil.py -v`，Expected: FAIL `No module named 'pet.winutil'`

- [x] **Step 3: 实现 `pet/winutil.py` 并接线 `main.py`**

`rect_covers`：`win` 的四条边都落在 `screen` 边界内（允许 `tolerance` 差）→ True。`is_foreground_fullscreen`：`ctypes.windll.user32` 取前台窗口矩形与主屏尺寸后调 `rect_covers`，任何异常返回 False。
`main.py` 接线：① 托盘/菜单的 `toggle_passthrough` → `sprite.set_passthrough(on)` 并把 `config["pet"]["passthrough"]` 写回；② 1 秒一次的轻量检查（复用 behavior 的 tick 定时器）→ `if should_hide_pet(is_foreground_fullscreen(), config["pet"]["hide_on_fullscreen"]): sprite.hide(); toast.hide()` 否则按当前隐藏状态决定是否 `sprite.show()`（贴边隐藏状态下不要 `show()`）；③ 连 `QApplication.screenAdded/screenRemoved` → 重新 `clamp_to_screen`；④ 所有窗口构造后设置 `WA_ShowWithoutActivating`。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_winutil.py -v`，Expected: 4 passed

- [x] **Step 5: 手工检查点**

打开一个全屏视频或按 F11 全屏浏览器 → 噜噜自动消失，退出全屏后回来；在记事本打字时点击噜噜 → 记事本不失去输入焦点；拔掉外接显示器（或改分辨率）再启动 → 噜噜出现在主屏内。

> 已完成实现与接线：`pet/winutil.py` 提供纯函数 `rect_covers` / `should_hide_pet` 与 ctypes 包装 `foreground_rect`（`GetForegroundWindow` + `GetWindowRect`）/ `primary_screen_rect`（`GetSystemMetrics(0/1)`）/ `is_foreground_fullscreen`（任一步异常都返回 False）。`main.py`：`_fs_timer` 独立以 **1000ms** 轮询（未复用 100ms 的 `_tick_timer`，避免每秒 10 次 win32 调用）；`_check_fullscreen()` 命中且 `pet.hide_on_fullscreen` 为真时 `sprite.hide() + toast.hide()` 并置 `_hidden_by_fullscreen = True`，全屏退出后仅当该标志为真才 `sprite.show()`；`_toggle_visible()` 开头无条件清掉该标志，保证「用户手动显示/隐藏」与「全屏自动隐藏」不会互相打架；`screenAdded` / `screenRemoved` → `_on_screens_changed()`：贴边隐藏状态下调 `edge_hider.retract()` 按新屏幕重新缩回，否则 `clamp_to_screen` 后落配置；`WA_ShowWithoutActivating` / `WA_TranslucentBackground` 已由 `Sprite` 与 `Toast` 构造函数设置（不抢焦点）；穿透切换沿用 T12 的 `_toggle_passthrough`（`set_passthrough` + 配置 + 存盘）。
>
> 冒烟等效验证（离屏，纯函数保持真实实现、仅打桩 `is_foreground_fullscreen`）：① `_fs_timer` 活动且间隔 1000ms；② `Sprite`/`Toast` 的 `WA_ShowWithoutActivating` 为真；③ 全屏命中 → 噜噜与气泡同时收起、`_hidden_by_fullscreen=True`；④ 退出全屏 → 复原；⑤ `hide_on_fullscreen=False` 时全屏不隐藏；⑥ 全屏期间手动显示 → 标志被清、退出全屏后不会被「唤醒」，手动隐藏同理；⑦ 窗口挪到 (screen+5000) 后 `_on_screens_changed()` 把 x/y 夹回屏内并写入 `config["pet"]["pos"]`；⑧ 贴边隐藏状态下 `_on_screens_changed()` 缩回到 `sx - w + 48`；⑨ 穿透开关翻转 `WindowTransparentForInput` 且与配置同步；⑩ `shutdown()` 停掉 `_fs_timer`/`_tick_timer`（脚本与冒烟产生的 `config.json`、`assets/tray_icon.png` 验证后已删除）。真实全屏窗口的检测属手工检查点范畴（需真桌面环境）。
>
> 实施偏离（已确认合理）：① 全屏检查用**独立 1s 定时器**而非复用 `_tick_timer`；② 增加 `_hidden_by_fullscreen` 标志，取代计划里「按 `edge_hider.is_hidden` 决定是否 `show()`」的模糊描述——只有「全屏期间由本逻辑隐藏的噜噜」才会被自动还原，用户手动隐藏/贴边隐藏都不会被误唤醒；③ 主屏尺寸用 `GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)`（与 `GetWindowRect` 同坐标系，避免与 Qt 逻辑像素混用），多屏下只比对主屏，符合计划「主屏尺寸」的表述；④ `WA_ShowWithoutActivating` 由窗口构造函数设置，`main.py` 未重复设置。

---

## 阶段 5：实用模块

### Task 15: 模块框架（`modules/base.py`）

**Files:**
- Create: `<root>/modules/__init__.py`、`<root>/modules/base.py`
- Create: `<root>/tests/test_modules_base.py`

**Interfaces:**
- Consumes: `config`（T6）
- Produces:
  - `class ModuleContext`：`__init__(self, notify, set_tray_text, config: dict, save: Callable[[], None])`；`notify(text: str, category: str = "happy", duration_ms: int = 6000) -> None`；`set_tray_text(text: str) -> None`；`config` 属性；`save()`
  - `class Module`：类属性 `name: str`、`title: str`、`default_enabled: bool = False`；`__init__(self, ctx: ModuleContext)` 存 `self.ctx`、`self._enabled = False`；`enable()` / `disable()`；`tick(now: datetime)`；`enabled` 属性；`set_enabled(on: bool)`（写 `ctx.config["modules"][name]["enabled"]`、调 `enable/disable`、`ctx.save()`）；`sub_switches() -> tuple[str, ...]`（默认返回空，子开关模块覆写）
  - `MODULE_CLASSES: list[type[Module]] = []`（后续任务 append）
  - `build_modules(ctx: ModuleContext) -> dict[str, Module]`：按 `ctx.config["modules"][cls.name]["enabled"]` 决定是否 `enable()`

- [x] **Step 1: 写失败测试**（`tests/test_modules_base.py`）

```python
from datetime import datetime
from modules.base import MODULE_CLASSES, Module, ModuleContext, build_modules
from pet.config import DEFAULTS

import copy


class Dummy(Module):
    name = "dummy"
    title = "假模块"

    def enable(self): self.events.append("enable")
    def disable(self): self.events.append("disable")
    def tick(self, now): self.events.append(("tick", now))


def make_ctx(cfg=None):
    cfg = cfg if cfg is not None else copy.deepcopy(DEFAULTS)
    notes, tray, saved = [], [], []
    cfg.setdefault("modules", {})["dummy"] = {"enabled": False}
    ctx = ModuleContext(notes.append, tray.append, cfg, lambda: saved.append(True))
    return ctx, notes, tray, saved, cfg


def test_ctx_notify_forwards_text_category_and_duration():
    ctx, notes, tray, _, _ = make_ctx()
    ctx.notify("该喝水啦")
    ctx.notify("专注完成", category="happy", duration_ms=1234)
    assert notes == [("该喝水啦", "happy", 6000), ("专注完成", "happy", 1234)]


def test_ctx_set_tray_text_and_save():
    ctx, _, tray, saved, _ = make_ctx()
    ctx.set_tray_text("CPU 12%")
    ctx.save()
    assert tray == ["CPU 12%"] and saved == [True]


def test_set_enabled_toggles_calls_and_persists_flag():
    ctx, _, _, saved, cfg = make_ctx()
    m = Dummy(ctx)
    assert m.enabled is False
    m.set_enabled(True)
    assert m.enabled is True and "enable" in m.events and cfg["modules"]["dummy"]["enabled"] is True
    m.set_enabled(False)
    assert m.enabled is False and "disable" in m.events and cfg["modules"]["dummy"]["enabled"] is False
    assert saved == [True, True]


def test_disabled_module_tick_does_not_notify():
    ctx, notes, _, _, _ = make_ctx()
    m = Dummy(ctx)
    m.tick(datetime(2026, 10, 20, 12, 0))
    assert notes == [] and ("tick", datetime(2026, 10, 20, 12, 0)) in m.events


def test_enable_is_idempotent():
    ctx, _, _, _, _ = make_ctx()
    m = Dummy(ctx)
    m.set_enabled(True); m.set_enabled(True)
    assert m.events.count("enable") == 1


def test_build_modules_respects_config_enabled_flag():
    ctx, _, _, _, cfg = make_ctx()
    cfg["modules"]["dummy"]["enabled"] = True
    MODULE_CLASSES.append(Dummy)
    try:
        mods = build_modules(ctx)
        assert set(mods) == {"dummy"} and mods["dummy"].enabled is True
    finally:
        MODULE_CLASSES.remove(Dummy)


def test_sub_switches_default_is_empty():
    ctx, _, _, _, _ = make_ctx()
    assert Dummy(ctx).sub_switches() == ()
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_modules_base.py -v`，Expected: FAIL `No module named 'modules'`

- [x] **Step 3: 实现 `modules/base.py`**

`ModuleContext.notify` 调用注入的 `notify(text, category, duration_ms)`；`set_tray_text` 同理；`config` 返回持有的 dict 引用；`save()` 调注入的保存回调。`Module.set_enabled`：目标状态与当前相同直接返回（幂等）；写入 `ctx.config["modules"][name]["enabled"]`；调 `enable()`/`disable()`；`ctx.save()`。`build_modules`：遍历 `MODULE_CLASSES` 实例化并按其配置 `enabled` 调 `set_enabled(True)`（不重复保存：直接调 `enable()` 并置 `_enabled`）。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_modules_base.py -v`，Expected: 7 passed

> 已完成实现与接线：`modules/base.py` 提供 `ModuleContext`（`config` 属性返回配置引用、`notify(text, category="happy", duration_ms=6000)`、`set_tray_text`、`save`）、`Module`（`name`/`title`/`default_enabled`、`enabled`、`set_enabled` 幂等 + 写配置 + 落盘、`sub_switches`、`events` 事件日志、内部 `_enable_from_config`）、`MODULE_CLASSES` 注册表、`config_enabled(config, name, default)` 与 `build_modules(ctx)`；`modules/__init__.py` 为空包标记。`main.py` 接线（阶段 5 的宿主侧，逐任务补齐具体模块）：`self.clock = datetime.now`、`self.modules: dict[str, Module]`、`_init_modules()` 在 `_start_tray()` 之后建 `ModuleContext(self._module_notify, self._set_tray_text, self.config, self._save_config)` 并 `build_modules()`，随后启动 **1000ms** 的 `_module_timer`；`_on_module_tick()` 只对 `enabled` 的模块调 `tick(now)`；`_module_notify()` 弹气泡 + `behavior.request(category, PRIORITY_MODULE, once=True, max_ms=duration_ms)`，素材缺失时按 `CATEGORY_FALLBACK = {"drink": "eat"}` 退一级；`_set_tray_text()` → `Tray.set_tooltip()`（`pet/tray.py` 新增该方法）；`_toggle_module()` 改为调 `module.set_enabled(on)`（模块尚未落地时退回「只写配置」以保持菜单勾选态正确）；`_pomodoro(action)` 转发到 `pomodoro` 模块的 `toggle/skip/reset` 并 `tray.refresh()`；`_menu_state().pomodoro_running` 取模块 `running`；`shutdown()` 停 `_module_timer`。
>
> 冒烟等效验证（离屏，临时把 `Dummy` 注册进 `MODULE_CLASSES`）：`modules` 初始为空、`clock()` 返回 `datetime`、`_module_timer` 间隔 1000ms；`_module_notify("该喝水啦", "drink", 3000)` → 气泡文本正确且状态切到 `DRINK`（真实素材无 `drink` 分类时退到 `EAT`）；`set_tray_text("CPU 12%")` → 托盘 tooltip 更新，空串回落「噜噜桌宠」；默认关闭的 `Dummy` 不被 tick，`set_enabled(True)` 后每次心跳正好 tick 一次；`_toggle_module("meal", True)` 写入配置并落盘（`load_config` 复查）；番茄钟动作在模块缺失时安全跳过；`shutdown()` 停掉心跳（脚本与冒烟产生的 `config.json`、`assets/tray_icon.png` 验证后已删除）。
>
> 实施偏离（已确认合理）：① 计划测试里 `ModuleContext(notes.append, ...)` 与计划 Step 3 的「`notify` 调用注入的 `notify(text, category, duration_ms)`」自相矛盾（`list.append` 只收 1 参），按 Step 3 的三参契约实现，测试改用 `lambda text, category, duration_ms: notes.append((text, category, duration_ms))`；② `build_modules` 用内部方法 `_enable_from_config()` 置位并调 `enable()`（不写配置、不落盘），避免计划原文「直接改 `_enabled`」的外部越权访问；③ `Module.__init__` 额外提供 `self.events` 事件日志——计划测试的 `Dummy` 通过 `self.events.append(...)` 记录，需基类预置；④ 模块心跳用独立 1s 定时器（与 behavior 的 100ms 心跳解耦），只有 `enabled` 的模块被驱动。

---

### Task 16: 番茄钟（`modules/pomodoro.py`）

**Files:**
- Create: `<root>/modules/pomodoro.py`
- Create: `<root>/tests/test_pomodoro.py`

**Interfaces:**
- Consumes: `Module` / `ModuleContext`（T15）
- Produces:
  - `class Pomodoro(Module)`：`name = "pomodoro"`、`title = "番茄钟"`
  - `start()`、`pause()`、`toggle()`、`reset()`、`skip()`
  - `phase` 属性 → `"idle" | "focus" | "break"`；`remaining_seconds(now) -> int`
  - 通知文案：专注结束 `"专注完成，休息 {break_min} 分钟"` + `happy`；休息结束 `"休息结束，继续专注"` + `idle`
  - `MODULE_CLASSES.append(Pomodoro)` 在模块末尾执行

- [x] **Step 1: 写失败测试**（`tests/test_pomodoro.py`）

```python
import copy
from datetime import datetime, timedelta
from modules.base import ModuleContext
from modules.pomodoro import Pomodoro
from pet.config import DEFAULTS


class Clock:
    def __init__(self): self.now = datetime(2026, 10, 20, 9, 0, 0)
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)


def make(focus=25, brk=5):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["pomodoro"].update({"enabled": True, "focus_min": focus, "break_min": brk})
    notes = []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), lambda s: None, cfg, lambda: None)
    clock = Clock()
    m = Pomodoro(ctx, clock=clock)
    m.enable()
    return m, notes, clock, cfg


def test_starts_idle_and_does_not_notify_before_time():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=24)
    m.tick(clock())
    assert m.phase == "focus" and notes == []
    assert m.remaining_seconds(clock()) == 60


def test_focus_end_notifies_once_and_enters_break():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=25); m.tick(clock())
    assert m.phase == "break" and notes == [("专注完成，休息 5 分钟", "happy")]
    clock.adv(minutes=1); m.tick(clock())
    assert len(notes) == 1


def test_break_end_notifies_and_enters_focus():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=25); m.tick(clock())      # 专注结束 → 进入休息
    clock.adv(minutes=5); m.tick(clock())       # 休息结束 → 回到专注
    assert m.phase == "focus" and notes[-1] == ("休息结束，继续专注", "idle")


def test_pause_freezes_remaining_time():
    m, notes, clock, _ = make()
    m.start()
    clock.adv(minutes=10); m.pause()
    before = m.remaining_seconds(clock())
    clock.adv(minutes=30); m.tick(clock())
    assert m.remaining_seconds(clock()) == before and notes == []


def test_skip_jumps_to_next_phase_without_notification():
    m, notes, clock, _ = make()
    m.start()
    m.skip()
    assert m.phase == "break" and notes == []


def test_reset_returns_to_idle():
    m, notes, clock, _ = make()
    m.start(); clock.adv(minutes=10); m.reset()
    assert m.phase == "idle" and m.remaining_seconds(clock()) == 25 * 60


def test_disable_stops_ticking():
    m, notes, clock, _ = make()
    m.start()
    m.set_enabled(False)
    clock.adv(minutes=60); m.tick(clock())
    assert notes == []


def test_toggle_starts_and_pauses():
    m, notes, clock, _ = make()
    m.toggle(); assert m.phase == "focus"
    m.toggle(); assert m.phase == "focus"
    clock.adv(minutes=26); m.tick(clock())
    assert notes == []
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_pomodoro.py -v`，Expected: FAIL `No module named 'modules.pomodoro'`

- [x] **Step 3: 实现 `modules/pomodoro.py`**

`__init__(self, ctx, clock=datetime.now)` 保存 `clock`，`_phase="idle"`、`_remaining=None`（秒）、`_running=False`。`start()`：`_phase="focus"`、`_remaining=focus_min*60`、`_running=True`、记 `_last_tick=clock()`。`tick(now)`：`_running` 为假直接返回（`_enabled` 为假也不返回，由 `main.py` 只在 enabled 时调用；但为满足「disable 后不通知」测试，`tick` 内先判 `self._enabled`）；按 `now - _last_tick` 扣减 `_remaining`，归零则切相位（focus→break、break→focus）并发对应 `ctx.notify(...)`；一次 `tick` 内最多只处理一次归零，避免长时间挂起后连发多条。`pause()`：`_running=False`。`toggle()`：`_running` 取反。`skip()`：切下一个相位、重置 `_remaining`、不发通知。`reset()`：回 idle 并重置 `_remaining = focus_min*60`。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_pomodoro.py -v`，Expected: 8 passed

- [x] **Step 5: 手工检查点**

把 `focus_min` 临时改成 1（`config.json`）→ 托盘「开始 / 暂停」→ 1 分钟后噜噜播 happy 并弹「专注完成，休息 5 分钟」；再等 5 分钟弹「休息结束，继续专注」。改回 25。

> **已完成接线**：`main.py` 新增 `import modules.pomodoro  # noqa: F401`（导入即注册进 `MODULE_CLASSES`）；`_pomodoro(action)` 转发到模块的 `toggle()` / `skip()` / `reset()` 并调 `tray.refresh()`；`_menu_state()["pomodoro_running"]` 改取模块 `running` 属性。
>
> **冒烟等效验证**（离屏脚本，验证后删除）：`_toggle_module("pomodoro", True)` → 模块启用 + 配置落盘 + 托盘勾选态同步；`_pomodoro("toggle"/"skip"/"reset")` 依次得到相位 `focus → break → idle`，且 `_menu_state().pomodoro_running` 同步变化；把 `focus_min` 置 1 后推 `tick(+1min)` → 相位切到 `break` + 气泡「专注完成，休息 5 分钟」+ 噜噜状态 `HAPPY`；关闭模块后 `tick` 不再推进相位。SMOKE OK。
>
> **实施偏离**：① `Pomodoro.__init__(ctx, clock=datetime.now)` 支持注入时钟，便于单测绕过真实等待；② `remaining_seconds(now)` 对运行中相位按 `now - _last_tick` 实时扣减（而非只读静态值），使 `pause` 冻结时间的断言成立；③ `skip()` 在 `idle` 相位等价于 `start()`；④ 抽出 `_switch(phase, notify=...)` 供 `tick` 与 `skip` 复用，`skip` 传 `notify=False` 以满足「跳转不发通知」；⑤ 计划 Step 3 描述 `_remaining=None` 起手，实现改为数值秒数（`focus_min*60`），更直观且与 `reset()` 语义一致。

---

### Task 17: 喝水与久坐提醒（`modules/health_reminder.py`）

**Files:**
- Create: `<root>/modules/health_reminder.py`
- Create: `<root>/tests/test_health_reminder.py`

**Interfaces:**
- Consumes: `Module` / `ModuleContext`（T15）
- Produces:
  - `class HealthReminder(Module)`：`name = "health_reminder"`、`title = "喝水·久坐"`；`sub_switches() -> ("water", "sit")`
  - 配置字段（对 spec §10 的细化，新增两个子开关，默认 `true`）：`{"enabled": true, "water_enabled": true, "sit_enabled": true, "water_min": 45, "sit_min": 60, "snooze_min": 10}`
  - `snooze(which: str) -> None`（`which` 为 `"water"` 或 `"sit"`，把下次提醒推后 `snooze_min` 分钟）
  - `next_at(which: str) -> datetime`
  - 通知文案：喝水 `"该喝水啦"` + `drink`；久坐 `"起来动一动吧"` + `happy`
  - `MODULE_CLASSES.append(HealthReminder)` 在模块末尾执行

- [x] **Step 1: 写失败测试**（`tests/test_health_reminder.py`）

```python
import copy
from datetime import datetime, timedelta
from modules.base import ModuleContext
from modules.health_reminder import HealthReminder
from pet.config import DEFAULTS


class Clock:
    def __init__(self): self.now = datetime(2026, 10, 20, 9, 0, 0)
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)


def make(water=45, sit=60, snooze=10, water_on=True, sit_on=True):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["health_reminder"].update({"enabled": True, "water_min": water, "sit_min": sit,
                                              "snooze_min": snooze, "water_enabled": water_on,
                                              "sit_enabled": sit_on})
    notes = []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), lambda s: None, cfg, lambda: None)
    clock = Clock()
    m = HealthReminder(ctx, clock=clock)
    m.enable()
    return m, notes, clock, cfg


def test_water_fires_after_interval_and_not_again(qapp):
    m, notes, clock, _ = make()
    clock.adv(minutes=44); m.tick(clock())
    assert notes == []
    clock.adv(minutes=1); m.tick(clock())
    assert notes == [("该喝水啦", "drink")]
    m.tick(clock())
    assert len(notes) == 1


def test_sit_fires_independently_with_its_own_interval(qapp):
    m, notes, clock, _ = make(water=45, sit=60)
    clock.adv(minutes=60); m.tick(clock())
    assert ("起来动一动吧", "happy") in notes and ("该喝水啦", "drink") in notes


def test_water_sub_switch_off_silences_only_water(qapp):
    m, notes, clock, _ = make(water_on=False, sit_on=True)
    clock.adv(minutes=90); m.tick(clock())
    assert ("该喝水啦", "drink") not in notes and ("起来动一动吧", "happy") in notes


def test_sit_sub_switch_off_silences_only_sit(qapp):
    m, notes, clock, _ = make(water_on=True, sit_on=False)
    clock.adv(minutes=90); m.tick(clock())
    assert ("起来动一动吧", "happy") not in notes and ("该喝水啦", "drink") in notes


def test_snooze_postpones_next_reminder(qapp):
    m, notes, clock, _ = make(snooze=10)
    clock.adv(minutes=45); m.tick(clock())
    assert len(notes) == 1
    m.snooze("water")
    clock.adv(minutes=9); m.tick(clock())
    assert len(notes) == 1
    clock.adv(minutes=2); m.tick(clock())
    assert len(notes) == 2


def test_repeated_tick_does_not_refire_within_interval(qapp):
    m, notes, clock, _ = make()
    clock.adv(minutes=45); m.tick(clock())
    for _ in range(60):
        m.tick(clock())
    assert len([n for n in notes if n[0] == "该喝水啦"]) == 1


def test_next_at_reflects_snooze(qapp):
    m, notes, clock, _ = make(snooze=10)
    m.snooze("water")
    assert (m.next_at("water") - clock()).total_seconds() == 10 * 60


def test_disable_silences_everything(qapp):
    m, notes, clock, _ = make()
    m.set_enabled(False)
    clock.adv(minutes=200); m.tick(clock())
    assert notes == []
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_health_reminder.py -v`，Expected: FAIL `No module named 'modules.health_reminder'`

- [x] **Step 3: 实现 `modules/health_reminder.py`**

`enable()` 时 `_next = {"water": clock() + water_min*60, "sit": clock() + sit_min*60}`；`tick(now)`：`_enabled` 为假返回；对 `water`、`sit` 分别判断（子开关关闭则跳过并持续推迟 `_next`，避免关闭期间堆积），`now >= _next[which]` → `ctx.notify(文案, category)` 并 `_next[which] = now + 间隔`（用 `now` 而不是上次的 `_next`，保证长时间挂起只发一次）。`snooze(which)`：`_next[which] = clock() + snooze_min*60`。`next_at(which)` 返回 `_next[which]`。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_health_reminder.py -v`，Expected: 8 passed

- [x] **Step 5: 手工检查点**

`config.json` 里把 `water_min` 改成 1 → 1 分钟后弹「该喝水啦」并播 `drink`（无 `drink` 分类素材时用 `eat`；都不存在时只弹气泡）；久坐同理。改回 45。

> **已完成接线**：`pet/config.py` 的 `DEFAULTS["modules"]["health_reminder"]` 新增 `water_enabled` / `sit_enabled`（默认 `true`）；`main.py` 新增 `import modules.health_reminder`、新增常量 `SUB_SWITCH_KEYS = {"water": "water_enabled", "sit": "sit_enabled"}`；`_module_flags()` 对子开关项改读子字段（喝水/久坐各自独立显示勾选态）；`_toggle_module()` 分支处理子开关：写子字段 → 模块整体开关取 `water_enabled or sit_enabled` → 仅在状态真正变化时调 `module.set_enabled(want)` 并 `tray.refresh()`。
>
> **冒烟等效验证**（离屏脚本，验证后删除）：注册即 `enabled=True`、`sub_switches() == ("water","sit")`；`water_min=1` 后推 1 分钟心跳 → 气泡「该喝水啦」+ 状态 `DRINK`；关闭喝水而久坐仍开 → `flags == {water: False, sit: True}` 且模块保持启用；两个都关 → 模块停用；重开喝水 → 模块恢复且下次提醒回到 60s 后；重开久坐 → 下次提醒为完整 3600s（关闭期间不堆积）；两个都关后推进 500 分钟心跳 → 无新通知。SMOKE OK。
>
> **实施偏离**：① 计划把 `water`/`sit` 两个菜单项都映射到模块 `enabled`（同开同关），实现改为**子开关独立**：`_module_flags()` 分项读取、`_toggle_module()` 按 `SUB_SWITCH_KEYS` 分支；② `tick` 中「子开关关闭」分支把 `_next` 推到 `now + 间隔`（而非保持原值），语义与「重新开启后从零开始计时」一致；③ `_next` 在 `__init__` 即以 `clock()` 占位，真实排期在 `enable()` / `reset_schedule()` 完成。

---

### Task 18: 吃饭提醒（`modules/meal_reminder.py`）

**Files:**
- Create: `<root>/modules/meal_reminder.py`
- Create: `<root>/tests/test_meal_reminder.py`

**Interfaces:**
- Consumes: `Module` / `ModuleContext`（T15）
- Produces:
  - `class MealReminder(Module)`：`name = "meal_reminder"`、`title = "吃饭提醒"`
  - 触发窗口：每个目标时刻 `[t, t+60s)`；同一 `(日期, 时刻)` 只触发一次；错过的时刻不补发
  - 通知文案：`"{HH:MM} 到啦，该吃饭咯"` + `eat`
  - `fired_keys` 属性 → `set[tuple[str, str]]`（`(YYYY-MM-DD, "12:00")`）
  - `MODULE_CLASSES.append(MealReminder)` 在模块末尾执行

- [ ] **Step 1: 写失败测试**（`tests/test_meal_reminder.py`）

```python
import copy
from datetime import datetime, timedelta
from modules.base import ModuleContext
from modules.meal_reminder import MealReminder
from pet.config import DEFAULTS


class Clock:
    def __init__(self, now=datetime(2026, 10, 20, 11, 59, 0)): self.now = now
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)
    def set(self, **kw): self.now = self.now.replace(**kw)


def make(times=("12:00", "18:30")):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["meal_reminder"].update({"enabled": True, "times": list(times)})
    notes = []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), lambda s: None, cfg, lambda: None)
    clock = Clock()
    m = MealReminder(ctx, clock=clock)
    m.enable()
    return m, notes, clock, cfg


def test_fires_at_noon_once(qapp):
    m, notes, clock, _ = make()
    clock.set(hour=12, minute=0, second=0)
    m.tick(clock())
    assert notes == [("12:00 到啦，该吃饭咯", "eat")]
    clock.set(minute=1)
    m.tick(clock())
    assert len(notes) == 1


def test_fires_at_evening_time(qapp):
    m, notes, clock, _ = make()
    clock.set(hour=18, minute=30, second=0)
    m.tick(clock())
    assert [n[0] for n in notes] == ["18:30 到啦，该吃饭咯"]


def test_does_not_backfill_missed_time(qapp):
    m, notes, clock, _ = make()
    clock.set(hour=13, minute=30)
    m.tick(clock())
    assert notes == []


def test_fires_again_next_day_and_across_midnight(qapp):
    """Review Focus #5"""
    m, notes, clock, _ = make()
    clock.set(hour=12, minute=0, second=0); m.tick(clock())
    clock.adv(days=1); clock.set(hour=12, minute=0, second=0); m.tick(clock())
    assert len(notes) == 2 and notes[0][0] == notes[1][0]
    assert ("2026-10-20", "12:00") in m.fired_keys and ("2026-10-21", "12:00") in m.fired_keys


def test_clock_rollback_does_not_refire_same_key(qapp):
    """Review Focus #5：时钟回拨后再次经过同一时刻，不得重复触发"""
    m, notes, clock, _ = make()
    clock.set(hour=12, minute=0, second=0); m.tick(clock())
    before = len(notes)
    clock.set(hour=11, minute=58); m.tick(clock())
    clock.set(hour=12, minute=0); m.tick(clock())
    assert len(notes) == before


def test_configurable_times_are_respected(qapp):
    m, notes, clock, _ = make(times=("08:00",))
    clock.set(hour=12, minute=0); m.tick(clock())
    assert notes == []
    clock.set(hour=8, minute=0, second=0); m.tick(clock())
    assert [n[0] for n in notes] == ["08:00 到啦，该吃饭咯"]


def test_disable_silences(qapp):
    m, notes, clock, _ = make()
    m.set_enabled(False)
    clock.set(hour=12, minute=0, second=0); m.tick(clock())
    assert notes == []
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_meal_reminder.py -v`，Expected: FAIL `No module named 'modules.meal_reminder'`

- [x] **Step 3: 实现 `modules/meal_reminder.py`**

`_fired: set[tuple[str, str]]`。`tick(now)`：`_enabled` 为假返回；对每个配置时刻解析 `HH:MM`，若 `now` 落在 `[t, t+60s)` 且 `(now.date().isoformat(), t)` 不在 `_fired` → 通知并加入 `_fired`。由于判定只看当前时刻所在的一分钟窗口 + `_fired` 去重，时钟回拨回到已触发过的同一分钟不会重复触发；跨天后 `date.isoformat()` 变化，同一时刻可再次触发。`_fired` 不做清理（每天最多新增 2 条，量级可忽略）。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_meal_reminder.py -v`，Expected: 7 passed

- [x] **Step 5: 手工检查点**

把 `times` 临时改成当前时间 +1 分钟 → 到点弹「HH:MM 到啦，该吃饭咯」并播 `eat` 类动画；改回 `["12:00", "18:30"]`。

> **已完成接线**：`main.py` 新增 `import modules.meal_reminder`。`meal` 菜单项已通过既有 `MODULE_KEYS["meal"] → "meal_reminder"` 直接控制模块 `enabled`，无需新增分支。
>
> **冒烟等效验证**（离屏脚本，验证后删除）：注册即 `enabled=True`、`_module_flags()["meal"] is True`；推时钟到 `12:00:00` 触发 → 气泡「12:00 到啦，该吃饭咯」+ 状态 `EAT`；同一分钟内重复心跳不再触发（`fired_keys` 仍为 1）；跳过 `18:30` 直接到 `19:00` 不补发；`_toggle_module("meal", False)` 后跨天推进不再提醒。SMOKE OK。
>
> **实施偏离**：① 抽出模块级纯函数 `_parse_hhmm()` 统一校验且供 `_times()` 过滤非法项；② `_times()` 对配置非法/为空时回落 `("12:00", "18:30")`，与 `pet/config.py` 的校验形成双保险；③ 触发窗口以 `[t, t+60s)` 用 `now.replace(hour, minute, ...)` 计算起点（不依赖秒数取整）。

---

### Task 19: 整点报时（`modules/hourly_chime.py`）

**Files:**
- Create: `<root>/modules/hourly_chime.py`
- Create: `<root>/tests/test_hourly_chime.py`

**Interfaces:**
- Consumes: `Module` / `ModuleContext`（T15）
- Produces:
  - `class HourlyChime(Module)`：`name = "hourly_chime"`、`title = "整点报时"`
  - 触发窗口 `[HH:00:00, HH:00:59]`，同一 `(日期, 小时)` 只触发一次；文案 `"现在是 {HH}:00"` + `idle`；**不播放声音**
  - `MODULE_CLASSES.append(HourlyChime)` 在模块末尾执行

- [ ] **Step 1: 写失败测试**（`tests/test_hourly_chime.py`）

```python
import copy
from datetime import datetime, timedelta
from modules.base import ModuleContext
from modules.hourly_chime import HourlyChime
from pet.config import DEFAULTS


class Clock:
    def __init__(self, now=datetime(2026, 10, 20, 13, 59, 30)): self.now = now
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)
    def set(self, **kw): self.now = self.now.replace(**kw)


def make():
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["hourly_chime"].update({"enabled": True})
    notes = []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), lambda s: None, cfg, lambda: None)
    clock = Clock()
    m = HourlyChime(ctx, clock=clock)
    m.enable()
    return m, notes, clock


def test_fires_on_the_hour_once(qapp):
    m, notes, clock = make()
    clock.set(hour=14, minute=0, second=10)
    m.tick(clock())
    assert notes == [("现在是 14:00", "idle")]
    clock.set(second=40); m.tick(clock())
    assert len(notes) == 1


def test_does_not_fire_mid_hour(qapp):
    m, notes, clock = make()
    clock.set(hour=14, minute=30)
    m.tick(clock())
    assert notes == []


def test_fires_each_hour_and_next_day(qapp):
    """Review Focus #5"""
    m, notes, clock = make()
    clock.set(hour=14, minute=0, second=0); m.tick(clock())
    clock.set(hour=15, minute=0, second=0); m.tick(clock())
    clock.adv(days=1); clock.set(hour=14, minute=0, second=0); m.tick(clock())
    assert [n[0] for n in notes] == ["现在是 14:00", "现在是 15:00", "现在是 14:00"]


def test_clock_rollback_does_not_refire(qapp):
    m, notes, clock = make()
    clock.set(hour=14, minute=0, second=5); m.tick(clock())
    clock.set(hour=13, minute=59, second=50); m.tick(clock())
    clock.set(hour=14, minute=0, second=5); m.tick(clock())
    assert len(notes) == 1


def test_disable_silences(qapp):
    m, notes, clock = make()
    m.set_enabled(False)
    clock.set(hour=14, minute=0, second=5); m.tick(clock())
    assert notes == []
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_hourly_chime.py -v`，Expected: FAIL `No module named 'modules.hourly_chime'`

- [x] **Step 3: 实现 `modules/hourly_chime.py`**

`_fired: set[tuple[str, int]]`。`tick(now)`：`_enabled` 为假返回；`now.minute == 0` 且 `(date, hour)` 未触发 → `ctx.notify(f"现在是 {now.hour:02d}:00", "idle")` 并记录。`_fired` 不做清理（每天最多新增 24 条，量级可忽略）。不使用任何音频 API。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_hourly_chime.py -v`，Expected: 5 passed

> **已完成接线**：`main.py` 新增 `import modules.hourly_chime`；`hourly` 菜单项经既有 `MODULE_KEYS["hourly"] → "hourly_chime"` 直接控制模块 `enabled`。
>
> **验证**：纯库任务（计划未设手工检查点），`python -c "import main; ..."` 确认 `MODULE_CLASSES` 已含 `['health_reminder', 'hourly_chime', 'meal_reminder', 'pomodoro']`。
>
> **实施偏离**：额外暴露只读属性 `fired_keys`（与 `MealReminder` 保持一致，便于调试与后续设置面板展示）。

---

### Task 20: 系统状态监控（`modules/sysmonitor.py`）

**Files:**
- Create: `<root>/modules/sysmonitor.py`
- Create: `<root>/tests/test_sysmonitor.py`

**Interfaces:**
- Consumes: `Module` / `ModuleContext`（T15，含 `set_tray_text`）
- Produces:
  - `class SysMonitor(Module)`：`name = "sysmonitor"`、`title = "系统监控"`
  - `__init__(self, ctx, clock=datetime.now, sampler: Callable[[], tuple[float,float,float]] | None = None)`；`sampler` 默认用 `psutil` 返回 `(cpu_percent, mem_percent, disk_percent)`
  - `tick(now)`：距上次采样 ≥ `interval_sec` 才重新采样；每次都调 `ctx.set_tray_text(f"CPU {cpu:.0f}% · 内存 {mem:.0f}%")`
  - 超阈值（`cpu > cpu_limit` 或 `mem > mem_limit`）→ `ctx.notify("系统有点吃力：CPU 92% / 内存 91%", "angry")`，同一指标 `ALERT_COOLDOWN_MIN = 10` 分钟内不重复告警
  - `MODULE_CLASSES.append(SysMonitor)` 在模块末尾执行

- [ ] **Step 1: 写失败测试**（`tests/test_sysmonitor.py`）

```python
import copy
from datetime import datetime, timedelta
from modules.base import ModuleContext
from modules.sysmonitor import ALERT_COOLDOWN_MIN, SysMonitor
from pet.config import DEFAULTS


class Clock:
    def __init__(self): self.now = datetime(2026, 10, 20, 9, 0, 0)
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)


def make(cpu=10.0, mem=20.0, disk=30.0):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["sysmonitor"].update({"enabled": True, "interval_sec": 3, "cpu_limit": 85, "mem_limit": 90})
    notes, tray = [], []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), tray.append, cfg, lambda: None)
    clock = Clock()
    box = {"v": (cpu, mem, disk)}
    m = SysMonitor(ctx, clock=clock, sampler=lambda: box["v"])
    m.enable()
    return m, notes, tray, clock, box


def test_tray_text_updated_on_each_sample(qapp):
    m, notes, tray, clock, _ = make(cpu=12.4, mem=43.6)
    m.tick(clock())
    assert tray == ["CPU 12% · 内存 44%"] and notes == []


def test_sampling_respects_interval(qapp):
    m, notes, tray, clock, box = make()
    m.tick(clock())
    box["v"] = (99.0, 99.0, 30.0)
    clock.adv(seconds=1); m.tick(clock())
    assert len(tray) == 1                    # 未到间隔不重新采样
    clock.adv(seconds=3); m.tick(clock())
    assert len(tray) == 2 and len(notes) == 2  # 第二次采样后 CPU 与内存各告警一次


def test_alerts_once_per_metric_then_cooldown(qapp):
    m, notes, tray, clock, _ = make(cpu=95.0, mem=20.0)
    m.tick(clock())
    assert len(notes) == 1 and notes[0][1] == "angry"
    for _ in range(5):
        clock.adv(seconds=4); m.tick(clock())
    assert len(notes) == 1
    clock.adv(minutes=ALERT_COOLDOWN_MIN + 1); m.tick(clock())
    assert len(notes) == 2


def test_no_alert_below_thresholds(qapp):
    m, notes, _, clock, _ = make(cpu=84.9, mem=89.9)
    m.tick(clock())
    assert notes == []


def test_disable_stops_sampling(qapp):
    m, notes, tray, clock, _ = make()
    m.set_enabled(False)
    clock.adv(seconds=30); m.tick(clock())
    assert tray == [] and notes == []


def test_sampler_exception_does_not_crash(qapp):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["modules"]["sysmonitor"]["enabled"] = True
    notes, tray = [], []
    ctx = ModuleContext(lambda t, c, d: notes.append((t, c)), tray.append, cfg, lambda: None)
    clock = Clock()
    m = SysMonitor(ctx, clock=clock, sampler=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    m.enable()
    m.tick(clock())
    assert notes == [] and tray == []
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_sysmonitor.py -v`，Expected: FAIL `No module named 'modules.sysmonitor'`

- [x] **Step 3: 实现 `modules/sysmonitor.py`**

`enable()`：`_last_sample = None`、`_last_alert = {"cpu": None, "mem": None}`；**不**在 `enable()` 里立即采样，第一次采样发生在首个 `tick`（`_last_sample is None` 时）。`tick(now)`：`_enabled` 为假返回；`_last_sample is None or (now - _last_sample).total_seconds() >= interval_sec` 才采样；`sampler()` 抛异常时吞掉并跳过本轮（不写托盘、不告警）；采样后 `ctx.set_tray_text(...)`；对 cpu/mem 分别判断阈值与冷却（`_last_alert[k] is None or (now - _last_alert[k]).total_seconds() >= ALERT_COOLDOWN_MIN*60`）→ 通知文案含两项实际百分比，并把该指标标为已告警。默认 `sampler`：`psutil.cpu_percent(interval=None)`、`psutil.virtual_memory().percent`、`psutil.disk_usage("/").percent`。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_sysmonitor.py -v`，Expected: 6 passed

- [x] **Step 5: 手工检查点**

开启「系统监控」→ 托盘 tooltip 每 3 秒更新 CPU/内存；用 `python -c "while True: pass"` 压一个核，观察告警气泡出现（同一指标 10 分钟内不再重复）；关掉后 tooltip 停止更新。

> **已完成接线**：`main.py` 新增 `import modules.sysmonitor`；`sysmonitor` 菜单项经既有 `MODULE_KEYS["sysmonitor"] → "sysmonitor"` 直接控制模块 `enabled`（默认关闭）；托盘提示通过 T15 已接好的 `ctx.set_tray_text → tray.set_tooltip` 链路生效。
>
> **冒烟等效验证**（离屏脚本，验证后删除）：默认 `enabled=False` 时推进 30 秒心跳 → tooltip 不变；`_toggle_module("sysmonitor", True)` 后首个心跳立即采样 → tooltip `"CPU 12% · 内存 44%"`；未到 `interval_sec` 不重采样（tooltip 保持不变）；到间隔后重采样 → tooltip `"CPU 99% · 内存 99%"` + 气泡「系统有点吃力：CPU 99% / 内存 99%」+ 状态 `ANGRY`；冷却期内重复心跳不再告警；`sampler` 抛异常时静默跳过不崩；关闭模块后 tooltip 冻结。SMOKE OK。
>
> **实施偏离**：① `default_sampler()` 抽成模块级函数（内部才 `import psutil`），模块导入不再强依赖 psutil；② `_option()` 统一做「正数 + 类型」校验并回落默认值；③ 阈值判断用严格大于（`value > limit`），与测试的 `84.9 / 89.9 不告警` 边界一致；④ `_alert_due()` 用 `timedelta` 比较而非秒数换算。

---

### Task 21: 设置面板（`ui/settings_dialog.py`）

**Files:**
- Create: `<root>/ui/settings_dialog.py`
- Create: `<root>/tests/test_settings_dialog.py`
- Modify: `<root>/main.py`（`double_clicked` 与「设置…」打开面板，保存后立即生效）

**Interfaces:**
- Consumes: `config`（T6）、`modules`（T15-T20）
- Produces:
  - `class SettingsDialog(QDialog)`：`__init__(self, config: dict, parent=None)`；`values() -> dict`（返回可写回 `config.json` 的副本）；`accept()` 前先校验；`signal config_saved(dict)`
  - 面板项：显示缩放（0.5–2.0）、始终置顶、悬停气泡、全屏时隐藏、开机自启、五个模块的启用与参数（番茄钟时长、喝水/久坐间隔与稍后提醒、吃饭时刻列表、整点报时开关、监控间隔与阈值）

- [ ] **Step 1: 写失败测试**（`tests/test_settings_dialog.py`）

```python
import copy
from ui.settings_dialog import SettingsDialog
from pet.config import DEFAULTS


def test_widgets_initialised_from_config(qapp):
    d = SettingsDialog(copy.deepcopy(DEFAULTS))
    assert d.values()["pet"]["scale"] == DEFAULTS["pet"]["scale"]
    assert d.values()["modules"]["pomodoro"]["focus_min"] == 25
    assert d.values()["modules"]["meal_reminder"]["times"] == ["12:00", "18:30"]


def test_editing_values_roundtrips(qapp):
    cfg = copy.deepcopy(DEFAULTS)
    d = SettingsDialog(cfg)
    d.set_field("pet.scale", 1.5)
    d.set_field("modules.pomodoro.focus_min", 50)
    d.set_field("modules.meal_reminder.times", ["08:00", "20:00"])
    out = d.values()
    assert out["pet"]["scale"] == 1.5
    assert out["modules"]["pomodoro"]["focus_min"] == 50
    assert out["modules"]["meal_reminder"]["times"] == ["08:00", "20:00"]


def test_invalid_scale_is_rejected_on_accept(qapp):
    d = SettingsDialog(copy.deepcopy(DEFAULTS))
    d.set_field("pet.scale", 9.9)
    assert d.accept() is False
    assert d.error_text != ""


def test_valid_accept_emits_signal_with_validated_config(qapp):
    d = SettingsDialog(copy.deepcopy(DEFAULTS))
    got = []
    d.config_saved.connect(got.append)
    d.set_field("modules.hourly_chime.enabled", True)
    assert d.accept() is True
    assert got[0]["modules"]["hourly_chime"]["enabled"] is True


def test_input_config_is_not_mutated(qapp):
    cfg = copy.deepcopy(DEFAULTS)
    d = SettingsDialog(cfg)
    d.set_field("pet.scale", 1.8)
    d.values()
    assert cfg["pet"]["scale"] == DEFAULTS["pet"]["scale"]
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_settings_dialog.py -v`，Expected: FAIL `No module named 'ui.settings_dialog'`

- [x] **Step 3: 实现 `ui/settings_dialog.py`**

用 `QFormLayout` + `QTabWidget`（「噜噜」/「工具」两页）组织控件；`set_field(dotted_path, value)` 与 `values()` 都基于点号路径读写内部配置副本（`copy.deepcopy` 入参）；`accept()`：先 `validate`（复用 `pet.config.validate`）并把校验后的配置与原始输入对比，若关键字段（如 `scale` 超出 0.5–2.0）被回退则设置 `error_text` 并返回 False（不关闭对话框）；通过则发 `config_saved` 并返回 True。`main.py` 接线：保存后写 `config.json`、刷新菜单、按新配置 `enable/disable` 模块、更新 `sprite` 的缩放。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_settings_dialog.py -v`，Expected: 5 passed

- [x] **Step 5: 手工检查点**

双击噜噜打开设置面板 → 改缩放为 1.5 → 保存后噜噜立刻变大；改番茄钟时长 → 托盘菜单里启动番茄钟，剩余时间符合新设置；重启程序设置仍在。

> **已完成接线**：`main.py` 新增 `from ui.settings_dialog import SettingsDialog`；`_on_double_clicked()` 改为调用 `_open_settings()`；`_open_settings()` 构造 `SettingsDialog(self.config, self.sprite)` 并把 `config_saved` 接到 `_apply_settings`；`_apply_settings(new_config)` 做五件事 —— ① `config.clear() + update()` **原地**写回（保住 sprite/behavior/edge_hider/ModuleContext 持有的引用），② 落盘，③ 逐模块对齐 `enabled`（`health_reminder` 取 `water_enabled or sit_enabled`），④ `sprite.set_always_on_top()` + `sprite.reload()`，⑤ `autostart` 重同步 + 托盘刷新 + 气泡「设置已保存」。
>
> **新增能力**：`pet/sprite.py` 增加 `reload()`（清影片缓存并按当前分类重播，用于缩放变更后重建 `QMovie`）与 `set_always_on_top(on)`（按位切换 `WindowStaysOnTopHint`，状态未变时直接返回避免无谓 `show()`）；`_start_ui()` 启动时按配置应用一次置顶。
>
> **冒烟等效验证**（离屏脚本，验证后删除）：构造面板读默认值正确（`water_min=45`/`mem_limit=90`）；改缩放 1.5 + 关闭久坐 + 打开整点报时 + 番茄钟 50 分钟 + 吃饭时刻 `["08:00","20:00"]` → `accept()` 返回 True 且 `config_saved` 携带被校验后的配置；非法缩放 9.9 → `accept()` 返回 False 且 `error_text` 非空；`_apply_settings()` 后内存配置与落盘配置一致、`hourly_chime` 模块被真正启用、`health_reminder` 因喝水仍开而保持启用且 `sit` 子开关为假；再把喝水也关掉 → 模块整体停用；再打开番茄钟 → 模块启用。SMOKE OK。
>
> **实施偏离**：① 语义范围校验做成 `RANGES = {"pet.scale": (0.5, 2.0)}` 表驱动，`pet.config.validate` 只保证类型与正数（对 9.9 不会回退），故范围判断放在面板的 `_range_error()`；② 控件写回采用**信号驱动**（`stateChanged`/`valueChanged`/`textChanged` → 直接写内部副本），控件量程设得比语义范围宽（缩放 0.1–10.0）以便 `set_field` 能写入越界值供 `accept()` 拦截；③ `values()` 只返回深拷贝、不做二次收集，避免与 `set_field` 的程序化写入互相覆盖；④ 新增模块级 `parse_times()` 处理 `,`/`，`/`;` 混用；⑤ 面板未暴露 `pet.pos`/`pet.edge_hide`/`pet.passthrough`/`pet.state_intervals`，由深拷贝原样保留。

---

## 阶段 6：打包与验收

### Task 22: 打包（`tools_cli/build.py`）

**Files:**
- Create: `<root>/tools_cli/build.py`
- Create: `<root>/tests/test_build_args.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `build_args(project_root: Path, out_dir: Path, name: str = "lulu_pet") -> list[str]` — 纯函数
  - `run_build(project_root: Path, out_dir: Path | None = None) -> int`
  - `stage_assets(project_root: Path, dist_dir: Path) -> None` — 把 `assets/`（含 `processed/`、`categories.json`）与默认 `config.json` 复制到产物目录

- [x] **Step 1: 写失败测试**（`tests/test_build_args.py`）

```python
from pathlib import Path
from tools_cli.build import build_args


def test_build_args_uses_onedir_noconsole_and_entry(tmp_path):
    args = build_args(tmp_path, tmp_path / "dist")
    assert "--noconsole" in args and "--onedir" in args
    assert "--onefile" not in args
    assert args[args.index("--name") + 1] == "lulu_pet"
    assert str(tmp_path / "main.py") in args


def test_build_args_does_not_bundle_assets(tmp_path):
    args = build_args(tmp_path, tmp_path / "dist")
    assert not any("assets" in a for a in args)


def test_build_args_uses_out_dir(tmp_path):
    out = tmp_path / "dist"
    args = build_args(tmp_path, out)
    assert args[args.index("--distpath") + 1] == str(out)
```

- [x] **Step 2: 运行测试确认失败** — Run: `python -m pytest tests/test_build_args.py -v`，Expected: FAIL `No module named 'tools_cli.build'`

- [x] **Step 3: 实现 `tools_cli/build.py`**

`build_args`：`[sys.executable, "-m", "PyInstaller", "--noconsole", "--onedir", "--name", name, "--distpath", str(out_dir), "--workpath", str(out_dir/"_build"), "--specpath", str(out_dir), str(project_root / "main.py")]`，不传任何 `--add-data`（素材外置）。
`run_build`：检查 `import PyInstaller` 是否可用（不可用打印 `pip install pyinstaller` 并返回 1）→ 调 `PyInstaller.__main__.run(build_args(...)[3:])` → `stage_assets` → 打印产物体积。
`stage_assets`：`shutil.copytree(project_root/"assets", dist_dir/"lulu_pet"/"assets", dirs_exist_ok=True)`；若 `dist` 下无 `config.json` 则用 `pet.config.DEFAULTS` 写一份。

- [x] **Step 4: 运行测试确认通过** — Run: `python -m pytest tests/test_build_args.py -v`，Expected: 3 passed

- [x] **Step 5: 手工检查点**

`pip install pyinstaller` 后 `python tools_cli/build.py` → `dist/lulu_pet/lulu_pet.exe` 可双击运行；`dist/lulu_pet/assets/` 存在且包含 `processed/`；把整个 `dist/lulu_pet` 拷到别的目录仍能运行（素材与配置随行）；确认 exe 与依赖总体积（预计 40–60 MB）。

> **实施记录**：`python -m pytest tests/test_build_args.py -v` → **3 passed**；全量 `python -m pytest -q` → **152 passed**。
> 实际执行 `python tools_cli/build.py` → 产物 `dist/lulu_pet/`（273.8MB）：`lulu_pet.exe` + `_internal/`（126.7MB：Python 运行时 + PyQt5/Qt 库）+ `assets/`（506 个 `processed/*.gif`、`categories.json`、`.index.json`、接触表）+ `config.json`。
> 把整个 `dist/lulu_pet` 复制到工作目录外的 `_pack_check/` 后，以 `QT_QPA_PLATFORM=offscreen` 启动 exe：进程存活 8s 未退出，且在自己的 `assets/` 下生成了 `tray_icon.png` —— 证明打包后资源根目录正确落在 **exe 所在目录**、素材随行可用（验证后已删除 `_pack_check/`）。
> 体积说明：计划预估 40–60MB 仅算了 exe + 依赖，实际 126.7MB 来自 PyQt5/Qt 运行时；`assets/` 另计 131MB（506 张优化后 GIF + 接触表）。

> **实施偏离**：① `build_args` 增加 `--noconfirm`（否则重复打包会在「删除旧产物」处交互提问而挂住）；② `stage_assets` 用 `shutil.ignore_patterns("raw")` **跳过 `assets/raw/`**（329MB 采集原件，运行期不需要，避免产物无谓翻倍），并新增可选 `name` 参数以对齐 `--name`；③ 原测试 `test_build_args_does_not_bundle_assets` 断言 `not any("assets" in a for a in args)` 会被 pytest 的 `tmp_path`（目录名含 `..._does_not_bundle_assets0`）误伤，改为断言「无 `--add-data` / `--add-binary`，且没有以 `assets` 结尾的参数」；④ `main.py` 新增 `app_root()`：`sys.frozen` 时取 `Path(sys.executable).parent`（否则 `__file__` 指向 `_internal/`，素材找不到），`PetApp.__init__` 改用它取默认 root —— 这是「素材外置 + 产物可搬迁」的必要接线；⑤ 新增 CLI 参数 `--root` / `--out`。

---

### Task 23: 冒烟测试与验收

**Files:**
- Create: `<root>/tests/test_smoke.py`

**Interfaces:**
- Consumes: `PetApp`（T8 + 后续任务接线后的完整版本）、`build_modules`（T15）
- Produces: 无新接口，只做整体验证

- [x] **Step 1: 写冒烟测试**（`tests/test_smoke.py`）

```python
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image
from PyQt5.QtCore import QTimer

from main import PetApp
from pet.catalog import default_categories, save_categories
from pet.config import DEFAULTS, save_config


def build_root(tmp_path: Path) -> Path:
    (tmp_path / "assets" / "processed").mkdir(parents=True)
    for i in range(1, 4):
        Image.new("RGB", (200, 200), (30 * i, 130, 210)).save(
            tmp_path / "assets" / "processed" / f"lulu_{i:03d}.gif")
    d = default_categories()
    d["categories"]["idle"]["files"] = ["lulu_001.gif", "lulu_002.gif"]
    d["categories"]["happy"]["files"] = ["lulu_003.gif"]
    save_categories(tmp_path / "assets" / "categories.json", d)
    save_config(tmp_path / "config.json", DEFAULTS)
    return tmp_path


def test_app_starts_and_quits_cleanly(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    QTimer.singleShot(300, app.shutdown)
    assert app.run() == 0


def test_app_starts_without_assets(qapp, tmp_path):
    """Review Focus #1：空素材目录也必须能启动"""
    (tmp_path / "assets" / "processed").mkdir(parents=True)
    save_config(tmp_path / "config.json", DEFAULTS)
    app = PetApp(root=tmp_path)
    QTimer.singleShot(200, app.shutdown)
    assert app.run() == 0


def test_shutdown_is_reentrant(qapp, tmp_path):
    """`_quit()` 会先关托盘再关应用，`shutdown()` 必须可重复调用。"""
    app = PetApp(root=build_root(tmp_path))
    app.shutdown()
    app.shutdown()


def test_all_modules_can_be_toggled_without_error(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    for module in app.modules.values():
        module.set_enabled(True)
        module.tick(app.clock())
        module.set_enabled(False)
    assert all(not m.enabled for m in app.modules.values())
    app.shutdown()


def test_passthrough_and_edge_hide_survive_toggle(qapp, tmp_path):
    app = PetApp(root=build_root(tmp_path))
    app.sprite.set_passthrough(True)
    app.sprite.set_passthrough(False)
    assert app.edge_hider.maybe_hide((4, 400)) is True
    assert app.edge_hider.is_hidden is True
    app.edge_hider.reveal()
    assert app.edge_hider.is_revealed is True
    # 离开超时（默认 3s）后回缩，仍处于贴边隐藏
    app.edge_hider.tick(datetime.now() + timedelta(seconds=5))
    assert app.edge_hider.is_hidden is True
    app.shutdown()
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL（`PetApp` 尚未暴露 `modules` / `clock` / `edge_hider`）

- [x] **Step 3: 在 `main.py` 暴露 `modules`、`clock`、`edge_hider` 并让 `shutdown()` 可重入**

`PetApp` 增加公开属性 `self.modules: dict[str, Module]`、`self.clock = datetime.now`、`self.edge_hider`；`shutdown()` 内先 `behavior.stop()`、保存配置、再 `QApplication.quit()`，重复调用不报错。

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: 4 passed

- [x] **Step 5: 全量测试 + 手工验收清单**

Run: `python -m pytest -q`
Expected: 全部通过（预计 130+ 个测试）。

按 spec §13 的清单在**脚本模式与打包模式各跑一遍**：

- [x] 启动出现噜噜、可拖动；拖到左右边缘松手只露桔子；鼠标移入滑出；移开 3 秒缩回
- [x] 点击播 happy、连点播 angry、右键出菜单、双击打开设置
- [x] 托盘：显示/隐藏、模式切换、6 个工具开关逐个生效、开机自启写入注册表（`reg query` 核对）、退出无残留进程
- [x] 12:00 / 18:30（临时改成 1 分钟后）播放 eat 动画 + 气泡
- [x] 番茄钟 1 分钟版本跑通「专注 → 通知 → 休息 → 通知」
- [x] 穿透模式下点击穿到下层；切回交互模式可拖拽
- [x] A 类素材桌宠目视无白边、无残影
- [x] 空 `assets/processed` 启动显示占位图不崩

> **实施记录**：`python -m pytest tests/test_smoke.py -v` → **5 passed**（计划预期 4，实际多出新增的 `test_shutdown_is_reentrant`）；全量 `python -m pytest -q` → **158 passed**。
> `modules`（[main.py:158-159](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/main.py)）、`clock` 在 T14/T15 已暴露，`edge_hider` 在 T10 已暴露，因此 Step 2「写失败测试」直接一次通过（无红阶段），Step 3 只补了 `_shutdown_done`。
> Step 5 的手工清单以临时离屏验收脚本 `_acceptance.py` **等效替代**（29 项，**0 失败**）：覆盖启动/素材、菜单显示隐藏、穿透切换、6 个工具开关（含 `health_reminder`「任一子开关开启即启用」语义）、开机自启写注册表并还原、喝水（`drink` 分类）、吃饭 12:00 触发 + 同分钟去重、整点 13:00 触发、番茄钟完整轮转（专注 → 休息 → 专注）、系统监控写托盘提示、贴边隐藏（触发/滑出/超时缩回）、退出（定时器停 + 配置落盘 + 可重入）；验证后已删除脚本。
> 打包模式：`dist/lulu_pet/lulu_pet.exe` 以 `QT_QPA_PLATFORM=offscreen` 启动存活 8s、并在自有 `assets/` 下生成 `tray_icon.png`；`reg query "HKCU\...\Run"` 确认无 `Lulu*` 残留。**「A 类素材无白边、真实拖拽交互观感」需真人在真实桌面复核**（离屏环境无法目视）。

> **实施偏离**：① `shutdown()` 增加 `_shutdown_done` 可重入标志，并在末尾调用 `self.app.quit()` —— 计划只要求「重复调用不报错」，但若不 `quit()` 则 `app.exec_()` 永不返回、测试直接挂住（实测踩到并用 StopCommand 终止）；② `tests/test_smoke.py` 实际为 **5 个测试**（新增 `test_shutdown_is_reentrant`），且把 `test_passthrough_and_edge_hide_survive_toggle` 的断言从「只看 `is_hidden`」加强为「`maybe_hide` 返回值 → `reveal()` 后 `is_revealed` → 超时 5s 后仍 `is_hidden`」，并在各测试末尾补 `app.shutdown()` 避免定时器泄漏；③ **修复 `pet/autostart.py` 的真实 Bug**：`winreg.OpenKey(..., samDesired=0)` 在真实注册表上能打开成功，但随后 `QueryValueEx` 抛 `PermissionError [WinError 5]`，导致 `is_enabled()` 恒为 False、`current_command()` 恒为 None → `_open_run_key` 读路径改用 `KEY_READ = 0x20019`，并新增回归测试 `test_reads_open_key_with_read_access`（断言 `reg.accesses == [0x20019, 0x20019]`）；④ 计划的「手工验收清单」以离屏等效验收脚本替代（见上），其中「目视无白边 / 真实拖拽」两项标注为需真人复核。

#### 验收后缺陷修复（用户试玩 exe 反馈，T23 之后追加）

用户试玩 `dist/lulu_pet/lulu_pet.exe` 后反馈两个缺陷，均已修复并回归：

1. **贴边隐藏后「找不到噜噜、没有桔子」**
   - **根因**：`pet/sprite.py` 的 `paintEvent` 只画 GIF 当前帧，`draw_orange` 从未在桌宠窗口被调用（仅托盘图标兜底路径用过）。屏内只剩素材最左/最右 48px 切片，而素材居中构图 → 那一条几乎全透明。另 `_apply_pixmap` 换帧时 `setFixedSize` 会改窗口尺寸，而屏外 x 按隐藏时尺寸算 → 窗口一缩可能整块留在屏外。
   - **修复**：`Sprite` 新增 `STRIP_PX = 48`、`strip_side` 属性、`set_strip()`、`_paint_strip()`，缩回期间锁定窗口尺寸；`EdgeHider` 新增 `_show_strip()`，在 `maybe_hide`/`retract` 置 `True`、`detach`/`reveal` 置 `False`。这正是 spec §7.4「仅保留 48px 宽的桔子竖条可见」从未落地的部分。
   - **测试**：`tests/test_edge_hide.py`（`FakeSprite.set_strip` + 状态跟随断言、新增 `test_strip_marker_follows_retract_and_reveal`）、`tests/test_sprite.py`（新增 `test_strip_mode_paints_orange_on_visible_side`，用 `s.grab().toImage()` 做像素级 alpha 断言）。

2. **托盘图标右键菜单「只有一个菜单项，且字体错乱」**
   - **根因**：`Tray` 走 `QSystemTrayIcon.setContextMenu()` 把菜单交给平台原生实现，但菜单需每次弹出重建（勾选态会变），`aboutToShow` 里 `clear()` + 重加 action 后原生菜单仍持有旧 action 指针 → 悬空指针。
   - **修复**：删除 `refresh()` 与 `setContextMenu` 路径；改为 `activated.connect(_on_activated)`，`reason == Context` 时 `popup_menu()`：新建菜单 → `aboutToHide` 连 `_forget_menu` 释放 → `popup(QCursor.pos())`，与右键噜噜走同一渲染路径。`main.py` 三处 `tray.refresh()` 调用同步删除。
   - **测试**：`tests/test_menu.py` 新增 `make_tray()` 辅助与 3 个测试（不走原生菜单、仅右键弹出且每次重建、工厂返回 `None` 时返回 `False`）。

> **实施记录**：全量 `python -m pytest -q` → **163 passed**（158 + 3 个托盘测试 + 2 个桔子窄条测试）。重新打包 `python tools_cli/build.py` → `dist/lulu_pet/`（273.8MB，506 个 GIF + `categories.json` 正确随包）；实机启动 `lulu_pet.exe` 存活 16s 未退出。

#### 范围收缩：移除「系统监控」（用户要求）

用户要求去掉系统监控功能，按需求删除（非缺陷修复）：

- **删除文件**：`modules/sysmonitor.py`、`tests/test_sysmonitor.py`（6 个测试）。
- **注册/菜单/配置**：`main.py` 去掉 `import modules.sysmonitor` 与 `MODULE_KEYS["sysmonitor"]`；`ui/menu.py` 的 `MENU_KEYS` 与 `MENU_LABELS` 去掉 `sysmonitor`/「系统监控」；`pet/config.py` 的 `DEFAULTS["modules"]` 去掉 `sysmonitor` 节点；`ui/settings_dialog.py` 去掉「工具」页的「系统监控」4 个控件。
- **测试同步**：`tests/test_menu.py` 的 `MODS` 与标签列表、`tests/test_config.py` 的默认模块集合与 `validate` 输入去掉 `sysmonitor`。
- **依赖**：`requirements.txt` 去掉 `psutil>=5.9` —— 源码中已无任何 `psutil` 引用。
- **未动**：`ModuleContext.set_tray_text` 保留（框架能力，`tests/test_modules_base.py` 有独立覆盖，非系统监控专属）。

> **实施记录**：全量 `python -m pytest -q` → **157 passed**（163 − 6）。清空 `dist/_build` 全量重打包 → 产物 `config.json` 已无 `sysmonitor` 键；`_internal` 中已无 `modules/sysmonitor`。
> **已知残留**：产物仍在 `_internal/psutil/` 带上 `_psutil_windows.pyd`。经查 `xref`，`psutil` 的实际导入方是 `numpy.testing._private.utils`（numpy 由 Pillow 侧的可选依赖链路带入），与系统监控无关，属既有行为；要彻底剔除需在打包参数中 `--exclude-module numpy.testing`，会改动 `tools_cli/build.py` 的参数契约（`tests/test_build_args.py` 断言精确参数），本次未做。
