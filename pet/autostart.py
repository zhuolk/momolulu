"""开机自启：读写 `HKCU\\...\\Run` 下的启动项（Windows 专有）。

只做「注册表事实」的读改，不读配置；是否该启用由调用方（`main.py`）决定，
`sync()` 负责把注册表对齐到期望状态。
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Momolulu"

KEY_READ = getattr(winreg, "KEY_READ", 0x20019)
KEY_SET_VALUE = getattr(winreg, "KEY_SET_VALUE", 0)
REG_SZ = getattr(winreg, "REG_SZ", 1)


def build_command(frozen: bool, exe_path: Path, script_path: Path) -> str:
    """打包后直接指向 exe；脚本模式用同目录的 `pythonw.exe` 跑 `main.py`（无控制台窗口）。"""
    if frozen:
        return f'"{exe_path}"'
    pythonw = Path(exe_path).parent / "pythonw.exe"
    return f'"{pythonw}" "{script_path}"'


def _open_run_key(reg, access: int = KEY_READ):
    # 读取必须带 KEY_READ/KEY_QUERY_VALUE：samDesired=0 打开成功但读值会被拒绝
    return reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, access)


def is_enabled(reg=winreg) -> bool:
    """注册表里是否存在本程序的启动项。"""
    try:
        key = _open_run_key(reg)
        reg.QueryValueEx(key, APP_NAME)
        return True
    except OSError:
        return False


def current_command(reg=winreg) -> str | None:
    """启动项当前记录的命令；不存在返回 None。"""
    try:
        key = _open_run_key(reg)
        value, _ = reg.QueryValueEx(key, APP_NAME)
        return value
    except OSError:
        return None


def set_enabled(on: bool, command: str, reg=winreg) -> bool:
    """写入 / 删除启动项；被拒绝或无权限时返回 False（不抛异常）。"""
    try:
        key = _open_run_key(reg, KEY_SET_VALUE)
        if on:
            reg.SetValueEx(key, APP_NAME, 0, REG_SZ, command)
        else:
            try:
                reg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        return True
    except OSError:
        return False


def sync(want_enabled: bool, command: str, reg=winreg) -> bool:
    """把注册表对齐到期望状态，返回「对齐后是否启用」。"""
    current = current_command(reg=reg)
    if want_enabled:
        if current != command and not set_enabled(True, command, reg=reg):
            return current is not None
        return True
    if current is None:
        return False
    return not set_enabled(False, "", reg=reg)


def default_command(script_path: Path) -> str:
    """按当前运行方式（脚本 / 打包）生成启动命令。"""
    frozen = bool(getattr(sys, "frozen", False))
    return build_command(frozen, Path(sys.executable), script_path)
