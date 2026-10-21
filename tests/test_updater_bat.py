import re
from pathlib import Path

import pytest

from pet.updater import build_updater_bat, write_updater_bat


def _text(**over):
    args = {
        "install_dir": Path(r"C:\Users\zhang san\Desktop\momolulu"),
        "staged_dir": Path(r"C:\Users\zhang san\AppData\Local\Temp\momolulu-update\0.2.0\momolulu.new"),
        "backup_dir": Path(r"C:\Users\zhang san\Desktop\momolulu.old"),
        "exe_name": "momolulu.exe",
        "retries": 30,
    }
    args.update(over)
    return build_updater_bat(**args)


def test_bat_quotes_every_path():
    text = _text()
    assert 'set "TARGET=C:\\Users\\zhang san\\Desktop\\momolulu"' in text
    assert '"%TARGET%"' in text and '"%OLD%"' in text and '"%NEW%"' in text
    assert "momolulu.exe" in text


def test_bat_has_reorder_retry_and_rollback():
    text = _text()
    assert "move" in text and "rmdir" in text
    assert "config.json" in text                     # 从旧目录搬配置
    assert "tries" in text and "30" in text          # 重试上限来自 retries
    assert text.count(":retry") >= 1 and ":rollback" in text
    assert "\r\n" in text                            # cmd 需要 CRLF


def test_bat_uses_given_exe_name_and_retries():
    text = _text(exe_name="lulu.exe", retries=7)
    assert "lulu.exe" in text and "geq 7" in text


def test_write_updater_bat_roundtrip(tmp_path):
    out = write_updater_bat(tmp_path / "updater.bat", _text())
    assert out.exists()
    assert out.read_bytes().startswith(b"@echo off")


def test_retry_cleans_old_before_move():
    text = _text()
    retry_at = text.index(":retry")
    clean_at = text.index('rmdir /s /q "%OLD%"')
    move_at = text.index('move "%TARGET%" "%OLD%"')
    assert retry_at < clean_at < move_at


def test_bat_has_no_pid_based_liveness_check():
    lower = _text().lower()
    for keyword in ("tasklist", "wmic", "taskkill"):
        assert keyword not in lower


def test_write_updater_bat_roundtrips_chinese_via_mbcs(tmp_path):
    text = _text(install_dir=Path(r"C:\Users\张三\Desktop\momolulu 桌宠"))
    path = write_updater_bat(tmp_path / "updater.bat", text)

    # 必须读字节再解码：read_text 默认 newline=None，读侧也会把 \r\n 翻译成 \n，
    # 那样就分不清「写侧漏了 CR」和「读侧吃了 CR」。
    raw = path.read_bytes()
    assert raw.decode("mbcs") == text                # mbcs 无损往返，换行也不被二次翻译

    assert b"\r\r\n" not in raw                      # 不得写出 \r\r\n
    assert b"\n" not in raw.replace(b"\r\n", b"")    # 不得有裸 \n（cmd 需要 CRLF）

    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")                          # mbcs 字节恰不是合法 utf-8，证明写的不是 utf-8


_VAR_RE = re.compile(r"%(?:TARGET|NEW|OLD|EXE)%")


def test_every_path_expansion_is_quoted():
    text = _text(install_dir=Path(r"C:\Users\张三\Desktop\momolulu 桌宠"))
    checked = 0
    for line in text.splitlines():
        if line.lstrip().lower().startswith("rem"):
            continue
        quoted = [m.group(1) for m in re.finditer(r'"([^"]*)"', line)]
        for match in _VAR_RE.finditer(line):
            var = match.group(0)
            assert any(var in seg for seg in quoted), f"路径变量未被引号包裹：{line!r}"
            checked += 1
    assert checked > 0
