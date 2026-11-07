"""Windows 辅助：前台全屏判定（全屏时自动隐藏桌宠）与单实例守卫。"""

from __future__ import annotations

import ctypes

_SM_CXSCREEN = 0
_SM_CYSCREEN = 1


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def rect_covers(
    win_rect: tuple[int, int, int, int],
    screen_rect: tuple[int, int, int, int],
    tolerance: int = 2,
) -> bool:
    """窗口矩形 (x, y, w, h) 是否把屏幕矩形整个盖住（允许 tolerance 像素误差）。"""
    wx, wy, ww, wh = win_rect
    sx, sy, sw, sh = screen_rect
    return (
        wx <= sx + tolerance
        and wy <= sy + tolerance
        and wx + ww >= sx + sw - tolerance
        and wy + wh >= sy + sh - tolerance
    )


def should_hide_pet(fullscreen: bool, config_enabled: bool) -> bool:
    """全屏检查命中且配置开启「全屏时隐藏」→ 隐藏桌宠。"""
    return bool(fullscreen and config_enabled)


def _user32():
    """返回 user32（非 Windows 或加载失败返回 None）。"""
    try:
        return ctypes.windll.user32  # type: ignore[attr-defined]
    except Exception:
        return None


def foreground_rect() -> tuple[int, int, int, int] | None:
    """前台窗口矩形 (x, y, w, h)，单位为物理像素；取不到返回 None。"""
    user32 = _user32()
    if user32 is None:
        return None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    rect = _RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def primary_screen_rect() -> tuple[int, int, int, int]:
    """主屏矩形 (0, 0, w, h)；取不到返回 (0, 0, 0, 0)。"""
    user32 = _user32()
    if user32 is None:
        return 0, 0, 0, 0
    return (
        0,
        0,
        int(user32.GetSystemMetrics(_SM_CXSCREEN)),
        int(user32.GetSystemMetrics(_SM_CYSCREEN)),
    )


def is_foreground_fullscreen(tolerance: int = 2) -> bool:
    """前台窗口是否盖住整个主屏（全屏视频 / F11 浏览器 / 全屏游戏）。"""
    try:
        win = foreground_rect()
        screen = primary_screen_rect()
        if win is None or screen[2] <= 0 or screen[3] <= 0:
            return False
        return rect_covers(win, screen, tolerance)
    except Exception:
        return False


# ---------------------------------------------------------------- 单实例守卫

MUTEX_NAME = r"Local\momolulu-single-instance"
ERROR_ALREADY_EXISTS = 183

_kernel32 = None
_mutex_handle = None  # 持有句柄引用：句柄一关/被回收就等于放掉互斥体，必须留到进程结束


def _kernel32_lib():
    """加载 kernel32（非 Windows 或加载失败会抛异常，由调用方兜底）。"""
    global _kernel32
    if _kernel32 is None:
        lib = ctypes.WinDLL("kernel32", use_last_error=True)
        lib.CreateMutexW.restype = ctypes.c_void_p
        lib.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        lib.CloseHandle.argtypes = [ctypes.c_void_p]
        _kernel32 = lib
    return _kernel32


def acquire_single_instance(name: str = MUTEX_NAME) -> bool:
    """抢占单实例守卫：True = 本进程可以继续跑，False = 已有实例在跑（应直接退出）。

    重复双击 exe、或「开机自启」与手动启动撞车时会各起一个进程（屏幕上一堆噜噜、
    托盘图标成排）。这里用系统级命名互斥体判定：后到的进程拿到的是同名已存在的
    对象，`GetLastError()` 会是 ERROR_ALREADY_EXISTS，据此退位。互斥体随进程退出
    自动释放，不需要显式清理。非 Windows 或系统调用出错时一律放行 —— 守卫自身
    有问题不该把噜噜彻底挡在门外。
    """
    global _mutex_handle
    try:
        kernel32 = _kernel32_lib()
        handle = kernel32.CreateMutexW(None, 0, name)
    except Exception:  # noqa: BLE001 - 守卫失败放行，不影响启动
        return True
    if not handle:
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _mutex_handle = handle
    return True
