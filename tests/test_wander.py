"""自动走动：`WANDER` 期间噜噜在屏幕上缓慢水平移动，碰边折返。"""

from pet.wander import WALK_SPEED_PX, Wanderer

PRIMARY = (0, 0, 1920, 1080)
SECOND = (1920, 0, 1920, 1080)


class FakeSprite:
    """只实现 `Wanderer` 用到的那几个方法。"""

    def __init__(self, x=800, y=300, w=200, h=200):
        self._x, self._y = int(x), int(y)
        self._w, self._h = w, h
        self.strip_side = None
        self.flip = None
        self.moves = []

    def x(self):
        return self._x

    def y(self):
        return self._y

    def width(self):
        return self._w

    def height(self):
        return self._h

    def move_to(self, x, y):
        self._x, self._y = int(x), int(y)
        self.moves.append((self._x, self._y))

    def place(self, x, y=None):
        """测试里直接把噜噜挪到别处，不动 `moves` 记录。"""
        self._x = int(x)
        if y is not None:
            self._y = int(y)

    def set_flip(self, on):
        self.flip = bool(on)


def make(sprite=None, screens=(PRIMARY,)):
    sprite = sprite if sprite is not None else FakeSprite()
    return sprite, Wanderer(sprite, lambda: list(screens))


def test_walk_step_moves_right_and_keeps_height(qapp):
    sprite, wanderer = make()

    wanderer.tick(True)

    assert sprite.moves == [(800 + WALK_SPEED_PX, 300)]
    assert sprite.flip is False  # 向右走不镜像


def test_standing_still_does_not_move(qapp):
    sprite, wanderer = make()

    wanderer.tick(False)
    wanderer.tick(False)

    assert sprite.moves == []


def test_edge_hidden_pet_does_not_walk(qapp):
    """贴边缩回时噜噜在屏外，不能再自己往下走。"""
    sprite, wanderer = make()
    sprite.strip_side = "left"

    wanderer.tick(True)

    assert sprite.moves == []


def test_no_screens_does_not_move(qapp):
    sprite, wanderer = make(screens=())

    wanderer.tick(True)

    assert sprite.moves == []


def test_bounces_at_right_edge_and_faces_left(qapp):
    sprite, wanderer = make(FakeSprite(x=1720))  # 1920 - 200：已经贴右缘

    wanderer.tick(True)
    assert sprite.x() == 1720
    assert sprite.flip is True

    wanderer.tick(True)
    assert sprite.x() == 1720 - WALK_SPEED_PX  # 折返后向左走
    assert sprite.flip is True


def test_bounces_at_left_edge_and_faces_right(qapp):
    sprite, wanderer = make(FakeSprite(x=1720))
    wanderer.tick(True)  # 先碰右缘，方向折返为向左
    sprite.place(0)
    sprite.moves.clear()

    wanderer.tick(True)  # 已到左缘：贴住并折返向右

    assert sprite.moves == [(0, 300)]
    assert sprite.flip is False


def test_walks_within_screen_holding_the_pet(qapp):
    """多屏时按噜噜所在的那块屏算边界，不会把它拽回主屏。"""
    sprite, wanderer = make(FakeSprite(x=1930), screens=(PRIMARY, SECOND))

    wanderer.tick(True)

    assert sprite.moves == [(1930 + WALK_SPEED_PX, 300)]
