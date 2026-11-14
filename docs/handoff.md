# 交接说明（handoff）

给"换一台电脑继续开发"用的上下文快照。读完这份文档 + `docs/superpowers/` 下的 spec/plan，即可接手。

## 这是什么

噜噜桌宠（打包名 `momolulu`）：Windows 桌面水豚挂件。PyQt5 无边框置顶窗口循环播放 GIF，
带行为状态机、自主走动、绕屏散步、贴边隐藏、鼠标穿透双模式、托盘菜单，
番茄钟 / 喝水·久坐 / 吃饭 / 整点报时提醒，生活数值（心情·活力·饱腹）与噜噜币（上班赚钱 + 商店喂食），
以及启动时自动检查的素材热更与主程序自动更新。

- 仓库（**公开**）：<https://github.com/zhuolk/momolulu>
- 分支：`main` —— 发布直接推 `main`，自动更新只认 `main` 上的 `update/latest.json`
- 当前版本：`0.2.9`（唯一来源 `pet/version.py` 的 `VERSION`）
- 测试：396 个 pytest 用例全量通过
- 打包：`dist/momolulu/`（PyInstaller onedir，约 132.6MB）＋ 分发用 `dist/momolulu-<版本>.zip`（约 54MB），已实机启动验证
- 已具备自动更新：启动时探测远端 `latest.json`，有新版弹窗征得同意后下载整包自替换（详见「自动更新」）

## 本轮改动（0.2.9）

- **界面风格统一**：新增 `ui/theme.py`（调色板 + `draw_card()` + `menu_style()`），
  `ui/toast.py` / `ui/status_card.py` / `ui/update_prompt.py` / `ui/menu.py` 改用它，
  气泡与更新弹窗的圆角、阴影、配色从此跟状态卡一处改、处处变。
- **右键菜单加数值摘要**：菜单最上面一条 `StatusHeader`（状态卡同款进度条：心情 / 活力 / 饱腹 +
  噜噜币或本班进账），数据由 `main._menu_state()` 从 `vitals` / `economy` 两个模块取。
- **踩坑记录**：`QMenu` 的样式表里一旦出现 `border-radius`，本机 `QStyleSheetStyle` 会写坏堆，
  全量测试跑到 `main.py::_start_ui` 的 `sprite.show()` 时整个进程 access violation；
  菜单圆角改用窗口 mask（`ui/menu.CardMenu`）。
- 测试 383 → **396**（新增 `tests/test_theme.py` 6 项、`tests/test_menu.py` +6、`tests/test_status_card.py` +1）。

## 最近一批改动（已随 `0.2.8` 提交推送）

- **状态卡浮窗（`ui/status_card.py`）**：托盘原生悬停提示（`QSystemTrayIcon.setToolTip`）只能一行纯文本，
  画不出进度条，于是另起一个自绘顶层窗：鼠标穿透、不抢焦点、8 秒后自动收起。卡片用三条彩色进度条展示
  心情 / 活力 / 饱腹（按阈值变色：<30 红 / <60 黄 / <85 绿 / ≥85 深绿，横向 `QLinearGradient` 渐变填充），
  底部一行显示噜噜币余额（上班中则改显示本班进账）。弹出入口：**托盘图标左键单击**
  （`pet/tray.py` 新增 `clicked` 信号）或右键菜单「照顾噜噜 ▸ 看看状态」。
- `main.py` 新增 `_show_status_card` / `_refresh_status_card` / `_fill_status_card`；心跳 `_update_status()`
  会在卡片可见时每秒刷新；`_toggle_visible` 与 `shutdown` 都要 `status_card.hide()`。
- 新增 `tests/test_status_card.py`，并在 `tests/test_menu.py`（托盘 `clicked` 信号 + 「看看状态」）与
  `tests/test_smoke.py`（状态卡接线）补用例。**测试 370 → 383**，全绿（退出码 0）。
- 生活数值 / 噜噜币（`modules/vitals.py` / `modules/economy.py`：心情·活力·饱腹按在线时间衰减、上班按分钟
  进账、商店喂食）随 `0.2.7` 提交推送，`tests/test_vitals.py` / `tests/test_economy.py` 一并入库。

## 环境

- Python 3.10.4、PyQt5 5.15.11、Pillow >= 11（见 `requirements.txt`）
- 开发额外需要：pytest、PyInstaller
- 内网装包需显式走代理：
  `python -m pip install --proxy http://127.0.0.1:8888 --index-url https://pypi.org/simple <pkg>`
- **本机装了实时杀软（腾讯电脑管家）**：它会在新写出的 exe / dll 上短暂持句柄，此时对这些文件做
  改名 / 搬移 / 删除会偶发 `WinError 5 拒绝访问`（PyInstaller 打包日志里也会看到
  `remove_all_resources failed ... error(5, 'EndUpdateResourceW')`，它自己重试几次就过）。
  遇到这种报错**先重试**，不要当成逻辑 bug。
- 本机 `python -m pytest -q` **不打印 `N passed` 汇总行**：判断全绿要看**退出码是否为 0**，
  并用 `python -m pytest --collect-only -q -p no:cacheprovider` 逐文件求和交叉确认用例数。
- 跑测试建议加 `-p no:cacheprovider`，避免在仓库里留下 `.pytest_cache`。

## 目录结构

```
main.py               程序入口：PetApp 组装窗口 / 行为机 / 模块 / 托盘 / 自动更新接线
requirements.txt      运行期依赖
pytest.ini            测试配置（testpaths = tests）
pet/                  核心层
  config.py           配置默认值 + 深合并 + 类型校验 + 原子写入
  catalog.py          素材目录与分类读取；找不到目标分类时按 FALLBACK 链回退
  sprite.py           无边框窗口 + GIF 播放 + 拖拽/连点/穿透 + 贴边条渲染 + moved 信号
  behavior.py         行为状态机（idle/walk/stroll/sleep/eat/... 与优先级）
  wander.py           自主走动（WANDER 期间水平挪 4px/100ms，碰边缘折返 + 镜像转身）
  stroll.py           绕屏散步（STROLL 期间沿工作区边缘逆时针走一圈，四角各转 90°）
  edge_hide.py        贴边隐藏（缩进屏幕外，只露 24px 桔子窄条）
  tray.py             托盘图标（固定取 lulu_002.gif）+ Qt 托盘菜单
  autostart.py        开机自启（注册表 Run 项，项名 Momolulu）
  winutil.py          Win32 窗口辅助（置顶 / 点击穿透 / 全屏检测）
  version.py          VERSION 常量（发版的唯一版本来源）
  updater.py          更新元数据解析 / 版本比较 / 素材差分 / 整包校验与暂存 / updater.bat
  download.py         受限下载（白名单 host + 重定向上限 + 可选的进度回调）
  update_runner.py    三个 QThread：检查更新 / 素材热更 / 程序整包更新
modules/              功能模块层，统一 enable/tick/disable（见 base.py）
  pomodoro.py         番茄钟
  health_reminder.py  喝水与久坐提醒（两个独立子开关 + snooze）
  meal_reminder.py    吃饭提醒（时间点列表）
  hourly_chime.py     整点报时
  vitals.py           生活数值：心情 / 活力 / 饱腹（按在线时间衰减，低值软影响待机情绪）
  economy.py          噜噜币与上班（按分钟进账 + 商店食物表；扣币与补数值在 main 牵线）
ui/                   托盘菜单、设置对话框、气泡提示 toast、数值状态卡、更新弹窗
  theme.py            界面统一风格：调色板 / 圆角阴影卡片画法 / 右键菜单样式表（几处共用）
  status_card.py      数值状态卡（自绘进度条浮窗，托盘左键 / 菜单「看看状态」弹出）＋菜单顶部同款摘要条
  update_prompt.py    更新提示弹窗（版本 / 更新说明 / 下载百分比 / 失败文案）
tools_cli/            开发工具（不进产物）
  prepare.py          素材预处理：编号 / md5 去重 / 分类登记（不再去背，见「素材规范」）
  assign.py           素材整理：按 CSV 清单批量归位分类 + 打循环标，并清理悬空引用
  gif_pipeline.py     GIF 流水线（缩放 / 抽帧 / 调色 / 体积控制）＋ 保留但不再调用的去背函数
  contact_sheet.py    生成预览接触表
  build.py            PyInstaller 打包 + 素材外置 + 打 zip + 生成 latest.json
tests/                396 个用例（pytest，conftest 里提供 qapp fixture）
assets/               素材（外置，不打进 exe，当前 26 张 `processed/lulu_001~026.gif`）
update/latest.json    自动更新清单（**发布源，必须入库**）
docs/                 本文件 + `handoff-prompt.md`（新会话开场提示词）+ superpowers 下的 spec / plan
```

## 架构要点

- **分层**：`tools_cli`（素材 / 打包）→ `pet`（核心）→ `modules`（功能）→ `ui`（界面）。
  功能模块必须实现 `enable/tick/disable`，由 `main.py` 统一驱动。
- **GIF 双轨渲染**：素材分 `transparent`（已去背，直接画在桌面上）与 `card`（带背景，
  走圆角卡片渲染）两轨。轨道实测记录在 `assets/categories.json` 的 `tracks` 字段，
  `Sprite.play()` 按**被选中素材的实测轨道**渲染（不要按分类固定轨道）。
  **新素材一律要求预先去背**，管线不再去背，所以现在 26 张全是透明轨（`tracks` 为空即按
  `auto` 处理，渲染走透明分支）；`card` 轨目前没有素材在用，渲染分支要留着。
- **是否可循环由素材说了算**：`assets/categories.json` 的 `loops` 字段（文件名 → bool）记录每张素材
  是否可循环，缺省或非布尔值一律当**可循环**（兼容 0.2.4 及更早的 json）。
  `Sprite.play(category)` 只按**被选中素材**的属性设 `QMovie.loopCount`（`-1` 一直播、`1` 播一次），
  **不接受调用方干预**——可循环的素材永远循环。标了「只播一次」的素材播完发 `play_finished`，
  由 `Behavior.on_play_finished()` 收尾：普通状态回待机、`idle` 接着挑下一张待机素材
  （避免画面死在末帧）、`stroll` 忽略（一圈走完由 `on_stroll_finished` 收尾，不能半路停下）、
  分类已被别的高优先级状态顶掉时忽略。
  注意 PyQt5 里 `loopCount` 是**属性不是 setter**，要写 `movie.loopCount = -1`。
- **行为状态机** `pet/behavior.py`：`idle` 空闲一段时间后随机触发小动作，
  `_AUTO_ACTIONS = ("walk", "sad", "bath", "cry", "anxious", "surprise")` **默认等概率六选一**；
  `vitals.action_weights()` 给出的权重表经 `set_action_weights()` 传进来后改为**按权重不放回抽**
  （`_action_order()`）——权重只改「先试哪个」的顺序，抽到的分类缺素材仍会往后试，不会空转一整轮；
  `set_action_weights(None)` 或空表即恢复等概率。
  状态常量 `IDLE` / `DRAGGED` / `WANDER` / `STROLL` / `AWAKE`，分类到状态的映射见 `_STATE_NAMES`
  （默认取分类名大写，`walk → WANDER`、`stroll → STROLL` 是特例）。几个「插播式」触发点：
  - `showup`：启动后首次露面（`main._start_ui`）与从贴边隐藏恢复（`_on_edge_hidden_changed`）
    各播一次，播完再补一个 `surprise` 然后回待机。它只占 `auto` 级，不挡用户点击 / 模块通知。
  - `awake`：睡觉中被任何请求打断时插播一次（`request()` 检测到从 `sleep` 出来，
    `_to_idle()` 那条路走同一个入口），最多 8s 后回待机（可循环素材也靠这个计时兜底）。
  - `think`：番茄钟专注期间 `main._sync_life()` 用 `set_idle_category("think")` 把待机素材
    换掉，退出专注换回 `idle`；待机态没结束时会自愈（`_to_idle()` 用的就是当前 `_idle_category`）。
    上班（手动或番茄钟联动）也算「在忙」，共用这条切换。
  - `move`：拖拽时播（`on_drag_started`）；没这个分类的素材则定格当前一帧。
  - `sport`：久坐提醒触发时播（`modules/health_reminder.py` 的 SIT 表情分类）。
- **贴边隐藏** `pet/edge_hide.py`：拖到屏幕左右边缘松手即缩进屏幕外，只露 **24px** 桔子窄条
  （`DEFAULT_EDGE_PX = DEFAULT_STRIP_PX = 24`）；
  **只有把桔子拖离边缘并松手才恢复显示**，鼠标划过 / 悬停都不唤醒。状态持久化到 `config.json` 的 `pet.edge_hide`。
- **鼠标穿透双模式**：交互模式可拖拽；穿透模式不拦截鼠标（`winutil` 里改窗口扩展样式）。
- **托盘**：图标固定由 `lulu_002.gif` 首帧生成 64×64 PNG（`assets/tray_icon.png`，缺失时自动重建）；
  菜单必须用 `QMenu.popup()` 渲染，原生托盘菜单在此环境字体与项渲染异常。
  左键单击图标（`activated(Trigger)`）发 `Tray.clicked` 信号弹状态卡，右键（`Context`）才弹菜单。
- **配置**：`config.json` 位于程序目录，运行期自动生成，不入库；结构见 `pet/config.py` 的 `DEFAULTS`
  （默认显示缩放 `pet.scale = 0.5`；设置面板可调范围 0.5~2.0）。已存在的 `config.json` 不会被打包覆盖，
  且深合并时**旧值优先**——直接改 `DEFAULTS` 只对新机器生效。
- **配置版本迁移**：`DEFAULTS["version"]` 一变，`load_config` 就会跑 `pet/config.py` 的 `_migrate()`，
  按版本号补上历史默认值改动。**只迁移仍停留在旧默认值的字段**，用户自己调过的值保留；迁完写上当前版本号，
  所以是**一次性**的。当前 v1→v2：待机小动作间隔 `[30, 120]` 秒 → `[3300, 3900]` 秒（约 1 小时）。
- **素材外置**：`assets/` 与 exe 平级存放，换素材只需替换 `assets/`（改代码或素材后仍需重新打包）。
  打包时 `build.py` 会用 `_DEV_ONLY` 排除开发期产物（`.index.json` / `id_map.csv` /
  `prepare_report.json` / `contact_sheet_*.png`），`assets/` 里只剩运行期必需文件。
- **自主走动** `pet/wander.py`：`WANDER` 状态期间每 100ms 水平挪 4px（约 40px/s），碰屏幕左右缘
  折返并把噜噜镜像转身。它只负责位移，走路的 GIF 由 `Behavior` 按 `walk` 分类播。
- **绕屏散步** `pet/stroll.py`：右键菜单「搞搞震 ▸ 散步」触发。`STROLL` 状态期间每 100ms
  走 8px（约 80px/s）。起步先瞬移到当前屏右下角，再逆时针绕**工作区**边缘一圈：
  右边向上 → 顶边向左 → 左边向下 → 底边向右 → 回右下角。
  四角各逆时针转 90°（`_LEGS` 里的旋转角为 270 / 180 / 90 / 0；`QTransform.rotate()` 顺时针为正，
  故 270 即逆时针 90°）。素材是**正方形**，转 90° 不改窗口长宽，`setFixedSize` 因此不受影响。
  和 `wander.py` 一样只管位移，走路 GIF 由 `Behavior` 按 `stroll` 分类播；窗口移动发 `Sprite.moved`。
  素材朝右为基准 0°，所以走右边（向上）时是 270。
  **贴的是「工作区」而不是整屏**：`main` 通过 `bounds_provider=self._work_areas` 传入
  `availableGeometry()`，否则底边那段会走进任务栏那条带里被压住看不见（任务栏同为置顶层）。
  用哪块屏仍按**整屏**矩形判断——噜噜卡在任务栏带里时工作区判定不到它。
- **气泡跟随**：`main` 里 `_follow_toast` 订阅 `Sprite.moved`（只在坐标真变时发），
  拖拽 / 自主走动 / 散步 / 贴边滑出等**所有**位移场景都会同步气泡。
  不要在各个交互函数里分别补气泡位置——加一处新的位移逻辑时容易漏。
- **数值状态卡** `ui/status_card.py`：另一条自绘顶层窗（和 `toast.py` 同套路：
  `Qt.Tool | FramelessWindowHint | WindowStaysOnTopHint | WindowTransparentForInput` + 半透明 + 不激活），
  用彩色进度条展示心情 / 活力 / 饱腹。`main._show_status_card()` 弹（托盘左键 / 菜单），
  `_update_status()`（1s 心跳）在卡片可见时刷新。**托盘原生 tooltip 只能一行纯文本，放不下进度条**，
  所以别再往 `setToolTip` 里塞可视化。
- **界面风格统一走 `ui/theme.py`**：调色板（`BG` / `BORDER` / `TEXT_COLOR` / `STYLES`）、圆角阴影卡片画法
  `draw_card()`、右键菜单样式表 `menu_style()` 都只有这一份。状态卡、气泡、更新弹窗、右键菜单共用；
  改观感改这里。`qcolor()` 解析的是 CSS 风格 `#RRGGBBAA`（末两位是 alpha），
  **QSS 里不认这种写法**，所以 `menu_style()` 一律写 `rgba()`。
- **`menu_style()` 里绝不能出现 `border-radius`**：本机 `QStyleSheetStyle` 处理圆角时会写坏堆，
  之后任意一次 `show()`（比如 `Sprite.show()`）直接 access violation，全量测试跑到一半整个进程崩掉，
  且崩溃点看起来和菜单毫无关系。菜单圆角改由 `ui/menu.CardMenu` 的**窗口 mask** 提供。
  护栏：`tests/test_theme.py::test_menu_style_keeps_radius_off_the_menu_panel`。
- **右键菜单顶部有一条数值摘要**：`ui/menu.MenuState.vitals`（心情 / 活力 / 饱腹 / 噜噜币 / 本班进账，
  为 `None` 则不显示）→ `build_header()` 造 `StatusHeader`（状态卡同款进度条，但不画卡片边框阴影）
  → `QWidgetAction` 塞在菜单最前。`main._menu_state()` 从 `vitals` / `economy` 两个模块取数。
- **生活系统（数值 + 噜噜币）拆成两个模块**，`main` 是唯一的牵线人：
  - `modules/vitals.py`（心情 / 活力 / 饱腹）与 `modules/economy.py`（噜噜币 / 上班）**互不 import**；
    上班→衰减翻倍、食物→补数值、币→扣减这三处耦合全在 `main._sync_life()` / `_buy_food()` 里连。
  - `main._sync_life()` 由模块心跳（1s）与各交互入口调用：番茄钟专注 → `economy.set_focus()`，
    上班状态 → `vitals.set_working()`，「在忙」（专注或上班）→ 待机切 `think`，数值偏低 → 行为机加权表。
    它取代了旧的 `_sync_focus_mood()`。
  - `main._update_status()` 把两个模块的 `status_text()` 用 `" · "` 拼进托盘悬停，避免互相覆盖。
  - `behavior.state_changed` → `main._on_behavior_state()` 把「是否在睡觉」告诉 vitals（睡着活力回升）。
  - **持运行时状态的模块要实现 `Module.sync_config()`**：设置面板保存会**整份覆盖** `self.config`，
    `_apply_settings()` 在 `_save_config()` 前统一调一遍 `sync_config()`，把当下的数值 / 币补回去，
    否则会被面板打开时的旧快照顶掉。`mood` / `energy` / `satiety` / `coins` 允许为 0，
    所以在 `pet/config.py` 的 `_SPECIAL` 里注册了专门校验器（`_valid_scalar` 要求默认值 `> 0`，0 会判非法）。
- **`setWindowFlags()` 在 Windows 上会销毁重建窗口**（穿透模式切换会用到）：
  调用后必须显式 `show()` 一次，否则噜噜会从桌面消失。
- **自动更新**：见下面「自动更新」小节。

## 素材规范（改素材前必读）

- 原始件放 `assets/raw/`；工具处理后产出 `assets/processed/lulu_NNN.gif`，桌宠只引用 `processed`。
- **素材必须提前去好背（自带 alpha）**。管线**不再做去背**，`process_gif()` 拿到没有 alpha 的素材
  会直接抛 `ValueError`：该素材计入 `report["failed"]`、半成品被删掉、报告里点名，`prepare.py` 退出码 1。
  这是刻意设计的硬门槛——漏去背要立刻暴露，不许静默出片。
  去背实现（`sample_background` / `remove_background` / `analyze_frame` / `grade` 等）仍保留在
  `tools_cli/gif_pipeline.py` 里且有单测，但**已无调用方**，需要时可手工调用。
  旧版靠 `--tol` / `--edge-min` 控制去背质量，这两个参数现在只是留着，传了也不生效。
- 命名必须 `lulu_xxx.gif`；采集与处理按 **md5 去重**，同图不得重复入库。
- 账本文件：
  - `assets/.index.json`：md5 → {name, track}
  - `assets/id_map.csv`：id / raw / track 对照表（目前 `prepare.py` 已不生成，仅历史遗留）
  - `assets/categories.json`：分类结构、每张图的实测轨道与是否可循环（`loops` 字段，缺省视为可循环）
- 分类：`idle` `walk` `stroll` `sleep` `eat` `drink` `happy` `angry` `sad` `bath` `showup` `awake`
  `move` `think` `sport` `cry` `anxious` `surprise`（18 个）＋ `unassigned`。
  缺素材时按语义就近降级再落 `idle`，最后才到 `unassigned`（见 `catalog.FALLBACK`）：
  `cry→sad`、`move→walk`、`anxious→angry`、`surprise→happy`、`drink→eat`，其余同名 → `idle`。
- 当前共 **26 张**（`assets/processed/lulu_001~026.gif`）：`idle` 6、`happy` 3、`walk` 3、`angry` 3、
  `showup` 2、`awake` 2，`drink` / `move` / `think` / `sport` / `cry` / `anxious` / `surprise` 各 1；
  `stroll` / `sleep` / `eat` / `sad` / `bath` 暂无素材（靠回退链顶替），`unassigned` 为空。
  标了「只播一次」的 6 张：`lulu_001` `005` `006` `007` `013` `016`。
  `tracks` 字段目前是空的（`track_of()` 一律返回 `auto`，渲染走透明分支），实测 26 张都自带 alpha。
- 默认参数：`TOL=32`、`EDGE_MIN=0.70`、`MAX_SIDE=200`、`MAX_FPS=10`、`COLORS=96`、`MAX_BYTES=300KB`。
  高帧率 / 高分辨率素材要显式放宽，例如散步那张用的是
  `--max-side 240 --fps 20 --max-kb 500`（240×240、34 帧、394KB），
  用默认档会被抽帧到明显卡顿。
- 标准流程：**去好背的** GIF 放入 `raw/` → `python tools_cli/prepare.py [放宽参数]`
  → `python tools_cli/contact_sheet.py`（人工看图分类）→ 用 `assign.py` 按清单归位分类与循环标
  → `python tools_cli/build.py`。
- **批量整理用 `assign.py`**（`tools_cli/assign.py`），别在 `categories.json` 里手数文件名：
  - `python tools_cli/assign.py --template assets/assign.csv` 生成待填清单（列出现有素材的归属与循环标记）；
  - 清单是带表头的 CSV `file,category,loop`，一张图想挂多分类就写多行（如吃 / 喝共用一张）；
    `loop` 留空表示不改动；
  - `python tools_cli/assign.py assets/assign.csv` 落盘。**清单里出现过的文件会先摘出原分类再归位**，
    没点名的文件原样不动；未知分类、`processed/` 里不存在的文件名会跳过并点名，退出码 1。
  - 清单是开发期输入（`.gitignore` + `build.py` 的 `_DEV_ONLY` 都已排除），真相始终是 `categories.json`。
- **删素材只需删文件**，再跑 `python tools_cli/assign.py --prune`：它会把 `categories.json` 的
  分类归属 / `tracks` / `loops` 与 `.index.json` 里指向已删文件的条目一并摘掉。
  不清理 `.index.json` 的话，以后重新放回**同一张图**会被 md5 去重当成重复而跳过。
- **可循环**：`prepare.py` 登记新素材时默认在 `categories.json` 的 `loops` 里写 `true`。
  要某张图只能播一次，用 `assign.py` 的清单把 `loop` 写成 `false` 即可（`categories.json` 走素材热更
  静默下发，但用户端生效需要程序重新读一次清单）。
- 坑：
  - `prepare.py --rebuild` 会从 1 重新编号，会让既有分类错位，**不要随意使用**。
  - 手动删素材后跑一次 `assign.py --prune` 清理悬空引用（见上），别只删文件不管账本。
  - `catalog.existing_files()` 会过滤磁盘上不存在的文件名，所以删图即刻生效。
  - **`processed/` 里素材尺寸并不统一**（现有 155×155、200×200、240×240 三种）。窗口尺寸 =
    素材尺寸 × `pet.scale`，所以换分类 / 散步时噜噜体型会跳变。管线里**没有**「统一画布」这一步，
    要修得单独加。

## 常用命令

```powershell
cd momolulu
python -m pytest -q -p no:cacheprovider   # 全量测试，期望 396 项且退出码 0（本机不打印汇总行）
python tools_cli/build.py                 # 打包到 dist/momolulu/，并产出 dist/momolulu-<版本>.zip 与 dist/latest.json
python tools_cli/prepare.py               # 素材预处理
python tools_cli/contact_sheet.py         # 生成预览接触表
python tools_cli/assign.py --template assets/assign.csv   # 生成待填清单（分类 + 循环标记）
python tools_cli/assign.py assets/assign.csv --prune      # 按清单落盘，并清掉悬空引用
```

## 已确认的产品行为

- **连点**：5 秒内连点 ≥5 次触发快速点击反馈（`sprite.py` 的 `_CLICK_WINDOW_S`）。
- **贴边隐藏**：拖到屏幕左右边缘松手隐藏，露 **24px** 桔子条；拖离边缘松手才恢复，悬停不唤醒。
- **双击不打开设置**：设置入口**只在右键菜单**里（曾经的双击打开已移除，避免误触）。
- **无状态气泡**：已移除"噜噜在 XXX"的悬停状态提示，相关配置项与设置面板勾选项一并删掉。
- **气泡只用于到点提醒**：`Toast` 只在模块到点提醒时出现（番茄钟 / 喝水 / 久坐 / 吃饭 / 整点报时），
  唯一入口是 `main._module_notify`（`modules/*` 经 `ctx.notify` 调用）。点击、连点、切穿透、
  开关模块、保存设置、开关自启、发起散步、素材热更完成**都不再冒泡**——交互反馈靠噜噜的表情动作，
  别在交互处理里再加 `_show_toast`。
- **自主走动**：`idle` 待久了会随机切到 `walk`，噜噜自己在桌面上慢慢走（约 40px/s），
  走到屏幕边缘折返；走动时气泡一路跟随。
- **绕屏散步**：右键菜单「搞搞震 ▸ 散步」触发。噜噜先瞬移到当前屏右下角，再沿**工作区**边缘
  逆时针走一圈（约 80px/s），四个拐角各逆时针转 90° 保持脚贴边，走完落回待机；
  中途拖拽即中止散步。底边那段踩在任务栏上沿，不会走进任务栏区域。
- **素材可循环属性**：每张素材在 `categories.json` 的 `loops` 里标「是否可循环」。可循环的素材
  **永远循环**（调用方无法要求它只播一次）；标成「只播一次」的素材播完最后一帧就停下回待机
  （`idle` 则接着挑下一张待机图继续播，不会死在末帧；散步途中不截断，由一圈走完统一收尾）。
  新素材默认 `true`。当前 26 张里有 6 张是 `false`。
- **新表情的触发时机**：启动 / 从贴边隐藏恢复播 `showup`（随后补一个 `surprise`）；
  睡觉被叫醒先播 `awake`；番茄钟专注期间待机素材换成 `think`；久坐提醒触发时播 `sport`；
  拖拽时播 `move`（没有该素材则定格当前帧）；`cry` / `anxious` / `surprise` 也进了待机随机小动作池。
- **生活系统数值**：心情 / 活力 / 饱腹三项 0~100，**在线时**按小时衰减（心情 6、活力 8、饱腹 10），
  睡觉时活力改为 +30/h，上班时心情 / 活力衰减 ×2（饱腹不受影响）。跌破 10 冒一次泡（回到 30 以上才重新武装）。
  数值偏低时待机小动作更偏负面情绪（`sad` / `cry` / `anxious` 加权，软影响，不强制）。
- **噜噜币 / 上班**：右键菜单「照顾噜噜 ▸ 上班 / 下班」手动开关，或番茄钟专注时自动联动（两者「或」）。
  上班按 1 币/分钟进账，时长越长赚越多；上班时待机素材切 `think`，托盘悬停显示「上班中 · 已赚 N 噜噜币」。
- **商店喂食**：右键菜单「照顾噜噜 ▸ 喂食」用噜噜币买：冰淇淋 10→+10 饱腹 & 心情、蛋糕 20→+20、
  汉堡 30→+30（越贵补得越多），买不起的项置灰。「照顾噜噜 ▸ 哄睡」直接把噜噜哄睡（睡着活力回升）。
- **提醒模块默认值**：`pomodoro` 关、`health_reminder` 开（喝水 45min / 久坐 60min）、
  `meal_reminder` 开（12:00、18:30）、`hourly_chime` 关；`vitals` / `economy` 均开（初始 80/80/80、0 币）。

## 待办 / 未决

1. 待机小动作加权已落地（数值偏低时由 `vitals.action_weights()` 给行为机权重表，软影响）；
   是否还要给「上班 / 专注」再叠一层权重、以及各食物是否要差异化加成（目前按价线性）尚未定。
2. `docs/superpowers/` 下 **2026-10-20 那份 spec / plan 是改名前的旧描述**（`lulu_pet`、
   悬停滑出 + 3s 缩回、48px 桔子条、双击打开设置），**尚未回写**，读的时候注意甄别；
   2026-10-21 那份（`2026-10-21-auto-update*`）是自动更新这一版，与代码一致。
3. 开机自启项名已从 `LuluPet` 改为 `Momolulu`，旧注册表项可能残留：
   在设置面板里关一次再开一次自启，或手工删 `HKCU\...\Run\LuluPet`。
4. aigei 采集候选约 254 张（约 630MB）仍在开发机的 `_stage_gifs/aigei/`，未入库、可清理。
5. **更新分两条轨**（同一次启动检查里各自独立判断）：
   - 素材热更：`info["asset_changes"]` 非空时**静默**下载替换 `assets/`，不打扰用户；
   - 主程序更新：`info["package"]` 存在时**弹窗**征求同意，才下载整包自替换。
6. `.gitignore` 覆盖 `dist/`、`*.spec`、`config.json`、`momolulu.log`、`.superpowers/`、
   `assets/raw/`、`.index.json`、`id_map.csv`、`prepare_report.json`、`contact_sheet_*.png`、
   `tray_icon.png`。clone 后 `assets/` 里只有 `processed` 的 26 张图与 `categories.json`；
   完整素材链路（`raw/` 采集件与账本）需要另外传输。
7. 睡着时被点击 / 提醒打断，只会播 `awake`，被打断的那个表情（如喝水 / 开心）不播——当前是
   「插播式覆盖」。要「醒觉播完再接原表情」得给行为机加个待播队列，产品上还没定。
8. `categories.json` 的 `tracks` 是空的（素材改名那轮重置的遗留）：26 张实测都自带 alpha，
   `track_of()` 返回 `auto`、渲染走透明分支，画面正确；若将来要按目录记实测轨道，得重跑一次素材管线。

## 在另一台电脑继续

```powershell
git clone https://github.com/zhuolk/momolulu.git
cd momolulu
python -m pip install -r requirements.txt
python -m pip install pytest pyinstaller
python -m pytest -q -p no:cacheprovider    # 期望 396 项且退出码 0
```

然后让 AI 先读本文件、再读 `docs/superpowers/specs/` 与 `plans/` 即可接手。
想省事就直接把 [`docs/handoff-prompt.md`](handoff-prompt.md) 里「## 提示词」一节整段贴进新会话
（它已把「先读哪些文件 / 怎么验收 / 哪些不许擅自做」写好，只在末尾补一句本轮要做什么）。

注意：**Trae 的对话历史不在仓库里**——它由客户端 / 云端账号管理，本机没有可搬运的会话文件
（已确认 `%APPDATA%\Trae\User\workspaceStorage\` 下没有 chatSessions 之类的记录）。
跨设备靠的是"仓库 + 本交接文档"，或在新客户端登录同一 Trae 账号看账号下的历史会话。
新机器 clone 到的是 `0.2.6`；「当前进度」那批生活系统改动**只有提交推送后**才会跟着走，
否则新机器上 `modules/vitals.py`、`modules/economy.py` 与对应测试都不存在。

## 自动更新

两条轨，都在**启动 5 秒后**检查一次（仅打包版执行，脚本模式跳过——源码目录不是可替换的安装目录）。
检查源是 `pet/updater.py` 里的常量 `LATEST_URL`
（`https://raw.githubusercontent.com/zhuolk/momolulu/main/update/latest.json`）。

- **素材热更（静默）**：比对 `latest.json` 的 `assets.files`（文件名 → md5）与本地 `assets/`，
  有差异就后台下载替换，完成后重载 `categories.json`，弹一句「噜噜换新衣服啦」。
  **不发新版本号也能生效**——把新 GIF 传到仓库 `assets/processed/` 即可。
- **主程序更新（弹窗）**：`latest.json` 的 `package` 带整包 `url` / `sha256` / `size`。
  本地版本低于远端时弹 `UpdatePrompt`，用户点「现在更新」才走：
  下载整包 → 校验 sha256 与体积 → 解压到 `%TEMP%/momolulu-update/momolulu.new/`（剥掉 zip 顶层目录）
  → 写 `updater.bat` → 退出主程序 → 由 bat 在进程结束后做目录交换（程序**自己覆盖不了自己**），
  并保留用户 `config.json`、失败可回滚。

踩过的坑（别再踩）：

- **`updater.bat` 第一步必须 `cd /d "%~dp0"` 把工作目录切出安装目录**：`cmd` 继承的是噜噜的 cwd，
  而从资源管理器双击启动时 cwd 就是安装目录本身；Windows 下「某进程的当前目录」会一直持有该目录句柄，
  导致 `move "%TARGET%" "%OLD%"` **每圈都失败**，30 次重试耗尽后走 `:failed` 重新拉起旧版，
  于是又弹更新提示，循环往复。现象是**「点了确认更新后一直停在 ping -n 2 127.0.0.1」**
  （ping 只是它的 1 秒定时器）。回归测试：`tests/test_updater_bat.py::test_bat_leaves_its_cwd_before_moving`。
- **解压必须逐成员直接写最终路径，不要「先 `extractall` 再改名展平」**：实时杀软会短暂持有刚写出的
  exe / dll 句柄，此时对目录改名 / 搬移会稳定吃 `WinError 5 拒绝访问`，整包永远装不上，
  而 UI 上只表现为**「一直卡在正在下载」**（其实线程已失败，只是会晚一点恢复按钮）。
  这条有回归测试盯着：
  `tests/test_program_update.py::test_prepare_program_update_denied_rename_still_stages`
  （把所有 rename / move 封成 `PermissionError(5)`，流程仍须落出完整暂存目录与 bat）。
- 下载期弹窗显示百分比（**封顶 99%**，后面还有校验与解压，报 100% 会像卡住），
  失败则追加「更新失败，已保留当前版本」。
- **已安装的旧版本若自身带更新 bug，是没法靠自动更新自救的**（0.1.0 就卡在上面那个 `WinError 5`），
  只能让用户手工换包。
- 打包后是 `--noconsole`，出问题只能看安装目录下的 `momolulu.log`（`WARNING` 级起，utf-8）。

## 发版

1. 改 `pet/version.py` 的 `VERSION`
2. `python tools_cli/build.py`
   → 产出 `dist/momolulu/`（onedir）、`dist/momolulu-<版本>.zip`、`dist/latest.json`
   （注意 `dist/latest.json` 的 `notes` 是**空的**，发布前自己填）
3. 建 GitHub Release 并上传整包。**本机没有 `gh` CLI**（`build.py` 末尾那两行 `gh` 提示只是文案），两条路：
   - 网页手动：新建 tag `v<版本>` 的 Release，把 `dist/momolulu-<版本>.zip` 拖上去；
   - 或 REST API（系统自带 `curl.exe`；PAT 从本机 Git 凭据管理器取）：
     `POST https://api.github.com/repos/zhuolk/momolulu/releases` 建 release，
     再 `POST https://uploads.github.com/repos/zhuolk/momolulu/releases/<id>/assets?name=momolulu-<版本>.zip`
     上传资产。**上传后核对返回的 `digest`（sha256）与本地 `Get-FileHash` 是否逐字一致**。
4. 把 `dist/latest.json` 的内容（**补上 `notes`**）覆盖到仓库 `update/latest.json`，`git push`
   —— **顺序很重要：先让 Release 资产可下载，再推 `latest.json`**，否则用户会探测到新版却下载 404。
5. 素材有变动时 `assets/` 已在 git 里，push 完即生效。
6. 复核：`curl` 拉一次 raw 上的 `latest.json` 确认版本号与 `sha256` / `size` 对得上；
   再对资产 URL 发一次 range 请求，确认返回 `206`。

注意 `raw.githubusercontent.com` 有几分钟 CDN 缓存，push 完对方不一定立刻看到。
