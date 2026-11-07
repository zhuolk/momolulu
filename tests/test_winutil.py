import uuid

from pet import winutil
from pet.winutil import acquire_single_instance, rect_covers, should_hide_pet

SCREEN = (0, 0, 1920, 1080)


def test_rect_covers_exact_and_larger():
    assert rect_covers((0, 0, 1920, 1080), SCREEN) is True
    assert rect_covers((-5, -5, 1930, 1090), SCREEN) is True


def test_rect_covers_smaller_window_is_false():
    assert rect_covers((0, 0, 1600, 900), SCREEN) is False
    assert rect_covers((0, 0, 1920, 1000), SCREEN) is False


def test_rect_covers_tolerance_allows_one_pixel_off():
    assert rect_covers((1, 1, 1919, 1079), SCREEN, tolerance=2) is True


def test_should_hide_pet_matrix():
    assert should_hide_pet(True, True) is True
    assert should_hide_pet(True, False) is False
    assert should_hide_pet(False, True) is False
    assert should_hide_pet(False, False) is False


def _unique_mutex() -> str:
    """每个用例用独立互斥体名，免得互相抢（同名第二次占位必定失败）。"""
    return rf"Local\momolulu-test-{uuid.uuid4()}"


def test_second_launch_with_same_mutex_is_rejected():
    """连点两次 exe 只留一只噜噜：同名互斥体第二次占位必须失败。"""
    name = _unique_mutex()
    assert acquire_single_instance(name) is True
    assert acquire_single_instance(name) is False


def test_different_mutex_names_do_not_conflict():
    assert acquire_single_instance(_unique_mutex()) is True
    assert acquire_single_instance(_unique_mutex()) is True


def test_guard_failure_allows_start(monkeypatch):
    """守卫自身加载不起来（非 Windows / 出错）时放行，不能把噜噜挡在门外。"""

    def boom():
        raise OSError("kernel32 不可用")

    monkeypatch.setattr(winutil, "_kernel32_lib", boom)
    assert acquire_single_instance(_unique_mutex()) is True
