"""Desktop window and transactional command/settings editor."""
import base64
import copy
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal, QSize, QEvent, QUrl
from PySide6.QtGui import QAction, QIcon, QMouseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView, QTabWidget, QInputDialog, QCheckBox, QToolButton, QTabBar, QStatusBar,
)

from . import config
from ._version import __version__
from .window_theme import install_titlebar_theme
from .external_shell import open_external
from .terminal_settings import TerminalSettingsDialog

APP_ICON = Path(__file__).parent / "assets" / "bashdock.ico"


def create_terminal(parent):
    from .terminal import Terminal
    return Terminal(parent)


class FooterBar(QStatusBar):
    """Keep the version at the left even while status/error messages are displayed."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("footerVersion")
        self.version_label.setToolTip("BashDock version")
        self.message_label = QLabel()
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.addWidget(self.version_label)
        self.addWidget(self.message_label, 1)
        self.clear_timer = QTimer(self)
        self.clear_timer.setSingleShot(True)
        self.clear_timer.timeout.connect(self.clearMessage)

    def showMessage(self, text, timeout=0):
        self.clear_timer.stop()
        self.message_label.setText(text)
        self.message_label.setToolTip(text)
        self.messageChanged.emit(text)
        if timeout > 0:
            self.clear_timer.start(timeout)

    def currentMessage(self):
        return self.message_label.text()

    def clearMessage(self):
        self.showMessage("")


class SettingsDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure tab")
        self.resize(780, 520)
        self.result_data = None
        self.original = copy.deepcopy(data)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(data["name"])
        form.addRow("Tab name", self.name)
        self.bash = QLineEdit(data["bash_path"] or config.find_bash())
        self.folder = QLineEdit(data["startup_folder"])
        for label, edit, is_folder in (("Git Bash executable", self.bash, False),
                                        ("Startup folder", self.folder, True)):
            row = QHBoxLayout()
            row.addWidget(edit)
            browse = QPushButton("Browse…")
            browse.clicked.connect(lambda checked=False, e=edit, f=is_folder: self.browse(e, f))
            row.addWidget(browse)
            form.addRow(label, row)
        layout.addLayout(form)
        note = QLabel("Buttons send commands to the active terminal. Use them at an empty shell prompt.\n"
                      "Buttons belong to this tab. The Git Bash executable is shared by all tabs.\n"
                      "Startup folder changes apply when you restart this shell.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Button label", "Bash command"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for button in data["buttons"]:
            self.add_row(button["label"], button["command"])
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        for label, callback in (("Add", lambda: self.add_row("New button", "pwd")),
                                ("Delete", self.delete_row),
                                ("Move left", lambda: self.move_row(-1)),
                                ("Move right", lambda: self.move_row(1))):
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self, edit, folder):
        selected = (QFileDialog.getExistingDirectory(self, "Choose startup folder", edit.text())
                    if folder else QFileDialog.getOpenFileName(self, "Choose Git's bash.exe",
                        edit.text(), "Bash executable (bash.exe);;Executables (*.exe)")[0])
        if selected:
            edit.setText(selected)

    def add_row(self, label, command):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(label))
        self.table.setItem(row, 1, QTableWidgetItem(command))
        self.table.selectRow(row)

    def delete_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def move_row(self, delta):
        row = self.table.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self.table.rowCount():
            return
        for col in range(2):
            first = self.table.takeItem(row, col)
            second = self.table.takeItem(target, col)
            self.table.setItem(row, col, second)
            self.table.setItem(target, col, first)
        self.table.selectRow(target)

    def commit(self):
        data = {"name": self.name.text().strip(), "bash_path": self.bash.text().strip(),
                "current_folder": self.original["current_folder"],
                "startup_folder": self.folder.text().strip(), "buttons": []}
        for row in range(self.table.rowCount()):
            data["buttons"].append({key: self.table.item(row, col).text()
                                    for col, key in enumerate(("label", "command"))})
        try:
            config.validate_tab(data)
            if not Path(data["bash_path"]).is_file() or Path(data["bash_path"]).name.lower() != "bash.exe":
                raise ValueError("Select Git for Windows' bash.exe (usually Git/bin/bash.exe).")
            if not Path(data["startup_folder"]).is_dir():
                raise ValueError("Select an existing startup folder.")
            if data["startup_folder"] != self.original["startup_folder"]:
                data["current_folder"] = data["startup_folder"]
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Cannot save settings", str(error))
            return
        self.result_data = data
        self.accept()


class CommandScrollArea(QScrollArea):
    """Fit the button height, reserving scrollbar space only when needed."""
    def fit_height(self):
        if self.widget() is None:
            return
        size = self.widget().minimumSizeHint()
        height = max(1, size.height())
        if size.width() > self.viewport().width():
            height += self.horizontalScrollBar().sizeHint().height()
        if self.height() != height:
            self.setFixedHeight(height)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Resize):
            self.fit_height()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_height()


class ShellTab(QWidget):
    """Each tab owns a shell, its button bar, and its saved profile."""
    configure_requested = Signal()

    def __init__(self, data, parent=None, terminal_factory=create_terminal):
        super().__init__(parent)
        self.data = copy.deepcopy(data)
        self.shell_bash_path = ""
        self.status = "Loading terminal…"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 0)
        layout.setSpacing(0)
        self.terminal = terminal_factory(self)
        layout.addWidget(self.terminal, 1)
        footer = QHBoxLayout()
        footer.setContentsMargins(3, 6, 3, 6)
        scroll = CommandScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bar = QWidget()
        self.bar_layout = QHBoxLayout(self.bar)
        self.bar_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.bar)
        self.bar.installEventFilter(scroll)
        footer.addWidget(scroll, 1)
        configure = QPushButton("Configure tab…")
        configure.clicked.connect(self.configure_requested.emit)
        footer.addWidget(configure)
        layout.addLayout(footer)
        self.command_buttons = []
        self.build_buttons()

    def build_buttons(self):
        while self.bar_layout.count():
            item = self.bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.command_buttons = []
        for entry in self.data["buttons"]:
            button = QPushButton(entry["label"])
            button.setToolTip(entry["command"])
            # A mouse click should return input to this tab's terminal.
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda checked=False, command=entry["command"]:
                                   self.terminal.run_command(command))
            self.bar_layout.addWidget(button)
            self.command_buttons.append(button)
        self.bar_layout.addStretch()
        self.set_running(bool(self.terminal.process))

    def set_running(self, running):
        for button in self.command_buttons:
            button.setEnabled(running)


class TabStrip(QTabBar):
    """Reserve enough top-row height for the corner control and its padding."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.top_inset = 0
        self.inset_pending = False
        self.currentChanged.connect(self.position_close_buttons)

    def update_tab_inset(self):
        self.inset_pending = False
        parent = self.parentWidget()
        corner = parent.cornerWidget(Qt.Corner.TopRightCorner) if isinstance(parent, QTabWidget) else None
        if self.count() == 0 or corner is None:
            return
        compact_height = max(QTabBar.tabSizeHint(self, i).height() - self.top_inset
                             for i in range(self.count()))
        inset = max(0, corner.sizeHint().height() + 1 - compact_height)
        if inset != self.top_inset:
            self.top_inset = inset
            # Blank space belongs above compact tabs, so their bottoms still meet the shell.
            self.setStyleSheet(f"QTabBar::tab {{ margin-top:{inset}px; }}")
            self.updateGeometry()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) and not self.inset_pending:
            self.inset_pending = True
            QTimer.singleShot(0, self.update_tab_inset)

    def tabLayoutChange(self):
        super().tabLayoutChange()
        self.position_close_buttons()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            # Qt calls mousePressEvent after tabBarDoubleClicked returns. By
            # then the modal rename dialog has already consumed the release.
            # Finish that press so hovering cannot start dragging the tab.
            release = QMouseEvent(QEvent.Type.MouseButtonRelease, event.position(), event.globalPosition(),
                                  event.button(), Qt.MouseButton.NoButton, event.modifiers())
            super().mouseReleaseEvent(release)
        self.position_close_buttons()

    def position_close_buttons(self, *args):
        # Qt also lays out tab buttons when selection changes, without calling
        # tabLayoutChange. Reapply the same offset after either operation.
        inset = getattr(self, "top_inset", 0)
        for index in range(self.count()):
            close = self.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if close is not None:
                rect = self.tabRect(index)
                visible_top = rect.top() + inset
                visible_height = rect.height() - inset
                close.move(close.x(), visible_top + (visible_height - close.height()) // 2)

    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        parent = self.parentWidget()
        if isinstance(parent, QTabWidget):
            corner = parent.cornerWidget(Qt.Corner.TopRightCorner)
            if corner is not None:
                size.setHeight(max(size.height(), corner.sizeHint().height() + 1))
        return size

    def sizeHint(self):
        size = super().sizeHint()
        parent = self.parentWidget()
        if isinstance(parent, QTabWidget):
            corner = parent.cornerWidget(Qt.Corner.TopRightCorner)
            if corner is not None:
                # QTabWidget reserves one pixel of the row for its pane boundary.
                size.setHeight(max(size.height(), corner.sizeHint().height() + 1))
        return size

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        size.setHeight(max(size.height(), self.sizeHint().height()))
        return size


class MainWindow(QMainWindow):
    def __init__(self, terminal_factory=create_terminal):
        super().__init__()
        install_titlebar_theme(QApplication.instance())
        self.terminal_factory = terminal_factory
        self.setWindowTitle("BashDock — Git Bash")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.resize(1120, 760)
        self.config_error = ""
        self.restoring = True
        self.closing = False
        try:
            self.data = config.load()
        except (OSError, ValueError) as error:
            self.data = config.defaults()
            self.config_error = str(error)
        self.allow_save = not bool(self.config_error)
        self.data["bash_path"] = self.data["bash_path"] or config.find_bash()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(350)
        self.save_timer.timeout.connect(self.persist)
        self.tabs = QTabWidget()
        self.tabs.setTabBar(TabStrip(self.tabs))
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.tabBar().tabMoved.connect(self.schedule_save)
        add = QPushButton("+ New tab")
        add.clicked.connect(self.new_tab)
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(3, 0, 3, 3)
        corner_layout.addWidget(add)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(3, 3, 3, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        self.setCentralWidget(body)
        self.setStatusBar(FooterBar(self))
        # Keep Python wrappers alive as well as Qt ownership. Some supported
        # PySide versions otherwise destroy menus when temporary wrappers expire.
        self.manage_menu = self.menuBar().addMenu("Manage")
        menu = self.manage_menu
        for label, callback, shortcut in (
            ("New tab", self.new_tab, "Ctrl+Shift+T"),
            ("Rename tab…", lambda: self.rename_tab(self.tabs.currentIndex()), ""),
            ("Close tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+Shift+W"),
            ("", None, ""),
            ("Open external shell", self.open_external, ""),
            ("Restart shell…", self.restart, ""),
            ("Interrupt (Ctrl+C)", self.interrupt, ""),
        ):
            if callback is None:
                menu.addSeparator()
                continue
            action = QAction(label, self)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(shortcut)
            menu.addAction(action)
        self.settings_menu = self.menuBar().addMenu("Settings")
        settings = self.settings_menu
        configure_action = QAction("Configure current tab…", self)
        configure_action.triggered.connect(self.configure)
        settings.addAction(configure_action)
        terminal_action = QAction("Terminal Settings…", self)
        terminal_action.triggered.connect(self.configure_terminal)
        settings.addAction(terminal_action)
        settings.addSeparator()
        for label, callback in (
            ("Export settings…", self.export_settings),
            ("Import settings…", self.import_settings),
            ("Restore automatic backup…", self.restore_backup),
        ):
            action = QAction(label, self)
            action.triggered.connect(callback)
            settings.addAction(action)
        settings.addSeparator()
        self.confirm_exit_action = QAction("Confirm before quitting", self)
        self.confirm_exit_action.setCheckable(True)
        self.confirm_exit_action.setChecked(self.data["confirm_on_exit"])
        self.confirm_exit_action.toggled.connect(self.set_confirm_on_exit)
        settings.addAction(self.confirm_exit_action)
        self.help_menu = self.menuBar().addMenu("Help")
        help_menu = self.help_menu
        about_action = QAction("About BashDock…", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        # Older PySide bindings can delete a submenu when a temporary action
        # wrapper expires after QAction.menu() is called.
        self.menu_actions = tuple(menu.menuAction() for menu in
                                  (self.manage_menu, self.settings_menu, self.help_menu))
        for profile in self.data["tabs"]:
            self.add_tab(profile)
        self.tabs.setCurrentIndex(self.data["active_tab"])
        self.restoring = False
        self.tab_changed()
        self.setStyleSheet("""
            QMainWindow,QDialog,QWidget { background:#181e29;color:#dde4ef; }
            QPushButton { background:#273344;border:1px solid #3c4b60;border-radius:5px;padding:8px 12px; }
            QPushButton:hover { border-color:#70dcc2; }
            QPushButton:disabled { color:#77818f; }
            QLineEdit,QTableWidget { background:#10141c;selection-background-color:#365e66; }
            QLineEdit { padding:6px; }
            QStatusBar { background:#111b2b;border-top:1px solid #27384d; }
            QStatusBar::item { border:0; }
            QStatusBar QLabel { background:transparent;padding:3px 6px; }
            QLabel#footerVersion { color:#9baec4; }
            QTabWidget::pane { border:0;border-top:1px solid #3c4b60;top:-1px; }
            QTabWidget::tab-bar { left:3px; }
            QTabBar::tab {
                padding:6px 8px 3px;background:#202a39;color:#aab6c8;
                border:1px solid #3c4b60;
                border-top-left-radius:6px;border-top-right-radius:6px;
                margin-right:3px;margin-top:0;
            }
            QTabBar::tab:!selected:hover { background:#2b394b;color:#dde4ef; }
            QTabBar::tab:selected {
                background:#181e29;color:#dde4ef;
                border-top:1px solid #53647c;border-bottom-color:#181e29;
            }
            QToolButton#tabClose { border:0;padding:0;margin:0;border-radius:3px;background:transparent; }
            QToolButton#tabClose:hover { background:#3c4b60; }
        """)
        self.tabs.tabBar().update_tab_inset()
        self.restore_window_geometry()
        if self.config_error:
            QTimer.singleShot(0, self.show_config_error)

    def show_config_error(self):
        if not self.config_error:
            return
        self.statusBar().showMessage("Settings could not be read. Choose a recovery option in Settings.")
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Recover settings")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("BashDock could not read your settings.")
        dialog.setInformativeText(
            "Restore the automatic backup, import an exported settings file, or start fresh. "
            "The damaged file will be preserved when you recover.\n\n"
            "Until then, defaults are in use and automatic saving is paused.\n\n"
            f"File: {config.config_path()}\n{self.config_error}")
        restore = dialog.addButton("Restore backup…", QMessageBox.ButtonRole.ActionRole)
        restore.setEnabled(config.backup_path().is_file())
        imported = dialog.addButton("Import settings…", QMessageBox.ButtonRole.ActionRole)
        fresh = dialog.addButton("Start fresh…", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        clicked = dialog.clickedButton()
        dialog.deleteLater()
        if clicked == restore:
            self.restore_backup()
        elif clicked == imported:
            self.import_settings()
        elif clicked == fresh:
            self.replace_workspace(config.defaults(), "Start with default settings")

    def export_settings(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export settings", str(Path.home() / "bashdock-settings.json"), "JSON settings (*.json)")
        if not filename:
            return
        try:
            path = Path(filename)
            if path.resolve() in (config.config_path().resolve(), config.backup_path().resolve()):
                raise ValueError("Choose a separate file for your export, outside the active settings and automatic backup.")
            config.save(self.snapshot(), path, backup=False)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot export settings", str(error))
            return
        self.statusBar().showMessage(f"Settings exported to {filename}")

    def import_settings(self, checked=False, *, path=None):
        if path is None:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Import settings", str(Path.home()), "Settings files (*.json *.bak);;All files (*)")
            if not filename:
                return
            path = Path(filename)
        try:
            data = config.read(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot import settings", f"The settings file was not imported.\n\n{error}")
            return
        self.replace_workspace(data, f"Import settings from {path}")

    def restore_backup(self):
        self.import_settings(path=config.backup_path())

    def replace_workspace(self, data, description):
        running = sum(bool(self.tabs.widget(i).terminal.process) for i in range(self.tabs.count()))
        if QMessageBox.question(self, "Replace workspace?",
                f"{description}?\n\nThis will replace your tabs and settings with {len(data['tabs'])} tab(s) "
                f"and close {running} running shell session(s). "
                "Your current workspace will be backed up first. Only import settings files you trust.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False
        self.save_timer.stop()
        try:
            if self.allow_save:
                config.archive_workspace(self.snapshot())
            # Commit to disk before touching any live shells. Saving also preserves damaged files.
            config.save(data)
        except (OSError, ValueError) as error:
            self.schedule_save()
            QMessageBox.warning(self, "Cannot replace workspace", f"Your open shells were kept.\n\n{error}")
            return False
        self.restoring = True
        for i in reversed(range(self.tabs.count())):
            tab = self.tabs.widget(i)
            tab.terminal.stop()
            self.tabs.removeTab(i)
            tab.deleteLater()
        self.data = copy.deepcopy(data)
        self.data["bash_path"] = self.data["bash_path"] or config.find_bash()
        self.config_error = ""
        self.allow_save = True
        for profile in self.data["tabs"]:
            self.add_tab(profile)
        self.tabs.setCurrentIndex(self.data["active_tab"])
        self.sync_confirm_action()
        self.restore_window_geometry()
        self.restoring = False
        self.tab_changed()
        self.statusBar().showMessage("Settings restored. Your previous settings were backed up.")
        return True

    def current_tab(self):
        return self.tabs.currentWidget()

    def add_tab(self, profile):
        tab = ShellTab(profile, self, self.terminal_factory)
        tab.terminal.apply_settings(self.data["terminal"])
        tab.configure_requested.connect(lambda: self.configure(tab))
        tab.terminal.loaded.connect(lambda: self.start_shell(tab))
        tab.terminal.ended.connect(lambda text: self.on_ended(tab, text))
        tab.terminal.problem.connect(lambda text: self.show_status(tab, text))
        tab.terminal.directory_changed.connect(lambda path: self.directory_changed(tab, path))
        index = self.tabs.addTab(tab, profile["name"])
        # Native tab close controls clamp the image size on some Windows styles.
        close = QToolButton()
        close.setObjectName("tabClose")
        close.setIcon(QIcon(str(APP_ICON.parent / "tab-close.svg")))
        close.setIconSize(QSize(12, 12))
        close.setFixedSize(12, 12)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.setToolTip("Close tab")
        close.setAccessibleName("Close tab")
        close.clicked.connect(lambda: self.close_tab(self.tabs.indexOf(tab)))
        inset = QWidget()
        inset_layout = QHBoxLayout(inset)
        inset_layout.setContentsMargins(4, 0, 6, 0)
        inset_layout.addWidget(close)
        self.tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, inset)
        return tab

    def new_tab(self):
        profile = config.default_tab(f"Git Bash {self.tabs.count() + 1}")
        current = self.current_tab()
        if current:
            profile["startup_folder"] = current.data["current_folder"]
            profile["current_folder"] = current.data["current_folder"]
        tab = self.add_tab(profile)
        self.tabs.setCurrentWidget(tab)
        self.schedule_save()

    def rename_tab(self, index):
        if index < 0:
            return
        tab = self.tabs.widget(index)
        name, accepted = QInputDialog.getText(self, "Rename tab", "Tab name:", text=tab.data["name"])
        if accepted and name.strip():
            tab.data["name"] = name.strip()
            self.tabs.setTabText(index, tab.data["name"])
            self.schedule_save()

    def tab_changed(self, *args):
        tab = self.current_tab()
        if tab:
            self.statusBar().showMessage(tab.status)
            if tab.terminal.ready:
                tab.terminal.bridge.focus.emit()
        self.schedule_save()

    def show_status(self, tab, text):
        tab.status = text
        if tab is self.current_tab():
            self.statusBar().showMessage(text)

    def directory_changed(self, tab, path):
        if tab.data["current_folder"] != path:
            tab.data["current_folder"] = path
            self.schedule_save()

    def snapshot(self):
        return {"version": 2, "bash_path": self.data["bash_path"],
                "window_geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
                "confirm_on_exit": self.data["confirm_on_exit"],
                "terminal": copy.deepcopy(self.data["terminal"]),
                "active_tab": self.tabs.currentIndex(),
                "tabs": [copy.deepcopy(self.tabs.widget(i).data) for i in range(self.tabs.count())]}

    def restore_window_geometry(self):
        # Optional metadata: old workspaces and damaged geometry still load normally.
        encoded = self.data.get("window_geometry")
        if not isinstance(encoded, str) or not encoded:
            return
        try:
            geometry = base64.b64decode(encoded, validate=True)
        except (ValueError, UnicodeError):
            logging.warning("Ignoring invalid saved window geometry")
            return
        # Qt also brings windows back onto an available screen if monitors changed.
        if not self.restoreGeometry(geometry):
            logging.warning("Ignoring unrecognized saved window geometry")

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "save_timer"):
            self.schedule_save()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "save_timer"):
            self.schedule_save()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "save_timer"):
            self.schedule_save()

    def schedule_save(self, *args):
        if not self.restoring and not self.closing and self.allow_save:
            self.save_timer.start()

    def persist(self):
        if not self.allow_save:
            return False
        try:
            config.save(self.snapshot())
            return True
        except (ValueError, OSError) as error:
            self.statusBar().showMessage(f"Could not save workspace: {error}")
            return False

    def start_shell(self, tab):
        if self.tabs.indexOf(tab) < 0 or self.closing:
            return
        if not Path(self.data["bash_path"]).is_file():
            # Retry discovery so installing Git does not require restarting BashDock.
            self.data["bash_path"] = config.find_bash()
            if not self.data["bash_path"]:
                self.show_status(tab, "Git Bash not found. Install Git for Windows, then use Manage → Restart shell.")
                tab.set_running(False)
                self.show_git_setup()
                return
            self.schedule_save()
        try:
            folder = tab.data["current_folder"]
            if not Path(folder).is_dir():
                folder = tab.data["startup_folder"]
            if not Path(folder).is_dir():
                folder = str(Path.home())
            if folder != tab.data["current_folder"]:
                tab.data["current_folder"] = folder
                self.schedule_save()
            tab.terminal.start(self.data["bash_path"], folder)
            tab.shell_bash_path = self.data["bash_path"]
        except Exception as error:
            logging.exception("Could not start Git Bash")
            self.show_status(tab, f"Cannot start shell: {error}")
            tab.set_running(False)
            QMessageBox.warning(self, "Cannot start Git Bash", str(error))
            return
        tab.set_running(True)
        self.show_status(tab, "")

    def show_git_setup(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Git for Windows required")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText("BashDock needs Git Bash, which is included with Git for Windows.")
        dialog.setInformativeText(
            "1. Download and install Git for Windows using the default options.\n"
            "2. Return to BashDock and choose Manage → Restart shell.\n\n"
            "Already installed? Open Settings → Configure current tab… and select "
            "bash.exe from your Git installation (usually C:\\Program Files\\Git\\bin\\bash.exe).")
        download = dialog.addButton("Download Git for Windows", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton(QMessageBox.StandardButton.Close)
        dialog.exec()
        if dialog.clickedButton() == download:
            QDesktopServices.openUrl(QUrl("https://gitforwindows.org/"))
        dialog.deleteLater()

    def configure_terminal(self):
        dialog = TerminalSettingsDialog(self.data["terminal"], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            dialog.deleteLater()
            return
        previous = self.data["terminal"]
        self.data["terminal"] = dialog.values()
        dialog.deleteLater()
        if not self.persist():
            self.data["terminal"] = previous
            QMessageBox.warning(self, "Settings were not saved", "Check the status bar for details.")
            return
        for index in range(self.tabs.count()):
            self.tabs.widget(index).terminal.apply_settings(self.data["terminal"])

    def show_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("About BashDock")
        dialog.setWindowIcon(self.windowIcon())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        content = QHBoxLayout()
        content.setSpacing(16)
        icon = QLabel()
        icon.setPixmap(self.windowIcon().pixmap(64, 64))
        content.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        details = QVBoxLayout()
        title = QLabel(f"<h2>BashDock</h2><p>Version {__version__}</p>")
        details.addWidget(title)
        description = QLabel("A tabbed Git Bash workspace for Windows, with remembered folders "
                             "and custom command buttons.")
        description.setWordWrap(True)
        details.addWidget(description)
        repository = QLabel('<a href="https://github.com/chrisbokitch/bashdock" '
                            'style="color:#9baec4">BashDock on GitHub</a>')
        repository.setOpenExternalLinks(True)
        details.addWidget(repository)
        content.addLayout(details, 1)
        layout.addLayout(content)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(440, dialog.sizeHint().height())
        dialog.exec()
        dialog.deleteLater()

    def open_external(self):
        tab = self.current_tab()
        if not tab:
            return
        bash_path = tab.shell_bash_path if tab.terminal.process else self.data["bash_path"]
        try:
            open_external(bash_path, tab.data["current_folder"])
        except (OSError, ValueError, RuntimeError) as error:
            self.statusBar().showMessage(f"Could not open external shell: {error}")
            QMessageBox.warning(self, "Cannot open external shell", str(error))

    def configure(self, tab=None):
        if not isinstance(tab, ShellTab):
            tab = self.current_tab()
        if not tab:
            return
        original = copy.deepcopy(tab.data)
        original_bash = self.data["bash_path"]
        dialog = SettingsDialog(dict(tab.data, bash_path=original_bash), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = copy.deepcopy(dialog.result_data)
            self.data["bash_path"] = result.pop("bash_path")
            tab.data = result
            previous_allow = self.allow_save
            self.allow_save = True
            if not self.persist():
                tab.data = original
                self.data["bash_path"] = original_bash
                self.allow_save = previous_allow
                QMessageBox.warning(self, "Cannot save tab", "Changes were not saved. Check the status bar for details.")
                return
            self.tabs.setTabText(self.tabs.indexOf(tab), tab.data["name"])
            tab.build_buttons()
            if not tab.terminal.process and tab.terminal.ready:
                self.start_shell(tab)

    def on_ended(self, tab, text):
        tab.set_running(False)
        self.show_status(tab, text)

    def interrupt(self):
        tab = self.current_tab()
        if tab:
            tab.terminal.write("\x03")

    def restart(self):
        tab = self.current_tab()
        if not tab or not tab.terminal.ready:
            return
        if tab.terminal.process and QMessageBox.question(self, "Restart shell?",
                f"Close the shell in {tab.data['name']} and start a fresh session?") != QMessageBox.StandardButton.Yes:
            return
        tab.terminal.stop()
        tab.set_running(False)
        self.start_shell(tab)

    def close_tab(self, index):
        if index < 0:
            return
        if self.tabs.count() == 1:
            self.close()
            return
        tab = self.tabs.widget(index)
        if tab.terminal.process and QMessageBox.question(self, "Close tab?",
                f"Close {tab.data['name']} and its shell session?") != QMessageBox.StandardButton.Yes:
            return
        tab.terminal.stop()
        self.tabs.removeTab(index)
        tab.deleteLater()
        self.schedule_save()

    def set_confirm_on_exit(self, enabled):
        previous = self.data["confirm_on_exit"]
        self.data["confirm_on_exit"] = enabled
        if not self.persist():
            self.data["confirm_on_exit"] = previous
            self.sync_confirm_action()
            QMessageBox.warning(self, "Setting was not saved", "Could not save the confirmation setting. Check the status bar for details.")

    def sync_confirm_action(self):
        self.confirm_exit_action.blockSignals(True)
        self.confirm_exit_action.setChecked(self.data["confirm_on_exit"])
        self.confirm_exit_action.blockSignals(False)

    def confirm_quit(self, running):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Close BashDock?")
        dialog.setText(f"Close {running} shell session(s) and quit?")
        dialog.setInformativeText("Your tabs and folders will be remembered.")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        skip = QCheckBox("Don't show this again", dialog)
        dialog.setCheckBox(skip)
        accepted = dialog.exec() == QMessageBox.StandardButton.Yes
        return accepted, skip.isChecked()

    def closeEvent(self, event):
        running = sum(bool(self.tabs.widget(i).terminal.process) for i in range(self.tabs.count()))
        previous_confirm = self.data["confirm_on_exit"]
        if running and previous_confirm:
            accepted, skip = self.confirm_quit(running)
            if not accepted:
                event.ignore()
                return
            if skip:
                self.data["confirm_on_exit"] = False
        self.save_timer.stop()
        if self.allow_save and not self.persist():
            self.data["confirm_on_exit"] = previous_confirm
            self.sync_confirm_action()
            QMessageBox.warning(self, "Workspace was not saved", "Could not save your tabs. Resolve the save error before closing.")
            event.ignore()
            return
        self.sync_confirm_action()
        self.closing = True
        for i in range(self.tabs.count()):
            self.tabs.widget(i).terminal.stop()
        event.accept()


def main():
    from .diagnostics import initialize
    initialize()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("chrisbokitch.bashdock")
    app = QApplication(sys.argv)
    app.setApplicationName("BashDock")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(APP_ICON)))
    if sys.platform != "win32":
        QMessageBox.warning(None, "Windows required", "BashDock currently supports Windows 10/11 with Git for Windows.")
        return
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


