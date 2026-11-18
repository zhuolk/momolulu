from PyQt5.QtCore import QPoint, QPointF, QRect, Qt

from ui.bubbles import BubbleOverlay


def test_bubbles_spread_from_pet_across_current_screen(qapp):
    overlay = BubbleOverlay()
    screen = QRect(-1600, 0, 1600, 900)
    origin = QPoint(-800, 700)
    overlay.start(screen, origin, 6000)
    try:
        first = list(overlay._particles(0))
        middle = list(overlay._particles(.22))
        late = list(overlay._particles(.85))
        assert len(first) == 1 and first[0][0] == QPointF(origin - screen.topLeft())
        assert len(first) < len(middle) < len(late)
        assert {(p.x() > 800, p.y() > 450) for p, _, _ in late} == {
            (False, False), (False, True), (True, False), (True, True)
        }
        assert overlay.windowFlags() & Qt.WindowTransparentForInput
        assert overlay.windowFlags() & Qt.WindowDoesNotAcceptFocus
    finally:
        overlay.stop()
    assert not overlay.isVisible() and not overlay._timer.isActive()
