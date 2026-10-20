from pathlib import Path

from pet.autostart import APP_NAME, build_command, current_command, is_enabled, set_enabled, sync


class FakeReg:
    HKEY_CURRENT_USER = "HKCU"

    def __init__(self, fail=False):
        self.store = {}
        self.fail = fail
        self.accesses = []

    def OpenKey(self, root, path, reserved=0, access=0):
        self.accesses.append(access)
        return (root, path)

    def QueryValueEx(self, key, name):
        if name not in self.store:
            raise FileNotFoundError(name)
        return (self.store[name], 1)

    def SetValueEx(self, key, name, reserved, type, value):
        if self.fail:
            raise PermissionError("denied")
        self.store[name] = value

    def DeleteValue(self, key, name):
        if name not in self.store:
            raise FileNotFoundError(name)
        del self.store[name]


def test_build_command_frozen_and_script_mode():
    assert build_command(True, Path(r"C:\apps\lulu pet\lulu_pet.exe"), Path("x")) == r'"C:\apps\lulu pet\lulu_pet.exe"'
    cmd = build_command(False, Path(r"C:\py\python.exe"), Path(r"D:\pet\main.py"))
    assert "pythonw" in cmd.lower() and "main.py" in cmd


def test_set_enabled_writes_and_is_enabled_reads():
    reg = FakeReg()
    assert is_enabled(reg=reg) is False
    assert set_enabled(True, '"C:\\x\\lulu.exe"', reg=reg) is True
    assert is_enabled(reg=reg) is True and reg.store[APP_NAME] == '"C:\\x\\lulu.exe"'


def test_set_enabled_false_removes_value():
    reg = FakeReg()
    set_enabled(True, '"C:\\x\\lulu.exe"', reg=reg)
    assert set_enabled(False, "", reg=reg) is True and is_enabled(reg=reg) is False


def test_set_enabled_returns_false_on_permission_error():
    assert set_enabled(True, '"C:\\x\\lulu.exe"', reg=FakeReg(fail=True)) is False


def test_current_command_none_when_absent():
    assert current_command(reg=FakeReg()) is None


def test_reads_open_key_with_read_access():
    """samDesired=0 时真实注册表打开成功但读值被拒，读路径必须带 KEY_READ。"""
    reg = FakeReg()
    is_enabled(reg=reg)
    current_command(reg=reg)
    assert reg.accesses == [0x20019, 0x20019]


def test_sync_adds_removes_and_rewrites():
    reg = FakeReg()
    assert sync(True, '"C:\\x\\lulu.exe"', reg=reg) is True
    assert current_command(reg=reg) == '"C:\\x\\lulu.exe"'
    assert sync(False, '"C:\\x\\lulu.exe"', reg=reg) is False
    assert current_command(reg=reg) is None
    set_enabled(True, '"C:\\old\\lulu.exe"', reg=reg)
    sync(True, '"C:\\new\\lulu.exe"', reg=reg)
    assert current_command(reg=reg) == '"C:\\new\\lulu.exe"'


def test_sync_idempotent_when_already_correct():
    reg = FakeReg()
    sync(True, '"C:\\x\\lulu.exe"', reg=reg)
    assert sync(True, '"C:\\x\\lulu.exe"', reg=reg) is True
