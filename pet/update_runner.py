"""把同步的更新逻辑包进 QThread，保证检查与下载都不阻塞 UI。"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from pet.download import fetch_bytes
from pet.updater import LATEST_URL, check_for_update, prepare_program_update

logger = logging.getLogger(__name__)


class UpdateCheckThread(QThread):
    """启动后跑一次更新检查；结果通过 `checked` 回主线程。"""

    checked = pyqtSignal(object)

    def __init__(
        self,
        local_version: str,
        local_assets_dir: Path,
        latest_url: str = LATEST_URL,
        fetch=fetch_bytes,
        parent=None,
    ):
        super().__init__(parent)
        self._args = (local_version, Path(local_assets_dir), latest_url, fetch)

    def run(self) -> None:  # noqa: D102 - QThread
        try:
            self.checked.emit(check_for_update(*self._args))
        except Exception as exc:  # noqa: BLE001 - 更新检查绝不允许拖垮主程序
            logger.warning("检查更新线程失败：%s", exc)
            self.checked.emit(None)


class ProgramUpdateThread(QThread):
    """下载并暂存新版整包；成功发 bat 路径，失败发 None。"""

    staged = pyqtSignal(object)

    def __init__(self, info: dict, install_dir: Path, temp_root: Path, download=None, parent=None):
        """`temp_root` 推荐取 `%TEMP%/momolulu-update`，且必须在安装目录之外。

        暂存目录若落在安装目录内，updater.bat 做目录交换时会把脚本自己一起搬走。
        """
        super().__init__(parent)
        self._info = info
        self._install_dir = Path(install_dir)
        self._temp_root = Path(temp_root)
        self._download = download

    def run(self) -> None:  # noqa: D102 - QThread
        try:
            bat = prepare_program_update(
                self._info, self._install_dir, self._temp_root, download=self._download
            )
        except Exception as exc:  # noqa: BLE001 - 更新下载绝不允许拖垮主程序
            logger.warning("程序更新线程失败：%s", exc)
            self.staged.emit(None)
            return
        self.staged.emit(bat)
