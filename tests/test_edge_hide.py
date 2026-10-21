from pet.edge_hide import DEFAULT_STRIP_PX, EdgeHider, hidden_x, strip_rect

SCREEN = (0, 0, 1920, 1080)
SIZE = (200, 200)
STRIP = DEFAULT_STRIP_PX


class FakeSprite:
    """模拟桌宠窗口：仅暴露 EdgeHider 用到的接口。"""

    def __init__(self):
        self.pos = (500, 500)
        self.strips = []  # 记录 set_strip 调用（None 表示恢复正常渲染）

    def move_to(self, x, y):
        self.pos = (x, y)

    def width(self):
        return SIZE[0]

    def height(self):
        return SIZE[1]

    def set_strip(self, side, strip_px=DEFAULT_STRIP_PX):
        self.strips.append(side)


def make(cfg=None):
    sp = FakeSprite()
    return EdgeHider(sp, cfg if cfg is not None else {}, lambda: [SCREEN]), sp


def test_hidden_x_only_left_and_right_edges():
    assert hidden_x((800, 400), SIZE, SCREEN) is None
    assert hidden_x((5, 400), SIZE, SCREEN) == STRIP - 200
    assert hidden_x((1920 - 200 - 5, 400), SIZE, SCREEN) == 1920 - STRIP
    assert hidden_x((800, 2), SIZE, SCREEN) is None
    assert hidden_x((800, 1078), SIZE, SCREEN) is None


def test_strip_rect_left_right_and_middle():
    assert strip_rect(STRIP - 200, SCREEN, SIZE, 400) == (0, 400, STRIP, 200)
    assert strip_rect(1920 - STRIP, SCREEN, SIZE, 400) == (1920 - STRIP, 400, STRIP, 200)
    assert strip_rect(500, SCREEN, SIZE, 400) is None


def test_maybe_hide_moves_offscreen_only_near_edge():
    h, sp = make()
    assert h.maybe_hide((900, 500)) is False and h.is_hidden is False
    assert h.maybe_hide((4, 500)) is True and h.is_hidden is True
    assert sp.pos[0] == STRIP - 200
    assert sp.strips[-1] == "left"  # 缩回状态：窗口改为只画桔子窄条
    assert h.maybe_hide((900, 500)) is False and h.is_hidden is False
    assert sp.strips[-1] is None  # 离开边缘：恢复正常渲染


def test_strip_marker_follows_hide_and_detach():
    """Review 反馈：「贴边隐藏后找不到噜噜、没有桔子」——缩回必须让窗口画桔子。"""
    h, sp = make()
    h.maybe_hide((1920 - 204, 500))
    assert sp.strips[-1] == "right"
    h.detach()
    assert sp.strips[-1] is None
    assert h.is_hidden is False


def test_dragging_strip_away_from_edge_restores_display():
    """鼠标只是划过桔子不会恢复显示，必须把桔子拖离边缘松手。"""
    h, sp = make()
    h.maybe_hide((4, 500))
    assert h.is_hidden is True and sp.strips[-1] == "left"
    assert h.maybe_hide((20, 500)) is True      # 松手时仍在边缘内 → 继续贴边隐藏
    assert h.is_hidden is True
    assert h.maybe_hide((600, 500)) is False    # 拖离边缘松手 → 恢复显示
    assert h.is_hidden is False and sp.strips[-1] is None


def test_config_roundtrip_restores_hidden_state():
    cfg = {}
    h, sp = make(cfg)
    h.maybe_hide((4, 500))
    assert cfg["pet"]["edge_hide"] == {"side": "left", "y": 500}
    h2, sp2 = make(cfg)
    h2.restore_from_config()
    assert h2.is_hidden is True and sp2.pos[0] == STRIP - 200


def test_restore_from_config_noop_when_not_hidden():
    cfg = {"pet": {"edge_hide": None}}
    h, sp = make(cfg)
    h.restore_from_config()
    assert h.is_hidden is False and sp.pos == (500, 500)
