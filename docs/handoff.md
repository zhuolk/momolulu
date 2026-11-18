# 交接说明（handoff）

给"换一台电脑继续开发"用的上下文快照。读完这份文档 + `docs/superpowers/` 下的 spec/plan，即可接手。

## 这是什么

噜噜桌宠（打包名 `momolulu`）：Windows 桌面水豚挂件。PyQt5 无边框置顶窗口循环播放 GIF，
带行为状态机、自主走动、绕屏散步、贴边隐藏、鼠标穿透双模式、托盘菜单，
番茄钟 / 喝水·久坐 / 吃饭 / 整点报时提醒，生活数值（心情·活力·饱腹）与噜噜币（上班赚钱 + 商店喂食），
以及启动时自动检查的素材热更与主程序自动更新。

- 仓库（**公开**）：<https://github.com/zhuolk/momolulu>
- 分支：`main` —— 发布直接推 `main`，自动更新只认 `main` 上的 `update/latest.json`
- 当前版本：`0.3.0`（唯一来源 `pet/version.py` 的 `VERSION`）
- 测试：408 个 pytest 用例全量通过
- 本地构建：PyInstaller onedir 约 119 MB；分发 zip 约 52 MB。若旧程序占用 dist，可用 `tools_cli/build.py --out <独立目录>`。
- 已具备自动更新：启动时探测远端 `latest.json`，有新版弹窗征得同意后下载整包自替换（详见「自动更新」）

## 0.3.0 与近期界面变更

- **界面风格统一**：新增 `ui/theme.py`（调色板 + `draw_card()` + `menu_style()`），
  `ui/toast.py` / `ui/status_card.py` / `ui/update_prompt.py` / `ui/menu.py` 改用它，
  气泡与更新弹窗的圆角、阴影、配色从此跟状态卡一处改、处处变。
- **右键菜单加数值摘要**：菜单最上面一条 `StatusHeader`（状态卡同款进度条：心情 / 活力 / 饱腹三个
  小图标 + 进度条 + 噜噜币或本班进账），数据由 `main._menu_state()` 从 `vitals` / `economy` 两个模块取。
- **踩坑记录**：`QMenu` 的样式表里一旦出现 `border-radius`，本机 `QStyleSheetStyle` 会写坏堆，
  全量测试跑到 `main.py::_start_ui` 的 `sprite.show()` 时整个进程 access violation；
  菜单圆角改用窗口 mask（`ui/menu.CardMenu`）。
- **状态卡图标改彩色**：`ui/status_card.py` 的 `icon_path()` 换成 `icon_parts()`（返回多段「矢量路径 + 色值」），
  心情=红心、活力=闪电、饱腹=汉堡、噜噜币=星金币，**固定彩色、不随数值变色**；
  note 行左侧也画一枚星金币，文字里的「噜噜币」三个字去掉只留数额。
- **素材管线取消去背硬门槛**：`process_gif()` 按首帧 alpha 分轨，没去背的素材不再抛错，
  改记成 `card` 轨（渲染层套圆角卡片遮背景），两条轨都收。
- **素材新增「启用」标记**：`assets/categories.json` 升到 `version 4`，新增顶层 `enabled`
  （文件名 → bool，缺省视为启用）。`enable=false` 的素材**不参与播放**（`catalog.pick()` 过滤掉）、
  **打包时跳过**（`build.py` 的 `disabled_assets()` 同时作用于产物目录与 `latest.json` 的 `assets.files`，
  所以老用户不会被提示下载它；但不会主动删除别人机器上的存量副本）。`assign.py` 清单相应加第 4 列
  `enable`；托盘图标原固定取 `lulu_002.gif`，它被标成不启用后改用 `lulu_008.gif`。
- `confuse` 等新分类已接入实际触发点，移除了 `sad`、`bath`、`cry`、`surprise` 及其废弃场景。

## 最近一批改动（已随 `0.2.8` 提交推送）

- **状态卡浮窗（`ui/status_card.py`）**：托盘原生悬停提示（`QSystemTrayIcon.setToolTip`）只能一行纯文本，
  画不出进度条，于是另起一个自绘顶层窗：鼠标穿透、不抢焦点、8 秒后自动收起。卡片用三条彩色进度条展示
  心情 / 活力 / 饱腹（左侧是红心 / 闪电 / 汉堡小图标，`icon_parts()` 矢量自绘、固定彩色、不依赖图片或字体符号；
  进度条按阈值变色：<30 红 / <60 黄 / <85 绿 / ≥85 深绿，横向 `QLinearGradient` 渐变填充），
  底部一行是星金币图标 + 噜噜币数额（上班中则改显示本班进账）。弹出入口：**托盘图标左键单击**
  （`pet/tray.py` 新增 `clicked` 信号）。
- `main.py` 新增 `_show_status_card` / `_refresh_status_card` / `_fill_status_card`；心跳 `_update_status()`
  会在卡片可见时每秒刷新；`_toggle_visible` 与 `shutdown` 都要 `status_card.hide()`。
- 新增 `tests/test_status_card.py`，并在 `tests/test_menu.py`（托盘 `clicked` 信号）与
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
  tray.py             托盘图标（固定取 lulu_008.gif）+ Qt 托盘菜单
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
  vitals.py           生活数值：心情 / 活力 / 饱腹（按在线时间衰减，低值触发提醒）
  economy.py          噜噜币与上班（按分钟进账 + 商店食物表；扣币与补数值在 main 牵线）
ui/                   托盘菜单、设置对话框、气泡提示 toast、数值状态卡、更新弹窗
  theme.py            界面统一风格：调色板 / 圆角阴影卡片画法 / 右键菜单样式表（几处共用）
  status_card.py      数值状态卡（自绘进度条浮窗，托盘左键弹出）＋菜单顶部同款摘要条
  update_prompt.py    更新提示弹窗（版本 / 更新说明 / 下载百分比 / 失败文案）
tools_cli/            开发工具（不进产物）
  prepare.py          素材预处理：编号 / md5 去重 / 分类登记（不再去背，见「素材规范」）
  assign.py           素材整理：按 CSV 清单批量归位分类 + 打循环标 + 标启用，并清理悬空引用
  gif_pipeline.py     GIF 流水线（缩放 / 抽帧 / 调色 / 体积控制）＋ 保留但不再调用的去背函数
  contact_sheet.py    生成预览接触表
  build.py            PyInstaller 打包 + 素材外置 + 打 zip + 生成 latest.json
tests/                408 个用例（pytest，conftest 里提供 qapp fixture）
assets/               素材（外置，不打进 exe，当前 41 张 `processed/lulu_001~041.gif`）
update/latest.json    自动更新清单（**发布源，必须入库**）
docs/                 本文件 + `handoff-prompt.md`（新会话开场提示词）+ superpowers 下的 spec / plan
```

## 架构要点

- **分层**：`tools_cli`（素材 / 打包）→ `pet`（核心）→ `modules`（功能）→ `ui`（界面）。
  功能模块必须实现 `enable/tick/disable`，由 `main.py` 统一驱动。
- **GIF 双轨渲染**：素材分 `transparent`（已去背，直接画在桌面上）与 `card`（带背景，
  走圆角卡片渲染）两轨。轨道实测记录在 `assets/categories.json` 的 `tracks` 字段，
  `Sprite.play()` 按**被选中素材的实测轨道**渲染（不要按分类固定轨道）。
  管线按**首帧是否有 alpha** 分轨：自带 alpha → 透明轨；没去背 → 卡片轨
  （渲染层套一层圆角卡片把不透明背景框起来，见 `render_frame()`），不再拒收。
  `tracks` 里没有记录的素材按 `auto` 处理，渲染走透明分支。
- **是否可循环由素材说了算**：`assets/categories.json` 的 `loops` 字段（文件名 → bool）记录每张素材
  是否可循环，缺省或非布尔值一律当**可循环**（兼容 0.2.4 及更早的 json）。
  `Sprite.play(category)` 只按**被选中素材**的属性设 `QMovie.loopCount`（`-1` 一直播、`1` 播一次），
  **不接受调用方干预**——可循环的素材永远循环。标了「只播一次」的素材播完发 `play_finished`，
  由 `Behavior.on_play_finished()` 收尾：普通状态回待机、`idle` 接着挑下一张待机素材
  （避免画面死在末帧）、`stroll` 忽略（一圈走完由 `on_stroll_finished` 收尾，不能半路停下）、
  分类已被别的高优先级状态顶掉时忽略。
  注意 PyQt5 里 `loopCount` 是**属性不是 setter**，要写 `movie.loopCount = -1`。
- **是否启用由素材说了算**：`assets/categories.json` 的 `enabled` 字段（文件名 → bool）记录每张素材
  是否启用，缺省或非布尔值一律当**启用**（`catalog.enabled_of()`）。`false` 的素材：
  ① `catalog.pick()` 会把它滤掉，任何分类都不会挑中它（该分类因此可能只剩别的素材或返回 `None`）；
  ② `build.py` 打包时跳过它（不进产物 `assets/processed/`，也不进 `latest.json` 的 `assets.files`）。
  改启用标记走 `assign.py` 清单第 4 列，别手改 json。
- **行为状态机**：待机小动作只保留 `walk`，普通待机久了也可入睡。数值低时走模块提醒，不再给动作池加权。
  状态常量 `IDLE` / `DRAGGED` / `WANDER` / `STROLL` / `AWAKE`，分类到状态的映射见 `_STATE_NAMES`
  （默认取分类名大写，`walk → WANDER`、`stroll → STROLL` 是特例）。几个「插播式」触发点：
  - `showup`：启动后首次露面（`main._start_ui`）与从贴边隐藏恢复（`_on_edge_hidden_changed`）
    各播一次，播完回待机。
  - `awake`：睡觉中被任何请求打断时插播一次（`request()` 检测到从 `sleep` 出来，
    `_to_idle()` 那条路走同一个入口），最多 8s 后回待机（可循环素材也靠这个计时兜底）。
  - 专注、上班、搬砖分别将待机分类切为 `think`、`work`、`bricklay`；期间可自主走动，不会自动入睡。
  - `move`：拖拽时播（`on_drag_started`）；没这个分类的素材则定格当前一帧。
  - `sport`：久坐提醒触发时播（`modules/health_reminder.py` 的 SIT 表情分类）。
- **贴边隐藏** `pet/edge_hide.py`：拖到屏幕左右边缘松手即缩进屏幕外，只露 **24px** 桔子窄条
  （`DEFAULT_EDGE_PX = DEFAULT_STRIP_PX = 24`）；
  **只有把桔子拖离边缘并松手才恢复显示**，鼠标划过 / 悬停都不唤醒。状态持久化到 `config.json` 的 `pet.edge_hide`。
- **鼠标穿透双模式**：交互模式可拖拽；穿透模式不拦截鼠标（`winutil` 里改窗口扩展样式）。
- **托盘**：图标固定由 `lulu_008.gif` 首帧生成 64×64 PNG（`assets/tray_icon.png`，缺失时自动重建）；
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
  用彩色进度条展示心情 / 活力 / 饱腹（左侧小图标由 `icon_parts()` 自绘：红心 / 闪电 / 汉堡，固定彩色），
  底部一行是星金币图标 + 噜噜币数额。`main._show_status_card()` 弹（托盘左键），
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
- **这个 mask 只能从 1 位位图（`QBitmap`）生成**：别用 `QPainterPath.toFillPolygon().toPolygon()`
  再喂给 `QRegion`——同样会写坏堆，症状和上面那条一模一样（全量测试跑到 `test_smoke` 里
  `Sprite.show()` 时整个进程崩掉，`setMask` 一个正矩形区域却没事）。
- **右键菜单顶部有一条数值摘要**：`ui/menu.MenuState.vitals`（心情 / 活力 / 饱腹 / 噜噜币 / 本班进账，
  为 `None` 则不显示）→ `build_header()` 造 `StatusHeader`（状态卡同款进度条，但不画卡片边框阴影）
  → `QWidgetAction` 塞在菜单最前。`main._menu_state()` 从 `vitals` / `economy` 两个模块取数。
- **生活系统（数值 + 噜噜币）拆成两个模块**，`main` 是唯一的牵线人：
  - `modules/vitals.py`（心情 / 活力 / 饱腹）与 `modules/economy.py`（噜噜币 / 上班）**互不 import**；
    `main._activity()` 由当前班次与动画判定生活活动；菜单和处理函数双重检查。`_sync_life()` 将上班、搬砖分别联动心情和活力衰减，专注不抢占其他生活活动。
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
- **按首帧有没有 alpha 分轨**，两条轨都收：
  - 自带 alpha → **透明轨**，直接画在桌面上，边缘干净；
  - 没去背（不透明底）→ **卡片轨**，渲染层套一层圆角卡片把背景框起来（观感像一张相片）。
  判定只看**首帧**（加上 `im.info["transparency"]`）——首帧透明但后续帧不透明的素材会被误判成透明轨。
  去背实现（`sample_background` / `remove_background` / `analyze_frame` / `grade` 等）仍保留在
  `tools_cli/gif_pipeline.py` 里且有单测，但**已无调用方**，需要时可手工调用。
  旧版靠 `--tol` / `--edge-min` 控制去背质量，这两个参数现在只是留着，传了也不生效。
- 命名必须 `lulu_xxx.gif`；采集与处理按 **md5 去重**，同图不得重复入库。
- 账本文件：
  - `assets/.index.json`：md5 → {name, track}
  - `assets/id_map.csv`：id / raw / track 对照表（目前 `prepare.py` 已不生成，仅历史遗留）
  - `assets/categories.json`：分类结构、每张图的实测轨道（`tracks`）、是否可循环（`loops`）
    与是否启用（`enabled`）；`loops` / `enabled` 缺省或非布尔值分别当 `true` / 启用
- 27 个动作分类另加 `unassigned`；`pet/catalog.py` 是分类与回退链的真相源。`stroll` 不回退；`drink→eat`、`move→walk`、`anxious→angry` 后再按通用链降级。0.3.0 有 41 张 GIF，11 张停用，整包及热更清单均含 30 张 GIF。
  `tracks` 里 `lulu_027~036` 是 `transparent`、`lulu_037~041` 是 `card`（这 5 张没去背，走卡片轨）。
- 默认参数：`TOL=32`、`EDGE_MIN=0.70`、`MAX_SIDE=200`、`MAX_FPS=10`、`COLORS=96`、`MAX_BYTES=300KB`。
  高帧率 / 高分辨率素材要显式放宽，例如散步那张用的是
  `--max-side 240 --fps 20 --max-kb 500`（240×240、34 帧、394KB），
  用默认档会被抽帧到明显卡顿。
- 标准流程：**去好背的** GIF 放入 `raw/` → `python tools_cli/prepare.py [放宽参数]`
  → `python tools_cli/contact_sheet.py`（人工看图分类）→ 用 `assign.py` 按清单归位分类 / 循环标 / 启用标
  → `python tools_cli/build.py`。
- **批量整理用 `assign.py`**（`tools_cli/assign.py`），别在 `categories.json` 里手数文件名：
  - `python tools_cli/assign.py --template assets/assign.csv` 生成待填清单（列出现有素材的归属、循环标记与启用标记）；
  - 清单是带表头的 CSV `file,category,loop,enable`，一张图想挂多分类就写多行（如吃 / 喝共用一张）；
    `loop` / `enable` 留空表示不改动，`enable=false` 的素材不参与播放、打包也不带；
  - `python tools_cli/assign.py assets/assign.csv` 落盘。**清单里出现过的文件会先摘出原分类再归位**，
    没点名的文件原样不动；未知分类、`processed/` 里不存在的文件名会跳过并点名，退出码 1。
  - 清单是开发期输入（`.gitignore` + `build.py` 的 `_DEV_ONLY` 都已排除），真相始终是 `categories.json`。
- **删素材只需删文件**，再跑 `python tools_cli/assign.py --prune`：它会把 `categories.json` 的
  分类归属 / `tracks` / `loops` / `enabled` 与 `.index.json` 里指向已删文件的条目一并摘掉。
  不清理 `.index.json` 的话，以后重新放回**同一张图**会被 md5 去重当成重复而跳过。
- **可循环**：`prepare.py` 登记新素材时默认在 `categories.json` 的 `loops` 里写 `true`。
  要某张图只能播一次，用 `assign.py` 的清单把 `loop` 写成 `false` 即可（`categories.json` 走素材热更
  静默下发，但用户端生效需要程序重新读一次清单）。
- **是否启用**：`prepare.py` 登记的新素材默认启用（`enabled` 里不写或写 `true`）。
  要停用某张素材，用 `assign.py` 的清单把 `enable` 写成 `false`；它既不参与播放也不进打包产物。
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
python -m pytest -q -p no:cacheprovider   # 全量测试，期望 408 项且退出码 0（本机不打印汇总行）
python tools_cli/build.py                 # 打包到 dist/momolulu/，并产出 dist/momolulu-<版本>.zip 与 dist/latest.json
python tools_cli/prepare.py               # 素材预处理
python tools_cli/contact_sheet.py         # 生成预览接触表
python tools_cli/assign.py --template assets/assign.csv   # 生成待填清单（分类 + 循环标记 + 启用标记）
python tools_cli/assign.py assets/assign.csv --prune      # 按清单落盘，并清掉悬空引用
```

## 已确认的产品行为

- **连点**：5 秒内连点 ≥5 次触发快速点击反馈（`sprite.py` 的 `_CLICK_WINDOW_S`）。
- **贴边隐藏**：拖到屏幕左右边缘松手隐藏，露 **24px** 桔子条；拖离边缘松手才恢复，悬停不唤醒。
- **双击不打开设置**：设置入口**只在右键菜单**里（曾经的双击打开已移除，避免误触）。
- **无状态气泡**：已移除"噜噜在 XXX"的悬停状态提示，相关配置项与设置面板勾选项一并删掉。
- **提示与特效**：模块提醒与部分生活操作用 Toast；桌面泡泡由独立的透明穿透窗口绘制，隐藏、拖动或退出时收起。
- **自主走动**：`idle` 待久了会随机切到 `walk`，噜噜自己在桌面上慢慢走（约 40px/s），
  走到屏幕边缘折返；走动时气泡一路跟随。
- **绕屏散步**：右键菜单「搞搞震 ▸ 散步」触发。噜噜先瞬移到当前屏右下角，再沿**工作区**边缘
  逆时针走一圈（约 80px/s），四个拐角各逆时针转 90° 保持脚贴边，走完落回待机；
  中途拖拽即中止散步。底边那段踩在任务栏上沿，不会走进任务栏区域。
- **素材可循环属性**：每张素材在 `categories.json` 的 `loops` 里标「是否可循环」。可循环的素材
  **永远循环**（调用方无法要求它只播一次）；标成「只播一次」的素材播完最后一帧就停下回待机
  （`idle` 则接着挑下一张待机图继续播，不会死在末帧；散步途中不截断，由一圈走完统一收尾）。
  新素材默认 `true`。当前 41 张里有 8 张是 `false`（`lulu_001` `005` `006` `007` `013` `016` `027` `037`）。
- **素材启用属性**：每张素材在 `categories.json` 的 `enabled` 里标「是否启用」，缺省视为启用。
  标成 `false` 的素材**不参与播放**（同类里会被跳过，选不出来）且**打包时被忽略**
  （不进产物目录，也不进自动更新素材清单）。菜单入口、数值变化与工种互斥规则见 README 的「右键菜单」。睡眠恢复活力，生日当天（12 月 24 日）启动时触发生日表情。
- **提醒模块默认值**：`pomodoro` 关、`health_reminder` 开（喝水 45min / 久坐 60min）、
  `meal_reminder` 开（12:00、18:30）、`hourly_chime` 关；`vitals` / `economy` 均开（初始 80/80/80、0 币）。

## 待办 / 未决

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
   `tray_icon.png`。clone 后 `assets/` 里只有 `processed` 的 41 张图与 `categories.json`；
   完整素材链路（`raw/` 采集件与账本）需要另外传输。
7. 睡着时被点击 / 提醒打断，只会播 `awake`，被打断的那个表情（如喝水 / 开心）不播——当前是
   「插播式覆盖」。要「醒觉播完再接原表情」得给行为机加个待播队列，产品上还没定。
8. `categories.json` 的 `tracks` 只记了 `lulu_027~041`（`027~036` 透明轨、`037~041` 卡片轨）；
   更早的 `lulu_001~026` 没有记录（素材改名那轮重置的遗留），它们实测都自带 alpha，
   `track_of()` 返回 `auto`、渲染走透明分支，画面正确；若要把旧素材也补上实测轨道，得重跑一次素材管线。

## 在另一台电脑继续

```powershell
git clone https://github.com/zhuolk/momolulu.git
cd momolulu
python -m pip install -r requirements.txt
python -m pip install pytest pyinstaller
python -m pytest -q -p no:cacheprovider    # 期望 408 项且退出码 0
```

然后让 AI 先读本文件、再读 `docs/superpowers/specs/` 与 `plans/` 即可接手。
想省事就直接把 [`docs/handoff-prompt.md`](handoff-prompt.md) 里「## 提示词」一节整段贴进新会话
（它已把「先读哪些文件 / 怎么验收 / 哪些不许擅自做」写好，只在末尾补一句本轮要做什么）。

注意：**Trae 的对话历史不在仓库里**——它由客户端 / 云端账号管理，本机没有可搬运的会话文件
（已确认 `%APPDATA%\Trae\User\workspaceStorage\` 下没有 chatSessions 之类的记录）。
跨设备靠的是"仓库 + 本交接文档"，或在新客户端登录同一 Trae 账号看账号下的历史会话。
新机器以 main 分支的已提交文件为准；用户配置和原始素材不会随 clone 迁移。

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
