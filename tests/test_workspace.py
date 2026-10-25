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
from bashdock import config
from bashdock.app import MainWindow, SettingsDialog


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

    def apply_settings(self, settings):
        self.preferences = copy.deepcopy(settings)

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
        self.paths = patch("bashdock.config.config_path", return_value=self.path)
        self.paths.start()
        self.answers = patch("bashdock.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
        self.answers.start()
        self.window = MainWindow(terminal_factory=FakeTerminal)

    def tearDown(self):
        self.window.allow_save = False
        self.window.data["confirm_on_exit"] = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.answers.stop()
        self.paths.stop()
        self.temp.cleanup()

    def ready(self, tab):
        tab.terminal.ready = True
        tab.terminal.loaded.emit()

    def test_save_subset_preserves_order_active_tab_and_independent_command_bars(self):
        for name in ("Website", "Droplet", "CIDR Manager"):
            self.window.new_tab()
            self.window.current_tab().data["name"] = name
        self.window.tabs.widget(0).data["name"] = "App"
        self.window.tabs.widget(2).data["buttons"] = [{"label": "Connect", "command": "ssh root@example.test"}]
        self.window.tabs.setCurrentIndex(2)
        self.assertTrue(self.window.save_workspace("BashDock Development", [2, 0, 1]))
        saved = self.window.data["workspaces"][0]
        self.assertEqual(["App", "Website", "Droplet"], [t["name"] for t in saved["tabs"]])
        self.assertEqual(2, saved["active_tab"])
        self.window.tabs.widget(2).data["buttons"][0]["command"] = "changed"
        self.assertEqual("ssh root@example.test", saved["tabs"][2]["buttons"][0]["command"])
        self.window.tabs.setCurrentIndex(3)
        self.assertTrue(self.window.save_workspace("CIDR", [0, 1]))
        self.assertEqual(0, self.window.data["workspaces"][1]["active_tab"])
        self.assertEqual(self.window.data["workspaces"], config.read(self.path)["workspaces"])

    def test_open_saved_workspace_adds_fresh_tabs_without_stopping_existing_shell(self):
        first = self.window.current_tab()
        first.data["buttons"] = [{"label": "Connect", "command": "ssh root@example.test"}]
        self.ready(first)
        self.assertTrue(self.window.save_workspace("Droplet", [0]))
        self.window.data["terminal"]["font_size"] = 23
        self.assertTrue(self.window.open_workspace(0))
        opened = self.window.current_tab()
        self.assertEqual(2, self.window.tabs.count())
        self.assertEqual(0, first.terminal.stops)
        self.assertEqual(23, opened.terminal.preferences["font_size"])
        self.ready(opened)
        self.assertEqual(1, len(opened.terminal.starts))
        self.assertEqual([], opened.terminal.commands)
        opened.data["buttons"][0]["label"] = "Changed"
        self.assertEqual("Connect", self.window.data["workspaces"][0]["tabs"][0]["buttons"][0]["label"])

    def test_replace_saved_workspace_confirms_preserves_global_settings_and_archives_current_tabs(self):
        self.assertTrue(self.window.save_workspace("Project", [0]))
        self.window.new_tab()
        self.window.current_tab().data["name"] = "Unsaved other project"
        old = self.window.current_tab()
        self.ready(old)
        with patch("bashdock.app.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.assertFalse(self.window.open_workspace(0, replace=True))
        self.assertEqual(2, self.window.tabs.count())
        self.assertEqual(0, old.terminal.stops)
        self.window.data["terminal"]["font_size"] = 24
        self.window.data["confirm_on_exit"] = False
        self.assertTrue(self.window.open_workspace(0, replace=True))
        self.assertEqual(1, self.window.tabs.count())
        self.assertEqual(1, old.terminal.stops)
        self.assertEqual(24, self.window.data["terminal"]["font_size"])
        self.assertFalse(self.window.data["confirm_on_exit"])
        self.assertEqual("Project", self.window.data["workspaces"][0]["name"])
        archives = list((self.path.parent / "backups").glob("settings-before-workspace-*.json"))
        self.assertEqual(1, len(archives))
        self.assertEqual("Unsaved other project", config.read(archives[0])["tabs"][1]["name"])

    def test_workspace_errors_keep_saved_library_and_running_tabs(self):
        self.assertTrue(self.window.save_workspace("Project", [0]))
        first = self.window.current_tab()
        self.ready(first)
        saved = copy.deepcopy(self.window.data["workspaces"])
        with patch("bashdock.app.QMessageBox.warning"):
            self.assertFalse(self.window.save_workspace(" project ", [0]))
            self.assertFalse(self.window.save_workspace("Empty", []))
            with patch("bashdock.config.save", side_effect=PermissionError("locked")):
                self.assertFalse(self.window.save_workspace("New project", [0]))
                self.assertFalse(self.window.open_workspace(0))
                self.assertFalse(self.window.open_workspace(0, replace=True))
        self.assertEqual(saved, self.window.data["workspaces"])
        self.assertEqual(1, self.window.tabs.count())
        self.assertEqual(0, first.terminal.stops)

    def test_workspace_manager_updates_renames_and_deletes_without_closing_tabs(self):
        from bashdock.workspaces import WorkspacesDialog, SaveWorkspaceDialog
        from PySide6.QtCore import Qt

        self.assertTrue(self.window.save_workspace("Project", [0]))
        self.window.new_tab()
        self.window.current_tab().data["name"] = "Second tab"
        dialog = WorkspacesDialog(self.window)
        picker = SaveWorkspaceDialog(self.window.snapshot()["tabs"], dialog, "Project", updating=True)
        picker.tabs.item(0).setCheckState(Qt.CheckState.Unchecked)
        self.assertEqual([1], picker.selected_indexes())
        with patch("bashdock.workspaces.SaveWorkspaceDialog", return_value=picker), \
                patch.object(picker, "exec", return_value=1):
            dialog.update_selected()
        self.assertEqual("Second tab", self.window.data["workspaces"][0]["tabs"][0]["name"])
        with patch("bashdock.workspaces.QInputDialog.getText", return_value=("Renamed", True)):
            dialog.rename_selected()
        self.assertEqual("Renamed", dialog.list.currentItem().text())
        dialog.delete_selected()
        self.assertEqual([], self.window.data["workspaces"])
        self.assertEqual(2, self.window.tabs.count())
        self.assertFalse(dialog.open_button.isEnabled())
        dialog.deleteLater()

    def test_saved_workspaces_survive_export_import_and_recovery(self):
        self.assertTrue(self.window.save_workspace("Project", [0]))
        saved = copy.deepcopy(self.window.data["workspaces"])
        export = Path(self.temp.name) / "export.json"
        with patch("bashdock.app.QFileDialog.getSaveFileName", return_value=(str(export), "")):
            self.window.export_settings()
        self.assertTrue(self.window.store_workspaces([]))
        self.window.import_settings(path=export)
        self.assertEqual(saved, self.window.data["workspaces"])
        self.assertTrue(self.window.store_workspaces([]))
        self.window.restore_backup()
        self.assertEqual(saved, self.window.data["workspaces"])

    def test_export_includes_unsaved_workspace_without_changing_live_sessions(self):
        tab = self.window.current_tab()
        self.ready(tab)
        tab.data["name"] = "Unsaved name"
        target = Path(self.temp.name) / "export.json"
        original = self.path.read_bytes()
        with patch("bashdock.app.QFileDialog.getSaveFileName", return_value=(str(target), "")):
            self.window.export_settings()
        self.assertEqual("Unsaved name", config.read(target)["tabs"][0]["name"])
        self.assertEqual(original, self.path.read_bytes())
        self.assertFalse(config.backup_path(target).exists())
        self.assertEqual(0, tab.terminal.stops)

    def test_import_restores_workspace_and_archives_live_settings_before_stopping_shells(self):
        tab = self.window.current_tab()
        self.ready(tab)
        tab.data["name"] = "Unsaved previous workspace"
        imported = config.defaults()
        imported["bash_path"] = str(self.bash)
        imported["tabs"] = [config.default_tab("Imported one"), config.default_tab("Imported two")]
        imported["active_tab"] = 1
        imported["terminal"]["font_size"] = 22
        imported["confirm_on_exit"] = False
        target = Path(self.temp.name) / "export.json"
        config.save(imported, target, backup=False)
        self.window.import_settings(path=target)
        self.assertEqual(1, tab.terminal.stops)
        self.assertEqual(2, self.window.tabs.count())
        self.assertEqual("Imported two", self.window.current_tab().data["name"])
        self.assertEqual(22, self.window.current_tab().terminal.preferences["font_size"])
        self.assertFalse(self.window.confirm_exit_action.isChecked())
        self.assertEqual(imported, config.read(self.path))
        archives = list((self.path.parent / "backups").glob("settings-before-import-*.json"))
        self.assertEqual(1, len(archives))
        self.assertEqual("Unsaved previous workspace", config.read(archives[0])["tabs"][0]["name"])

    def test_cancelled_or_invalid_import_keeps_settings_and_shells(self):
        tab = self.window.current_tab()
        self.ready(tab)
        original = self.path.read_bytes()
        with patch("bashdock.app.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.window.import_settings(path=self.path)
        target = Path(self.temp.name) / "invalid.json"
        target.write_text('{"version": 999}', encoding="utf-8")
        with patch("bashdock.app.QMessageBox.warning") as warning:
            self.window.import_settings(path=target)
            self.window.import_settings(path=target.parent / "missing.json")
        self.assertEqual(2, warning.call_count)
        self.assertEqual(0, tab.terminal.stops)
        self.assertEqual(original, self.path.read_bytes())
        self.assertFalse((self.path.parent / "backups").exists())

    def test_failed_import_write_keeps_existing_shells_and_workspace(self):
        tab = self.window.current_tab()
        self.ready(tab)
        original = self.path.read_bytes()
        real_save = config.save
        for fail_archive in (True, False):
            def fail_save(data, path=None, **kwargs):
                if fail_archive or path is None:
                    raise PermissionError("locked")
                real_save(data, path, **kwargs)

            with patch("bashdock.config.save", side_effect=fail_save), \
                    patch("bashdock.app.QMessageBox.warning") as warning:
                self.assertFalse(self.window.replace_workspace(config.defaults(), "Import settings"))
            warning.assert_called_once()
            self.assertIs(tab, self.window.current_tab())
            self.assertEqual(0, tab.terminal.stops)
            self.assertEqual(original, self.path.read_bytes())

    def test_startup_recovery_restores_backup_and_preserves_damaged_file(self):
        from PySide6.QtCore import QTimer

        self.window.allow_save = False
        self.window.close()
        self.window.deleteLater()
        expected = config.read(config.backup_path(self.path))
        damaged = b'{"version": broken'
        self.path.write_bytes(damaged)
        self.window = MainWindow(terminal_factory=FakeTerminal)
        self.assertFalse(self.window.allow_save)

        def choose_restore():
            dialog = self.app.activeModalWidget()
            self.assertEqual("Recover settings", dialog.windowTitle())
            next(b for b in dialog.buttons() if b.text() == "Restore backup…").click()

        QTimer.singleShot(0, choose_restore)
        self.app.processEvents()
        self.assertTrue(self.window.allow_save)
        self.assertEqual("", self.window.config_error)
        self.assertEqual(expected, config.read(self.path))
        archives = list((self.path.parent / "backups").glob("settings-damaged-*.json"))
        self.assertEqual([damaged], [p.read_bytes() for p in archives])

    def test_cancelled_recovery_does_not_overwrite_damaged_settings(self):
        from PySide6.QtCore import QTimer

        self.window.allow_save = False
        self.window.close()
        self.window.deleteLater()
        damaged = b'not json'
        self.path.write_bytes(damaged)
        self.window = MainWindow(terminal_factory=FakeTerminal)
        QTimer.singleShot(0, lambda: self.app.activeModalWidget().reject())
        self.app.processEvents()
        self.assertFalse(self.window.allow_save)
        self.assertFalse(self.window.persist())
        self.assertEqual(damaged, self.path.read_bytes())

    def test_start_fresh_without_backup_preserves_damaged_settings_and_resumes_saving(self):
        from PySide6.QtCore import QTimer

        self.window.allow_save = False
        self.window.close()
        self.window.deleteLater()
        config.backup_path(self.path).unlink()
        damaged = b'not json'
        self.path.write_bytes(damaged)
        self.window = MainWindow(terminal_factory=FakeTerminal)

        def choose_fresh():
            dialog = self.app.activeModalWidget()
            restore = next(b for b in dialog.buttons() if b.text() == "Restore backup…")
            self.assertFalse(restore.isEnabled())
            next(b for b in dialog.buttons() if b.text() == "Start fresh…").click()

        QTimer.singleShot(0, choose_fresh)
        self.app.processEvents()
        self.assertTrue(self.window.allow_save)
        self.assertEqual(config.defaults(), config.read(self.path))
        archives = list((self.path.parent / "backups").glob("settings-damaged-*.json"))
        self.assertEqual([damaged], [p.read_bytes() for p in archives])
        self.assertTrue(self.window.persist())

    def reopen_window(self):
        self.window.data["confirm_on_exit"] = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.window = MainWindow(terminal_factory=FakeTerminal)
        self.window.show()
        self.app.processEvents()

    def test_window_size_and_position_are_saved_automatically_and_restored(self):
        from PySide6.QtTest import QTest

        self.window.show()
        self.app.processEvents()
        self.window.resize(640, 480)
        self.window.move(30, 45)
        self.app.processEvents()
        expected_size, expected_pos = self.window.size(), self.window.pos()
        QTest.qWait(450)
        self.assertTrue(config.load(self.path)["window_geometry"])
        self.reopen_window()
        self.assertEqual(expected_size, self.window.size())
        self.assertEqual(expected_pos, self.window.pos())

    def test_maximized_window_remembers_normal_size_and_does_not_reopen_minimized(self):
        self.window.show()
        self.app.processEvents()
        self.window.resize(640, 480)
        self.window.move(30, 45)
        self.app.processEvents()
        normal_size = self.window.size()
        self.window.showMaximized()
        self.app.processEvents()
        self.reopen_window()
        self.assertTrue(self.window.isMaximized())
        self.window.showNormal()
        self.app.processEvents()
        self.assertEqual(normal_size, self.window.size())
        self.window.showMinimized()
        self.app.processEvents()
        self.reopen_window()
        self.assertFalse(self.window.isMinimized())
        self.assertEqual(normal_size, self.window.size())

    def test_damaged_geometry_does_not_prevent_workspace_restoration(self):
        data = config.load(self.path)
        data["tabs"][0]["name"] = "My workspace"
        for encoded in ("not base64!", "bm90IFF0IGdlb21ldHJ5", 123):
            self.window.allow_save = False
            self.window.close()
            self.window.deleteLater()
            data["window_geometry"] = encoded
            config.save(data, self.path)
            self.window = MainWindow(terminal_factory=FakeTerminal)
            self.assertEqual("", self.window.config_error)
            self.assertEqual("My workspace", self.window.current_tab().data["name"])
            self.assertEqual((1120, 760), (self.window.width(), self.window.height()))

    def test_missing_git_explains_setup_and_restart_detects_new_installation(self):
        tab = self.window.current_tab()
        self.window.data["bash_path"] = "C:/Removed Git/bin/bash.exe"
        with patch("bashdock.app.config.find_bash", return_value=""), \
                patch.object(self.window, "show_git_setup") as setup:
            self.ready(tab)
        setup.assert_called_once()
        self.assertEqual([], tab.terminal.starts)
        self.assertIn("Install Git for Windows", self.window.statusBar().currentMessage())
        self.assertIn("Manage → Restart shell", self.window.statusBar().currentMessage())
        with patch("bashdock.app.config.find_bash", return_value=str(self.bash)), \
                patch.object(self.window, "show_git_setup") as setup:
            self.window.restart()
        setup.assert_not_called()
        self.assertEqual([(str(self.bash), self.temp.name)], tab.terminal.starts)
        self.assertEqual(str(self.bash), self.window.data["bash_path"])
        self.assertEqual("", self.window.statusBar().currentMessage())

    def test_git_setup_offers_download_and_current_menu_instructions(self):
        from PySide6.QtCore import QTimer

        observed = []

        def download():
            dialog = self.app.activeModalWidget()
            observed.append((dialog.windowTitle(), dialog.text(), dialog.informativeText()))
            button = next(b for b in dialog.buttons() if b.text() == "Download Git for Windows")
            button.click()

        with patch("bashdock.app.QDesktopServices.openUrl") as open_url:
            QTimer.singleShot(0, download)
            self.window.show_git_setup()
        open_url.assert_called_once()
        self.assertEqual("https://gitforwindows.org/", open_url.call_args.args[0].toString())
        self.assertIn("Git for Windows required", observed[0][0])
        self.assertIn("Manage → Restart shell", observed[0][2])
        self.assertIn("Settings → Configure current tab", observed[0][2])

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
        with patch("bashdock.app.QInputDialog.getText", return_value=("Build & test", True)):
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
            restored.data["confirm_on_exit"] = False
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
        with patch("bashdock.app.SettingsDialog") as dialog:
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
        with patch("bashdock.app.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.window.close_tab(1)
        self.assertEqual(2, self.window.tabs.count())
        original = self.path.read_bytes()
        with patch("bashdock.config.save", side_effect=PermissionError("locked")):
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

    def test_dont_show_again_saves_preference_and_workspace_before_stopping(self):
        tab = self.window.current_tab()
        self.ready(tab)

        def accept_dialog(dialog):
            self.assertEqual("Don't show this again", dialog.checkBox().text())
            dialog.checkBox().setChecked(True)
            return QMessageBox.StandardButton.Yes

        with patch.object(QMessageBox, "exec", accept_dialog):
            self.assertTrue(self.window.close())
        saved = config.load(self.path)
        self.assertFalse(saved["confirm_on_exit"])
        self.assertEqual(tab.data, saved["tabs"][0])
        self.assertEqual(1, tab.terminal.stops)
        restored = MainWindow(terminal_factory=FakeTerminal)
        try:
            self.ready(restored.current_tab())
            with patch.object(restored, "confirm_quit") as confirm:
                self.assertTrue(restored.close())
                confirm.assert_not_called()
        finally:
            restored.allow_save = False
            restored.data["confirm_on_exit"] = False
            restored.close()
            restored.deleteLater()

    def test_cancelling_quit_does_not_change_preference_or_stop_shell(self):
        tab = self.window.current_tab()
        self.ready(tab)
        with patch.object(self.window, "confirm_quit", return_value=(False, True)):
            self.assertFalse(self.window.close())
        self.assertTrue(self.window.data["confirm_on_exit"])
        self.assertTrue(config.load(self.path)["confirm_on_exit"])
        self.assertEqual(0, tab.terminal.stops)

    def test_menu_setting_can_disable_and_reenable_confirmation(self):
        self.window.confirm_exit_action.setChecked(False)
        self.assertFalse(config.load(self.path)["confirm_on_exit"])
        self.window.confirm_exit_action.setChecked(True)
        self.assertTrue(config.load(self.path)["confirm_on_exit"])

    def test_terminal_preferences_save_apply_to_all_tabs_and_new_tabs_without_restart(self):
        self.window.new_tab()
        for index in range(self.window.tabs.count()):
            self.ready(self.window.tabs.widget(index))
        settings = copy.deepcopy(self.window.data["terminal"])
        settings.update(font_size=20, background="#223344", copy_on_select=True)
        with patch("bashdock.app.TerminalSettingsDialog") as dialog:
            dialog.return_value.exec.return_value = 1
            dialog.return_value.values.return_value = settings
            self.window.configure_terminal()
        self.assertEqual(settings, config.load(self.path)["terminal"])
        for index in range(self.window.tabs.count()):
            tab = self.window.tabs.widget(index)
            self.assertEqual(settings, tab.terminal.preferences)
            self.assertEqual(0, tab.terminal.stops)
            self.assertEqual(1, len(tab.terminal.starts))
        self.window.new_tab()
        self.assertEqual(settings, self.window.current_tab().terminal.preferences)

    def test_terminal_preferences_cancel_or_save_failure_leave_active_settings_intact(self):
        original = copy.deepcopy(self.window.data["terminal"])
        with patch("bashdock.app.TerminalSettingsDialog") as dialog:
            dialog.return_value.exec.return_value = 0
            self.window.configure_terminal()
            dialog.return_value.values.assert_not_called()
        with patch("bashdock.app.TerminalSettingsDialog") as dialog, \
                patch("bashdock.config.save", side_effect=PermissionError("locked")), \
                patch("bashdock.app.QMessageBox.warning"):
            dialog.return_value.exec.return_value = 1
            changed = dict(original, font_size=22)
            dialog.return_value.values.return_value = changed
            self.window.configure_terminal()
        self.assertEqual(original, self.window.data["terminal"])
        self.assertEqual(original, self.window.current_tab().terminal.preferences)
        self.assertEqual(original, config.load(self.path)["terminal"])

    def test_menus_group_actions_and_about_shows_current_version_and_repository(self):
        from PySide6.QtWidgets import QDialog, QLabel
        from bashdock import __version__
        menus = {action.text(): action.menu() for action in self.window.menuBar().actions()}
        self.assertEqual(["Manage", "Settings", "Help"], list(menus))
        manage = menus["Manage"].actions()
        self.assertEqual(["New tab", "Rename tab…", "Close tab", "Workspaces…", "", "Open external shell",
                          "Restart shell…", "Interrupt (Ctrl+C)"], [a.text() for a in manage])
        self.assertTrue(manage[4].isSeparator())
        self.assertEqual("Ctrl+Shift+T", manage[0].shortcut().toString())
        self.assertEqual("Ctrl+Shift+W", manage[2].shortcut().toString())
        self.assertIn(self.window.confirm_exit_action, menus["Settings"].actions())
        settings_labels = [a.text() for a in menus["Settings"].actions()]
        for label in ("Export settings…", "Import settings…", "Restore automatic backup…"):
            self.assertIn(label, settings_labels)
        manage[0].trigger()
        self.assertEqual(2, self.window.tabs.count())
        with patch("bashdock.app.QDialog.exec", return_value=0) as show:
            menus["Help"].actions()[0].trigger()
            show.assert_called_once()
            dialog = next(d for d in self.window.findChildren(QDialog) if d.windowTitle() == "About BashDock")
            labels = dialog.findChildren(QLabel)
            self.assertTrue(any(f"Version {__version__}" in label.text() for label in labels))
            self.assertTrue(any(not label.pixmap().isNull() for label in labels))
            link = next(label for label in labels if 'href="https://github.com/chrisbokitch/bashdock"' in label.text())
            self.assertTrue(link.openExternalLinks())

    def test_save_failure_during_opt_out_keeps_shell_and_original_preference(self):
        tab = self.window.current_tab()
        self.ready(tab)
        with patch.object(self.window, "confirm_quit", return_value=(True, True)), \
                patch("bashdock.config.save", side_effect=PermissionError("locked")), \
                patch("bashdock.app.QMessageBox.warning"):
            self.assertFalse(self.window.close())
        self.assertTrue(self.window.data["confirm_on_exit"])
        self.assertTrue(self.window.confirm_exit_action.isChecked())
        self.assertEqual(0, tab.terminal.stops)

    def test_footer_keeps_version_visible_when_status_changes(self):
        from bashdock import __version__
        self.window.show()
        self.app.processEvents()
        footer = self.window.statusBar()
        self.window.show_status(self.window.current_tab(), "Test status message")
        self.assertEqual("Test status message", footer.currentMessage())
        self.assertEqual(f"v{__version__}", footer.version_label.text())
        self.assertTrue(footer.version_label.isVisible())
        footer.clearMessage()
        self.assertEqual("", footer.currentMessage())
        self.assertTrue(footer.version_label.isVisible())

    def test_new_tab_button_is_not_squeezed_by_corner_padding(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QPushButton
        self.window.show()
        for width in (1120, 600):
            self.window.resize(width, 760)
            for _ in range(4):
                self.app.processEvents()
            button = next(b for b in self.window.findChildren(QPushButton) if b.text() == "+ New tab")
            self.assertGreaterEqual(button.height(), button.sizeHint().height())
            self.assertEqual(3, button.parentWidget().height() - button.geometry().bottom() - 1)
            bar = self.window.tabs.tabBar()
            tab_bottom = bar.mapTo(self.window, QPoint(0, bar.tabRect(0).bottom() + 1)).y()
            shell_top = self.window.current_tab().terminal.mapTo(self.window, QPoint(0, 0)).y()
            self.assertEqual(3, shell_top - tab_bottom)

    def test_tab_close_icons_stay_in_place_when_switching_tabs(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QTabBar
        self.window.new_tab()
        self.window.show()
        for width in (1120, 600):
            self.window.resize(width, 760)
            for _ in range(4):
                self.app.processEvents()
            bar = self.window.tabs.tabBar()

            def positions():
                return [bar.tabButton(i, QTabBar.ButtonPosition.RightSide).pos() - bar.tabRect(i).topLeft()
                        for i in range(bar.count())]

            expected = positions()
            for index in range(bar.count()):
                visible_tab = bar.tabRect(index).adjusted(0, bar.top_inset, 0, 0)
                close = bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
                self.assertLessEqual(abs(close.geometry().center().y() - visible_tab.center().y()), 1)
            for index in (0, 1, 0, 1):
                rect = bar.tabRect(index)
                QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=QPoint(rect.left() + 15, rect.bottom() - 8))
                self.assertEqual(index, self.window.tabs.currentIndex())
                self.assertEqual(expected, positions())
                self.app.processEvents()
                self.assertEqual(expected, positions())
            self.window.tabs.setCurrentIndex(0)
            self.assertEqual(expected, positions())

    def test_cancelled_tab_rename_does_not_leave_tab_dragging_on_hover(self):
        from PySide6.QtCore import QPoint, Qt, QTimer
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QTabBar, QInputDialog
        self.window.new_tab()
        self.window.show()
        for _ in range(4):
            self.app.processEvents()
        bar = self.window.tabs.tabBar()

        def geometry():
            return [(bar.tabRect(i).getRect(),
                     bar.tabButton(i, QTabBar.ButtonPosition.RightSide).geometry().getRect())
                    for i in range(bar.count())]

        expected = geometry()
        names = [self.window.tabs.tabText(i) for i in range(bar.count())]
        cancelled = []

        def cancel_dialog():
            dialog = next(d for d in self.window.findChildren(QInputDialog) if d.isVisible())
            cancelled.append(True)
            dialog.reject()

        QTimer.singleShot(25, cancel_dialog)
        QTest.mouseDClick(bar, Qt.MouseButton.LeftButton,
                         pos=QPoint(20, bar.tabRect(0).bottom() - 8))
        self.assertEqual([True], cancelled)
        for index in (0, 1, 0, 1):
            QTest.mouseMove(bar, bar.tabRect(index).center())
            self.app.processEvents()
            self.assertEqual(expected, geometry())
        self.assertEqual(names, [self.window.tabs.tabText(i) for i in range(bar.count())])

    def test_external_menu_uses_active_shell_and_remembered_directory_without_stopping_it(self):
        self.window.new_tab()
        tab = self.window.current_tab()
        self.ready(tab)
        tab.data["current_folder"] = self.temp.name + "/Project with spaces"
        # Changing the shared setting must not change the running tab's shell.
        self.window.data["bash_path"] = "C:/Other Git/bin/bash.exe"
        manage = next(a.menu() for a in self.window.menuBar().actions() if a.text() == "Manage")
        external = next(a for a in manage.actions() if a.text() == "Open external shell")
        with patch("bashdock.app.open_external") as launch:
            external.trigger()
        launch.assert_called_once_with(str(self.bash), tab.data["current_folder"])
        self.assertEqual(0, tab.terminal.stops)
        self.assertIsNotNone(tab.terminal.process)
        with patch("bashdock.app.open_external", side_effect=OSError("launch failed")), \
                patch("bashdock.app.QMessageBox.warning") as warning:
            external.trigger()
        warning.assert_called_once()
        self.assertIn("launch failed", self.window.statusBar().currentMessage())
