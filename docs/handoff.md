# 交接说明（handoff）

给"换一台电脑继续开发"用的上下文快照。读完这份文档 + `docs/superpowers/` 下的 spec/plan，即可接手。

## 这是什么

噜噜桌宠（打包名 `momolulu`）：Windows 桌面水豚挂件。PyQt5 无边框置顶窗口循环播放 GIF，
带行为状态机、贴边隐藏、鼠标穿透双模式、托盘菜单，以及番茄钟 / 喝水·久坐 / 吃饭 / 整点报时提醒。

- 仓库（私有）：<https://github.com/zhuolk/momolulu>
- 分支：`main`
- 测试：155 个 pytest 用例全量通过
- 打包：`dist/momolulu/`（PyInstaller onedir，约 138.6MB），已实机启动验证

## 环境

- Python 3.10.4、PyQt5 5.15.11、Pillow >= 11（见 `requirements.txt`）
- 开发额外需要：pytest、PyInstaller
- 内网装包需显式走代理：
  `python -m pip install --proxy http://127.0.0.1:8888 --index-url https://pypi.org/simple <pkg>`

## 目录结构

```
main.py               程序入口：PetApp 组装窗口 / 行为机 / 模块 / 托盘
requirements.txt      运行期依赖
pytest.ini            测试配置（testpaths = tests）
pet/                  核心层
  config.py           配置默认值 + 深合并 + 类型校验 + 原子写入
  catalog.py          素材目录与分类读取；找不到目标分类时按 FALLBACK 链回退
  sprite.py           无边框窗口 + GIF 播放 + 拖拽/连点/穿透 + 贴边条渲染
  behavior.py         行为状态机（idle/walk/sleep/eat/... 与优先级）
  edge_hide.py        贴边隐藏（缩进屏幕外，只露桔子窄条）
  tray.py             托盘图标（固定取 lulu_002.gif）+ Qt 托盘菜单
  autostart.py        开机自启（注册表 Run 项，项名 Momolulu）
  winutil.py          Win32 窗口辅助（置顶 / 点击穿透 / 全屏检测）
modules/              功能模块层，统一 enable/tick/disable（见 base.py）
  pomodoro.py         番茄钟
  health_reminder.py  喝水与久坐提醒（两个独立子开关 + snooze）
  meal_reminder.py    吃饭提醒（时间点列表）
  hourly_chime.py     整点报时
ui/                   托盘菜单、设置对话框、气泡提示 toast
tools_cli/            开发工具（不进产物）
  prepare.py          素材预处理：编号 / md5 去重 / 分类登记
  gif_pipeline.py     GIF 处理流水线（缩放 / 抽帧 / 调色 / 去背判定轨道）
  contact_sheet.py    生成预览接触表
  build.py            PyInstaller 打包 + 素材外置
tests/                155 个用例（pytest，Conftest 里提供 qapp fixture）
assets/               素材（外置，不打进 exe）
docs/                 本文件 + superpowers 下的 spec / plan
```

## 架构要点

- **分层**：`tools_cli`（素材 / 打包）→ `pet`（核心）→ `modules`（功能）→ `ui`（界面）。
  功能模块必须实现 `enable/tick/disable`，由 `main.py` 统一驱动。
- **GIF 双轨渲染**：素材分 `transparent`（已去背，直接画在桌面上）与 `card`（带背景，
  走圆角卡片渲染）两轨。轨道实测记录在 `assets/categories.json` 的 `tracks` 字段，
  `Sprite.play()` 按**被选中素材的实测轨道**渲染（不要按分类固定轨道）。
- **行为状态机** `pet/behavior.py`：`idle` 空闲一段时间后随机触发小动作，
  `_AUTO_ACTIONS = ("walk", "sad", "bath")` 等概率三选一。
- **贴边隐藏** `pet/edge_hide.py`：拖到屏幕左右边缘松手即缩进屏幕外，只露 48px 桔子窄条；
  **只有把桔子拖离边缘并松手才恢复显示**，鼠标划过不恢复。状态持久化到 `config.json` 的 `pet.edge_hide`。
- **鼠标穿透双模式**：交互模式可拖拽；穿透模式不拦截鼠标（`winutil` 里改窗口扩展样式）。
- **托盘**：图标固定由 `lulu_002.gif` 首帧生成 64×64 PNG（`assets/tray_icon.png`，缺失时自动重建）；
  菜单必须用 `QMenu.popup()` 渲染，原生托盘菜单在此环境字体与项渲染异常。
- **配置**：`config.json` 位于程序目录，运行期自动生成，不入库；结构见 `pet/config.py` 的 `DEFAULTS`
  （默认显示缩放 `pet.scale = 0.5`；设置面板可调范围 0.5~2.0）。已存在的 `config.json` 不会被打包覆盖，
  改默认值后要让旧机器生效，需删掉该文件或手动改设置项。
- **素材外置**：`assets/` 与 exe 平级存放，换素材只需替换 `assets/`（改代码或素材后仍需重新打包）。

## 素材规范（改素材前必读）

- 原始采集件放 `assets/raw/`；工具处理后产出 `assets/processed/lulu_NNN.gif`，桌宠只引用 `processed`。
- 命名必须 `lulu_xxx.gif`；采集与处理按 **md5 去重**，同图不得重复入库。
- 账本文件：
  - `assets/.index.json`：md5 → {name, track}
  - `assets/id_map.csv`：id / raw / track 对照表
  - `assets/categories.json`：分类结构与每张图的实测轨道
- 分类：`idle` `walk` `sleep` `eat` `drink` `happy` `angry` `sad` `bath` `unassigned`。
  当前共 11 张：`idle` 3 张、`happy` 2 张，其余各 1 张，`unassigned` 为空。
- 标准流程：GIF 放入 `raw/` → `python tools_cli/prepare.py` → `python tools_cli/contact_sheet.py`
  → `python tools_cli/build.py`。
- 坑：
  - `prepare.py --rebuild` 会从 1 重新编号，会让既有分类错位，**不要随意使用**。
  - 手动删素材后必须同步清理 `categories.json` 与 `.index.json`，否则出现悬空引用。
  - `catalog.existing_files()` 会过滤磁盘上不存在的文件名，所以删图即刻生效。

## 常用命令

```powershell
cd capybara_pet
python -m pytest -q                  # 全量测试，期望 155 passed
python tools_cli/build.py            # 打包到 dist/momolulu/
python tools_cli/prepare.py          # 素材预处理
python tools_cli/contact_sheet.py    # 生成预览接触表
```

## 已确认的产品行为

- **连点**：5 秒内连点 ≥5 次触发快速点击反馈（`sprite.py` 的 `_CLICK_WINDOW_S`）。
- **贴边隐藏**：拖到屏幕左右边缘松手隐藏，露 48px 桔子条；拖离边缘松手才恢复。
- **无状态气泡**：已移除"噜噜在 XXX"的悬停状态提示，相关配置项与设置面板勾选项一并删掉。
- **提醒模块默认值**：`pomodoro` 关、`health_reminder` 开（喝水 45min / 久坐 60min）、
  `meal_reminder` 开（12:00、18:30）、`hourly_chime` 关。

## 待办 / 未决

1. 待机小动作中 `walk` 是否加权（目前 walk / sad / bath 等概率）。
2. `docs/superpowers/` 下的 plan 与 spec 仍是**改名前的旧描述**（`lulu_pet`、悬停滑出 + 3s 缩回、
   悬停气泡），尚未回写，读的时候注意甄别。
3. 开机自启项名已从 `LuluPet` 改为 `Momolulu`，旧注册表项可能残留：
   在设置面板里关一次再开一次自启，或手工删 `HKCU\...\Run\LuluPet`。
4. aigei 采集候选约 254 张（约 630MB）仍在开发机的 `_stage_gifs/aigei/`，未入库、可清理。
5. `assets/raw/`、`.index.json`、`id_map.csv`、`contact_sheet_*.png`、`tray_icon.png` 都在
   `.gitignore` 里（体积 / 依赖 raw），clone 后只有 `processed` 的 11 张图与 `categories.json`；
   完整素材链路需要另外传输。

## 在另一台电脑继续

```powershell
git clone https://github.com/zhuolk/momolulu.git
cd momolulu
python -m pip install -r requirements.txt
python -m pip install pytest pyinstaller
python -m pytest -q        # 期望 155 passed
```

然后让 AI 先读本文件、再读 `docs/superpowers/specs/` 与 `plans/` 即可接手。

注意：**Trae 的对话历史不在仓库里**——它由客户端 / 云端账号管理，本机没有可搬运的会话文件
（已确认 `%APPDATA%\Trae\User\workspaceStorage\` 下没有 chatSessions 之类的记录）。
跨设备靠的是"仓库 + 本交接文档"，或在新客户端登录同一 Trae 账号看账号下的历史会话。

## 发版（自动更新源）

1. 改 `pet/version.py` 里的 `VERSION`
2. `python tools_cli/build.py`
3. `gh release create v<version> dist/momolulu-<version>.zip`
4. 把 `dist/latest.json` 覆盖到仓库的 `update/latest.json`，`git push`
5. 素材有变动时 `assets/` 已在 git 里，push 完即生效

注意 `raw.githubusercontent.com` 有几分钟 CDN 缓存，push 完对方不一定立刻看到。
