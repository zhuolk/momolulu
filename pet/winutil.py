"""Windows 辅助：判断前台窗口是否全屏，供「全屏时自动隐藏桌宠」使用。"""

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
