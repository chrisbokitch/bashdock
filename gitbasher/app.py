"""Desktop window and transactional command/settings editor."""
import copy
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView, QTabWidget, QInputDialog, QCheckBox,
)

from . import config


def create_terminal(parent):
    from .terminal import Terminal
    return Terminal(parent)


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


class ShellTab(QWidget):
    """Each tab owns a shell, its button bar, and its saved profile."""
    configure_requested = Signal()

    def __init__(self, data, parent=None, terminal_factory=create_terminal):
        super().__init__(parent)
        self.data = copy.deepcopy(data)
        self.status = "Loading terminal…"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        self.terminal = terminal_factory(self)
        layout.addWidget(self.terminal, 1)
        footer = QHBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(64)
        self.bar = QWidget()
        self.bar_layout = QHBoxLayout(self.bar)
        self.bar_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.bar)
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


class MainWindow(QMainWindow):
    def __init__(self, terminal_factory=create_terminal):
        super().__init__()
        self.terminal_factory = terminal_factory
        self.setWindowTitle("gitbasher — Git Bash")
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
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.tabBar().tabMoved.connect(self.schedule_save)
        add = QPushButton("+ New tab")
        add.clicked.connect(self.new_tab)
        self.tabs.setCornerWidget(add, Qt.Corner.TopRightCorner)
        self.setCentralWidget(self.tabs)
        menu = self.menuBar().addMenu("Session")
        for label, callback, shortcut in (
            ("New tab", self.new_tab, "Ctrl+Shift+T"),
            ("Rename tab…", lambda: self.rename_tab(self.tabs.currentIndex()), ""),
            ("Close tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+Shift+W"),
            ("Restart shell…", self.restart, ""),
            ("Interrupt (Ctrl+C)", self.interrupt, ""),
            ("Configure tab…", self.configure, ""),
        ):
            action = QAction(label, self)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(shortcut)
            menu.addAction(action)
        menu.addSeparator()
        self.confirm_exit_action = QAction("Confirm before quitting", self)
        self.confirm_exit_action.setCheckable(True)
        self.confirm_exit_action.setChecked(self.data["confirm_on_exit"])
        self.confirm_exit_action.toggled.connect(self.set_confirm_on_exit)
        menu.addAction(self.confirm_exit_action)
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
            QTabBar::tab { padding:9px 16px;background:#202a39; }
            QTabBar::tab:selected { background:#33475a;color:#70dcc2; }
        """)
        if self.config_error:
            QTimer.singleShot(0, self.show_config_error)

    def show_config_error(self):
        QMessageBox.warning(self, "Settings could not be read",
            f"{self.config_error}\n\nDefaults are in use. The original file is unchanged until you save tab settings.")

    def current_tab(self):
        return self.tabs.currentWidget()

    def add_tab(self, profile):
        tab = ShellTab(profile, self, self.terminal_factory)
        tab.configure_requested.connect(lambda: self.configure(tab))
        tab.terminal.loaded.connect(lambda: self.start_shell(tab))
        tab.terminal.ended.connect(lambda text: self.on_ended(tab, text))
        tab.terminal.problem.connect(lambda text: self.show_status(tab, text))
        tab.terminal.directory_changed.connect(lambda path: self.directory_changed(tab, path))
        self.tabs.addTab(tab, profile["name"])
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
                "confirm_on_exit": self.data["confirm_on_exit"],
                "active_tab": self.tabs.currentIndex(),
                "tabs": [copy.deepcopy(self.tabs.widget(i).data) for i in range(self.tabs.count())]}

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
        try:
            if not Path(self.data["bash_path"]).is_file():
                raise ValueError("Git Bash was not found. Choose Git/bin/bash.exe in Configure tab.")
            folder = tab.data["current_folder"]
            if not Path(folder).is_dir():
                folder = tab.data["startup_folder"]
            if not Path(folder).is_dir():
                folder = str(Path.home())
            if folder != tab.data["current_folder"]:
                tab.data["current_folder"] = folder
                self.schedule_save()
            tab.terminal.start(self.data["bash_path"], folder)
        except Exception as error:
            self.show_status(tab, f"Cannot start shell: {error}")
            tab.set_running(False)
            return
        tab.set_running(True)
        self.show_status(tab, "Git Bash · Buttons type into this shell · Copy: Ctrl+Shift+C · Paste: Ctrl+Shift+V")

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
        dialog.setWindowTitle("Close gitbasher?")
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
    app = QApplication(sys.argv)
    app.setApplicationName("gitbasher")
    if sys.platform != "win32":
        QMessageBox.warning(None, "Windows required", "gitbasher currently supports Windows 10/11 with Git for Windows.")
        return
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


