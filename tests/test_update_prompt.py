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


def test_accept_keeps_prompt_visible_for_busy_feedback(qapp):
    p = UpdatePrompt()
    p.show_version("0.2.0")
    assert p.isVisible() is True
    p._accept()
    assert p.isVisible() is True
    p.set_busy(True)
    assert p.isVisible() is True
    assert "正在下载…" in p.body_text()


def test_download_progress_replaces_busy_text_and_keeps_buttons_disabled(qapp):
    p = UpdatePrompt()
    p.show_version("0.2.0", "新增两张素材")
    p.set_busy(True)

    p.set_download_progress(42)

    text = p.body_text()
    assert "正在下载…42%" in text
    assert "0.2.0" in text and "新增两张素材" in text
    assert p.is_busy is True
    assert all(not b.isEnabled() for b in buttons(p).values())


def test_download_progress_is_ignored_once_result_is_shown(qapp):
    # 迟到的进度事件不能把「更新失败」的结论盖回「正在下载」。
    p = UpdatePrompt()
    p.show_version("0.2.0")
    p.set_busy(False, "更新失败，已保留当前版本")

    p.set_download_progress(42)

    assert "更新失败，已保留当前版本" in p.body_text()
    assert "42%" not in p.body_text()


def test_download_progress_is_reset_by_next_show_version(qapp):
    p = UpdatePrompt()
    p.show_version("0.2.0")
    p.set_busy(True)
    p.set_download_progress(42)

    p.show_version("0.2.0")          # 重新点「现在更新」
    p.set_busy(True)

    assert "42%" not in p.body_text()
    assert "正在下载…" in p.body_text()


def test_anchor_offscreen_is_clamped_into_screen(qapp):
    p = UpdatePrompt()
    area = qapp.primaryScreen().availableGeometry()

    p.show_version("0.2.0", anchor=(-9999, -9999))
    assert area.left() <= p.x() and area.top() <= p.y()

    p.show_version("0.2.0", anchor=(99999, 99999))
    assert p.x() + p.width() <= area.right() + 1
    assert p.y() + p.height() <= area.bottom() + 1
