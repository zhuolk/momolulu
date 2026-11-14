"""状态卡：数值条配色分档、底部备注、定位夹取与重绘。"""

from ui.status_card import StatusCard, StatusHeader, card_height, header_height, level_color

RED = "#e5484d"
AMBER = "#f5a524"
GREEN = "#46a758"
DEEP = "#30a46c"


def test_level_color_picks_band_by_threshold():
    """阈值分档：<30 红 / <60 黄 / <85 绿 / ≥85 深绿。"""
    assert level_color(0).name() == RED
    assert level_color(29).name() == RED
    assert level_color(30).name() == AMBER
    assert level_color(59).name() == AMBER
    assert level_color(60).name() == GREEN
    assert level_color(84).name() == GREEN
    assert level_color(85).name() == DEEP
    assert level_color(100).name() == DEEP


def test_card_height_wraps_fixed_size(qapp):
    card = StatusCard()
    assert card.height() == card_height()
    assert card.width() > 0 and card.height() > 0


def test_note_text_shows_balance_when_idle(qapp):
    card = StatusCard()
    card.set_state(mood=80, energy=80, satiety=80, coins=42.7, working=False, earned=0)
    assert card.note_text() == "噜噜币 42"


def test_note_text_shows_earnings_while_working(qapp):
    card = StatusCard()
    card.set_state(mood=80, energy=80, satiety=80, coins=42.7, working=True, earned=15)
    assert card.note_text() == "上班中 · 已赚 15 噜噜币"


def test_show_near_makes_card_visible(qapp):
    card = StatusCard()
    card.set_state(mood=50, energy=50, satiety=50, coins=0, working=False, earned=0)
    card.show_near(400, 400)
    assert card.isVisible() is True
    card.hide()


def test_move_above_clamps_into_screen(qapp):
    """锚点在屏幕外时卡片要夹回可用区域内。"""
    card = StatusCard()
    card.show_near(0, 0)
    assert card.x() >= 0 and card.y() >= 0
    card.hide()


def test_set_state_redraws_visible_card_without_error(qapp):
    card = StatusCard()
    card.show_near(400, 400)
    card.set_state(mood=10, energy=95, satiety=45, coins=7, working=True, earned=3)
    card.repaint()  # 触发 paintEvent，越界 / 空值都会在这里炸
    card.hide()


def test_header_fixed_size_and_state(qapp):
    """菜单摘要条：固定尺寸、写入数值后可无错重绘。"""
    header = StatusHeader()
    assert header.height() == header_height() and header.width() > 0
    header.set_state(mood=10, energy=95, satiety=45, coins=42.7, working=False, earned=0)
    header.repaint()
    assert header._values() == [10.0, 95.0, 45.0] and header.note_text() == "噜噜币 42"
