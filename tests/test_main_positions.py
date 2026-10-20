from main import clamp_to_screen

PRIMARY = (0, 0, 1920, 1080)
SECOND = (1920, 0, 1920, 1080)
LEFT = (-1920, 0, 1920, 1080)


def test_position_kept_when_inside_any_screen():
    assert clamp_to_screen((300, 400), (200, 200), [PRIMARY, SECOND]) == (300, 400)
    assert clamp_to_screen((2000, 100), (200, 200), [PRIMARY, SECOND]) == (2000, 100)


def test_offscreen_position_returns_primary_bottom_right():
    """Review Focus #4"""
    assert clamp_to_screen((3000, 500), (200, 200), [PRIMARY]) == (1720, 880)


def test_partially_visible_position_is_pushed_inside():
    x, y = clamp_to_screen((1850, 1050), (200, 200), [PRIMARY])
    assert x <= 1720 and y <= 880


def test_negative_monitor_coordinates_supported():
    assert clamp_to_screen((-1900, 10), (200, 200), [PRIMARY, LEFT]) == (-1900, 10)


def test_empty_screens_returns_input():
    assert clamp_to_screen((50, 50), (200, 200), []) == (50, 50)
