"""Exercise the real Qt tab UI with isolated fake terminal processes."""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
from gitbasher import config
from gitbasher.app import MainWindow, SettingsDialog


class FakeBridge(QObject):
    focus = Signal()


class FakeTerminal(QWidget):
    loaded = Signal()
    ended = Signal(str)
    problem = Signal(str)
    directory_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ready = False
        self.process = None
        self.bridge = FakeBridge(self)
        self.commands = []
        self.starts = []
        self.stops = 0

    def start(self, bash, folder):
        self.starts.append((bash, folder))
        self.process = object()

    def run_command(self, command):
        self.commands.append(command)

    def stop(self):
        self.stops += 1
        self.process = None

    def write(self, text):
        self.commands.append(text)


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "settings.json"
        self.bash = Path(self.temp.name) / "bash.exe"
        self.bash.touch()
        data = config.defaults()
        data["bash_path"] = str(self.bash)
        data["tabs"][0]["startup_folder"] = self.temp.name
        data["tabs"][0]["current_folder"] = self.temp.name
        config.save(data, self.path)
        self.paths = patch("gitbasher.config.config_path", return_value=self.path)
        self.paths.start()
        self.answers = patch("gitbasher.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
        self.answers.start()
        self.window = MainWindow(terminal_factory=FakeTerminal)

    def tearDown(self):
        self.window.allow_save = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.answers.stop()
        self.paths.stop()
        self.temp.cleanup()

    def ready(self, tab):
        tab.terminal.ready = True
        tab.terminal.loaded.emit()

    def test_buttons_route_to_their_own_shell_and_bar_is_below_terminal(self):
        first = self.window.current_tab()
        self.ready(first)
        self.window.new_tab()
        second = self.window.current_tab()
        second.data["buttons"] = [{"label": "Build", "command": "make"}]
        second.build_buttons()
        self.ready(second)
        first.command_buttons[0].click()
        second.command_buttons[0].click()
        self.assertEqual(["git status --short --branch"], first.terminal.commands)
        self.assertEqual(["make"], second.terminal.commands)
        self.assertIs(first.layout().itemAt(0).widget(), first.terminal)
        self.assertIsNotNone(first.layout().itemAt(1).layout())

    def test_remembers_order_names_directories_active_tab_and_buttons(self):
        first = self.window.current_tab()
        self.window.new_tab()
        second = self.window.current_tab()
        with patch("gitbasher.app.QInputDialog.getText", return_value=("Build & test", True)):
            self.window.rename_tab(1)
        remembered = Path(self.temp.name) / "Project with spaces"
        remembered.mkdir()
        second.terminal.directory_changed.emit(str(remembered))
        second.data["buttons"] = [{"label": "Tests", "command": "make test"}]
        self.window.tabs.tabBar().moveTab(1, 0)
        self.window.tabs.setCurrentWidget(second)
        self.assertTrue(self.window.persist())
        restored = MainWindow(terminal_factory=FakeTerminal)
        try:
            self.assertEqual(0, restored.tabs.currentIndex())
            self.assertEqual("Build & test", restored.tabs.tabText(0))
            self.assertEqual(second.data, restored.tabs.widget(0).data)
            self.assertEqual(first.data, restored.tabs.widget(1).data)
            self.ready(restored.tabs.widget(0))
            self.assertEqual(str(remembered), restored.tabs.widget(0).terminal.starts[0][1])
        finally:
            restored.allow_save = False
            restored.close()
            restored.deleteLater()

    def test_close_one_tab_leaves_other_shell_running_and_removes_saved_tab(self):
        first = self.window.current_tab()
        self.ready(first)
        self.window.new_tab()
        second = self.window.current_tab()
        self.ready(second)
        self.window.close_tab(1)
        self.assertEqual(1, second.terminal.stops)
        self.assertIsNotNone(first.terminal.process)
        self.assertTrue(self.window.persist())
        self.assertEqual(1, len(config.load(self.path)["tabs"]))

    def test_missing_remembered_folder_falls_back_to_startup_folder(self):
        tab = self.window.current_tab()
        tab.data["current_folder"] = str(Path(self.temp.name) / "removed")
        self.ready(tab)
        self.assertEqual(self.temp.name, tab.terminal.starts[0][1])

    def test_configure_updates_only_selected_tab(self):
        first = self.window.current_tab()
        original = copy.deepcopy(first.data)
        self.window.new_tab()
        second = self.window.current_tab()
        edited = dict(second.data, bash_path=str(self.bash), name="Edited", buttons=[])
        with patch("gitbasher.app.SettingsDialog") as dialog:
            dialog.DialogCode.Accepted = 1
            dialog.return_value.exec.return_value = 1
            dialog.return_value.result_data = edited
            self.window.configure(second)
        self.assertEqual(original, first.data)
        self.assertEqual([], second.data["buttons"])
        self.assertEqual("Edited", self.window.tabs.tabText(1))

    def test_cancelled_tab_close_keeps_both_shells_and_save_failure_preserves_file(self):
        self.window.new_tab()
        self.ready(self.window.current_tab())
        with patch("gitbasher.app.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.window.close_tab(1)
        self.assertEqual(2, self.window.tabs.count())
        original = self.path.read_bytes()
        with patch("gitbasher.config.save", side_effect=PermissionError("locked")):
            self.assertFalse(self.window.persist())
        self.assertEqual(original, self.path.read_bytes())

    def test_dialog_startup_folder_change_resets_remembered_folder(self):
        original = dict(self.window.current_tab().data, bash_path=str(self.bash))
        dialog = SettingsDialog(original, self.window)
        try:
            folder = Path(self.temp.name) / "new folder"
            folder.mkdir()
            dialog.folder.setText(str(folder))
            dialog.commit()
            self.assertEqual(str(folder), dialog.result_data["current_folder"])
            self.assertEqual(original["buttons"], dialog.result_data["buttons"])
        finally:
            dialog.deleteLater()
