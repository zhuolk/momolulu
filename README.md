# 噜噜（momolulu）

一只住在 Windows 桌面上的水豚挂件。无边框置顶窗口循环播放 GIF 动图，带行为状态机、
自主走动、绕屏散步、贴边隐藏、鼠标穿透，以及番茄钟 / 喝水·久坐 / 吃饭 / 整点报时提醒，
并支持启动时自动检查的素材热更与主程序自动更新。

- 仓库：<https://github.com/zhuolk/momolulu>
- 当前版本：`0.2.2`（唯一来源 `pet/version.py` 的 `VERSION`）
- 平台：Windows

## 特性

- **GIF 动画挂件**：透明无边框、置顶，播放 `assets/processed/` 里的动图。
- **行为状态机**：待机一段时间后随机触发小动作（走路 / 难过 / 洗澡），带优先级抢占。
- **自主走动**：待机久了会在桌面上慢慢走（约 40px/s），碰到屏幕边缘折返并转身。
- **绕屏散步**（右键「搞搞震 ▸ 散步」）：先瞬移到屏幕右下角，再沿屏幕边缘逆时针走一圈，
  四角各逆时针转 90° 保持脚贴边，走完落回待机，中途拖拽即中止。
- **贴边隐藏**：拖到屏幕左右边缘松手即缩进屏幕外，只露 24px 桔子窄条；把窄条拖离边缘才恢复。
- **鼠标穿透双模式**：交互模式可拖拽；穿透模式不拦截鼠标点击。
- **提醒模块**：番茄钟、喝水 / 久坐提醒、吃饭提醒、整点报时（各自独立开关）。
- **自动更新**：启动时探测远端清单，素材静默热更、主程序弹窗确认后下载整包自替换。
- **开机自启**：注册表 `Run` 项（项名 `Momolulu`）。

## 安装与运行

### 直接使用

到 [Releases](https://github.com/zhuolk/momolulu/releases) 下载最新整包 `momolulu-<版本>.zip`，
解压后运行 `momolulu.exe`。**必须保留整个目录**（含 `_internal/` 运行时与 `assets/`），单拿一个 exe 无法运行。

### 从源码运行

```powershell
python -m pip install -r requirements.txt
python main.py
```

需要 Python 3.10.4、PyQt5 5.15.11、Pillow >= 11。脚本模式不会执行自动更新
（源码目录不是可替换的安装目录）。

## 右键菜单

- **显示 / 隐藏噜噜**、**交互模式 / 穿透模式**
- **实用工具**：番茄钟、喝水提醒、久坐提醒、吃饭提醒、整点报时、番茄钟开始 / 暂停 · 跳过 · 重置
- **搞搞震 ▸ 散步**
- **立即更新到 x.y.z**（检测到新版时才出现）
- **设置…**、**开机自启**、**关于**、**退出**

## 素材

素材与程序分离，放在与 exe 平级的 `assets/` 目录，替换素材无需改代码（改完仍需重新打包才分发）：

- `assets/processed/`：桌宠实际引用的动图，命名必须为 `lulu_xxx.gif`。
- `assets/categories.json`：分类结构与每张图的实测轨道。
- `assets/raw/`：原始采集件（不入库）。

**素材必须提前去好背（自带 alpha）**：处理管线不再做去背，拿到没有 alpha 的素材会直接报错。

素材管线流程：

```powershell
# 1. 去好背的 GIF 放入 assets/raw/
python tools_cli/prepare.py            # 编号 / md5 去重 / 分类登记（高帧率素材需放宽参数）
python tools_cli/contact_sheet.py      # 生成预览接触表，人工看图
# 2. 手工把文件名从 unassigned 挪到目标分类
python tools_cli/build.py              # 打包
```

分类：`idle` `walk` `stroll` `sleep` `eat` `drink` `happy` `angry` `sad` `bath` `unassigned`。

## 开发

```powershell
python -m pytest -q -p no:cacheprovider   # 全量测试（277 个用例）
python tools_cli/build.py                 # 打包到 dist/momolulu/，产出 dist/momolulu-<版本>.zip 与 dist/latest.json
```

目录结构：

```
main.py          程序入口：PetApp 组装窗口 / 行为机 / 模块 / 托盘 / 自动更新接线
pet/             核心层（窗口、行为状态机、走动/散步、贴边、托盘、更新…）
modules/         功能模块层，统一 enable/tick/disable
ui/              托盘菜单、设置对话框、气泡提示、更新弹窗
tools_cli/       开发工具（素材预处理 / GIF 流水线 / 接触表 / 打包），不进产物
tests/           pytest 用例
assets/          素材（外置，不打进 exe）
update/latest.json  自动更新清单（发布源，必须入库）
```

## 自动更新

启动 5 秒后检查一次远端 [`update/latest.json`](https://raw.githubusercontent.com/zhuolk/momolulu/main/update/latest.json)
（仅打包版执行）：

- **素材热更（静默）**：比对清单里的 `assets.files` 与本地，有差异就后台下载替换，无需发新版本号。
- **主程序更新（弹窗）**：本地版本低于远端时弹窗，用户同意后下载整包、校验 sha256 与体积，
  再由外部 `updater.bat` 在进程退出后完成目录交换（程序无法自己覆盖自己），并保留用户 `config.json`。

发布流程：改 `pet/version.py` → 运行 `tools_cli/build.py` → 建 GitHub Release 上传整包 →
更新仓库内 `update/latest.json`。

## 许可

素材来自网络，仅供个人学习使用。
