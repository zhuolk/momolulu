"""把同步的更新逻辑包进 QThread，保证检查与下载都不阻塞 UI。"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from pet.download import fetch_bytes
from pet.updater import LATEST_URL, apply_asset_update, check_for_update, prepare_program_update

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


class AssetUpdateThread(QThread):
    """素材热更：把逐文件下载搬到后台线程；成功发写入的相对路径列表，失败发空列表。"""

    done = pyqtSignal(object)

    def __init__(self, changes: dict, base: str, local_dir: Path, fetch=fetch_bytes, parent=None):
        super().__init__(parent)
        self._args = (changes, base, Path(local_dir), fetch)

    def run(self) -> None:  # noqa: D102 - QThread
        try:
            self.done.emit(apply_asset_update(*self._args))
        except Exception as exc:  # noqa: BLE001 - 素材热更绝不允许拖垮主程序
            logger.warning("素材热更线程失败：%s", exc)
            self.done.emit([])


_DOWNLOAD_PERCENT_MAX = 99  # 后面还有校验与解压，报到 100% 反而像卡住


class ProgramUpdateThread(QThread):
    """下载并暂存新版整包；成功发 bat 路径，失败发 None，下载期发整数百分比。"""

    staged = pyqtSignal(object)
    progressed = pyqtSignal(int)

    def __init__(self, info: dict, install_dir: Path, temp_root: Path, download=None, parent=None):
        """`temp_root` 推荐取 `%TEMP%/momolulu-update`，且必须在安装目录之外。

        暂存目录若落在安装目录内，updater.bat 做目录交换时会把脚本自己一起搬走。
        """
        super().__init__(parent)
        self._info = info
        self._install_dir = Path(install_dir)
        self._temp_root = Path(temp_root)
        self._download = download
        self._percent = -1

    def run(self) -> None:  # noqa: D102 - QThread
        try:
            bat = prepare_program_update(
                self._info,
                self._install_dir,
                self._temp_root,
                download=self._download,
                progress=self._on_progress,
            )
        except Exception as exc:  # noqa: BLE001 - 更新下载绝不允许拖垮主程序
            logger.warning("程序更新线程失败：%s", exc)
            self.staged.emit(None)
            return
        self.staged.emit(bat)

    def _on_progress(self, done: int, total: int) -> None:
        """把分块回调收敛成整数百分比，只在百分比变化时发信号。

        56MB 按 1MB 分块会回调几十次，逐次发信号会把主线程的弹窗刷新刷爆。
        """
        if total <= 0:
            return
        percent = min(_DOWNLOAD_PERCENT_MAX, done * 100 // total)
        if percent == self._percent:
            return
        self._percent = percent
        self.progressed.emit(percent)
