"""自动更新的纯逻辑：版本比较、latest.json 解析、素材差异、bat 生成。

这一层不做任何网络 IO —— 取字节的能力一律由调用方以 `fetch` / `download` 注入，
所以单测完全离线、可以精确构造成功与失败。
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import zipfile
from functools import partial
from pathlib import Path

from pet.download import (
    UpdateError,
    download_file,
    fetch_bytes,
    md5_bytes,
    md5_file,
    sha256_file,
)

logger = logging.getLogger(__name__)

LATEST_URL = "https://raw.githubusercontent.com/zhuolk/momolulu/main/update/latest.json"

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_ZERO = (0, 0, 0)


def parse_version(text: object) -> tuple[int, int, int] | None:
    """严格解析 `x.y.z`；其余一律返回 None。"""
    if not isinstance(text, str):
        return None
    match = _SEMVER_RE.match(text.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def compare_versions(a: object, b: object) -> int:
    """比较两个版本号，返回 -1 / 0 / 1；无法解析的一侧按 `0.0.0` 处理。"""
    left = parse_version(a) or _ZERO
    right = parse_version(b) or _ZERO
    if left == right:
        return 0
    return 1 if left > right else -1


def update_available(local: str, remote: object) -> bool:
    """远端版本是否严格高于本地。"""
    return parse_version(remote) is not None and compare_versions(remote, local) > 0


def _package(raw: object) -> dict | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("package 不是对象")
    url, sha256, size = raw.get("url"), raw.get("sha256"), raw.get("size")
    if not isinstance(url, str) or not url:
        raise ValueError("package.url 非法")
    if not isinstance(sha256, str) or not sha256:
        raise ValueError("package.sha256 非法")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("package.size 非法")
    return {"url": url, "sha256": sha256, "size": size}


def _assets(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("assets 不是对象")
    base, files = raw.get("base"), raw.get("files")
    if not isinstance(base, str) or not base:
        raise ValueError("assets.base 非法")
    if not isinstance(files, dict) or not files:
        raise ValueError("assets.files 非法")
    clean: dict[str, str] = {}
    for name, digest in files.items():
        if not isinstance(name, str) or not isinstance(digest, str) or not digest:
            raise ValueError("assets.files 条目非法")
        clean[name] = digest
    return {"base": base, "files": clean}


def parse_latest(raw: bytes | str) -> dict | None:
    """解析远端 `latest.json`；任何问题都返回 None（放弃本次更新，不抛异常）。"""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        package = _package(data.get("package"))
        assets = _assets(data.get("assets"))
    except ValueError:
        return None
    version = data.get("version")
    notes = data.get("notes")
    return {
        "version": version if isinstance(version, str) else "",
        "notes": notes if isinstance(notes, str) else "",
        "package": package,
        "assets": assets,
    }


def safe_relpath(rel: str) -> Path | None:
    """把 `assets/` 下的相对路径收敛成安全的 Path；越界一律 None。"""
    if not isinstance(rel, str) or not rel:
        return None
    text = rel.replace("\\", "/")
    if "\x00" in text:
        return None
    if text.startswith("/") or ":" in text.split("/")[0]:
        return None
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return Path(*parts)


def _local_md5(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return md5_file(path)
    except OSError:
        return None


def asset_diff(remote_files: dict[str, str], local_dir: Path) -> dict[str, str]:
    """远端 md5 清单与本地实际文件的差异（只含新增与变更）。"""
    local_dir = Path(local_dir)
    changes: dict[str, str] = {}
    for rel, digest in remote_files.items():
        target = safe_relpath(rel)
        if target is None:
            continue
        want = str(digest).strip().lower()
        if _local_md5(local_dir / target) != want:
            changes[rel] = want
    return changes


def apply_asset_update(changes: dict[str, str], base: str, local_dir: Path, fetch) -> list[str]:
    """把有差异的素材下下来逐个原子替换；单文件失败只跳过。"""
    local_dir = Path(local_dir)
    done: list[str] = []
    for rel, digest in changes.items():
        target = safe_relpath(rel)
        if target is None:
            continue
        dest = local_dir / target
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            data = fetch(base + rel)
            if md5_bytes(data) != digest:
                logger.warning("素材 %s 校验不通过，已跳过", rel)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            os.replace(tmp, dest)
        except Exception as exc:  # noqa: BLE001 - 单个素材失败只跳过，绝不能拖垮整个更新
            logger.warning("素材 %s 更新失败，已跳过：%s", rel, exc)
            continue
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
        done.append(rel)
    return done


_BAT_TEMPLATE = """@echo off
setlocal
set "TARGET={target}"
set "NEW={new}"
set "OLD={old}"
set "EXE={exe}"
set /a tries=0

rem 1. 重试把安装目录改名成备份目录：能改名成功就说明噜噜确实退干净了。
rem    （不对 PID 打转：onedir 的 exe 是 bootloader，父子进程谁持有目录句柄不确定）
:retry
rmdir /s /q "%OLD%" >nul 2>&1
move "%TARGET%" "%OLD%" >nul 2>&1
if not exist "%TARGET%" goto swapped
set /a tries+=1
if %tries% geq {retries} goto failed
ping -n 2 127.0.0.1 >nul
goto retry

rem 2. 把旧目录的 config.json 搬进新目录，保住用户的缩放 / 位置 / 模块开关
:swapped
if exist "%OLD%\\config.json" copy /y "%OLD%\\config.json" "%NEW%\\" >nul 2>&1
if exist "%TARGET%" rmdir /s /q "%TARGET%" >nul 2>&1

rem 3. 新目录顶替安装目录
move "%NEW%" "%TARGET%" >nul 2>&1
if exist "%TARGET%\\%EXE%" goto ok

rem 交换失败：把备份改回来再启动，绝不让噜噜留在跑不起来的状态
:rollback
rmdir /s /q "%TARGET%" >nul 2>&1
move "%OLD%" "%TARGET%" >nul 2>&1
start "" "%TARGET%\\%EXE%"
goto done

:ok
rem 4. 删掉备份（失败就留着，下次启动再清）
rmdir /s /q "%OLD%" >nul 2>&1
rem 5. 启动新版
start "" "%TARGET%\\%EXE%"
goto done

:failed
rem 改名一直没成功说明噜噜还活着，原目录完好，直接把它拉起来
start "" "%TARGET%\\%EXE%"

:done
endlocal
"""


def build_updater_bat(
    install_dir: Path,
    staged_dir: Path,
    backup_dir: Path,
    exe_name: str = "momolulu.exe",
    retries: int = 30,
) -> str:
    """生成目录交换脚本：等待噜噜退出 -> 搬 config.json -> 交换 -> 删备份 -> 启动新版。"""
    return _BAT_TEMPLATE.format(
        target=Path(install_dir),
        new=Path(staged_dir),
        old=Path(backup_dir),
        exe=exe_name,
        retries=int(retries),
    ).replace("\n", "\r\n")


def write_updater_bat(path: Path, text: str) -> Path:
    """用 Windows ANSI 码页写盘，含中文的安装路径才能被 cmd 正确解析。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" 禁止换行翻译：build_updater_bat 已显式产出 CRLF，
    # 默认的 newline=None 会把其中的 \n 再翻译一次，写出 \r\r\n。
    path.write_text(text, encoding="mbcs", newline="")
    return path


def _download_zip(info: dict, temp_root: Path, download, progress=None) -> Path:
    package = info.get("package") or {}
    version = info.get("version") or "unknown"
    work = Path(temp_root) / version
    work.mkdir(parents=True, exist_ok=True)
    zip_path = work / f"momolulu-{version}.zip"
    url, sha256, size = package.get("url"), package.get("sha256"), package.get("size")
    if not isinstance(url, str) or not url:
        raise UpdateError("package.url 非法")
    if not isinstance(sha256, str) or not sha256:
        raise UpdateError("package.sha256 非法")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise UpdateError("package.size 非法")
    # 只有默认引擎认识 progress；注入进来的 download 保持 (url, dest) 这个窄契约。
    engine = download if download is not None else partial(download_file, progress=progress)
    engine(url, zip_path)
    if not zip_path.is_file():
        raise UpdateError("下载未产生文件")
    if zip_path.stat().st_size != size:
        raise UpdateError("整包大小与 latest.json 不符")
    if sha256_file(zip_path) != sha256:
        raise UpdateError("整包 sha256 校验失败")
    return zip_path


def _zip_top_prefix(zf: zipfile.ZipFile) -> str:
    """zip 只有一个顶层目录时返回 `顶层目录/`，否则返回空串（表示不剥前缀）。"""
    tops = {
        name.replace("\\", "/").split("/", 1)[0]
        for name in zf.namelist()
        if name.strip("/")
    }
    return f"{next(iter(tops))}/" if len(tops) == 1 else ""


def _extract(zip_path: Path, staged_root: Path) -> Path:
    """解压并剥掉顶层目录：zip 根是 `momolulu/`，处理后 `staged_root` 本身就是新安装目录。

    这里刻意不走「extractall + 改名展平」：解压出的 exe/dll 会被实时杀软短暂持有句柄，
    此时对目录改名或搬移会稳定吃 `WinError 5 拒绝访问`，整包就永远装不上。
    逐成员直接写到最终路径，全程零改名零搬移，从根上绕开这个竞态。
    """
    staged_root = Path(staged_root)
    shutil.rmtree(staged_root, ignore_errors=True)
    staged_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        prefix = _zip_top_prefix(zf)
        for member in zf.infolist():
            rel = member.filename.replace("\\", "/")
            if prefix and rel.startswith(prefix):
                rel = rel[len(prefix):]
            target = safe_relpath(rel)
            if target is None or member.is_dir():
                continue
            dest = staged_root / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
    if not (staged_root / "momolulu.exe").is_file():
        raise UpdateError("整包结构异常：找不到 momolulu.exe")
    return staged_root


def prepare_program_update(
    info: dict,
    install_dir: Path,
    temp_root: Path,
    download=None,
    retries: int = 30,
    progress=None,
) -> Path:
    """下载并校验整包、解压到暂存目录、写出 updater.bat；失败时不留任何中间产物。

    `progress` 透传给默认下载引擎（见 `_download_zip`），用于上报下载百分比。
    """
    package = info.get("package")
    if not isinstance(package, dict):
        raise UpdateError("latest.json 未提供程序整包")
    install_dir = Path(install_dir).resolve()
    temp_root = Path(temp_root)
    # 暂存目录必须在安装目录之外：否则 bat 执行目录交换时会连脚本自己一起搬走。
    temp_abs = temp_root.resolve()
    if temp_abs == install_dir or install_dir in temp_abs.parents:
        raise UpdateError("暂存目录不能位于安装目录内，否则更新脚本会把自己搬走")
    staged_root = temp_root / "momolulu.new"
    version = info.get("version") or "unknown"
    if not isinstance(version, str):
        raise UpdateError("latest.json 的 version 非法")
    work_dir = temp_root / version

    def _clear() -> None:
        # zip 落在 <temp_root>/<version>/，失败时连同整个工作目录一起清掉。
        shutil.rmtree(staged_root, ignore_errors=True)
        shutil.rmtree(work_dir, ignore_errors=True)

    try:
        downloaded = _download_zip(info, temp_root, download, progress)
        staged = _extract(downloaded, staged_root)
        backup = install_dir.with_name(install_dir.name + ".old")
        text = build_updater_bat(install_dir, staged, backup, retries=retries)
        return write_updater_bat(temp_root / "updater.bat", text)
    except UpdateError:
        _clear()
        raise
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        # UnicodeEncodeError 继承自 ValueError，会被这里兜住（bat 的 mbcs 写盘失败）。
        _clear()
        raise UpdateError(f"准备更新失败：{exc}") from exc


def check_for_update(
    local_version: str,
    local_assets_dir: Path,
    latest_url: str = LATEST_URL,
    fetch=fetch_bytes,
) -> dict | None:
    """取 latest.json、比对素材与版本，产出一份可执行的更新计划；任何问题都返回 None。"""
    try:
        parsed = parse_latest(fetch(latest_url))
    except Exception as exc:  # noqa: BLE001 - 检查更新绝不允许影响噜噜运行
        logger.warning("检查更新失败：%s", exc)
        return None
    if parsed is None:
        return None
    changes = asset_diff(parsed["assets"]["files"], Path(local_assets_dir))
    package = parsed["package"] if update_available(local_version, parsed["version"]) else None
    if package is None and not changes:
        return None
    return {
        "version": parsed["version"],
        "notes": parsed["notes"],
        "package": package,
        "assets_base": parsed["assets"]["base"],
        "asset_changes": changes,
    }
