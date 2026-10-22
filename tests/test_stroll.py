"""`Stroller`：沿边缘逆时针走一圈的位移与旋转。"""

from pet.stroll import STROLL_SPEED_PX, Stroller

PRIMARY = (0, 0, 1920, 1080)
LEFT_OF_PRIMARY = (-1920, 0, 1920, 1080)
# 工作区：底边让出 48px 给任务栏
WORK = (0, 0, 1920, 1032)
WORK_LEFT_OF_PRIMARY = (-1920, 0, 1920, 1032)


class FakeSprite:
    """只实现 `Stroller` 用到的那几个方法。"""

    def __init__(self, x=800, y=300, w=120, h=120):
        self._x, self._y = int(x), int(y)
        self._w, self._h = w, h
        self.strip_side = None
        self.flips = []
        self.rotations = []
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
        self.flips.append(bool(on))

    def set_rotation(self, deg):
        self.rotations.append(int(deg))

    @property
    def rotation(self):
        return self.rotations[-1] if self.rotations else 0


def make(sprite=None, screens=(PRIMARY,), finished=None, speed_px=STROLL_SPEED_PX, bounds=None):
    sprite = sprite if sprite is not None else FakeSprite()
    done = finished if finished is not None else []
    stroller = Stroller(
        sprite,
        lambda: list(screens),
        speed_px=speed_px,
        on_finished=lambda: done.append("done"),
        bounds_provider=(lambda: list(bounds)) if bounds is not None else None,
    )
    return sprite, stroller, done


def walk(stroller, ticks):
    for _ in range(ticks):
        stroller.tick()


# 120×120 的噜噜绕 1920×1080 走一圈：右段 960px、上段 1800px、左段 960px、下段 1800px
UP_TICKS, SIDE_TICKS = 120, 225
# 换工作区（高 1032）后，竖段只有 912px
WORK_UP_TICKS = 114


def test_start_teleports_to_bottom_right_and_faces_up():
    sprite, stroller, _ = make()
    assert stroller.start() is True
    assert (sprite.x(), sprite.y()) == (1800, 960)
    assert sprite.rotation == 270  # 逆时针 90°：朝上，脚贴屏幕右边
    assert sprite.flips[-1] is False  # 用旋转表达朝向，先清掉走动留下的镜像
    assert stroller.active is True


def test_speed_is_eighty_px_per_second():
    """每个心跳（100ms）走 8px。"""
    sprite, stroller, _ = make()
    stroller.start()
    walk(stroller, 10)
    assert sprite.y() == 960 - 80


def test_turn_at_each_corner_goes_counter_clockwise():
    """四个拐角各逆时针 90°：朝上 → 朝左 → 朝下 → 朝右。"""
    sprite, stroller, _ = make()
    stroller.start()
    assert sprite.rotation == 270

    walk(stroller, UP_TICKS)
    assert (sprite.x(), sprite.y()) == (1800, 0)  # 右上角
    assert sprite.rotation == 180

    walk(stroller, SIDE_TICKS)
    assert (sprite.x(), sprite.y()) == (0, 0)  # 左上角
    assert sprite.rotation == 90

    walk(stroller, UP_TICKS)
    assert (sprite.x(), sprite.y()) == (0, 960)  # 左下角
    assert sprite.rotation == 0


def test_full_loop_returns_to_start_and_reports_finished():
    sprite, stroller, done = make()
    stroller.start()
    walk(stroller, UP_TICKS + SIDE_TICKS + UP_TICKS + SIDE_TICKS)
    assert (sprite.x(), sprite.y()) == (1800, 960)  # 回到右下角
    assert sprite.rotation == 0
    assert stroller.active is False and done == ["done"]


def test_corner_leftover_is_not_lost():
    """段长除不尽步长时，跨过拐角的余量要接着走，不能凭空少走几像素。"""
    sprite, stroller, _ = make(speed_px=7)  # 960 / 7 除不尽
    stroller.start()
    walk(stroller, 138)  # 966px > 960px：既跨过右上角，又在上段走出 6px
    assert (sprite.x(), sprite.y()) == (1800 - 6, 0)
    assert sprite.rotation == 180


def test_stop_leaves_pet_where_it_stands():
    sprite, stroller, done = make()
    stroller.start()
    walk(stroller, 5)
    stopped_at = (sprite.x(), sprite.y())

    stroller.stop()
    walk(stroller, 10)

    assert stroller.active is False and done == []  # 中止不算走完
    assert (sprite.x(), sprite.y()) == stopped_at
    assert sprite.rotation == 0  # 恢复直立


def test_no_screens_cannot_start():
    sprite, stroller, _ = make(screens=())
    assert stroller.start() is False and stroller.active is False


def test_edge_hidden_pet_does_not_move():
    sprite, stroller, _ = make()
    sprite.strip_side = "left"
    stroller.start()
    before = (sprite.x(), sprite.y())
    walk(stroller, 5)
    assert (sprite.x(), sprite.y()) == before


def test_strolls_around_the_screen_the_pet_is_on():
    sprite, stroller, _ = make(
        sprite=FakeSprite(x=2500, y=500), screens=(PRIMARY, (1920, 0, 1920, 1080))
    )
    stroller.start()
    assert (sprite.x(), sprite.y()) == (3720, 960)  # 第二块屏的右下角


def test_edge_hidden_pet_strolls_around_its_own_screen():
    """贴边缩回时窗口大半在屏外（左下角压在双屏分界线上），不能被判成邻屏。"""
    sprite, stroller, _ = make(sprite=FakeSprite(x=-96, y=600), screens=(PRIMARY, LEFT_OF_PRIMARY))
    sprite.strip_side = "left"
    assert stroller.start() is True
    assert (sprite.x(), sprite.y()) == (1800, 960)  # 仍是主屏（0..1920）的右下角


def test_bottom_leg_runs_along_the_work_area_not_the_screen():
    """底边那段要踩在工作区下沿（任务栏上沿），走进任务栏会被压住看不见。"""
    sprite, stroller, done = make(screens=(PRIMARY,), bounds=(WORK,))
    stroller.start()
    assert (sprite.x(), sprite.y()) == (1800, 912)  # 1080 减 48px 任务栏，再减身高

    walk(stroller, WORK_UP_TICKS)  # 右边向上
    assert (sprite.x(), sprite.y()) == (1800, 0)  # 右上角
    walk(stroller, SIDE_TICKS)  # 顶边向左
    assert (sprite.x(), sprite.y()) == (0, 0)  # 左上角
    walk(stroller, WORK_UP_TICKS)  # 左边向下
    assert (sprite.x(), sprite.y()) == (0, 912)  # 左下角：踩任务栏上沿，不是整屏的 960
    walk(stroller, SIDE_TICKS)  # 底边向右
    assert (sprite.x(), sprite.y()) == (1800, 912)  # 走回起点
    assert stroller.active is False and done == ["done"]


def test_pet_inside_the_taskbar_strip_still_strolls_around_its_own_screen():
    """噜噜正卡在任务栏那条带里（工作区判定不到它）时，仍要按整屏认出自己在哪块屏。"""
    sprite, stroller, _ = make(
        sprite=FakeSprite(x=-120, y=1000),
        screens=(PRIMARY, LEFT_OF_PRIMARY),
        bounds=(WORK, WORK_LEFT_OF_PRIMARY),
    )
    assert stroller.start() is True
    assert (sprite.x(), sprite.y()) == (-120, 912)  # 左屏工作区的右下角，不是主屏
