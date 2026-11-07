# 新会话开场提示词（换电脑接手用）

**用法**：在新电脑上 `git clone https://github.com/zhuolk/momolulu.git`、装好依赖
（`python -m pip install -r requirements.txt`，再 `pytest pyinstaller`）后，开一个新会话，
把下面「## 提示词」一节的内容**整段贴进去**，并把最后一行的占位换成你这次真正要做的事。

为什么需要它：Trae 的对话历史不在仓库里，跨设备靠「仓库 + `docs/handoff.md` + 这份提示词」。

---

## 提示词

我在接手一个 Windows 桌宠项目「噜噜」（打包名 `momolulu`，仓库 <https://github.com/zhuolk/momolulu>，
当前工作目录就是仓库根）。**动手前先读这三个来源**：

1. `AGENTS.md` —— 仓库协作约定 + 本机环境坑（怎么跑测试、素材管线、提交与发版纪律）。
2. `docs/handoff.md` —— 架构要点、素材规范、**当前进度（未提交改动）**、待办 / 未决、发版流程。
3. `docs/superpowers/` 下的 spec / plan（注意：2026-10-20 那份是改名前的旧描述，别照做；
   2026-10-21 那份自动更新的与代码一致）。

项目概况：Python 3.10.4 + PyQt5 5.15.11 + Pillow >= 11，PyInstaller `--onedir` 打包，
pytest 测试；分层是 `tools_cli`（素材 / 打包）→ `pet`（核心）→ `modules`（功能）→ `ui`（界面）。
代码注释、文档、提交信息**一律用中文**。

验收方式（重要）：`python -m pytest -q -p no:cacheprovider`，
**判断全绿看退出码是否为 0**（本机不打印 `N passed` 汇总行），当前应为 **317 项**。
改完代码必须跑全量测试并把真实输出贴出来，不要口头声称通过；能验证就别猜。

本轮要做的事：
<在这里写你的需求，例如「把待办 7 改成待播队列：睡醒先播 awake，播完再接被打断的那个表情」>

约束（沿用仓库既定纪律）：
- **不要擅自 `git commit` / `git push`，不要发版**。发版是严格顺序的四步（改 `pet/version.py`
  → `tools_cli/build.py` → 建 GitHub Release 上传整包并核对 `digest` → **最后**才推
  `update/latest.json`），只在明确要求时做。
- 不要顺手重构与本次无关的代码、不要预置用不上的抽象；只做被要求的改动。
- 素材是**外部资产**：`assets/` 与 exe 平级，真相在 `assets/categories.json`
  （分类归属 + `tracks` 实测轨道 + `loops` 是否可循环）；批量改分类 / 循环标用
  `tools_cli/assign.py` 配 CSV 清单，**不要手工编辑 `categories.json` 的文件名**。
- 新增分类要一起改：`pet/catalog.py` 的 `CATEGORIES` + `FALLBACK`（回退链）、
  `assets/categories.json`（`default_categories()` 会补齐）、以及**实际触发点**
  （`pet/behavior.py` / `main.py` / `modules/*`），并补测试。
- 本机装了实时杀软，对刚写出的 exe / dll 做改名 / 搬移 / 删除可能偶发 `WinError 5`，**先重试**。
