# 噜噜自动更新设计（2026-10-21）

## 1. 意图

噜噜已经发给同事和朋友在用了。每加一张素材、每修一个 bug，都要重新发一次压缩包、
让对方手动解压覆盖，很麻烦。

这份设计要解决的是：**发出去一次之后，你在自己这边改完并发布，对方那边的噜噜
自己就能收到新素材和新功能。**

## 2. 目标 / 非目标 / 反目标

**目标**

- 噜噜启动时检查一次更新；素材更新静默生效，程序更新问一句再动手
- 对方**不需要装 Python、不需要装 git、不需要开命令行**，双击就用
- 更新源可替换（换成 Gitee / 对象存储 / 内网直链时只改一处）
- 任何一步失败都不影响噜噜继续用

**非目标**

- 不做增量二进制补丁（每次整包替换，简单可靠优先）
- 不做更新通道切换（正式版/测试版）
- 不做强制更新（用户永远有权拒绝）
- 不做后台常驻轮询（只在启动时检查一次，符合已确认的决定）

**反目标**

- 为了"自动"而在程序里内嵌任何 GitHub 凭据
- 更新失败后留下一个跑不起来的噜噜
- 替换过程中静默删掉对方的 `config.json`（缩放、位置、模块开关必须保留）

## 3. 已确认的决定（由你拍板）

| 决定 | 你选的 |
| --- | --- |
| 使用场景 | 发给同事/朋友，他们自动收到新素材和功能 |
| 更新源 | GitHub，把 `zhuolk/momolulu` 直接转成公开仓库 |
| 检查时机 | 只在启动时检查一次 |
| 程序更新交互 | 弹一句「有新版本，要现在更新吗」，同意才更新 |
| 弹窗点「稍后」后的入口 | 托盘菜单里加一项「立即更新到 x.y.z」 |

## 4. 现状（代码事实）

- 打包方式：PyInstaller `--onedir`，产物 `dist/momolulu/`，含 `momolulu.exe`、
  `_internal/`、`assets/`、`config.json`（见 [build.py](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/tools_cli/build.py)）
- 资源根：`app_root()` 打包后取 exe 所在目录，脚本模式取源码目录（见 [main.py](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/main.py#L60-L64)）
- 素材外置：`assets/processed/lulu_NNN.gif` + `assets/categories.json`；
  `assets/raw/`、`.index.json`、`id_map.csv`、`tray_icon.png` 不入库（见 [.gitignore](file:///d:/Users/linkai.zhuo/Documents/Trae/temp_20261020_01/capybara_pet/.gitignore)）
- **工程里目前没有任何应用版本号**（只有素材索引的 schema 版本 `catalog.VERSION = 2`）
- `config.json` 不在仓库里，是每台机器运行期生成/修改的
- `Sprite.reload()` 已存在，可在素材变化后重建影片缓存

## 5. 方案总览

两条更新路径分开走，因为代价差很多：

| 内容 | 大小 | 时机 | 交互 | 需要重启 |
| --- | --- | --- | --- | --- |
| 素材（`assets/`） | 几十 KB ~ 几百 KB | 启动检查时 | 静默 | 否 |
| 程序（整个安装目录，**不含 `config.json`**） | ~132MB（zip ~54MB） | 用户同意后 | 弹窗确认 | 是 |

更新源抽象成一个 URL 常量 + 一个 `fetch` 可调用对象（依赖注入），
换源或做测试时只替换这一处，上层逻辑不动。

```
启动 → 等 5s → 取 latest.json ──失败/超时──→ 静默放弃，本次不再检查
                                 │
                                 ├─ 素材有差异 → 逐个下载 → 覆盖 → 重载 → 不打扰用户
                                 │
                                 └─ 远端版本更新 → 弹窗「要现在更新吗」
                                                     │是
                                                     ↓
                                     下载 zip → 校验 → 写 updater.bat → 噜噜退出
                                                     ↓
                                     updater.bat：等退出 → 目录交换 → 重启噜噜
```

## 6. 版本与发布物

### 6.1 应用版本号

新增 `pet/version.py`：

```python
VERSION = "0.1.0"
```

单一真相源，程序读它、`build.py` 也读它。首次发布定为 `0.1.0`。

### 6.2 `latest.json`

发布时生成在仓库根目录的 `update/` 下（体积很小，可以进 git）：

```json
{
  "version": "0.2.0",
  "notes": "新增两张素材，修复穿透后消失",
  "package": {
    "url": "https://github.com/zhuolk/momolulu/releases/download/v0.2.0/momolulu-0.2.0.zip",
    "sha256": "…",
    "size": 56341000
  },
  "assets": {
    "base": "https://raw.githubusercontent.com/zhuolk/momolulu/main/assets/",
    "files": {
      "processed/lulu_001.gif": "<md5>",
      "processed/lulu_002.gif": "<md5>",
      "categories.json": "<md5>"
    }
  }
}
```

- `version`：远端版本，和本地 `VERSION` 做语义化比较
- `package`：程序整包。**放 GitHub Releases 资产，不进 git 历史**
  （54MB 每版进 git 会让仓库越滚越大）
- `assets.files`：`assets/` 下所有运行期需要的文件的 md5 清单，路径相对 `assets/`；
  素材走 `raw.githubusercontent.com` 逐文件下载（文件小、可缓存、无需鉴权）

`latest.json` 自身的地址是固定的，写在代码的常量里：

```
https://raw.githubusercontent.com/zhuolk/momolulu/main/update/latest.json
```

注意 `raw.githubusercontent.com` 有几分钟的 CDN 缓存，刚 push 完对方不一定立刻看到；
发布步骤里要留出这个时间（或带一个时间戳查询串破缓存）。

### 6.3 `build.py` 的新产出

打包完成后额外生成：

- `dist/momolulu-<version>.zip`（zip 根就是 `momolulu/` 目录）
- `dist/latest.json`（按上面格式填好 url/sha256/素材 md5）
- 顺带打印出需要执行的 GitHub Releases 上传命令

**打 zip 时必须排除 `config.json`**：它是每台机器运行期生成的，`stage_assets()` 会
往里塞一份默认值。若把默认 `config.json` 打进包，整目录交换后用户的缩放、位置、
模块开关会被默认值覆盖——这正是反目标里禁止的事。排除后由 `updater.bat` 显式把
旧目录的 `config.json` 搬到新目录（见 §7.3）。

### 6.4 发布步骤（你这边）

1. 改 `pet/version.py` 的版本号
2. `python tools_cli/build.py`
3. 把 `momolulu-<version>.zip` 传到 GitHub Releases（打 tag `v<version>`）
4. 把 `dist/latest.json` 覆盖到仓库 `update/latest.json` 并 `git push`
5. 素材变了的话，`assets/` 本身已经在 git 里，push 完就位

第 4 步是唯一的"手动同步"点：`latest.json` 里的 url 必须和 Release tag 对上。

## 7. 运行时

### 7.1 检查（启动后）

`main.py` 里用 `QTimer.singleShot(5000, …)` 触发，避免拖慢启动和抢首屏。
网络请求放在 `QThread` 或 `QThreadPool` 里跑，绝不阻塞 UI；超时 5 秒。
整个检查包在 try/except 里，**任何异常都只是日志 + 放弃，不弹错**。

未打包（脚本模式）时不检查更新——源码目录不是可替换的安装目录。

### 7.2 素材热更（静默）

1. 比对 `latest.json` 的 `assets.files` 与本地实际文件的 md5
2. **先让 `Sprite` 释放当前影片缓存**（`QMovie` 打开着文件，Windows 上覆盖被占用的
   文件会 `PermissionError`；不先释放的话，正在播放的那几张素材会永远更新不上）
3. 有差异的文件逐个下载到临时文件，校验 md5 通过后 `os.replace` 到目标路径
   （先写临时再原子替换，避免半截文件被读到）
4. 全部完成后：重新 `load_categories()`、更新 `PetApp.catalog` 并原地替换内容、
   调 `sprite.reload()`
5. 提示一句「噜噜换新衣服啦」（`Toast`，`info`），不打断、不需要点击

移除旧素材的情况：`latest.json` 里没有而本地有的文件**不删**（保守，避免误删）。

### 7.3 程序更新（目录交换）

直接覆盖运行中的目录是不安全的：覆盖到一半失败，噜噜就再也起不来了。
所以用"整目录换名"的原子替换：

1. 下载 zip 到 `%TEMP%\momolulu-update\<version>\`，校验 sha256 与大小
2. 解压到 `%TEMP%\momolulu-update\<version>\momolulu.new\`
3. 写一个 `%TEMP%\momolulu-update\updater.bat`（内容见下）
4. 启动该 bat（`DETACHED_PROCESS`，脱离噜噜的进程树）
5. 噜噜调用已有的 `_quit()` 正常退出

`updater.bat` 做五件事：

```bat
@echo off
rem 1. 循环重试重命名 <安装目录>\momolulu -> momolulu.old
rem    （不对 PID 打转：onedir 的 exe 是 bootloader，父子进程谁持有句柄不确定；
rem     重试重命名直到成功或超时 30 秒，成功即说明确实退干净了）
rem 2. 把 momolulu.old\config.json 复制进 momolulu.new\（保留用户的缩放/位置/模块开关）
rem 3. momolulu.new -> momolulu
rem 4. 删除 momolulu.old（失败就留着，下次启动再清）
rem 5. 启动新版的 momolulu.exe
```

- `momolulu.old` 就是回滚点：交换前任何一步失败，把 `momolulu.old` 改回来再启动
- `config.json` 不在 zip 里，靠第 2 步从旧目录搬过来，所以**用户的设置一定保留**
- 开机自启注册表指向的是 `...\momolulu\momolulu.exe`，路径不变，无需改动
- bat 放在 `%TEMP%` 而不在安装目录里，这样交换目录时 bat 自己不会被搬走
- 若第 2 步发现旧目录没有 `config.json`（第一次运行就更新），跳过，让噜噜首启自动生成

### 7.4 提示交互

`Toast` 是鼠标穿透的（`Qt.WindowTransparentForInput`），装不了按钮，不能直接复用。
新增一个 `UpdatePrompt` 小窗：复用 `Toast` 的画法（圆角卡片 + 投影 + 同样的配色），
去掉穿透标志，下面放「现在更新」「稍后」两个按钮，跟在噜噜旁边。

- 「现在更新」→ 走 7.3；下载期间把按钮置灰并显示「正在下载…」，失败时恢复并提示
- 「稍后」→ 关掉，本次不再问；下次启动还会再问（不做"不再提醒"）

**托盘菜单加常驻入口**：发现新版时，右键菜单里多一项「立即更新到 0.2.0」，
位置在「设置」之前。这样用户手快关掉弹窗、或者当时不想更新，之后随时能点。

- `MenuState` 加一个字段（如 `update_version: str | None`），`build_menu()` 据此
  决定是否插入这一项；`main.py` 注册对应 handler（复用 7.3 的流程）
- 不做"改托盘 tooltip"：`pet/tray.py` 的 tooltip 会被番茄钟等模块通过
  `ModuleContext.set_tray_text` 随时覆盖，"有新版本"挂不住
- 更新完成后菜单项消失（版本追平）

## 8. 失败、回滚与安全

| 场景 | 处理 |
| --- | --- |
| 取 `latest.json` 失败/超时 | 静默放弃，本次不再检查 |
| 单个素材下载失败 | 跳过该文件，其余照常；下次启动补上 |
| zip 下载中断 | 删临时文件，提示「更新失败，已保留当前版本」 |
| sha256 不匹配 | 同上，且**绝不解压** |
| 解压失败 | 删 `momolulu.new`，原目录未动，噜噜照常 |
| 目录交换失败 | bat 把 `momolulu.old` 改回来再启动 |
| `momolulu.old` 删不掉 | 留着，下次启动时清理 |

安全边界：

- **只允许 `https://`**，且**起始 URL 的主机必须在白名单里**
  （`raw.githubusercontent.com`、`github.com`）。`latest.json` 被篡改后也没法把
  下载指向任意地址
- GitHub 的 Release 下载会 302 到 `objects.githubusercontent.com` 之类的域，所以
  重定向**只校验协议仍是 https**、且最多跟 5 跳；不对每一跳做主机白名单
  （否则 54MB 的包会 100% 下载失败，而且表现为静默失败）
- 所有下载都校验 md5 / sha256
- 不内嵌任何 token（仓库公开后也不需要）

## 9. 我的判断（这些我替你定了，你觉得不对就说）

- **发布物放 GitHub Releases 而不是提交进 git**：理由如上，54MB 每版会把仓库撑爆
- **程序更新 = 整目录交换，但 zip 里排除 `config.json`**：整目录交换最不容易出现
  "覆盖一半"的坏状态；`config.json` 由 bat 显式搬过去，设置一定不丢
- **不做增量更新**：54MB 不算大，可靠性优先
- **素材热更静默、不弹窗**：素材是"锦上添花"，为它打断用户不值当
- **不做"不再提醒"开关**：默认每次启动都问，简单；用户嫌烦再说
- **脚本模式（未打包）不检查更新**：源码目录不是可替换的安装目录
- **旧素材不自动删**：宁可留一点垃圾，也不要误删用户在用的东西
- **判断噜噜是否退出用"重试重命名"而不是 PID**：onedir 的 exe 是 bootloader，
  父子进程谁持有目录句柄不确定；能改名成功就说明退干净了
- **重定向不做逐跳主机白名单**：GitHub 必然跳转到别的域，逐跳校验等于把更新做废

## 10. 留给实现者的

- `fetch` 的具体实现（`urllib.request` 标准库即可，不引入 `requests`）
- 后台线程的具体形态（`QThread` vs `QThreadPool`），只要不阻塞 UI
- `latest.json` 里 `assets.files` 的生成方式（`build.py` 里遍历 `assets/processed/` 算 md5）
- `UpdatePrompt` 的具体尺寸与配色细节，跟着 `Toast` 走
- 各种超时/重试次数
- 单测怎么注入假的 `fetch`（建议：给检查器传一个 `fetch` 参数，默认真实现）

## 11. 测试与验收

**单元测试（无需网络）**

- 版本比较：`0.2.0 > 0.1.0`、`0.1.0 == 0.1.0`、非法版本字符串不崩溃
- `latest.json` 解析：缺字段、多字段、畸形 JSON 都要安全失败
- 素材差异计算：新增 / 变更 / 未变 / 本地多出 四种情形
- URL 白名单：非 https、非白名单域名必须被拒
- `updater.bat` 生成：路径含空格、含中文时要正确加引号
- 校验失败时**不产生任何文件写入**
- 菜单：有新版时出现「立即更新到 x.y.z」，无新版时不出现

**集成验收（手工，用本地源）**

把更新源指向本地 `python -m http.server`，造一个 `version` 更高的 `latest.json`：

1. 新增素材、版本不变 → 噜噜没弹窗，素材变了
2. 版本变高 → 弹窗出现；点「稍后」→ 噜噜不受影响，下次启动还会问
3. 点「现在更新」→ 下载、退出、目录交换、自动重启，`config.json` 里的
   缩放/位置/模块开关全部保留
4. 故意把 sha256 写错 → 提示失败，噜噜照常运行
5. 故意断网 → 无任何提示，噜噜照常运行
