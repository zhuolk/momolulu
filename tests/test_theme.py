"""共享主题：`#RRGGBBAA` 解析、卡片画法与菜单样式表。"""

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainter, QPixmap

from ui.theme import STYLES, draw_card, menu_style, qcolor


def test_qcolor_parses_rrggbbaa_alpha():
    """CSS 风格的末两位是 alpha，不是 QSS 那种前置 alpha。"""
    colour = qcolor("#00000014")
    assert (colour.red(), colour.green(), colour.blue(), colour.alpha()) == (0, 0, 0, 20)


def test_qcolor_parses_six_digit_hex():
    colour = qcolor("#46A758")
    assert (colour.red(), colour.green(), colour.blue()) == (0x46, 0xA7, 0x58)
    assert colour.alpha() == 255


def test_styles_carry_bg_border_text():
    for kind in ("info", "warn"):
        for key in ("bg", "border", "text"):
            assert key in STYLES[kind]


def test_menu_style_uses_rgba_not_eight_digit_hex():
    """QSS 不认 `#RRGGBBAA`，样式表里必须写 `rgba()`。"""
    style = menu_style()
    assert "rgba(" in style
    assert "#00000014" not in style


def test_menu_style_keeps_radius_off_the_menu_panel():
    """样式表里不能有 `border-radius`：本机会写坏堆，随后任意 `show()` 直接崩，回归护栏。"""
    style = menu_style()
    assert "background-color" in style
    assert "border-radius" not in style


def test_draw_card_paints_without_error(qapp):
    pixmap = QPixmap(120, 80)
    painter = QPainter(pixmap)
    draw_card(painter, QRectF(14, 14, 92, 52))
    draw_card(painter, QRectF(14, 14, 92, 52), "warn")
    painter.end()
