# AGENTS.md

给在本仓库里干活的 AI 代理 / 协作者的约定。改代码前先读 `docs/handoff.md`（架构与交接），
再读 `docs/superpowers/` 下的 spec / plan。

## 通用

- 语言：代码注释、文档、提交信息一律用**中文**。
- 分层：`tools_cli`（素材 / 打包）→ `pet`（核心）→ `modules`（功能）→ `ui`（界面）。
  功能模块必须实现 `enable/tick/disable`，由 `main.py` 统一驱动。
- 不要过度设计：只做被要求的改动，不顺手重构、不预置用不上的抽象。

## 本机环境注意

- **PowerShell 5 不支持 heredoc（`<<`）与 `&&`**。多行提交信息先写到临时文件再用 `git commit -F <file>`；
  串联命令用 `;`。
- **`RunCommand` 每条命令都是新 shell，环境变量不跨命令保留**。需要 PAT 时，
  把「`git credential fill` 取 token + 调用 API」写在**同一条命令**里。
- **无 `gh` CLI**，发布用 `curl.exe`（`C:\WINDOWS\system32\curl.exe`）+ GitHub REST API。
- **本机装了实时杀软（腾讯电脑管家）**：会短暂持有刚写出的 exe / dll 句柄，
  对这些文件改名 / 搬移 / 删除可能偶发 `WinError 5 拒绝访问`。**先重试**，不要当逻辑 bug。
- 装包走内网代理：
  `python -m pip install --proxy http://127.0.0.1:8888 --index-url https://pypi.org/simple <pkg>`

## 测试

- 全量：`python -m pytest -q -p no:cacheprovider`（当前 **277** 个用例）。
- 本机 **不打印 `N passed` 汇总行**，判断全绿看**退出码是否为 0**；
  用例数用 `--collect-only -q -p no:cacheprovider` 逐文件求和交叉确认。
- 加 `-p no:cacheprovider` 避免在仓库留下 `.pytest_cache`。
- 改了行为 / 菜单 / 素材管线就要同步补测试，不要只改实现。

## 素材管线

- **素材必须提前去好背（自带 alpha）**。`process_gif()` 拿到没有 alpha 的素材会直接抛 `ValueError`，
  计入 `report["failed"]` 并让 `prepare.py` 退出码为 1。这是刻意的硬门槛，**不要加卡片轨兜底或静默出片**。
- 去背实现（`sample_background` / `remove_background` / `analyze_frame` / `grade` 等）保留在
  `tools_cli/gif_pipeline.py` 且有单测，但**已无调用方**；`--tol` / `--edge-min` 保留但不再生效。
- 命名必须 `lulu_xxx.gif`；同图按 md5 去重；手动删图后要同步清理 `categories.json` 与 `.index.json`。
- `prepare.py --rebuild` 会从 1 重新编号导致既有分类错位，**不要随意使用**。

## 提交与发版

- **不要擅自提交 / 推送**，只在用户明确要求时才做。
- 提交信息用中文，聚焦「为什么」。
- 发版顺序**不可颠倒**：
  1. 改 `pet/version.py` 的 `VERSION`；
  2. `python tools_cli/build.py` 打包；
  3. 建 GitHub Release 并上传整包，**核对远端 `digest` 与本地 sha256 一致、资产可下载**；
  4. **最后**才更新并推送仓库内 `update/latest.json`（它是自动更新的唯一发布源，只认 `main`）。
- 发布直接推 `main`。

## 已知坑（别再踩）

- **`setWindowFlags()` 在 Windows 上会销毁重建窗口**，调用后必须显式 `show()` 一次。
- **解压更新包必须逐成员直接写最终路径**，不要「先 `extractall` 再改名展平」——
  杀软持句柄会让目录改名稳定吃 `WinError 5`，整包永远装不上（回归测试见
  `tests/test_program_update.py::test_prepare_program_update_denied_rename_still_stages`）。
- 气泡跟随统一订阅 `Sprite.moved` 信号，**不要在各个交互函数里分别补气泡位置**。
- `docs/superpowers/` 下 **2026-10-20 那份 spec / plan 是改名前的旧描述**，尚未回写，读时注意甄别；
  2026-10-21 那份（自动更新）与代码一致。
- `.gitignore` 忽略 `dist/`、`*.spec`、`config.json`、`momolulu.log`、`.superpowers/`、
  `assets/raw/`、`assets/.index.json`、`assets/id_map.csv`、`assets/prepare_report.json`、
  `assets/contact_sheet_*.png`、`assets/tray_icon.png`；`update/latest.json` **必须入库**。
