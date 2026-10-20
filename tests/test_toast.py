from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication
from ui.toast import Toast, TOAST_WIDTH


def pump(pred, timeout=400):
    loop = QTimer()
    loop.setSingleShot(True)
    done = {"v": False}
    loop.timeout.connect(lambda: done.update(v=True))
    loop.start(timeout)
    while not pred() and not done["v"]:
        QApplication.processEvents()
    return pred()


def test_toast_window_flags(qapp):
    t = Toast()
    assert t.windowFlags() & Qt.FramelessWindowHint and t.windowFlags() & Qt.WindowStaysOnTopHint
    assert t.windowFlags() & Qt.WindowTransparentForInput
    assert t.testAttribute(Qt.WA_TranslucentBackground)


def test_show_message_sets_text_and_visible(qapp):
    t = Toast()
    t.show_message("该喝水啦", duration_ms=50)
    assert t.current_text == "该喝水啦" and t.isVisible() is True


def test_toast_autocloses_and_emits_dismissed(qapp):
    t = Toast()
    got = []
    t.dismissed.connect(lambda: got.append(True))
    t.show_message("hi", duration_ms=50)
    assert pump(lambda: not t.isVisible()) and got == [True]


def test_long_text_wrapped_within_width(qapp):
    t = Toast()
    t.show_message("噜" * 200, duration_ms=10)
    assert t.width() <= TOAST_WIDTH + 40


def test_anchor_positions_toast_above_point(qapp):
    t = Toast()
    t.show_message("x", duration_ms=10, anchor=(1000, 600))
    assert abs(t.x() - 1000) <= 260 and t.y() < 600


def test_kind_switches_style(qapp):
    t = Toast()
    t.show_message("warn", duration_ms=10, kind="warn")
    assert t.kind == "warn"
