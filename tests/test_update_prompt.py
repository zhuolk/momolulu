from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPushButton

from ui.update_prompt import TITLE, UpdatePrompt


def buttons(prompt):
    return {b.text(): b for b in prompt.findChildren(QPushButton)}


def test_buttons_and_title(qapp):
    p = UpdatePrompt()
    assert set(buttons(p)) == {"现在更新", "稍后"}
    assert p._title.text() == TITLE


def test_prompt_is_clickable(qapp):
    p = UpdatePrompt()
    assert not (p.windowFlags() & Qt.WindowTransparentForInput)


def test_accept_and_decline_emit(qapp):
    p = UpdatePrompt()
    got = []
    p.accepted.connect(lambda: got.append("accept"))
    p.declined.connect(lambda: got.append("decline"))
    buttons(p)["现在更新"].click()
    assert got == ["accept"] and p.isVisible() is False
    p.show_version("0.2.0")
    buttons(p)["稍后"].click()
    assert got == ["accept", "decline"] and p.isVisible() is False


def test_show_version_puts_version_and_notes_in_text(qapp):
    p = UpdatePrompt()
    p.show_version("0.2.0", "新增两张素材")
    assert p.current_version() == "0.2.0"
    text = p.body_text()
    assert "0.2.0" in text and "新增两张素材" in text


def test_busy_disables_buttons_and_shows_status(qapp):
    p = UpdatePrompt()
    p.show_version("0.2.0")
    p.set_busy(True)
    assert p.is_busy is True
    assert all(not b.isEnabled() for b in buttons(p).values())
    assert "正在下载…" in p.body_text()
    p.set_busy(False, "更新失败，已保留当前版本")
    assert p.is_busy is False
    assert all(b.isEnabled() for b in buttons(p).values())
    assert "更新失败，已保留当前版本" in p.body_text()
