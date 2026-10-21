from pathlib import Path

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
