from pet.winutil import rect_covers, should_hide_pet

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
