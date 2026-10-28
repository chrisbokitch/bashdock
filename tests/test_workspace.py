"""Exercise the real Qt tab UI with isolated fake terminal processes."""
import copy
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox, QPushButton
from bashdock import config, tab_icons
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
        self.focus_requests = 0

    def focus_terminal(self):
        self.focus_requests += 1
        self.setFocus()
        self.bridge.focus.emit()

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

    def test_command_presets_stage_append_replace_cancel_and_failed_save_without_shell_input(self):
        from PySide6.QtWidgets import QDialog
        from bashdock.preset_picker import PresetPicker
        from bashdock.command_presets import GROUPS
        from bashdock.command_editor import CommandEditor
        tab = self.window.current_tab()
        self.ready(tab)
        original = copy.deepcopy(tab.data)
        original_file = self.path.read_bytes()
        editor = SettingsDialog(dict(tab.data, bash_path=str(self.bash)), self.window)
        existing = [editor.row_data(row) for row in range(editor.table.rowCount())]
        def cancel(picker):
            picker.select_all.click()
            picker.reject()
            return picker.result()
        with patch.object(PresetPicker, 'exec', cancel):
            next(button for button in editor.findChildren(QPushButton) if button.text() == 'Presets…').click()
        self.assertEqual(existing, [editor.row_data(row) for row in range(editor.table.rowCount())])
        def append(picker):
            picker.groups.setCurrentRow(1)
            picker.select_all.click()
            picker.commit()
            return picker.result()
        with patch.object(PresetPicker, 'exec', append):
            editor.choose_presets()
        appended = [button.definition() for button in GROUPS[1].buttons]
        self.assertEqual(existing + appended, [editor.row_data(row) for row in range(editor.table.rowCount())])
        self.assertEqual(original, tab.data)
        self.assertEqual(original_file, self.path.read_bytes())
        editor.reject()
        self.assertIsNone(editor.result_data)
        editor.deleteLater()
        editor = SettingsDialog(dict(tab.data, bash_path=str(self.bash)), self.window)
        def replace(picker):
            picker.groups.setCurrentRow(1)
            picker.select_all.click()
            picker.replace.setChecked(True)
            picker.commit()
            return picker.result()
        with patch.object(PresetPicker, 'exec', replace):
            editor.choose_presets()
        self.assertEqual(appended, [editor.row_data(row) for row in range(editor.table.rowCount())])
        editor.table.selectRow(0)
        editor.move_row(1)
        self.assertEqual(appended[0], editor.row_data(1))
        def customize(inner):
            self.assertTrue(inner.confirm.isChecked())
            inner.label.setText('My recovery button')
            inner.confirmation_message.setText('Discard my unstaged edits?')
            inner.commit()
            return inner.result()
        with patch.object(CommandEditor, 'exec', customize):
            editor.edit_button()
        editor.commit()
        with patch('bashdock.app.SettingsDialog', return_value=editor), \
                patch.object(editor, 'exec', lambda: QDialog.DialogCode.Accepted), \
                patch('bashdock.app.config.save', side_effect=OSError('disk full')), \
                patch('bashdock.app.QMessageBox.warning'):
            self.window.configure(tab)
        self.assertEqual(original, tab.data)
        self.assertEqual(original_file, self.path.read_bytes())
        with patch('bashdock.app.SettingsDialog', return_value=editor), \
                patch.object(editor, 'exec', lambda: QDialog.DialogCode.Accepted):
            self.window.configure(tab)
        self.assertEqual('My recovery button', tab.data['buttons'][1]['label'])
        self.assertEqual('Discard my unstaged edits?', tab.data['buttons'][1]['confirmation_message'])
        self.assertEqual(tab.data['buttons'], config.read(self.path)['tabs'][0]['buttons'])
        self.assertEqual([], tab.terminal.commands)
        self.assertEqual(0, tab.terminal.stops)
        self.assertEqual(1, len(tab.terminal.starts))
        self.assertEqual(original['id'], tab.data['id'])
        editor.deleteLater()

    def test_command_presets_survive_saved_workspace_export_import_and_recovery_as_normal_buttons(self):
        from bashdock.command_presets import GROUPS
        from bashdock.preset_picker import PresetPicker
        tab = self.window.current_tab()
        self.ready(tab)
        picker = PresetPicker([])
        for group in range(len(GROUPS)):
            picker.groups.setCurrentRow(group)
            picker.select_all.click()
        picker.commit()
        tab.data['buttons'] = copy.deepcopy(picker.result_data['buttons'])
        tab.build_buttons()
        self.assertEqual(18, len(tab.command_buttons))
        self.assertTrue(self.window.save_workspace('Presets', [0]))
        export = Path(self.temp.name) / 'presets-export.json'
        with patch('bashdock.app.QFileDialog.getSaveFileName', return_value=(str(export), '')):
            self.window.export_settings()
        self.window.import_settings(path=export)
        expected = picker.result_data['buttons']
        self.assertEqual(expected, self.window.current_tab().data['buttons'])
        self.assertEqual(expected, self.window.data['workspaces'][0]['tabs'][0]['buttons'])
        config.save(self.window.snapshot(), self.path)
        self.assertEqual(expected, config.read(config.backup_path(self.path))['tabs'][0]['buttons'])
        self.assertTrue(self.window.open_workspace(0, replace=True))
        self.assertEqual(expected, self.window.current_tab().data['buttons'])
        self.assertEqual([], self.window.current_tab().terminal.commands)
        repeated = PresetPicker(expected)
        repeated.select_all.click()
        self.assertEqual(set(), repeated.selected)
        self.assertTrue(all('Already added' in repeated.entries.item(row).text() for row in range(4)))
        repeated.deleteLater()
        picker.deleteLater()

    def test_command_confirmation_cancel_default_and_accept_bind_to_reviewed_tab_once(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog
        from bashdock.command_confirmation import CommandConfirmation
        first = self.window.current_tab()
        self.ready(first)
        body = 'printf first\nprintf second'
        entry = {'label': 'Reviewed', 'command': body, 'confirm': True,
                 'confirmation_message': 'Run both lines?'}
        first.data['buttons'] = [entry]
        first.build_buttons()
        self.window.new_tab()
        second = self.window.current_tab()
        self.ready(second)
        self.window.tabs.setCurrentIndex(0)
        # Drive the actual modal Cancel, close and Run controls. No class-level
        # exec mock is used while PySide creates connections on the dialog.
        errors = []
        for action in ('cancel', 'close', 'run'):
            def respond(action=action):
                dialog = QApplication.activeModalWidget()
                try:
                    self.assertIsInstance(dialog, CommandConfirmation)
                    self.assertEqual([], first.terminal.commands)
                    self.assertEqual([], second.terminal.commands)
                    self.assertEqual(body, dialog.command.toPlainText())
                    # A nested invocation while confirmation is open is ignored.
                    first.run_button_command(entry)
                    self.window.tabs.setCurrentIndex(1)
                    if action == 'run':
                        first.data['buttons'][0]['command'] = 'changed while dialog was open'
                        dialog.run_button.click()
                    elif action == 'close':
                        dialog.close()
                    else:
                        dialog.cancel_button.click()
                except BaseException as error:
                    errors.append(error)
                    if isinstance(dialog, QDialog):
                        dialog.reject()
            QTimer.singleShot(0, respond)
            first.command_buttons[0].click()
            if errors:
                raise errors[0]
            self.assertFalse(first.command_confirmation_open)
            self.assertEqual([body] if action == 'run' else [], first.terminal.commands)
            self.assertEqual([], second.terminal.commands)

    def test_confirmation_acceptance_does_not_retarget_a_stopped_restarted_or_removed_tab(self):
        from PySide6.QtWidgets import QDialog
        from bashdock.command_confirmation import CommandConfirmation
        first = self.window.current_tab()
        self.ready(first)
        entry = {'label': 'Reviewed', 'command': 'echo reviewed', 'confirm': True}
        first.data['buttons'] = [entry]
        first.build_buttons()
        self.window.new_tab()
        for change in ('stop', 'restart', 'remove'):
            first.terminal.process = object()
            def accept(dialog):
                if change == 'stop':
                    first.terminal.process = None
                elif change == 'restart':
                    first.terminal.process = object()
                else:
                    self.window.tabs.removeTab(self.window.tabs.indexOf(first))
                return QDialog.DialogCode.Accepted
            with patch.object(CommandConfirmation, 'exec', accept):
                first.run_button_command(entry)
            self.assertEqual([], first.terminal.commands)
        first.deleteLater()

    def test_confirmation_edits_follow_reordering_and_outer_cancel_or_failed_save(self):
        from PySide6.QtWidgets import QDialog
        from bashdock.command_editor import CommandEditor
        tab = self.window.current_tab()
        self.ready(tab)
        original = copy.deepcopy(tab.data)
        original_file = self.path.read_bytes()
        editor = SettingsDialog(dict(tab.data, bash_path=str(self.bash)), self.window)
        editor.table.selectRow(0)
        def edit(inner):
            inner.confirm.setChecked(True)
            inner.confirmation_message.setText('Apply these changes?')
            inner.commit()
            return inner.result()
        with patch.object(CommandEditor, 'exec', edit):
            editor.edit_button()
        editor.move_row(1)
        self.assertTrue(editor.row_data(1)['confirm'])
        self.assertEqual('Apply these changes?', editor.row_data(1)['confirmation_message'])
        self.assertNotIn('confirm', editor.row_data(0))
        self.assertEqual(original, tab.data)
        editor.reject()
        self.assertIsNone(editor.result_data)
        editor.commit()
        with patch('bashdock.app.SettingsDialog', return_value=editor), \
                patch.object(editor, 'exec', lambda: QDialog.DialogCode.Accepted), \
                patch('bashdock.app.config.save', side_effect=OSError('disk full')), \
                patch('bashdock.app.QMessageBox.warning'):
            self.window.configure(tab)
        self.assertEqual(original, tab.data)
        self.assertEqual(original_file, self.path.read_bytes())
        with patch('bashdock.app.SettingsDialog', return_value=editor), \
                patch.object(editor, 'exec', lambda: QDialog.DialogCode.Accepted):
            self.window.configure(tab)
        self.assertTrue(tab.data['buttons'][1]['confirm'])
        self.assertEqual('Apply these changes?', config.read(self.path)['tabs'][0]['buttons'][1]['confirmation_message'])
        self.assertEqual([], tab.terminal.commands)
        self.assertEqual(0, tab.terminal.stops)
        editor.deleteLater()

    def test_multiline_editor_stages_cancels_reorders_and_saves_only_after_outer_save(self):
        from PySide6.QtWidgets import QDialog
        from bashdock.command_editor import CommandEditor
        tab = self.window.current_tab()
        self.ready(tab)
        original = copy.deepcopy(tab.data)
        original_file = self.path.read_bytes()
        body = '\n  printf "%s" "café 世界"\n\n\t# a comment\nprintf done\n'
        editor = SettingsDialog(dict(tab.data, bash_path=str(self.bash)), self.window)
        editor.table.selectRow(0)

        def accept(inner):
            self.assertIsInstance(inner, CommandEditor)
            inner.label.setText('Multiline')
            inner.command.setPlainText(body)
            inner.commit()
            return inner.result()

        with patch.object(CommandEditor, 'exec', lambda inner: QDialog.DialogCode.Rejected):
            editor.edit_button()
            editor.add_button()
        self.assertEqual(len(original['buttons']), editor.table.rowCount())
        self.assertEqual(original['buttons'][0]['command'], editor.table.item(0, 1).text())
        with patch.object(CommandEditor, 'exec', accept):
            editor.edit_button()
        self.assertEqual(body, editor.table.item(0, 1).text())
        self.assertEqual(body, editor.table.item(0, 1).toolTip())
        editor.move_row(1)
        self.assertEqual(body, editor.table.item(1, 1).text())
        self.assertEqual(original, tab.data)
        self.assertEqual(original_file, self.path.read_bytes())
        editor.reject()
        self.assertIsNone(editor.result_data)
        editor.deleteLater()

        editor = SettingsDialog(dict(tab.data, bash_path=str(self.bash)), self.window)
        with patch.object(CommandEditor, 'exec', accept):
            editor.add_button()
        editor.commit()
        expected = {'label': 'Multiline', 'command': body, 'confirm': False,
                    'confirmation_message': 'Are you sure?'}
        self.assertEqual(expected, editor.result_data['buttons'][-1])
        with patch('bashdock.app.SettingsDialog', return_value=editor), \
                patch.object(editor, 'exec', return_value=QDialog.DialogCode.Accepted), \
                patch('bashdock.app.config.save', side_effect=OSError('disk full')), \
                patch('bashdock.app.QMessageBox.warning'):
            self.window.configure(tab)
        self.assertEqual(original, tab.data)
        self.assertEqual(original_file, self.path.read_bytes())
        with patch('bashdock.app.SettingsDialog', return_value=editor), \
                patch.object(editor, 'exec', return_value=QDialog.DialogCode.Accepted):
            self.window.configure(tab)
        self.assertEqual(expected, tab.data['buttons'][-1])
        self.assertEqual(expected, config.read(self.path)['tabs'][0]['buttons'][-1])
        self.assertEqual([], tab.terminal.commands)
        self.assertEqual(0, tab.terminal.stops)
        tab.command_buttons[-1].click()
        self.assertEqual([body], tab.terminal.commands)
        editor.deleteLater()

    def test_multiline_buttons_survive_workspace_export_import_and_backup_recovery(self):
        body = '\nfunction greet() {\n  printf "%s" "café 世界"\n}\n\ngreet\n'
        tab = self.window.current_tab()
        entry = {'label': 'Script', 'command': body, 'confirm': True,
                 'confirmation_message': 'Execute this script?'}
        tab.data['buttons'] = [entry]
        tab.build_buttons()
        self.ready(tab)
        self.assertTrue(self.window.save_workspace('Scripts', [0]))
        exported = Path(self.temp.name) / 'export.json'
        with patch('bashdock.app.QFileDialog.getSaveFileName', return_value=(str(exported), '')):
            self.window.export_settings()
        self.window.import_settings(path=exported)
        restored = self.window.current_tab()
        self.ready(restored)
        self.assertEqual(entry, restored.data['buttons'][0])
        self.assertEqual([], restored.terminal.commands)
        self.assertEqual(entry, self.window.data['workspaces'][0]['tabs'][0]['buttons'][0])
        config.save(self.window.snapshot(), self.path)
        self.assertEqual(entry, config.read(config.backup_path(self.path))['tabs'][0]['buttons'][0])
        self.assertTrue(self.window.open_workspace(0, replace=True))
        self.assertEqual(entry, self.window.current_tab().data['buttons'][0])
        self.assertEqual([], self.window.current_tab().terminal.commands)

    def test_command_editor_opens_from_table_keyboard_and_double_click(self):
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QDialog
        editor = SettingsDialog(dict(self.window.current_tab().data, bash_path=str(self.bash)), self.window)
        editor.show()
        editor.table.selectRow(0)
        editor.table.setFocus()
        self.app.processEvents()
        opened = []

        def cancel(inner):
            opened.append(inner.windowTitle())
            return QDialog.DialogCode.Rejected

        with patch('bashdock.app.CommandEditor.exec', cancel):
            QTest.keyClick(editor.table, Qt.Key.Key_F2)
            self.assertEqual(1, len(opened))
            QTest.keyClick(editor.table, Qt.Key.Key_Return)
            self.assertEqual(2, len(opened))
            rect = editor.table.visualItemRect(editor.table.item(0, 1))
            QTest.mouseClick(editor.table.viewport(), Qt.MouseButton.LeftButton,
                            pos=rect.center())
            QTest.mouseDClick(editor.table.viewport(), Qt.MouseButton.LeftButton,
                             pos=rect.center())
            self.assertEqual(3, len(opened))
            for text in ('Edit…', 'Add'):
                next(button for button in editor.findChildren(QPushButton) if button.text() == text).click()
            self.assertEqual(5, len(opened))
        editor.reject()
        editor.deleteLater()

    def test_tab_command_buttons_wrap_and_unwrap_without_restarting_or_submitting(self):
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtTest import QTest
        from bashdock.app import CommandScrollArea
        tab = self.window.current_tab()
        tab.data['buttons'] = [{'label': f'Command {i}', 'command': f'echo {i}'} for i in range(3)]
        tab.build_buttons()
        self.ready(tab)
        process = tab.terminal.process
        self.window.new_tab()
        self.window.tabs.setCurrentIndex(0)
        screen = self.window.screen().availableGeometry()
        wide = min(1200, screen.width() - 80)
        narrow = min(300, wide // 2)
        self.window.move(screen.topLeft() + QPoint(20, 20))
        self.window.resize(wide, 760)
        self.window.show()
        scroll = tab.findChild(CommandScrollArea)
        heights = []
        for width in (wide, narrow, wide):
            self.window.resize(width, 760)
            for index in (1, 0):
                self.window.tabs.setCurrentIndex(index)
                for _ in range(12):
                    self.app.processEvents()
            rows = [button.y() for button in tab.command_buttons]
            self.assertEqual(width == narrow, len(set(rows)) > 1,
                             repr((width, self.window.size(), scroll.viewport().size(), rows)))
            self.assertEqual(rows, sorted(rows))
            heights.append(scroll.height())
            self.assertFalse(scroll.horizontalScrollBar().isVisible())
            self.assertFalse(scroll.verticalScrollBar().isVisible())
            previous = None
            for button in tab.command_buttons:
                self.assertTrue(scroll.viewport().rect().contains(
                    button.geometry().translated(tab.bar.pos())))
                self.assertEqual(Qt.FocusPolicy.NoFocus, button.focusPolicy())
                self.assertGreaterEqual(button.height(), button.sizeHint().height())
                if previous is not None and previous.y() == button.y():
                    self.assertLess(previous.geometry().right(), button.x())
                previous = button
            self.assertIs(process, tab.terminal.process)
            self.assertEqual([], tab.terminal.commands)
            self.assertEqual(0, tab.terminal.stops)
        self.assertGreater(heights[1], heights[0])
        self.assertEqual(heights[0], heights[2])
        self.assertEqual(1, len(tab.terminal.starts))
        self.window.resize(narrow, 760)
        for _ in range(12):
            self.app.processEvents()
        for button in tab.command_buttons:
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertEqual([f'echo {i}' for i in range(3)], tab.terminal.commands)
        gear = tab.findChild(QPushButton, 'configureTab')
        self.assertTrue(gear.isVisible())
        self.assertTrue(tab.rect().contains(gear.geometry()))

    def test_tab_command_buttons_long_labels_and_empty_rebuild_fit_the_viewport(self):
        from bashdock.app import CommandScrollArea
        tab = self.window.current_tab()
        label = 'A very long label ' * 40
        tab.data['buttons'] = [{'label': label, 'command': 'printf long'},
                               {'label': 'Second', 'command': 'printf second'}]
        tab.build_buttons()
        self.ready(tab)
        self.window.show()
        self.window.resize(600, 760)
        for _ in range(12):
            self.app.processEvents()
        scroll = tab.findChild(CommandScrollArea)
        first, second = tab.command_buttons
        self.assertLessEqual(first.width(), scroll.viewport().width())
        self.assertEqual(label, first.text())
        self.assertIn(label, first.toolTip())
        self.assertIn('printf long', first.toolTip())
        self.assertGreater(second.y(), first.y())
        self.assertFalse(scroll.horizontalScrollBar().isVisible())
        row_height = first.sizeHint().height()
        tab.data['buttons'] = []
        tab.build_buttons()
        for _ in range(12):
            self.app.processEvents()
        self.assertEqual([], tab.command_buttons)
        self.assertEqual(0, tab.bar_layout.count())
        self.assertLessEqual(scroll.height(), row_height)
        self.assertTrue(tab.findChild(QPushButton, 'configureTab').isVisible())

    def test_tab_command_buttons_extreme_rows_keep_terminal_and_gear_accessible(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from bashdock.app import CommandScrollArea
        tab = self.window.current_tab()
        tab.data['buttons'] = [{'label': f'Long command button {i}', 'command': f'echo {i}'} for i in range(45)]
        tab.build_buttons()
        self.ready(tab)
        self.window.show()
        self.window.resize(600, 380)
        for _ in range(16):
            self.app.processEvents()
        scroll = tab.findChild(CommandScrollArea)
        self.assertTrue(scroll.verticalScrollBar().isVisible())
        self.assertFalse(scroll.horizontalScrollBar().isVisible())
        self.assertLessEqual(scroll.height(), int(tab.height() * 0.4))
        self.assertGreater(tab.terminal.height(), scroll.height())
        last = tab.command_buttons[-1]
        scroll.ensureWidgetVisible(last)
        self.app.processEvents()
        self.assertTrue(scroll.viewport().rect().contains(last.geometry().translated(tab.bar.pos())))
        QTest.mouseClick(last, Qt.MouseButton.LeftButton)
        self.assertEqual(['echo 44'], tab.terminal.commands)
        self.assertTrue(tab.findChild(QPushButton, 'configureTab').isVisible())
        previous = scroll.height()
        self.window.resize(600, 900)
        for _ in range(16):
            self.app.processEvents()
        self.assertGreater(scroll.height(), previous)
        self.assertEqual(0, tab.terminal.stops)

    def test_tab_icons_automatic_assignment_persistence_and_shared_workspace_identity(self):
        from bashdock import tab_icons
        for _ in range(len(tab_icons.GENERIC) + 1):
            self.window.new_tab()
        tabs = [self.window.tabs.widget(i) for i in range(self.window.tabs.count())]
        keys = [tab.data['icon'] for tab in tabs]
        self.assertEqual(len(tab_icons.GENERIC), len(set(keys[:len(tab_icons.GENERIC)])))
        self.assertTrue(all(key in tab_icons.GENERIC for key in keys))
        tabs[2].data['icon'] = 'server'
        keys[2] = 'server'
        self.assertTrue(self.window.save_workspace('Icons', [0, 2, 4]))
        self.assertTrue(self.window.persist())
        saved = config.read(self.path)
        self.assertEqual(keys, [tab['icon'] for tab in saved['tabs']])
        self.assertEqual([keys[i] for i in (0, 2, 4)],
                         [tab['icon'] for tab in saved['workspaces'][0]['tabs']])
        self.assertTrue(self.window.open_workspace(0, replace=True))
        self.assertEqual([keys[i] for i in (0, 2, 4)],
                         [self.window.tabs.widget(i).data['icon'] for i in range(3)])
        exported = Path(self.temp.name) / 'icons-export.json'
        with patch('bashdock.app.QFileDialog.getSaveFileName', return_value=(str(exported), '')):
            self.window.export_settings()
        self.window.import_settings(path=exported)
        self.assertEqual(['circle', 'server', 'hexagon'],
                         [self.window.tabs.widget(i).data['icon'] for i in range(3)])
        # Legacy profiles gain icons only when used by the UI; shared IDs agree.
        legacy = copy.deepcopy(saved)
        for tab in legacy['tabs'] + legacy['workspaces'][0]['tabs']:
            del tab['icon']
        before = copy.deepcopy(legacy)
        self.assertEqual(before, config.migrate(legacy))
        tab_icons.assign_missing(legacy)
        for tab in legacy['workspaces'][0]['tabs']:
            live = next(item for item in legacy['tabs'] if item['id'] == tab['id'])
            self.assertEqual(live['icon'], tab['icon'])
        resolved = copy.deepcopy(legacy)
        tab_icons.assign_missing(legacy)
        self.assertEqual(resolved, legacy)

    def test_tab_icon_picker_cancel_save_and_failed_save_preserve_live_shell(self):
        from PySide6.QtWidgets import QDialog
        from bashdock.tab_icon_picker import TabIconPicker
        from bashdock import tab_icons
        tab = self.window.current_tab()
        self.ready(tab)
        original = copy.deepcopy(tab.data)
        dialog = SettingsDialog(dict(tab.data, bash_path=str(self.bash)))
        picker = TabIconPicker(dialog.icon_key)
        try:
            self.assertEqual(len(tab_icons.CATALOG), picker.icons.count())
            row = list(tab_icons.CATALOG).index('server')
            picker.icons.setCurrentRow(row)
            self.assertEqual('server', picker.selected_icon())
            self.assertEqual('Server', picker.icons.currentItem().text())
            with patch('bashdock.app.TabIconPicker.exec', return_value=QDialog.DialogCode.Rejected):
                dialog.choose_icon()
            self.assertEqual(original['icon'], dialog.icon_key)
            with patch('bashdock.app.TabIconPicker.exec', return_value=QDialog.DialogCode.Accepted), \
                    patch('bashdock.app.TabIconPicker.selected_icon', return_value='server'):
                dialog.choose_icon()
            self.assertEqual('server', dialog.icon_key)
            self.assertEqual(original, tab.data)
            dialog.commit()
            self.assertEqual('server', dialog.result_data['icon'])
            with patch.object(dialog, 'exec', return_value=QDialog.DialogCode.Accepted), \
                    patch('bashdock.app.SettingsDialog', return_value=dialog), \
                    patch('bashdock.app.config.save', side_effect=OSError('disk full')), \
                    patch('bashdock.app.QMessageBox.warning'):
                self.window.configure(tab)
            self.assertEqual(original, tab.data)
            with patch('bashdock.app.SettingsDialog', return_value=dialog), \
                    patch.object(dialog, 'exec', return_value=QDialog.DialogCode.Accepted):
                self.window.configure(tab)
            self.assertEqual('server', tab.data['icon'])
            self.assertEqual('server', config.read(self.path)['tabs'][0]['icon'])
            self.assertEqual(0, tab.terminal.stops)
            self.assertEqual([], tab.terminal.commands)
            self.assertEqual(1, len(tab.terminal.starts))
        finally:
            picker.deleteLater()
            dialog.deleteLater()
            self.app.processEvents()

    def test_tab_compact_overflow_preserves_names_icons_selection_and_shells(self):
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QStyleOptionTab, QToolButton, QTabBar
        for _ in range(3):
            self.window.new_tab()
        tabs = [self.window.tabs.widget(i) for i in range(4)]
        for tab in tabs:
            self.ready(tab)
        screen = self.window.screen().availableGeometry()
        wide = min(1200, screen.width() - 80)
        narrow = min(640, wide - 160)
        self.window.move(screen.topLeft() + QPoint(20, 20))
        self.window.resize(wide, 760)
        self.window.show()
        bar = self.window.tabs.tabBar()
        for _ in range(8):
            self.app.processEvents()
        # Keep both window sizes on-screen, including at fractional scaling.
        # Choose labels that fit its actual wide size and overflow when narrow.
        corner_width = self.window.tabs.cornerWidget().width()
        available = self.window.tabs.width() - corner_width - 6
        target = (available + narrow - corner_width - 12) // 2
        suffix = ''
        while True:
            for index, tab in enumerate(tabs):
                tab.data['name'] = f'{index}{suffix}'
                self.window.tabs.setTabText(index, tab.data['name'])
                self.window.tabs.setTabToolTip(index, tab.data['name'])
                bar.setAccessibleTabName(index, tab.data['name'])
            for _ in range(4):
                self.app.processEvents()
            natural = sum(QTabBar.tabSizeHint(bar, i).width() for i in range(4))
            if natural >= target:
                break
            suffix += 'x'
        self.assertLess(natural, available)
        for _ in range(8):
            self.app.processEvents()
        self.assertFalse(bar.compact, repr((self.window.size(), available, natural)))
        full_width = bar.tabRect(0).width()
        for width in (narrow, wide, narrow, wide, narrow):
            self.window.resize(width, 760)
            for _ in range(8):
                self.app.processEvents()
            self.assertEqual(width == narrow, bar.compact,
                repr(dict(requested=width, actual=self.window.size(), bar=bar.geometry(),
                          contents=self.window.tabs.contentsRect(), corner=corner_width,
                          natural=sum(QTabBar.tabSizeHint(bar, i).width() for i in range(4)))))
            option = QStyleOptionTab()
            bar.initStyleOption(option, 0)
            self.assertEqual('' if bar.compact else tabs[0].data['name'], option.text)
            for index, tab in enumerate(tabs):
                self.assertEqual(tab.data['name'], self.window.tabs.tabText(index))
                self.assertEqual(tab.data['name'], bar.tabToolTip(index))
                self.assertEqual(tab.data['name'], bar.accessibleTabName(index))
                self.assertFalse(bar.tabIcon(index).isNull())
            if bar.compact:
                self.assertLess(bar.tabRect(0).width(), full_width)
            self.assertIs(tabs[3], self.window.current_tab())
        QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=bar.tabRect(0).center())
        self.assertIs(tabs[0], self.window.current_tab())
        bar.moveTab(0, 2)
        self.assertIs(tabs[0], self.window.current_tab())
        self.assertEqual(tabs[0].data['name'], bar.tabToolTip(2))
        self.assertEqual([0] * 4, [tab.terminal.stops for tab in tabs])
        self.assertEqual([[]] * 4, [tab.terminal.commands for tab in tabs])
        self.assertTrue(all(len(tab.terminal.starts) == 1 for tab in tabs))
        QTest.keyClick(bar, Qt.Key.Key_Right)
        self.assertEqual(3, self.window.tabs.currentIndex())
        closed = self.window.tabs.widget(1)
        close = bar.tabButton(1, bar.ButtonPosition.RightSide).findChild(QToolButton)
        QTest.mouseClick(close, Qt.MouseButton.LeftButton)
        self.assertEqual(3, self.window.tabs.count())
        self.assertEqual(1, closed.terminal.stops)
        # Extreme overflow retains Qt's native scroll controls and active tab.
        for _ in range(15):
            self.window.new_tab()
        for _ in range(8):
            self.app.processEvents()
        self.assertTrue(bar.compact)
        arrows = [button for button in bar.findChildren(QToolButton)
                  if button.arrowType() in (Qt.ArrowType.LeftArrow, Qt.ArrowType.RightArrow)]
        self.assertTrue(any(button.isVisible() for button in arrows))
        self.assertEqual(self.window.tabs.count() - 1, self.window.tabs.currentIndex())

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

    def test_m3_workspace_picker_validates_then_saves_subset_through_real_dialog_and_cancel_is_inert(self):
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QDialogButtonBox
        from bashdock.workspaces import WorkspacesDialog, SaveWorkspaceDialog

        first = self.window.current_tab()
        self.ready(first)
        self.window.new_tab()
        second = self.window.current_tab()
        self.ready(second)
        dialog = WorkspacesDialog(self.window)
        observed = []

        def fill_picker():
            picker = next(d for d in dialog.findChildren(SaveWorkspaceDialog) if d.isVisible())
            buttons = picker.findChild(QDialogButtonBox)
            with patch('bashdock.workspaces.QMessageBox.warning') as warning:
                buttons.button(QDialogButtonBox.StandardButton.Save).click()
                self.assertTrue(picker.isVisible())
                picker.name.setText('  Selected project  ')
                for i in range(2):
                    picker.tabs.item(i).setCheckState(Qt.CheckState.Unchecked)
                buttons.button(QDialogButtonBox.StandardButton.Save).click()
                self.assertTrue(picker.isVisible())
                self.assertEqual(2, warning.call_count)
            picker.tabs.item(1).setCheckState(Qt.CheckState.Checked)
            observed.append(picker.selected_indexes())
            buttons.button(QDialogButtonBox.StandardButton.Save).click()

        try:
            QTimer.singleShot(25, fill_picker)
            dialog.save_new()
            self.assertEqual([[1]], observed)
            expected = [{'name': 'Selected project', 'tabs': [second.data], 'active_tab': 0}]
            self.assertEqual(expected, config.read(self.path)['workspaces'])
            self.assertEqual('Selected project', dialog.list.currentItem().text())
            before = self.path.read_bytes()

            def cancel_picker():
                picker = next(d for d in dialog.findChildren(SaveWorkspaceDialog) if d.isVisible())
                picker.name.setText('Do not save')
                picker.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()

            QTimer.singleShot(25, cancel_picker)
            dialog.save_new()
            self.assertEqual(before, self.path.read_bytes())
            self.assertEqual(expected, self.window.data['workspaces'])
            self.assertEqual([0, 0], [t.terminal.stops for t in (first, second)])
        finally:
            dialog.deleteLater()

    def test_m3_workspace_manager_cancel_invalid_names_and_write_failures_keep_library_and_shells(self):
        from bashdock.workspaces import WorkspacesDialog

        tab = self.window.current_tab()
        self.ready(tab)
        self.assertTrue(self.window.save_workspace('Project', [0]))
        self.assertTrue(self.window.save_workspace('Other', [0]))
        dialog = WorkspacesDialog(self.window)
        original = copy.deepcopy(self.window.data['workspaces'])
        disk = self.path.read_bytes()
        try:
            with patch('bashdock.workspaces.QMessageBox.question', return_value=QMessageBox.StandardButton.No), \
                    patch.object(dialog, 'choose_tabs') as picker:
                dialog.update_selected()
                dialog.delete_selected()
                picker.assert_not_called()
            with patch('bashdock.workspaces.QInputDialog.getText', return_value=('Discard', False)):
                dialog.rename_selected()
            for name in ('   ', ' other '):
                with self.subTest(name=name), patch('bashdock.app.QMessageBox.warning') as warning, \
                        patch('bashdock.workspaces.QInputDialog.getText', return_value=(name, True)):
                    dialog.rename_selected()
                    warning.assert_called_once()
            with patch('bashdock.config.save', side_effect=PermissionError('locked')), \
                    patch('bashdock.app.QMessageBox.warning'):
                with patch('bashdock.workspaces.QInputDialog.getText', return_value=('Changed', True)):
                    dialog.rename_selected()
                dialog.delete_selected()
                self.assertFalse(self.window.save_workspace('Project', [0], replace=0))
            self.assertEqual(original, self.window.data['workspaces'])
            self.assertEqual(disk, self.path.read_bytes())
            self.assertEqual(['Project', 'Other'], [dialog.list.item(i).text() for i in range(2)])
            self.assertIs(tab, self.window.current_tab())
            self.assertEqual(0, tab.terminal.stops)
            self.assertEqual([], tab.terminal.commands)
        finally:
            dialog.deleteLater()

    def test_m3_workspace_ssh_buttons_never_run_on_add_replace_import_or_reopen(self):
        tab = self.window.current_tab()
        tab.data['buttons'] = [{'label': 'Connect', 'command': 'ssh user@example.invalid'}]
        tab.build_buttons()
        self.ready(tab)
        self.assertTrue(self.window.save_workspace('SSH project', [0]))
        saved = copy.deepcopy(self.window.data['workspaces'])
        self.window.new_tab()
        self.ready(self.window.current_tab())
        self.window.close_tab(0)
        self.assertTrue(self.window.open_workspace(0))
        opened = self.window.current_tab()
        self.ready(opened)
        self.assertEqual([], opened.terminal.commands)
        self.assertEqual(1, len(opened.terminal.starts))
        # Clicking explicitly is the only route that may submit this command.
        opened.command_buttons[0].click()
        self.assertEqual(['ssh user@example.invalid'], opened.terminal.commands)
        opened.data['buttons'][0]['command'] = 'live edit'
        self.assertEqual(saved, self.window.data['workspaces'])
        self.assertTrue(self.window.open_workspace(0, replace=True))
        replacement = self.window.current_tab()
        self.ready(replacement)
        self.assertEqual(saved[0]['tabs'][0], replacement.data)
        self.assertEqual([], replacement.terminal.commands)
        export = Path(self.temp.name) / 'workspace-export.json'
        with patch('bashdock.app.QFileDialog.getSaveFileName', return_value=(str(export), '')):
            self.window.export_settings()
        self.window.import_settings(path=export)
        imported = self.window.current_tab()
        self.ready(imported)
        self.assertEqual([], imported.terminal.commands)
        self.window.data['confirm_on_exit'] = False
        self.window.close()
        self.window.deleteLater()
        self.window = MainWindow(terminal_factory=FakeTerminal)
        reopened = self.window.current_tab()
        self.ready(reopened)
        self.assertEqual(saved, self.window.data['workspaces'])
        self.assertEqual(saved[0]['tabs'][0], reopened.data)
        self.assertEqual([], reopened.terminal.commands)

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
        tab_icons.assign_missing(imported)
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
        tab_icons.assign_missing(expected)
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
        tab_icons.assign_missing(expected)
        self.assertEqual(expected, restored)
        archives = list((self.path.parent / "backups").glob("settings-damaged-*.json"))
        self.assertEqual([damaged], [p.read_bytes() for p in archives])
        self.assertTrue(self.window.persist())

    def test_m7_cancelled_protected_and_failed_exports_keep_live_settings_and_backup(self):
        tab = self.window.current_tab()
        self.ready(tab)
        primary, backup = self.path.read_bytes(), config.backup_path(self.path).read_bytes()
        for destination in ('', str(self.path), str(config.backup_path(self.path))):
            with self.subTest(destination=destination), \
                    patch('bashdock.app.QFileDialog.getSaveFileName', return_value=(destination, '')), \
                    patch('bashdock.app.QMessageBox.warning') as warning:
                self.window.export_settings()
                self.assertEqual(0 if not destination else 1, warning.call_count)
        target = Path(self.temp.name) / 'separate-export.json'
        with patch('bashdock.app.QFileDialog.getSaveFileName', return_value=(str(target), '')), \
                patch('bashdock.config.atomic_write', side_effect=PermissionError('locked')), \
                patch('bashdock.app.QMessageBox.warning') as warning:
            self.window.export_settings()
            warning.assert_called_once()
        self.assertFalse(target.exists())
        self.assertEqual(primary, self.path.read_bytes())
        self.assertEqual(backup, config.backup_path(self.path).read_bytes())
        self.assertEqual(0, tab.terminal.stops)
        self.assertEqual(1, len(tab.terminal.starts))

    def test_m7_recovery_cancelled_restore_or_invalid_backup_preserves_both_files_and_shell(self):
        from PySide6.QtCore import QTimer

        good_backup = config.backup_path(self.path).read_bytes()
        for invalid_backup in (False, True):
            with self.subTest(invalid_backup=invalid_backup):
                self.window.allow_save = False
                self.window.data['confirm_on_exit'] = False
                self.window.close()
                self.window.deleteLater()
                self.app.processEvents()
                damaged = b'\xffnot valid settings'
                backup = b'not a valid backup' if invalid_backup else good_backup
                self.path.write_bytes(damaged)
                config.backup_path(self.path).write_bytes(backup)
                self.window = MainWindow(terminal_factory=FakeTerminal)
                self.window.data['bash_path'] = str(self.bash)
                tab = self.window.current_tab()
                self.ready(tab)
                visited = []

                def restore():
                    dialog = self.app.activeModalWidget()
                    visited.append(dialog.windowTitle())
                    next(b for b in dialog.buttons() if b.text() == 'Restore backup…').click()

                with patch('bashdock.app.QMessageBox.question', return_value=QMessageBox.StandardButton.No) as confirm, \
                        patch('bashdock.app.QMessageBox.warning') as warning:
                    QTimer.singleShot(0, restore)
                    self.app.processEvents()
                self.assertEqual(['Recover settings'], visited)
                if invalid_backup:
                    confirm.assert_not_called()
                    warning.assert_called_once()
                else:
                    confirm.assert_called_once()
                    self.assertEqual(QMessageBox.StandardButton.No, confirm.call_args.args[-1])
                    warning.assert_not_called()
                self.assertFalse(self.window.allow_save)
                self.assertFalse(self.window.persist())
                self.assertIs(tab, self.window.current_tab())
                self.assertEqual(0, tab.terminal.stops)
                self.assertEqual(damaged, self.path.read_bytes())
                self.assertEqual(backup, config.backup_path(self.path).read_bytes())
                self.assertFalse(list((self.path.parent / 'backups').glob('settings-damaged-*.json')))

    def test_m7_recovery_import_cancel_and_export_restore_use_the_recovery_dialog(self):
        from PySide6.QtCore import QTimer

        exported = config.read(self.path)
        exported['tabs'][0]['name'] = 'Recovered from export'
        target = Path(self.temp.name) / 'saved-export.json'
        config.save(exported, target, backup=False)
        self.window.allow_save = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        damaged = b'broken settings'
        self.path.write_bytes(damaged)
        backup = config.backup_path(self.path).read_bytes()
        self.window = MainWindow(terminal_factory=FakeTerminal)

        def import_choice():
            dialog = self.app.activeModalWidget()
            next(b for b in dialog.buttons() if b.text() == 'Import settings…').click()

        with patch('bashdock.app.QFileDialog.getOpenFileName', return_value=('', '')):
            QTimer.singleShot(0, import_choice)
            self.app.processEvents()
        self.assertFalse(self.window.allow_save)
        self.assertEqual(damaged, self.path.read_bytes())
        with patch('bashdock.app.QFileDialog.getOpenFileName', return_value=(str(target), '')):
            QTimer.singleShot(0, import_choice)
            self.window.show_config_error()
        self.assertTrue(self.window.allow_save)
        self.assertEqual('', self.window.config_error)
        self.assertEqual('Recovered from export', self.window.current_tab().data['name'])
        tab_icons.assign_missing(exported)
        self.assertEqual(exported, config.read(self.path))
        self.assertEqual(backup, config.backup_path(self.path).read_bytes())
        archives = list((self.path.parent / 'backups').glob('settings-damaged-*.json'))
        self.assertEqual([damaged], [p.read_bytes() for p in archives])

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
        self.assertFalse(second.terminal.ready)
        self.assertEqual(1, second.terminal.focus_requests)
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

    def test_new_tab_deferred_focus_does_not_follow_a_tab_switch_or_modal(self):
        first = self.window.current_tab()
        with patch.object(self.window, 'isActiveWindow', return_value=True):
            self.window.new_tab()
            second = self.window.current_tab()
            self.window.tabs.setCurrentWidget(first)
            self.app.processEvents()
            self.assertEqual(1, second.terminal.focus_requests)
            self.window.new_tab()
            third = self.window.current_tab()
            with patch('bashdock.app.QApplication.activeModalWidget', return_value=self.window):
                self.app.processEvents()
            self.assertEqual(1, third.terminal.focus_requests)
            self.window.new_tab()
            fourth = self.window.current_tab()
            self.app.processEvents()
            self.assertEqual(2, fourth.terminal.focus_requests)

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
                errors = []
                timer = QTimer(self.window)
                timer.setInterval(10)
                deadline = time.monotonic() + 5

                def finish_dialog():
                    try:
                        dialog = next((d for d in self.window.findChildren(QInputDialog) if d.isVisible()), None)
                        if dialog is None:
                            if time.monotonic() < deadline:
                                return
                            raise AssertionError('Rename dialog did not become visible within five seconds')
                        timer.stop()
                        observed.append(dialog.textValue())
                        dialog.setTextValue(text)
                        if accepted:
                            dialog.accept()
                        else:
                            dialog.reject()
                    except BaseException as error:
                        errors.append(error)
                        timer.stop()
                        modal = QApplication.activeModalWidget()
                        if modal is not None:
                            modal.reject()

                bar = self.window.tabs.tabBar()
                self.app.processEvents()
                timer.timeout.connect(finish_dialog)
                timer.start()
                try:
                    # Deliberately service the callback before opening a dialog.
                    # A one-shot timer previously raised StopIteration here and
                    # left the subsequent native modal dialog open indefinitely.
                    QTest.qWait(60)
                    self.assertEqual([], observed)
                    self.assertEqual([], errors)
                    QTest.mouseDClick(bar, Qt.MouseButton.LeftButton,
                                     pos=bar.tabRect(0).center())
                    if errors:
                        raise errors[0]
                finally:
                    timer.stop()
                    timer.deleteLater()
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

    def test_close_active_tab_restores_native_focus_to_surviving_terminal(self):
        from PySide6.QtWidgets import QTabBar, QToolButton

        first = self.window.current_tab()
        self.ready(first)
        self.window.new_tab()
        self.ready(self.window.current_tab())
        self.window.show()
        self.app.processEvents()
        bar = self.window.tabs.tabBar()
        bar.setFocus()
        close = bar.tabButton(1, QTabBar.ButtonPosition.RightSide).findChild(QToolButton, 'tabClose')
        before = first.terminal.focus_requests
        with patch.object(self.window, 'isActiveWindow', return_value=True):
            close.click()
            self.assertIs(first, self.window.current_tab())
            self.assertEqual(before + 1, first.terminal.focus_requests)
            self.app.processEvents()
        self.assertEqual(before + 2, first.terminal.focus_requests)
        self.assertIs(first.terminal, QApplication.focusWidget())

    def test_close_tab_deferred_focus_respects_tab_switch_modal_and_inactive_window(self):
        for blocked in ('switch', 'modal', 'inactive'):
            with self.subTest(blocked=blocked):
                survivor = self.window.current_tab()
                self.window.new_tab()
                self.app.processEvents()
                before = survivor.terminal.focus_requests
                self.window.close_tab(self.window.tabs.currentIndex())
                self.assertEqual(before + 1, survivor.terminal.focus_requests)
                if blocked == 'switch':
                    other = self.window.add_tab(config.default_tab('Other'))
                    self.window.tabs.setCurrentWidget(other)
                with patch.object(self.window, 'isActiveWindow', return_value=blocked != 'inactive'), \
                        patch('bashdock.app.QApplication.activeModalWidget',
                              return_value=self.window if blocked == 'modal' else None):
                    self.app.processEvents()
                self.assertEqual(before + 1, survivor.terminal.focus_requests)

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

    def test_m8_real_quit_dialog_cancel_save_failure_and_opt_out_stop_only_after_save(self):
        from PySide6.QtCore import QTimer

        first = self.window.current_tab()
        self.ready(first)
        self.window.new_tab()
        second = self.window.current_tab()
        self.ready(second)
        self.assertTrue(self.window.persist())
        for answer, locked in ((QMessageBox.StandardButton.No, False),
                               (QMessageBox.StandardButton.Yes, True),
                               (QMessageBox.StandardButton.Yes, False)):
            with self.subTest(answer=answer, locked=locked):
                observed = []

                def respond():
                    dialog = QApplication.activeModalWidget()
                    observed.append((dialog.windowTitle(), dialog.text(),
                                     dialog.standardButton(dialog.defaultButton()), dialog.checkBox().text()))
                    dialog.checkBox().setChecked(True)
                    dialog.button(answer).click()

                QTimer.singleShot(0, respond)
                real_save = config.save
                stops_at_save = []

                def save(*args, **kwargs):
                    stops_at_save.append([first.terminal.stops, second.terminal.stops])
                    if locked:
                        raise PermissionError('locked')
                    return real_save(*args, **kwargs)

                with patch('bashdock.config.save', side_effect=save), \
                        patch('bashdock.app.QMessageBox.warning') as warning:
                    closed = self.window.close()
                self.assertEqual([('Close BashDock?', 'Close 2 shell session(s) and quit?',
                                   QMessageBox.StandardButton.No, "Don't show this again")], observed)
                accepted = answer == QMessageBox.StandardButton.Yes and not locked
                self.assertEqual(accepted, closed)
                self.assertEqual(accepted, not self.window.data['confirm_on_exit'])
                self.assertEqual(accepted, not config.read(self.path)['confirm_on_exit'])
                self.assertEqual([int(accepted)] * 2, [first.terminal.stops, second.terminal.stops])
                self.assertTrue(all(counts == [0, 0] for counts in stops_at_save))
                self.assertEqual(1 if locked else 0, warning.call_count)
        self.assertTrue(self.window.close())
        self.assertEqual([1, 1], [first.terminal.stops, second.terminal.stops])

    def test_m8_closing_without_running_shells_does_not_prompt_or_change_confirmation_preference(self):
        with patch.object(self.window, 'confirm_quit') as confirm:
            self.assertTrue(self.window.close())
            confirm.assert_not_called()
        self.assertTrue(config.read(self.path)['confirm_on_exit'])

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

    def test_m6_nested_terminal_dialog_save_cancel_and_return_to_defaults(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialogButtonBox
        from bashdock.terminal_settings import TerminalSettingsDialog

        first = self.window.current_tab()
        self.ready(first)
        self.window.new_tab()
        second = self.window.current_tab()
        self.ready(second)
        defaults = copy.deepcopy(self.window.data['terminal'])
        custom = dict(defaults, background='#331122', font_size=23)
        identity = first.data['id']
        for mode, save_inner, save_outer, expected in (
                ('custom', True, False, None),
                ('custom', True, True, custom),
                ('defaults', False, True, custom),
                ('defaults', True, False, custom),
                ('defaults', True, True, None)):
            with self.subTest(mode=mode, save_inner=save_inner, save_outer=save_outer):
                errors, visited = [], []
                before = copy.deepcopy(first.data.get('terminal'))

                def edit_outer():
                    outer = QApplication.activeModalWidget()

                    def edit_inner():
                        inner = QApplication.activeModalWidget()
                        try:
                            self.assertIsInstance(inner, TerminalSettingsDialog)
                            if mode == 'custom':
                                inner.use_defaults.setChecked(False)
                                inner.size.setValue(23)
                                inner.set_color('background', '#331122')
                            else:
                                inner.restore_button.click()
                                self.assertTrue(inner.use_defaults.isChecked())
                                self.assertFalse(inner.controls.isEnabled())
                            # A child Save only stages changes in Configure tab.
                            self.assertEqual(before, first.data.get('terminal'))
                            self.assertEqual(before or defaults, first.terminal.preferences)
                            visited.append('inner')
                            button = (QDialogButtonBox.StandardButton.Save if save_inner
                                      else QDialogButtonBox.StandardButton.Cancel)
                            inner.findChild(QDialogButtonBox).button(button).click()
                        except Exception as error:
                            errors.append(error)
                            inner.reject()

                    try:
                        self.assertIsInstance(outer, SettingsDialog)
                        QTimer.singleShot(25, edit_inner)
                        next(b for b in outer.findChildren(QPushButton)
                             if b.text() == 'Terminal settings…').click()
                        self.assertEqual(before, first.data.get('terminal'))
                        self.assertEqual(before, config.read(self.path)['tabs'][0].get('terminal'))
                        visited.append('outer')
                        button = (QDialogButtonBox.StandardButton.Save if save_outer
                                  else QDialogButtonBox.StandardButton.Cancel)
                        outer.findChild(QDialogButtonBox).button(button).click()
                    except Exception as error:
                        errors.append(error)
                        outer.reject()

                self.assertTrue(self.window.persist())
                QTimer.singleShot(25, edit_outer)
                self.window.configure(first)
                if errors:
                    raise errors[0]
                self.assertEqual(['inner', 'outer'], visited)
                self.assertEqual(expected, first.data.get('terminal'))
                self.assertEqual(expected, config.read(self.path)['tabs'][0].get('terminal'))
                self.assertEqual(expected or defaults, first.terminal.preferences)
                self.assertEqual(defaults, second.terminal.preferences)
                self.assertEqual(identity, first.data['id'])
                self.assertEqual([0, 0], [t.terminal.stops for t in (first, second)])
                self.assertEqual([1, 1], [len(t.terminal.starts) for t in (first, second)])

    def test_m6_restore_global_defaults_is_transactional_with_custom_tabs(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialogButtonBox
        from bashdock import terminal_preferences
        from bashdock.terminal_settings import TerminalSettingsDialog

        first = self.window.current_tab()
        self.window.new_tab()
        second = self.window.current_tab()
        changed = dict(self.window.data['terminal'], background='#223344', font_size=22)
        custom = dict(changed, background='#331122', cursor_style='bar')
        self.window.data['terminal'] = changed
        first.terminal.apply_settings(changed)
        second.data['terminal'] = copy.deepcopy(custom)
        second.terminal.apply_settings(custom)
        for tab in (first, second):
            self.ready(tab)
        self.assertTrue(self.window.persist())
        original = self.path.read_bytes()
        for save, locked in ((False, False), (True, True), (True, False)):
            with self.subTest(save=save, locked=locked):
                errors = []

                def edit():
                    dialog = QApplication.activeModalWidget()
                    try:
                        self.assertIsInstance(dialog, TerminalSettingsDialog)
                        self.assertIsNone(dialog.use_defaults)
                        dialog.restore_button.click()
                        self.assertEqual(terminal_preferences.defaults(), dialog.values())
                        self.assertEqual(changed, first.terminal.preferences)
                        button = (QDialogButtonBox.StandardButton.Save if save
                                  else QDialogButtonBox.StandardButton.Cancel)
                        dialog.findChild(QDialogButtonBox).button(button).click()
                    except Exception as error:
                        errors.append(error)
                        dialog.reject()

                QTimer.singleShot(25, edit)
                with patch('bashdock.app.QMessageBox.warning') as warning:
                    if locked:
                        with patch('bashdock.config.save', side_effect=PermissionError('locked')):
                            self.window.configure_terminal()
                        warning.assert_called_once()
                    else:
                        self.window.configure_terminal()
                        warning.assert_not_called()
                if errors:
                    raise errors[0]
                expected = terminal_preferences.defaults() if save and not locked else changed
                self.assertEqual(expected, self.window.data['terminal'])
                self.assertEqual(expected, first.terminal.preferences)
                self.assertEqual(custom, second.terminal.preferences)
                self.assertEqual(custom, second.data['terminal'])
                self.assertEqual(expected, config.read(self.path)['terminal'])
                if not save or locked:
                    self.assertEqual(original, self.path.read_bytes())
                self.assertEqual([0, 0], [t.terminal.stops for t in (first, second)])
                self.assertEqual([1, 1], [len(t.terminal.starts) for t in (first, second)])

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
        self.assertEqual(["Configure…", "", "Replace current"], [a.text() for a in submenu.actions()])
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
        self.assertEqual(["Configure…", "", "App && Website", "CIDR", "", "Replace current"],
                         [a.text() for a in submenu.actions()])
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
        self.assertEqual(["Configure…", "", "Replace current"], [a.text() for a in submenu.actions()])

    def test_workspace_replace_toggle_changes_only_mode_and_persists_after_menu_refresh_and_reopen(self):
        self.assertTrue(self.window.save_workspace('Project', [0]))
        self.window.new_tab()
        tabs = [self.window.tabs.widget(i) for i in range(2)]
        for tab in tabs:
            self.ready(tab)
        self.window.refresh_workspaces_menu()
        menu = self.window.workspaces_menu
        self.assertTrue(menu.actions()[-2].isSeparator())
        action = menu.actions()[-1]
        self.assertEqual('Replace current', action.text())
        self.assertTrue(action.isCheckable())
        self.assertFalse(action.isChecked())
        action.trigger()
        self.assertTrue(config.read(self.path)['workspace_replace_current'])
        self.assertEqual(tabs, [self.window.tabs.widget(i) for i in range(2)])
        self.assertEqual([0, 0], [tab.terminal.stops for tab in tabs])
        self.assertEqual([[], []], [tab.terminal.commands for tab in tabs])
        self.assertFalse(list((self.path.parent / 'backups').glob('settings-before-workspace-*.json')))
        self.window.refresh_workspaces_menu()
        self.assertTrue(menu.actions()[-1].isChecked())
        self.reopen_window()
        self.window.refresh_workspaces_menu()
        self.assertTrue(self.window.workspaces_menu.actions()[-1].isChecked())
        self.window.workspaces_menu.actions()[-1].trigger()
        self.assertFalse(config.read(self.path)['workspace_replace_current'])

    def test_workspace_replace_submenu_cancel_keeps_shells_and_accept_backs_up_then_replaces(self):
        self.assertTrue(self.window.save_workspace('Project', [0]))
        self.window.new_tab()
        self.window.current_tab().data['name'] = 'Unsaved work'
        tabs = [self.window.tabs.widget(i) for i in range(2)]
        for tab in tabs:
            self.ready(tab)
        self.window.refresh_workspaces_menu()
        menu = self.window.workspaces_menu
        menu.actions()[-1].trigger()
        saved = self.path.read_bytes()
        with patch('bashdock.app.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            menu.actions()[2].trigger()
        self.assertEqual(saved, self.path.read_bytes())
        self.assertEqual(tabs, [self.window.tabs.widget(i) for i in range(2)])
        self.assertEqual([0, 0], [tab.terminal.stops for tab in tabs])
        self.assertTrue(menu.actions()[-1].isChecked())
        menu.actions()[2].trigger()
        self.assertEqual(1, self.window.tabs.count())
        self.assertIsNot(tabs[0], self.window.current_tab())
        self.assertEqual([1, 1], [tab.terminal.stops for tab in tabs])
        self.assertTrue(self.window.data['workspace_replace_current'])
        archives = list((self.path.parent / 'backups').glob('settings-before-workspace-*.json'))
        self.assertEqual(1, len(archives))
        self.assertEqual('Unsaved work', config.read(archives[0])['tabs'][1]['name'])
        self.assertEqual([], self.window.current_tab().terminal.commands)

    def test_workspace_replace_toggle_failed_save_reverts_check_and_keeps_shell(self):
        tab = self.window.current_tab()
        self.ready(tab)
        self.window.refresh_workspaces_menu()
        before = self.path.read_bytes()
        with patch.object(self.window, 'persist', return_value=False), \
                patch('bashdock.app.QMessageBox.warning') as warning:
            self.window.workspace_replace_action.trigger()
        self.assertFalse(self.window.workspace_replace_action.isChecked())
        self.assertFalse(self.window.data['workspace_replace_current'])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(0, tab.terminal.stops)
        warning.assert_called_once()

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

    def test_m9_update_notice_and_controls_remain_accessible_after_resize_maximize_and_restore(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from bashdock.app import CommandScrollArea

        self.window.new_tab()
        self.window.tabs.setCurrentIndex(1)
        self.window.show()
        self.app.processEvents()
        self.reopen_window()
        self.window.show()
        self.assertEqual(1, self.window.tabs.currentIndex())
        requested = []
        footer = self.window.statusBar()
        footer.update_requested.connect(lambda: requested.append(True))
        processes = [self.window.tabs.widget(i).terminal.process for i in range(2)]

        for ready, local in ((False, False), (True, False), (True, True)):
            footer.show_update('0.14.7', ready=ready, local=local)
            footer.showMessage('A status message while an update notice is visible')
            for mode in ('wide', 'narrow', 'maximized', 'normal'):
                if mode == 'maximized':
                    self.window.showMaximized()
                elif mode == 'normal':
                    self.window.showNormal()
                else:
                    self.window.resize(1120 if mode == 'wide' else 600, 760)
                for index in (0, 1):
                    self.window.tabs.setCurrentIndex(index)
                    for _ in range(12):
                        self.app.processEvents()
                    with self.subTest(ready=ready, local=local, mode=mode, tab=index):
                        for widget in (footer.version_label, footer.update_button):
                            self.assertTrue(widget.isVisible())
                            self.assertTrue(footer.rect().contains(widget.geometry()))
                            self.assertGreaterEqual(widget.width(), widget.sizeHint().width())
                            self.assertGreaterEqual(widget.height(), widget.sizeHint().height())
                        self.assertLess(footer.version_label.geometry().right(),
                                        footer.update_button.geometry().left())
                        tab = self.window.current_tab()
                        scroll = tab.findChild(CommandScrollArea)
                        for button in tab.command_buttons:
                            bottom = button.mapTo(scroll.viewport(), button.rect().bottomLeft()).y()
                            self.assertLess(bottom, scroll.viewport().height())
                            self.assertGreaterEqual(button.height(), button.sizeHint().height())
                        gear = tab.findChild(QPushButton, 'configureTab')
                        new_tab = self.window.findChild(QPushButton, 'newTab')
                        for control in (gear, new_tab):
                            self.assertTrue(control.isVisible())
                            self.assertTrue(control.parentWidget().rect().contains(control.geometry()))
                            self.assertGreaterEqual(control.height(), control.sizeHint().height())
                        before = len(requested)
                        QTest.mouseClick(footer.update_button, Qt.MouseButton.LeftButton)
                        self.assertEqual(before + 1, len(requested))
                        self.assertIs(processes[index], tab.terminal.process)
                        self.assertEqual(0, tab.terminal.stops)

    def test_updater_u5_preference_actions_persist_gate_automatic_checks_and_rollback_on_failure(self):
        from unittest.mock import Mock
        updater = Mock()
        self.window.updater = updater
        self.window.download_updates_action.trigger()
        self.assertFalse(config.read(self.path)['updates']['download'])
        with patch('bashdock.update_security.load_key', return_value={}):
            self.window.automatic_update_check()
            updater.check.assert_called_once_with(False)
            updater.check.reset_mock()
            self.window.automatic_updates_action.trigger()
            self.assertFalse(config.read(self.path)['updates']['automatic'])
            self.window.automatic_update_check()
            updater.check.assert_not_called()
            # Disabling automatic checks still permits an explicit manual check.
            self.window.check_for_updates()
            updater.check.assert_called_once_with(False)
        saved = self.path.read_bytes()
        with patch.object(self.window, 'persist', return_value=False), \
                patch('bashdock.app.QMessageBox.warning'):
            self.window.download_updates_action.trigger()
        self.assertFalse(self.window.download_updates_action.isChecked())
        self.assertFalse(self.window.data['updates']['download'])
        self.assertEqual(saved, self.path.read_bytes())
        updater.launch_install.assert_not_called()
        self.window.updater = None

    def test_updater_u3_real_confirmation_cancel_and_failures_keep_offer_and_both_shells_usable(self):
        from PySide6.QtCore import QTimer
        from unittest.mock import Mock
        from types import SimpleNamespace
        self.window.new_tab()
        for index in range(2):
            self.ready(self.window.tabs.widget(index))
        self.window.show()
        updater = Mock()
        updater.ready = SimpleNamespace(manifest={'version': '0.14.7', 'channel': 'local-development'})
        self.window.updater = updater
        self.window.statusBar().show_update('0.14.7', local=True)
        initial = self.path.read_bytes()
        seen = []
        # Unpatch the global test answer stub to exercise the real default-No dialog.
        self.answers.stop()
        try:
            for outcome in ('cancel', 'save', 'launch'):
                def answer():
                    dialog = self.app.activeModalWidget()
                    seen.append((dialog.windowTitle(), dialog.defaultButton().text(), dialog.text()))
                    dialog.button(QMessageBox.StandardButton.No if outcome == 'cancel'
                                  else QMessageBox.StandardButton.Yes).click()
                QTimer.singleShot(0, answer)
                updater.launch_install.side_effect = OSError('fixture helper could not start')
                from contextlib import ExitStack
                with ExitStack() as stack:
                    stack.enter_context(patch('bashdock.app.QMessageBox.warning'))
                    if outcome == 'save':
                        stack.enter_context(patch.object(self.window, 'persist', return_value=False))
                    self.window.restart_for_update()
                self.assertFalse(self.window.closing)
                self.assertFalse(self.window.update_restart)
                self.assertTrue(self.window.statusBar().update_button.isVisible())
                self.assertIsNotNone(updater.ready)
                updater.cancel.assert_not_called()
                if outcome != 'launch':
                    updater.launch_install.assert_not_called()
                    self.assertEqual(initial, self.path.read_bytes())
                for index in range(2):
                    tab = self.window.tabs.widget(index)
                    self.assertEqual(0, tab.terminal.stops)
                    tab.terminal.run_command('fixture command after failed restart')
                    self.assertEqual('fixture command after failed restart', tab.terminal.commands[-1])
            self.assertEqual(3, len(seen))
            for title, default, text in seen:
                self.assertEqual('Restart to update?', title)
                self.assertIn('No', default)
                self.assertIn('locally built BashDock 0.14.7', text)
                self.assertIn('fresh shells', text)
            updater.launch_install.assert_called_once()
        finally:
            self.answers.start()
            self.window.updater = None

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
