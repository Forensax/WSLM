from __future__ import annotations

import re
from functools import partial
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig, ConfigStore
from .models import InstalledDistro, OnlineDistro
from .workers import FunctionWorker
from .wsl_service import (
    WslCommandError,
    WslService,
    validate_environment_name,
    validate_install_location,
)


APP_STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
    color: #1f2937;
}
QMainWindow, QDialog {
    background: #f7f8fa;
}
QFrame#toolbar, QTableWidget {
    background: #ffffff;
    border: 1px solid #dfe3e8;
    border-radius: 6px;
}
QTableWidget {
    gridline-color: #edf0f3;
    selection-background-color: #eaf2ff;
    selection-color: #1f2937;
}
QHeaderView::section {
    background: #f4f6f8;
    color: #4b5563;
    border: 0;
    border-bottom: 1px solid #dfe3e8;
    padding: 8px 10px;
    font-weight: 600;
}
QPushButton {
    min-height: 32px;
    padding: 0 14px;
    border: 1px solid #cfd5dc;
    border-radius: 5px;
    background: #ffffff;
    font-weight: 500;
}
QPushButton:hover {
    background: #f1f5f9;
}
QPushButton:pressed {
    background: #e5eaf0;
}
QPushButton:disabled {
    color: #9ca3af;
    background: #f3f4f6;
}
QPushButton#primaryButton {
    color: #ffffff;
    border-color: #2563eb;
    background: #2563eb;
}
QPushButton#primaryButton:hover {
    background: #1d4ed8;
}
QPushButton#dangerButton {
    color: #b42318;
    border-color: #f0b4ae;
}
QPushButton#dangerButton:hover {
    background: #fff1f0;
}
QLineEdit, QComboBox {
    min-height: 32px;
    padding: 0 9px;
    background: #ffffff;
    border: 1px solid #cfd5dc;
    border-radius: 5px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #2563eb;
}
QProgressBar {
    min-height: 4px;
    max-height: 4px;
    border: 0;
    background: #e5e7eb;
}
QProgressBar::chunk {
    background: #2563eb;
}
"""


class CreateEnvironmentDialog(QDialog):
    def __init__(
        self,
        distros: list[OnlineDistro],
        config: AppConfig,
        installed_names: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("创建环境")
        self.setModal(True)
        self.setMinimumWidth(540)
        self._config = config
        self._installed_names = installed_names
        self._path_was_edited = False

        self.distro_combo = QComboBox()
        for distro in distros:
            self.distro_combo.addItem(
                f"{distro.friendly_name}  ({distro.name})",
                distro.name,
            )

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如 Ubuntu-Dev")

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"D:\WSL\Ubuntu-Dev")
        browse_button = QPushButton("浏览")
        browse_button.clicked.connect(self._browse_location)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_button)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("发行版", self.distro_combo)
        form.addRow("环境名称", self.name_edit)
        path_widget = QWidget()
        path_widget.setLayout(path_row)
        form.addRow("安装目录", path_widget)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("创建")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primaryButton")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self._validate_and_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(18)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        preferred = config.last_distro
        selected_index = self.distro_combo.findData(preferred)
        if selected_index < 0:
            selected_index = self.distro_combo.findData("Ubuntu")
        if selected_index >= 0:
            self.distro_combo.setCurrentIndex(selected_index)

        self.distro_combo.currentIndexChanged.connect(self._suggest_name)
        self.name_edit.textChanged.connect(self._update_suggested_path)
        self.path_edit.textEdited.connect(self._mark_path_edited)
        self._suggest_name()

    @property
    def values(self) -> tuple[str, str, str]:
        return (
            str(self.distro_combo.currentData()),
            self.name_edit.text().strip(),
            self.path_edit.text().strip(),
        )

    def _suggest_name(self) -> None:
        distro = str(self.distro_combo.currentData() or "WSL")
        base = re.sub(r"[^A-Za-z0-9._-]", "-", distro).strip(".-_") or "WSL"
        candidate = base
        suffix = 2
        while candidate in self._installed_names:
            candidate = f"{base}-{suffix}"
            suffix += 1
        self.name_edit.setText(candidate)
        self.name_edit.selectAll()

    def _mark_path_edited(self) -> None:
        self._path_was_edited = True

    def _update_suggested_path(self, name: str) -> None:
        if self._path_was_edited:
            return
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "-", name.strip())
        self.path_edit.setText(str(Path(self._config.default_root) / safe_name))

    def _browse_location(self) -> None:
        initial = self.path_edit.text() or self._config.default_root
        selected = QFileDialog.getExistingDirectory(self, "选择安装目录", initial)
        if selected:
            self._path_was_edited = True
            self.path_edit.setText(selected)

    def _validate_and_accept(self) -> None:
        distro, name, location = self.values
        try:
            if not distro:
                raise ValueError("请选择发行版。")
            name = validate_environment_name(name)
            if name in self._installed_names:
                raise ValueError("环境名称已经存在。")
            validate_install_location(location)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "无法创建", str(exc))
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: WslService | None = None,
        config_store: ConfigStore | None = None,
    ) -> None:
        super().__init__()
        self.service = service or WslService()
        self.config_store = config_store or ConfigStore()
        self.config = self.config_store.load()
        self.thread_pool = QThreadPool.globalInstance()
        self.online_distros: list[OnlineDistro] = []
        self.installed_distros: list[InstalledDistro] = []
        self._active_workers: set[FunctionWorker] = set()
        self._refresh_pending = 0
        self._busy = False

        self.setWindowTitle("WSLM")
        self.resize(920, 580)
        self.setMinimumSize(760, 460)

        self._build_ui()
        self._refresh_all()

    def _build_ui(self) -> None:
        title = QLabel("WSL 环境")
        title.setStyleSheet("font-size: 22px; font-weight: 650; color: #111827;")

        self.status_label = QLabel("正在读取环境…")
        self.status_label.setStyleSheet("color: #6b7280;")

        self.create_button = QPushButton("创建环境")
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self._show_create_dialog)
        self.create_button.setEnabled(False)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self._refresh_all)

        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 10, 12, 10)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addWidget(self.status_label)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.refresh_button)
        toolbar_layout.addWidget(self.create_button)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["环境名称", "状态", "WSL", "默认", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 270)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(toolbar)
        layout.addWidget(self.progress)
        layout.addWidget(self.table, 1)
        self.setCentralWidget(content)

    def _run_worker(
        self,
        function: Callable[..., Any],
        *args: Any,
        on_success: Callable[[Any], None] | None = None,
        busy_text: str = "正在处理…",
        exclusive: bool = True,
    ) -> None:
        if exclusive:
            self._set_busy(True, busy_text)
        worker = FunctionWorker(function, *args)
        if on_success:
            worker.signals.succeeded.connect(on_success)
        worker.signals.failed.connect(self._show_error)
        finished_callback = partial(self._set_busy, False) if exclusive else None
        self._submit_worker(worker, finished_callback)

    def _submit_worker(
        self,
        worker: FunctionWorker,
        finished_callback: Callable[[], None] | None = None,
    ) -> None:
        self._active_workers.add(worker)
        worker.signals.finished.connect(
            partial(self._worker_finished, worker, finished_callback)
        )
        self.thread_pool.start(worker)

    def _worker_finished(
        self,
        worker: FunctionWorker,
        finished_callback: Callable[[], None] | None,
    ) -> None:
        self._active_workers.discard(worker)
        if finished_callback:
            finished_callback()

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        self.refresh_button.setEnabled(not busy)
        self.create_button.setEnabled(not busy and bool(self.online_distros))
        if text:
            self.status_label.setText(text)
        self._update_row_buttons()

    def _refresh_all(self) -> None:
        if self._busy:
            return
        self._set_busy(True, "正在刷新…")
        self._refresh_pending = 2

        installed_worker = FunctionWorker(self.service.list_installed)
        installed_worker.signals.succeeded.connect(self._receive_installed)
        installed_worker.signals.failed.connect(self._show_error)

        online_worker = FunctionWorker(self.service.list_online)
        online_worker.signals.succeeded.connect(self._receive_online)
        online_worker.signals.failed.connect(self._show_online_error)

        self._submit_worker(installed_worker, self._refresh_part_finished)
        self._submit_worker(online_worker, self._refresh_part_finished)

    def _refresh_part_finished(self) -> None:
        self._refresh_pending -= 1
        if self._refresh_pending <= 0:
            self._refresh_pending = 0
            self._set_busy(False)
            self._update_status()

    def _receive_installed(self, distros: object) -> None:
        self.installed_distros = list(distros)  # type: ignore[arg-type]
        self._render_table()

    def _receive_online(self, distros: object) -> None:
        self.online_distros = list(distros)  # type: ignore[arg-type]

    def _show_online_error(self, error: object) -> None:
        self.online_distros = []
        self.status_label.setText("无法获取在线发行版")
        self._show_error(error)

    def _update_status(self) -> None:
        count = len(self.installed_distros)
        self.status_label.setText(f"共 {count} 个环境")
        self.create_button.setEnabled(not self._busy and bool(self.online_distros))

    def _render_table(self) -> None:
        self.table.setRowCount(0)
        for distro in self.installed_distros:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 48)

            name_item = QTableWidgetItem(distro.name)
            name_item.setData(Qt.ItemDataRole.UserRole, distro)
            state_item = QTableWidgetItem(distro.state_label)
            version_item = QTableWidgetItem(distro.version or "—")
            default_item = QTableWidgetItem("是" if distro.is_default else "—")
            version_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            default_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if distro.is_running:
                state_item.setForeground(QColor("#067647"))
            elif distro.is_busy:
                state_item.setForeground(QColor("#b54708"))

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, state_item)
            self.table.setItem(row, 2, version_item)
            self.table.setItem(row, 3, default_item)
            self.table.setCellWidget(row, 4, self._build_action_widget(distro))

        self._update_status()

    def _build_action_widget(self, distro: InstalledDistro) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(6)

        open_button = QPushButton("打开")
        stop_button = QPushButton("停止")
        delete_button = QPushButton("删除")
        delete_button.setObjectName("dangerButton")

        open_button.clicked.connect(lambda: self._open_environment(distro.name))
        stop_button.clicked.connect(lambda: self._stop_environment(distro.name))
        delete_button.clicked.connect(lambda: self._delete_environment(distro.name))

        open_enabled = not distro.is_busy
        stop_enabled = distro.is_running and not distro.is_busy
        delete_enabled = not distro.is_busy
        for button, base_enabled in (
            (open_button, open_enabled),
            (stop_button, stop_enabled),
            (delete_button, delete_enabled),
        ):
            button.setProperty("rowAction", True)
            button.setProperty("baseEnabled", base_enabled)
            button.setEnabled(base_enabled and not self._busy)

        layout.addWidget(open_button)
        layout.addWidget(stop_button)
        layout.addWidget(delete_button)
        return widget

    def _update_row_buttons(self) -> None:
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 4)
            if not widget:
                continue
            for button in widget.findChildren(QPushButton):
                button.setEnabled(not self._busy and bool(button.property("baseEnabled")))

    def _show_create_dialog(self) -> None:
        if self._busy or not self.online_distros:
            return
        installed_names = {distro.name for distro in self.installed_distros}
        dialog = CreateEnvironmentDialog(
            self.online_distros,
            self.config,
            installed_names,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        distro, name, location = dialog.values
        self.config.last_distro = distro
        self.config.default_root = str(Path(location).parent)
        self.config_store.save(self.config)

        def created(path: object) -> None:
            self.config.created_environments[name] = str(path)
            self.config_store.save(self.config)
            QTimer.singleShot(0, lambda: self._refresh_installed_then_offer_launch(name))

        self._run_worker(
            self.service.install,
            distro,
            name,
            location,
            on_success=created,
            busy_text=f"正在创建 {name}…",
        )

    def _refresh_installed_then_offer_launch(self, name: str) -> None:
        def refreshed(distros: object) -> None:
            self._receive_installed(distros)
            answer = QMessageBox.question(
                self,
                "创建完成",
                f"{name} 已创建。\n\n现在打开终端完成首次初始化吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._open_environment(name)

        self._run_worker(
            self.service.list_installed,
            on_success=refreshed,
            busy_text="正在更新列表…",
        )

    def _open_environment(self, name: str) -> None:
        try:
            self.service.launch_terminal(name)
        except Exception as exc:
            self._show_error(exc)

    def _stop_environment(self, name: str) -> None:
        def stopped(_: object) -> None:
            QTimer.singleShot(0, self._refresh_installed)

        self._run_worker(
            self.service.terminate,
            name,
            on_success=stopped,
            busy_text=f"正在停止 {name}…",
        )

    def _delete_environment(self, name: str) -> None:
        answer = QMessageBox.warning(
            self,
            "删除环境",
            f"确定删除 {name} 吗？\n\n环境中的文件、软件和设置将永久删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def delete_operation() -> None:
            try:
                self.service.terminate(name)
            except WslCommandError:
                pass
            self.service.unregister(name)

        def deleted(_: object) -> None:
            location = self.config.created_environments.pop(name, "")
            self.config_store.save(self.config)
            if location:
                path = Path(location)
                try:
                    if path.exists() and not any(path.iterdir()):
                        path.rmdir()
                except OSError:
                    pass
            QTimer.singleShot(0, self._refresh_installed)

        self._run_worker(
            delete_operation,
            on_success=deleted,
            busy_text=f"正在删除 {name}…",
        )

    def _refresh_installed(self) -> None:
        self._run_worker(
            self.service.list_installed,
            on_success=self._receive_installed,
            busy_text="正在更新列表…",
        )

    def _show_error(self, error: object) -> None:
        message = str(error)
        if isinstance(error, WslCommandError):
            command = " ".join(error.command)
            message = f"{error}\n\n命令：{command}"
        QMessageBox.critical(self, "操作失败", message)


def configure_application_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f7f8fa"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLE)
