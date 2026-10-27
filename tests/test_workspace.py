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
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox, QPushButton
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
        self.window.new_tab()
        existing = self.window.current_tab()
        self.ready(existing)
        self.window.close_tab(0)
        self.window.data["terminal"]["font_size"] = 23
        self.assertTrue(self.window.open_workspace(0))
        opened = self.window.current_tab()
        self.assertEqual(2, self.window.tabs.count())
        self.assertEqual(0, existing.terminal.stops)
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
        self.window.new_tab()
        self.window.close_tab(0)
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

    def test_reopening_overlapping_workspaces_only_adds_missing_ids_and_focuses_existing_active_tab(self):
        first = self.window.current_tab()
        self.ready(first)
        first_id = first.data["id"]
        self.window.new_tab()
        second = self.window.current_tab()
        second_id = second.data["id"]
        self.window.tabs.setCurrentIndex(0)
        self.assertTrue(self.window.save_workspace("Shared project", [0, 1]))
        self.window.close_tab(1)
        with patch("bashdock.app.QInputDialog.getText", return_value=("Renamed live tab", True)):
            self.window.rename_tab(0)
        first.data["buttons"][0]["command"] = "live edit"
        self.assertTrue(self.window.open_workspace(0))
        self.assertEqual(2, self.window.tabs.count())
        self.assertIs(first, self.window.current_tab())
        self.assertEqual(first_id, first.data["id"])
        self.assertEqual(second_id, self.window.tabs.widget(1).data["id"])
        self.assertEqual("Renamed live tab", first.data["name"])
        self.assertEqual("live edit", first.data["buttons"][0]["command"])
        self.assertEqual(0, first.terminal.stops)
        self.assertTrue(self.window.save_workspace("Overlapping project", [0, 1]))
        self.assertTrue(self.window.open_workspace(1))
        self.assertTrue(self.window.open_workspace(0))
        self.assertEqual(2, self.window.tabs.count())
        self.assertEqual(1, len(first.terminal.starts))
        self.assertEqual(0, first.terminal.stops)
        self.assertEqual([], first.terminal.commands)

    def test_same_name_tabs_have_distinct_ids_and_configure_preserves_identity(self):
        first = self.window.current_tab()
        identity = first.data["id"]
        self.window.new_tab()
        second = self.window.current_tab()
        second.data["name"] = first.data["name"]
        self.assertNotEqual(identity, second.data["id"])
        self.assertTrue(self.window.save_workspace("Both tabs", [0, 1]))
        self.window.tabs.setCurrentIndex(0)
        values = copy.deepcopy(first.data)
        del values["id"]
        values.update(name="Configured name", bash_path=str(self.bash))
        with patch("bashdock.app.SettingsDialog") as dialog:
            dialog.return_value.exec.return_value = 1
            dialog.return_value.result_data = values
            self.window.configure()
        self.assertEqual(identity, first.data["id"])
        self.assertTrue(self.window.open_workspace(0))
        self.assertEqual(2, self.window.tabs.count())
        self.assertEqual(identity, config.read(self.path)["tabs"][0]["id"])

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
        restored = config.read(self.path)
        expected = config.defaults()
        expected["tabs"][0]["id"] = restored["tabs"][0]["id"]
        self.assertEqual(expected, restored)
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
        self.assertIs(first.layout().itemAt(0).widget(), first.top_border)
        self.assertIs(first.layout().itemAt(1).widget(), first.terminal)
        self.assertIsNotNone(first.layout().itemAt(2).layout())
        for tab in (first, second):
            configure = tab.findChild(QPushButton, 'configureTab')
            self.assertEqual('', configure.text())
            self.assertEqual('Configure tab…', configure.toolTip())
            self.assertEqual('Configure tab…', configure.accessibleName())
            self.assertFalse(configure.icon().pixmap(18, 18).isNull())
            self.assertEqual(36, configure.width())
            with patch.object(self.window, 'configure') as open_settings:
                configure.click()
                open_settings.assert_called_once_with(tab)

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

    def test_new_tab_button_creates_independent_profile_in_active_directory_and_autosaves(self):
        from PySide6.QtTest import QTest

        first = self.window.current_tab()
        self.ready(first)
        folder = Path(self.temp.name) / 'Project with spaces'
        folder.mkdir()
        first.terminal.directory_changed.emit(str(folder))
        self.window.show()
        self.app.processEvents()
        self.window.findChild(QPushButton, 'newTab').click()
        second = self.window.current_tab()
        self.assertEqual(2, self.window.tabs.count())
        self.assertIsNot(first, second)
        self.assertNotEqual(first.data['id'], second.data['id'])
        self.assertEqual('Git Bash 2', self.window.tabs.tabText(1))
        self.ready(second)
        self.assertEqual([(str(self.bash), str(folder))], second.terminal.starts)
        self.assertEqual(0, first.terminal.stops)
        second.data['buttons'][0]['label'] = 'Independent'
        self.assertNotEqual('Independent', first.data['buttons'][0]['label'])
        # Exercise the real debounce timer, rather than forcing persist().
        QTest.qWait(500)
        saved = config.read(self.path)
        self.assertEqual(1, saved['active_tab'])
        self.assertEqual([first.data, second.data], saved['tabs'])

    def test_tab_rename_dialog_accept_cancel_and_blank_preserve_saved_identity(self):
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QInputDialog

        self.window.show()
        tab = self.window.current_tab()
        self.ready(tab)
        identity = tab.data['id']
        for text, accepted, expected in (
                ('  Build & test  ', True, 'Build & test'),
                ('Discard this name', False, 'Build & test'),
                ('   ', True, 'Build & test')):
            with self.subTest(text=text, accepted=accepted):
                before = copy.deepcopy(tab.data)
                observed = []

                def finish_dialog():
                    dialog = next(d for d in self.window.findChildren(QInputDialog) if d.isVisible())
                    observed.append(dialog.textValue())
                    dialog.setTextValue(text)
                    if accepted:
                        dialog.accept()
                    else:
                        dialog.reject()

                QTimer.singleShot(25, finish_dialog)
                bar = self.window.tabs.tabBar()
                self.app.processEvents()
                QTest.mouseDClick(bar, Qt.MouseButton.LeftButton,
                                 pos=bar.tabRect(0).center())
                self.assertEqual([before['name']], observed)
                self.assertEqual(expected, self.window.tabs.tabText(0))
                self.assertEqual(dict(before, name=expected), tab.data)
                self.assertEqual(identity, tab.data['id'])
                self.assertEqual(0, tab.terminal.stops)
                QTest.qWait(500)
                self.assertEqual(tab.data, config.read(self.path)['tabs'][0])

    def test_reordered_tab_close_button_cancels_then_closes_its_own_shell_and_autosaves(self):
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QTabBar, QToolButton

        first = self.window.current_tab()
        self.ready(first)
        self.window.new_tab()
        second = self.window.current_tab()
        self.ready(second)
        self.window.new_tab()
        third = self.window.current_tab()
        self.ready(third)
        self.window.show()
        bar = self.window.tabs.tabBar()
        # Use Qt's move operation: tabMoved must save the new visual order,
        # retain active widget identity, and keep close callbacks bound to tabs.
        bar.moveTab(0, 2)
        QTest.qWait(500)
        saved = config.read(self.path)
        self.assertEqual([second.data, third.data, first.data], saved['tabs'])
        self.assertEqual(1, saved['active_tab'])
        self.assertIs(third, self.window.current_tab())
        close = bar.tabButton(2, QTabBar.ButtonPosition.RightSide).findChild(QToolButton, 'tabClose')
        original = self.path.read_bytes()
        with patch('bashdock.app.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            close.click()
        QTest.qWait(500)
        self.assertEqual(original, self.path.read_bytes())
        self.assertEqual(3, self.window.tabs.count())
        self.assertEqual([0, 0, 0], [t.terminal.stops for t in (first, second, third)])
        close.click()
        QTest.qWait(500)
        self.assertEqual([1, 0, 0], [t.terminal.stops for t in (first, second, third)])
        self.assertIs(third, self.window.current_tab())
        saved = config.read(self.path)
        self.assertEqual([second.data, third.data], saved['tabs'])
        self.assertEqual(1, saved['active_tab'])

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

    def test_dialog_native_path_display_and_browse_preserve_remembered_directory(self):
        from PySide6.QtCore import QDir
        startup = Path(self.temp.name)
        remembered = startup / 'remembered folder'
        remembered.mkdir()
        original = dict(self.window.current_tab().data, bash_path=self.bash.as_posix(),
                        startup_folder=startup.as_posix(), current_folder=str(remembered))
        dialog = SettingsDialog(original, self.window)
        try:
            self.assertEqual(QDir.toNativeSeparators(self.bash.as_posix()), dialog.bash.text())
            self.assertEqual(QDir.toNativeSeparators(startup.as_posix()), dialog.folder.text())
            with patch('bashdock.app.QFileDialog.getOpenFileName', return_value=(self.bash.as_posix(), '')):
                dialog.browse(dialog.bash, False)
            with patch('bashdock.app.QFileDialog.getExistingDirectory', return_value=startup.as_posix()):
                dialog.browse(dialog.folder, True)
            self.assertEqual(QDir.toNativeSeparators(self.bash.as_posix()), dialog.bash.text())
            self.assertEqual(QDir.toNativeSeparators(startup.as_posix()), dialog.folder.text())
            dialog.commit()
            self.assertEqual(str(remembered), dialog.result_data['current_folder'])
            self.assertEqual(dialog.bash.text(), dialog.result_data['bash_path'])
            self.assertEqual(dialog.folder.text(), dialog.result_data['startup_folder'])
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

    def test_custom_terminal_settings_apply_to_one_tab_and_defaults_only_update_inheriting_tabs(self):
        first = self.window.current_tab()
        self.ready(first)
        self.window.new_tab()
        second = self.window.current_tab()
        self.ready(second)
        preset = dict(self.window.data["terminal"], background="#331122", font_size=21)
        result = dict(first.data, bash_path=str(self.bash), terminal=preset)
        with patch("bashdock.app.SettingsDialog") as dialog:
            dialog.return_value.exec.return_value = 1
            dialog.return_value.result_data = result
            self.window.configure(first)
        self.assertEqual(preset, first.terminal.preferences)
        self.assertNotEqual(preset, second.terminal.preferences)
        defaults = dict(self.window.data["terminal"], background="#112233", font_size=25)
        with patch("bashdock.app.TerminalSettingsDialog") as dialog:
            dialog.return_value.exec.return_value = 1
            dialog.return_value.values.return_value = defaults
            self.window.configure_terminal()
        self.assertEqual(preset, first.terminal.preferences)
        self.assertEqual(defaults, second.terminal.preferences)
        self.assertEqual(0, first.terminal.stops)
        self.assertEqual(0, second.terminal.stops)
        self.window.new_tab()
        self.assertEqual(defaults, self.window.current_tab().terminal.preferences)
        result["terminal"] = None
        with patch("bashdock.app.SettingsDialog") as dialog:
            dialog.return_value.exec.return_value = 1
            dialog.return_value.result_data = result
            self.window.configure(first)
        self.assertEqual(defaults, first.terminal.preferences)
        self.assertIsNone(config.read(self.path)["tabs"][0]["terminal"])
        self.assertEqual(0, first.terminal.stops)

    def test_nested_terminal_editor_stages_override_until_configure_tab_is_saved(self):
        from bashdock.terminal_settings import TerminalSettingsDialog

        tab = self.window.current_tab()
        self.ready(tab)
        original = copy.deepcopy(tab.data)
        editor = SettingsDialog(dict(tab.data, bash_path=str(self.bash)), self.window,
                                terminal_defaults=self.window.data["terminal"])

        def choose_custom(dialog):
            self.assertTrue(dialog.use_defaults.isChecked())
            dialog.use_defaults.setChecked(False)
            dialog.set_color("background", "#331122")
            return 1

        with patch.object(TerminalSettingsDialog, "exec", choose_custom):
            editor.configure_terminal()
        self.assertEqual("#331122", editor.terminal_override["background"])
        self.assertEqual(original, tab.data)
        self.assertEqual(self.window.data["terminal"], tab.terminal.preferences)
        with patch("bashdock.app.SettingsDialog", return_value=editor), \
                patch.object(editor, "exec", return_value=0):
            self.window.configure(tab)
        self.assertEqual(original, tab.data)
        self.assertEqual(0, tab.terminal.stops)

    def test_failed_custom_terminal_save_keeps_running_appearance_and_preferences(self):
        tab = self.window.current_tab()
        self.ready(tab)
        original = copy.deepcopy(tab.data)
        preferences = copy.deepcopy(tab.terminal.preferences)
        result = dict(tab.data, bash_path=str(self.bash), terminal=dict(preferences, background="#331122"))
        with patch("bashdock.app.SettingsDialog") as dialog, \
                patch("bashdock.config.save", side_effect=PermissionError("locked")), \
                patch("bashdock.app.QMessageBox.warning"):
            dialog.return_value.exec.return_value = 1
            dialog.return_value.result_data = result
            self.window.configure(tab)
        self.assertEqual(original, tab.data)
        self.assertEqual(preferences, tab.terminal.preferences)
        self.assertEqual(0, tab.terminal.stops)

    def test_custom_terminal_presets_survive_workspaces_exports_and_restoration(self):
        tab = self.window.current_tab()
        preset = dict(self.window.data["terminal"], background="#331122", font_size=21)
        tab.data["terminal"] = preset
        self.assertTrue(self.window.save_workspace("Server", [0]))
        self.window.new_tab()
        self.window.close_tab(0)
        self.assertTrue(self.window.open_workspace(0))
        self.assertEqual(preset, self.window.current_tab().terminal.preferences)
        export = Path(self.temp.name) / "export.json"
        with patch("bashdock.app.QFileDialog.getSaveFileName", return_value=(str(export), "")):
            self.window.export_settings()
        self.window.import_settings(path=export)
        self.assertEqual(preset, self.window.current_tab().terminal.preferences)
        self.assertEqual(preset, self.window.data["workspaces"][0]["tabs"][0]["terminal"])
        self.assertEqual(preset, config.read(self.path)["tabs"][1]["terminal"])

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

    def test_inactive_tab_tints_follow_tab_identity_defaults_and_hover(self):
        from PySide6.QtCore import QEvent, QPoint, QPointF
        from PySide6.QtGui import QColor, QHoverEvent
        from PySide6.QtWidgets import QStyle, QStyleOptionTab
        self.window.show()
        first = self.window.current_tab()
        profile = config.default_tab('Server')
        profile['terminal'] = dict(self.window.data['terminal'], background='#341527', foreground='#f7ce63')
        server = self.window.add_tab(profile)
        self.window.new_tab()
        third = self.window.current_tab()
        bar = self.window.tabs.tabBar()

        def assert_surface(tab, color, *, hovered=None):
            self.app.processEvents()
            # QTest.mouseMove uses the desktop pointer on native Windows. If
            # another window owns it, Qt may receive no hover or an unrelated
            # leave. Deliver the real Qt hover events without desktop focus.
            point = (bar.tabRect(self.window.tabs.indexOf(hovered)).center()
                     if hovered is not None else QPoint(-1, -1))
            event_type = QEvent.Type.HoverMove if hovered is not None else QEvent.Type.HoverLeave
            self.app.sendEvent(bar, QHoverEvent(event_type, QPointF(point),
                               QPointF(bar.mapToGlobal(point)), QPointF(-1, -1)))
            index = self.window.tabs.indexOf(tab)
            option = QStyleOptionTab()
            bar.initStyleOption(option, index)
            self.assertEqual(tab is hovered, bool(option.state & QStyle.StateFlag.State_MouseOver))
            rect = bar.tabRect(index)
            image = bar.grab().toImage()
            ratio = image.devicePixelRatio()
            actual = image.pixelColor(int((rect.left() + 6) * ratio), int((rect.bottom() - 5) * ratio))
            self.assertEqual(QColor(color), actual)

        assert_surface(server, '#402334')
        assert_surface(first, '#1e222a')
        assert_surface(server, '#503645', hovered=server)
        assert_surface(first, '#1e222a', hovered=server)
        assert_surface(server, '#402334')
        bar.moveTab(self.window.tabs.indexOf(server), 0)
        assert_surface(server, '#402334')
        changed = dict(self.window.data['terminal'], background='#223344')
        with patch('bashdock.app.TerminalSettingsDialog') as dialog:
            dialog.return_value.exec.return_value = 1
            dialog.return_value.values.return_value = changed
            self.window.configure_terminal()
        assert_surface(first, '#2f3f4f')
        assert_surface(server, '#402334')
        self.window.close_tab(self.window.tabs.indexOf(first))
        assert_surface(server, '#402334')
        self.assertEqual(0, server.terminal.stops)
        self.assertEqual(0, third.terminal.stops)

    def test_shell_top_border_spans_the_shell_except_beneath_selected_tab(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QColor
        from bashdock import terminal_preferences
        self.window.show()
        first = self.window.current_tab()
        profile = config.default_tab('Server')
        profile['terminal'] = dict(self.window.data['terminal'], background='#341527')
        second = self.window.add_tab(profile)
        bar = self.window.tabs.tabBar()

        def inspect(selected, inactive, background, inactive_background):
            self.window.tabs.setCurrentWidget(selected)
            self.app.processEvents()
            border = selected.top_border
            image = border.grab().toImage()
            ratio = image.devicePixelRatio()
            self.assertEqual(selected.terminal.width(), border.width())
            def x_for(tab):
                center = bar.tabRect(self.window.tabs.indexOf(tab)).center()
                return border.mapFromGlobal(bar.mapToGlobal(center)).x()
            for x, color in ((x_for(selected), background), (x_for(inactive), '#3c4b60'),
                             (border.width() - 2, '#3c4b60')):
                self.assertEqual(QColor(color), image.pixelColor(int(x * ratio), 0))
            # Only the shell's rule remains: no second border on an inactive tab.
            tab_image = bar.grab().toImage()
            rect = bar.tabRect(self.window.tabs.indexOf(inactive))
            theme = terminal_preferences.effective(inactive.data, self.window.data['terminal'])
            hover = terminal_preferences.inactive_tab_colors(theme)['hover']
            self.assertIn(tab_image.pixelColor(int(rect.center().x() * ratio), int((rect.bottom() - 1) * ratio)),
                          (QColor(inactive_background), QColor(hover)))

        inspect(second, first, '#341527', '#1e222a')
        bar.moveTab(self.window.tabs.indexOf(second), 0)
        self.window.tabs.setTabText(self.window.tabs.indexOf(second), 'A much longer server tab name')
        inspect(second, first, '#341527', '#1e222a')
        inspect(first, second, '#10141c', '#402334')

    def test_selected_tab_meets_terminal_without_a_separator_or_layout_gap(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QColor
        self.window.show()
        tab = self.window.current_tab()
        tab.data['terminal'] = dict(self.window.data['terminal'], background='#341527')
        self.window.refresh_tab_colors()
        # Give the isolated fake terminal the same surface as the real web view.
        tab.terminal.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tab.terminal.setStyleSheet('background:#341527;')
        self.app.processEvents()
        bar = self.window.tabs.tabBar()
        rect = bar.tabRect(bar.currentIndex())
        bottom = bar.mapTo(self.window, rect.bottomLeft()).y()
        top = tab.terminal.mapTo(self.window, QPoint(0, 0)).y()
        border_top = tab.top_border.mapTo(self.window, QPoint(0, 0)).y()
        self.assertEqual(bottom + 1, border_top)
        self.assertEqual(border_top + 1, top)
        image = self.window.grab().toImage()
        ratio = image.devicePixelRatio()
        x = bar.mapTo(self.window, rect.center()).x()
        for y in range(int((bottom - 1) * ratio), int((top + 2) * ratio)):
            color = image.pixelColor(int(x * ratio), y)
            self.assertEqual(QColor('#341527'), color)

    def test_selected_tab_uses_effective_terminal_colors_on_switch_and_defaults_change(self):
        from PySide6.QtGui import QColor
        self.window.show()
        first = self.window.current_tab()
        custom = config.default_tab('Custom colors')
        custom['terminal'] = dict(self.window.data['terminal'], background='#341527', foreground='#f7ce63')
        second = self.window.add_tab(custom)
        bar = self.window.tabs.tabBar()

        def assert_colors(background, foreground):
            self.app.processEvents()
            image = bar.grab().toImage()
            ratio = image.devicePixelRatio()
            rect = bar.tabRect(bar.currentIndex())
            self.assertEqual(QColor(background), image.pixelColor(
                int((rect.left() + 6) * ratio), int((rect.bottom() - 4) * ratio)))
            name = rect.adjusted(8, bar.top_inset + 3, -30, -3)
            target = QColor(foreground)
            # LCD/subpixel font antialiasing can blend every glyph pixel.
            distance = min(sum(abs(a - b) for a, b in zip(image.pixelColor(x, y).getRgb()[:3],
                                                          target.getRgb()[:3]))
                           for x in range(int(name.left() * ratio), int(name.right() * ratio))
                           for y in range(int(name.top() * ratio), int(name.bottom() * ratio)))
            self.assertLess(distance, 60)

        self.window.tabs.setCurrentWidget(second)
        assert_colors('#341527', '#f7ce63')
        self.window.tabs.setCurrentWidget(first)
        assert_colors('#10141c', '#dde4ef')
        changed = dict(self.window.data['terminal'], background='#172c39', foreground='#e5faf7')
        with patch('bashdock.app.TerminalSettingsDialog') as dialog:
            dialog.return_value.exec.return_value = 1
            dialog.return_value.values.return_value = changed
            self.window.configure_terminal()
        assert_colors('#172c39', '#e5faf7')
        self.window.tabs.setCurrentWidget(second)
        assert_colors('#341527', '#f7ce63')
        self.assertEqual(0, first.terminal.stops)
        self.assertEqual(0, second.terminal.stops)

    def test_checkable_menu_preserves_text_alignment_and_displays_tick_in_padding(self):
        from bashdock.app import PopupMenu
        from PySide6.QtCore import QPoint
        images = []
        for checkable in (False, True):
            menu = PopupMenu('Alignment', self.window)
            action = menu.addAction('Identical menu label')
            action.setCheckable(checkable)
            action.setChecked(checkable)
            menu.popup(QPoint(20, 20))
            self.app.processEvents()
            images.append(menu.grab().toImage())
            if checkable:
                action.trigger()
                self.assertFalse(action.isChecked())
            menu.hide()
            menu.deleteLater()
        plain, checked = images
        self.assertEqual(plain.size(), checked.size())
        ratio = plain.devicePixelRatio()
        # The label and right edge are identical; only the existing left pad differs.
        x = int(12 * ratio)
        self.assertEqual(plain.copy(x, 0, plain.width() - x, plain.height()),
                         checked.copy(x, 0, checked.width() - x, checked.height()))
        self.assertNotEqual(plain.copy(0, 0, x, plain.height()),
                            checked.copy(0, 0, x, checked.height()))

    def test_menu_popups_have_visible_surface_and_vertical_edge_padding(self):
        from PySide6.QtCore import QPoint
        for menu in (self.window.manage_menu, self.window.settings_menu,
                     self.window.help_menu, self.window.workspaces_menu, self.window.updates_menu):
            with self.subTest(menu=menu.title()):
                menu.ensurePolished()
                flags_before = int(menu.windowFlags())
                menu.popup(QPoint(20, 20))
                self.app.processEvents()
                actions = [a for a in menu.actions() if a.isVisible()]
                first = menu.actionGeometry(actions[0])
                last = menu.actionGeometry(actions[-1])
                self.assertEqual(10, first.top())
                self.assertEqual(12, first.left())
                self.assertEqual(12, menu.width() - first.right() - 1)
                self.assertEqual(10, menu.height() - last.bottom() - 1)
                from PySide6.QtCore import Qt
                self.assertTrue(menu.windowFlags() & Qt.WindowType.NoDropShadowWindowHint,
                                f'popup flags before={flags_before:#x}, after={int(menu.windowFlags()):#x}, '
                                f'style={menu.style().objectName()}')
                self.assertTrue(menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
                image = menu.grab().toImage()
                self.assertEqual('#253144', image.pixelColor(menu.width() // 2, 3).name())
                # QWidget.grab() can include pixels outside the native window
                # mask, especially at fractional Windows scaling. The native
                # mask, in logical coordinates, determines visible corners.
                mask = menu.mask()
                self.assertEqual(menu.rect(), mask.boundingRect())
                for point in (menu.rect().topLeft(), menu.rect().topRight(),
                              menu.rect().bottomLeft(), menu.rect().bottomRight()):
                    self.assertFalse(mask.contains(point))
                self.assertTrue(mask.contains(menu.rect().center()))
                menu.hide()

    def test_popup_app_shadow_is_drawn_click_through_and_hidden_with_menu(self):
        from PySide6.QtCore import QPoint, Qt
        menu = self.window.manage_menu
        menu.popup(QPoint(40, 40))
        self.app.processEvents()
        shadow = self.window.menu_corners.shadows[menu]
        self.assertTrue(shadow.isVisible())
        self.assertIs(QApplication.activePopupWidget(), menu)
        self.assertTrue(shadow.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        self.assertTrue(shadow.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
        self.assertEqual(menu.width() + 16, shadow.width())
        self.assertEqual(menu.height() + 16, shadow.height())
        # Grab the shadow itself: pixels beyond the panel must be drawn, while
        # its centre stays transparent and cannot tint or obscure menu items.
        image = shadow.grab().toImage()
        ratio = image.devicePixelRatio()
        def alpha(x, y):
            return image.pixelColor(int(x * ratio), int(y * ratio)).alpha()
        self.assertEqual(0, alpha(shadow.width() // 2, shadow.height() // 2))
        self.assertGreater(alpha(shadow.width() // 2, shadow.height() - 5), 0)
        self.assertLess(alpha(shadow.width() // 2, shadow.height() - 5), 80)
        menu.hide()
        self.app.processEvents()
        self.assertFalse(shadow.isVisible())

    def test_popup_corner_mask_tracks_submenu_resizing_and_reopening(self):
        from PySide6.QtCore import QPoint
        menu = self.window.workspaces_menu
        for name in ('Short', 'A much longer workspace name that widens the submenu'):
            menu.addAction(name)
            menu.popup(QPoint(20, 20))
            self.app.processEvents()
            self.assertEqual(menu.rect(), menu.mask().boundingRect())
            self.assertFalse(menu.mask().contains(menu.rect().bottomRight()))
            self.assertTrue(menu.mask().contains(menu.rect().center()))
            menu.resize(menu.width() + 40, menu.height() + 20)
            self.app.processEvents()
            self.assertEqual(menu.rect(), menu.mask().boundingRect())
            self.assertFalse(menu.mask().contains(menu.rect().bottomRight()))
            menu.hide()

    def test_diagnostic_report_export_and_cancel(self):
        from bashdock.input_diagnostics import Recorder
        report = Path(self.temp.name) / 'diagnostics.json'
        recorder = Recorder()
        recorder.record('window_resize', width=900, height=600)
        with patch('bashdock.app.input_recorder', recorder), \
                patch('bashdock.app.QFileDialog.getSaveFileName', return_value=(str(report), '')):
            self.window.save_diagnostic_report()
        self.assertTrue(report.is_file())
        self.assertIn('window_resize', report.read_text())
        with patch('bashdock.app.input_recorder.save') as save, \
                patch('bashdock.app.QFileDialog.getSaveFileName', return_value=('', '')):
            self.window.save_diagnostic_report()
            save.assert_not_called()

    def test_menus_group_actions_and_about_shows_current_version_and_repository(self):
        from PySide6.QtWidgets import QDialog, QLabel
        from bashdock import __version__
        menus = {action.text(): action.menu() for action in self.window.menuBar().actions()}
        self.assertEqual(["Manage", "Settings", "Help"], list(menus))
        manage = menus["Manage"].actions()
        self.assertEqual(["New tab", "Rename tab…", "Close tab", "Workspaces", "", "Open external shell",
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
            self.assertEqual(['Check for updates…', 'Save diagnostic report…', '', 'About BashDock…'],
                             [a.text() for a in menus['Help'].actions()])
            self.assertTrue(menus['Help'].actions()[2].isSeparator())
            menus["Help"].actions()[3].trigger()
            show.assert_called_once()
            dialog = next(d for d in self.window.findChildren(QDialog) if d.windowTitle() == "About BashDock")
            labels = dialog.findChildren(QLabel)
            self.assertTrue(any(f"Version {__version__}" in label.text() for label in labels))
            self.assertTrue(any(not label.pixmap().isNull() for label in labels))
            link = next(label for label in labels if 'href="https://github.com/chrisbokitch/bashdock"' in label.text())
            self.assertTrue(link.openExternalLinks())

    def test_workspaces_submenu_configures_and_opens_current_saved_entries_without_duplicates(self):
        submenu = next(a.menu() for a in self.window.manage_menu.actions() if a.text() == "Workspaces")
        self.assertEqual(["Configure…"], [a.text() for a in submenu.actions()])
        with patch("bashdock.app.WorkspacesDialog") as dialog:
            submenu.actions()[0].trigger()
            dialog.return_value.exec.assert_called_once()
        first = self.window.current_tab()
        self.ready(first)
        self.assertTrue(self.window.save_workspace("App & Website", [0]))
        self.window.new_tab()
        second = self.window.current_tab()
        self.ready(second)
        self.assertTrue(self.window.save_workspace("CIDR", [1]))
        submenu.aboutToShow.emit()
        self.assertEqual(["Configure…", "", "App && Website", "CIDR"], [a.text() for a in submenu.actions()])
        self.assertTrue(submenu.actions()[1].isSeparator())
        submenu.actions()[2].trigger()
        self.assertIs(first, self.window.current_tab())
        submenu.actions()[3].trigger()
        self.assertIs(second, self.window.current_tab())
        self.window.close_tab(0)
        submenu.actions()[2].trigger()
        self.assertEqual(first.data["id"], self.window.current_tab().data["id"])
        self.assertEqual(2, self.window.tabs.count())
        self.assertEqual(0, second.terminal.stops)
        entries = copy.deepcopy(self.window.data["workspaces"])
        entries[0]["name"] = "Renamed"
        self.assertTrue(self.window.store_workspaces(entries))
        submenu.aboutToShow.emit()
        self.assertEqual("Renamed", submenu.actions()[2].text())
        self.assertTrue(self.window.store_workspaces([]))
        submenu.aboutToShow.emit()
        self.assertEqual(["Configure…"], [a.text() for a in submenu.actions()])

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

    def test_restoring_nonfirst_tab_keeps_command_buttons_inside_footer(self):
        from bashdock.app import CommandScrollArea

        self.window.new_tab()
        self.window.show()
        self.window.tabs.setCurrentIndex(1)
        for _ in range(12):
            self.app.processEvents()
        self.window.close()
        self.window = MainWindow(terminal_factory=FakeTerminal)
        self.window.show()
        for _ in range(12):
            self.app.processEvents()
        self.assertEqual(1, self.window.tabs.currentIndex())

        for long_labels in (False, True):
            first = self.window.tabs.widget(0)
            if long_labels:
                for button in first.command_buttons:
                    button.setText('A longer configured command button')
            for width in (1120, 600, 1120):
                self.window.resize(width, 760)
                for index in (1, 0, 1, 0):
                    self.window.tabs.setCurrentIndex(index)
                    for _ in range(12):
                        self.app.processEvents()
                    tab = self.window.current_tab()
                    scroll = tab.findChild(CommandScrollArea)
                    for button in tab.command_buttons:
                        with self.subTest(long_labels=long_labels, width=width, tab=index):
                            self.assertGreaterEqual(button.height(), button.sizeHint().height())
                            self.assertTrue(tab.bar.rect().contains(button.geometry()),
                                            f'{button.geometry()} outside {tab.bar.rect()}')
                            bottom = button.mapTo(scroll.viewport(), button.rect().bottomLeft()).y()
                            self.assertLess(bottom, scroll.viewport().height())

    def test_new_tab_button_is_not_squeezed_by_corner_padding(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QPushButton, QProxyStyle, QStyle, QStyleFactory

        class TabBaseStyle(QProxyStyle):
            def __init__(self, height):
                super().__init__(QStyleFactory.create("Fusion"))
                self.base_height = height

            def pixelMetric(self, metric, option=None, widget=None):
                if metric == QStyle.PixelMetric.PM_TabBarBaseHeight:
                    return self.base_height
                return super().pixelMetric(metric, option, widget)

        self.window.show()
        # Test the native style too, then exercise the metric variation that
        # reproduces the one-pixel squeeze even on a non-Windows test machine.
        styles = [None] + [TabBaseStyle(height) for height in (1, 2, 3)]
        for style in styles:
            if style is not None:
                style.setParent(self.window.tabs)
                self.window.tabs.setStyle(style)
                self.window.tabs.tabBar().update_tab_inset()
            for width in (1120, 600):
                with self.subTest(base_height=None if style is None else style.base_height, width=width):
                    self.window.resize(width, 760)
                    for _ in range(4):
                        self.app.processEvents()
                    button = self.window.findChild(QPushButton, "newTab")
                    self.assertGreaterEqual(button.height(), button.sizeHint().height())
                    self.assertEqual(3, button.parentWidget().height() - button.geometry().bottom() - 1)
                    bar = self.window.tabs.tabBar()
                    tab_bottom = bar.mapTo(self.window, QPoint(0, bar.tabRect(0).bottom() + 1)).y()
                    shell_top = self.window.current_tab().terminal.mapTo(self.window, QPoint(0, 0)).y()
                    self.assertEqual(1, shell_top - tab_bottom)

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

    def test_about_license_dialog_contains_complete_offline_license_and_notices(self):
        from PySide6.QtWidgets import QDialog, QPlainTextEdit, QTabWidget

        def inspect(dialog):
            self.assertIn('License and notices', dialog.windowTitle())
            tabs = dialog.findChild(QTabWidget)
            self.assertEqual(2, tabs.count())
            license_text = tabs.widget(0)
            self.assertIsInstance(license_text, QPlainTextEdit)
            self.assertTrue(license_text.isReadOnly())
            self.assertIn('GNU GENERAL PUBLIC LICENSE', license_text.toPlainText())
            self.assertGreater(len(license_text.toPlainText()), 30000)
            self.assertIn('Qt WebEngine / Chromium', tabs.widget(1).toPlainText())
            return 0

        with patch.object(QDialog, 'exec', inspect):
            self.window.show_licenses()

    def test_packaged_about_opens_the_bundled_notice_archive_offline(self):
        from PySide6.QtWidgets import QDialog, QPushButton
        from PySide6.QtCore import QUrl
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'third-party-licenses.zip'
            archive.write_bytes(b'archive fixture')
            def inspect(dialog):
                button = next(b for b in dialog.findChildren(QPushButton)
                              if b.text() == 'Open detailed notices…')
                button.click()
                return 0
            with patch('bashdock.app.sys.frozen', True, create=True), \
                    patch('bashdock.app.sys.executable', str(Path(temp) / 'bashdock.exe')), \
                    patch('bashdock.app.QDesktopServices.openUrl', return_value=True) as open_url, \
                    patch.object(QDialog, 'exec', inspect):
                self.window.show_licenses()
            open_url.assert_called_once_with(QUrl.fromLocalFile(str(archive)))

    def test_footer_update_notice_is_clickable_next_to_version_and_survives_status_messages(self):
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        footer = self.window.statusBar()
        self.window.show()
        footer.show_update('0.12.0')
        requested = []
        footer.update_requested.connect(lambda: requested.append(True))
        footer.showMessage('A shell status message')
        self.app.processEvents()
        self.assertEqual('Version 0.12.0 is ready — Restart to update', footer.update_button.text())
        self.assertTrue(footer.update_button.isVisible())
        self.assertGreaterEqual(footer.update_button.x(), footer.version_label.geometry().right())
        self.assertGreater(footer.message_label.x(), footer.update_button.x())
        QTest.mouseClick(footer.update_button, Qt.MouseButton.LeftButton)
        self.assertEqual([True], requested)
        footer.clearMessage()
        self.assertTrue(footer.update_button.isVisible())
        footer.show_update('0.14.0', local=True)
        self.assertEqual('Local build 0.14.0 is ready — Restart to update', footer.update_button.text())

    def test_local_update_confirmation_pins_the_build_even_if_newer_staging_finishes(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        chosen = SimpleNamespace(manifest={'version': '0.14.0', 'channel': 'local-development'})
        newer = SimpleNamespace(manifest={'version': '0.14.1', 'channel': 'local-development'})
        updater = Mock()
        updater.ready = chosen
        self.window.updater = updater
        def confirm(*args):
            self.assertIn('locally built BashDock 0.14.0', args[2])
            updater.ready = newer
            return QMessageBox.StandardButton.Yes
        with patch('bashdock.app.QMessageBox.question', side_effect=confirm), \
                patch.object(self.window, 'close', return_value=False):
            self.window.restart_for_update()
        self.assertIs(chosen, updater.install_choice)

    def test_update_restart_cancel_or_save_failure_does_not_stop_shells_or_launch_helper(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        tab = self.window.current_tab()
        self.ready(tab)
        updater = Mock()
        updater.ready = SimpleNamespace(manifest={'version': '0.12.0'})
        self.window.updater = updater
        with patch('bashdock.app.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            self.window.restart_for_update()
        updater.launch_install.assert_not_called()
        self.assertEqual(0, tab.terminal.stops)
        with patch.object(self.window, 'persist', return_value=False), patch('bashdock.app.QMessageBox.warning'):
            self.window.restart_for_update()
        updater.launch_install.assert_not_called()
        self.assertEqual(0, tab.terminal.stops)
        self.assertFalse(self.window.update_restart)

    def test_update_restart_keeps_quit_preference_and_launches_helper_before_closing_shells(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        tab = self.window.current_tab()
        self.ready(tab)
        self.window.data['confirm_on_exit'] = True
        updater = Mock()
        updater.ready = SimpleNamespace(manifest={'version': '0.12.0'})
        def launching():
            self.assertEqual(0, tab.terminal.stops)
            self.assertTrue(config.read(self.path)['confirm_on_exit'])
        updater.launch_install.side_effect = launching
        self.window.updater = updater
        with patch.object(self.window, 'confirm_quit', side_effect=AssertionError('update already confirmed')):
            self.window.restart_for_update()
        updater.launch_install.assert_called_once()
        self.assertEqual(1, tab.terminal.stops)
        self.assertTrue(self.window.data['confirm_on_exit'])
        self.window.updater = None

    def test_update_launch_failure_keeps_current_shell_and_ready_notice(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        tab = self.window.current_tab()
        self.ready(tab)
        updater = Mock()
        updater.ready = SimpleNamespace(manifest={'version': '0.12.0'})
        updater.launch_install.side_effect = OSError('folder not writable')
        self.window.updater = updater
        self.window.statusBar().show_update('0.12.0')
        with patch('bashdock.app.QMessageBox.warning'):
            self.window.restart_for_update()
        self.assertFalse(self.window.closing)
        self.assertFalse(self.window.update_restart)
        self.assertEqual(0, tab.terminal.stops)
        updater.cancel.assert_not_called()
        self.window.updater = None
