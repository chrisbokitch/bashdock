"""Desktop window and transactional command/settings editor."""
import copy
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView,
)

from . import config
from .terminal import Terminal


class SettingsDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("gitbasher settings")
        self.resize(780, 520)
        self.result_data = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
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
                      "Shell path and startup folder changes apply when you restart the shell.")
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
        data = {"bash_path": self.bash.text().strip(),
                "startup_folder": self.folder.text().strip(), "buttons": []}
        for row in range(self.table.rowCount()):
            data["buttons"].append({key: self.table.item(row, col).text()
                                    for col, key in enumerate(("label", "command"))})
        try:
            config.validate(data)
            if not Path(data["bash_path"]).is_file() or Path(data["bash_path"]).name.lower() != "bash.exe":
                raise ValueError("Select Git for Windows' bash.exe (usually Git/bin/bash.exe).")
            if not Path(data["startup_folder"]).is_dir():
                raise ValueError("Select an existing startup folder.")
            config.save(data)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Cannot save settings", str(error))
            return
        self.result_data = data
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("gitbasher — Git Bash")
        self.resize(1120, 760)
        self.config_error = ""
        try:
            self.data = config.load()
        except (OSError, ValueError) as error:
            self.data = config.defaults()
            self.config_error = str(error)
        self.data["bash_path"] = self.data["bash_path"] or config.find_bash()
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 5)
        header = QHBoxLayout()
        title = QLabel("GITBASHER")
        title.setStyleSheet("font-weight:700;letter-spacing:2px;color:#70dcc2;padding:8px")
        header.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(60)
        self.bar = QWidget()
        self.bar_layout = QHBoxLayout(self.bar)
        self.bar_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.bar)
        header.addWidget(scroll, 1)
        settings = QPushButton("Configure…")
        settings.clicked.connect(self.configure)
        header.addWidget(settings)
        layout.addLayout(header)
        self.terminal = Terminal()
        layout.addWidget(self.terminal, 1)
        self.setCentralWidget(body)
        self.command_buttons = []
        self.build_buttons()
        self.terminal.loaded.connect(self.on_ready)
        self.terminal.ended.connect(self.on_ended)
        self.terminal.problem.connect(lambda text: self.statusBar().showMessage(text))
        menu = self.menuBar().addMenu("Session")
        restart = QAction("Restart shell…", self)
        restart.triggered.connect(self.restart)
        menu.addAction(restart)
        interrupt = QAction("Interrupt (Ctrl+C)", self)
        interrupt.triggered.connect(lambda: self.terminal.write("\x03"))
        menu.addAction(interrupt)
        menu.addAction("Settings…", self.configure)
        self.statusBar().showMessage("Loading terminal…")
        self.setStyleSheet("""
            QMainWindow,QDialog,QWidget { background:#181e29;color:#dde4ef; }
            QPushButton { background:#273344;border:1px solid #3c4b60;border-radius:5px;padding:8px 12px; }
            QPushButton:hover { border-color:#70dcc2; }
            QPushButton:disabled { color:#77818f; }
            QLineEdit,QTableWidget { background:#10141c;selection-background-color:#365e66; }
            QLineEdit { padding:6px; }
        """)

    def build_buttons(self):
        while self.bar_layout.count():
            item = self.bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.command_buttons = []
        for entry in self.data["buttons"]:
            button = QPushButton(entry["label"])
            button.setToolTip(entry["command"])
            button.clicked.connect(lambda checked=False, command=entry["command"]: self.terminal.run_command(command))
            button.setEnabled(bool(self.terminal.process))
            self.bar_layout.addWidget(button)
            self.command_buttons.append(button)
        self.bar_layout.addStretch()

    def on_ready(self):
        if self.config_error:
            QMessageBox.warning(self, "Settings could not be read",
                f"{self.config_error}\n\nDefaults are in use. The original file is unchanged until you save settings.")
        if not self.data["bash_path"]:
            self.statusBar().showMessage("Choose your Git Bash executable in Configure.")
            self.configure()
        self.start_shell()

    def start_shell(self):
        try:
            if not Path(self.data["bash_path"]).is_file():
                raise ValueError("Git Bash was not found. Choose Git/bin/bash.exe in Configure.")
            if not Path(self.data["startup_folder"]).is_dir():
                raise ValueError("Startup folder no longer exists. Update it in Configure.")
            self.terminal.start(self.data["bash_path"], self.data["startup_folder"])
        except Exception as error:
            self.statusBar().showMessage("Shell could not start. Configure, then use Session → Restart shell.")
            QMessageBox.warning(self, "Cannot start Git Bash", str(error))
            return
        for button in self.command_buttons:
            button.setEnabled(True)
        self.statusBar().showMessage("Git Bash · Buttons type into the active terminal · Copy: Ctrl+Shift+C · Paste: Ctrl+Shift+V")

    def configure(self):
        dialog = SettingsDialog(copy.deepcopy(self.data), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.data = dialog.result_data
            self.build_buttons()

    def on_ended(self, text):
        for button in self.command_buttons:
            button.setEnabled(False)
        self.statusBar().showMessage(text)

    def restart(self):
        if not self.terminal.ready:
            return
        if self.terminal.process and QMessageBox.question(self, "Restart shell?",
                "Close the current shell and start a fresh session?") != QMessageBox.StandardButton.Yes:
            return
        self.terminal.stop()
        self.on_ended("Starting shell…")
        self.start_shell()

    def closeEvent(self, event):
        if self.terminal.process and QMessageBox.question(self, "Close gitbasher?",
                "Close the active shell session and quit?") != QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        self.terminal.stop()
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
