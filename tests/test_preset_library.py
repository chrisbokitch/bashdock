"""Personal preset groups, safe sharing, and the manager/picker integration."""
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPlainTextEdit
from bashdock import config
from bashdock.command_presets import GROUPS
from bashdock.preset_library import export_bytes, merge, read_import
from bashdock.preset_manager import PresetButtonEditor, PresetManager
from bashdock.preset_picker import PresetPicker
from qt_lifecycle import GuiTestCase


def group(name='My scripts'):
    return dict(name=name, description='Daily tasks', requirements='Git Bash',
                buttons=[dict(label='Check', command='printf "café"\nprintf done',
                              description='Show status', confirm=True,
                              confirmation_message='Run both lines?', timing=True)])


class PresetLibraryTests(GuiTestCase):
    def test_settings_migrate_and_validate_personal_groups_without_changing_tabs(self):
        data = config.defaults()
        self.assertEqual([], data['preset_groups'])
        before = copy.deepcopy(data['tabs'])
        data['preset_groups'] = [group()]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            config.save(data, path)
            self.assertEqual(data['preset_groups'], config.read(path)['preset_groups'])
            self.assertEqual(before, config.read(path)['tabs'])
            old = copy.deepcopy(data)
            del old['preset_groups']
            path.write_text(json.dumps(old), encoding='utf-8')
            self.assertEqual([], config.read(path)['preset_groups'])
        for invalid in ([group('Git essentials')], [group(), group('my SCRIPTS')],
                        [dict(group(), buttons=[])], [dict(group(), buttons=[dict(label='x', command='\x1b')])]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                config.validate_preset_groups(invalid)

    def test_selected_groups_export_import_conflicts_and_reject_bad_files(self):
        first, second = group(), group('Another group')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'selected.json'
            path.write_bytes(export_bytes([first]))
            self.assertEqual([first], read_import(path))
            self.assertEqual('bashdock-command-presets', json.loads(path.read_text())['format'])
            self.assertEqual([second, first], merge([second], read_import(path)))
            original = [first]
            kept = merge(original, [first], replace=False)
            self.assertEqual('My scripts (imported 2)', kept[1]['name'])
            very_long = group('A' * 100)
            renamed = merge([very_long], [very_long])[1]['name']
            self.assertLessEqual(len(renamed), 100)
            self.assertNotEqual(very_long['name'], renamed)
            replacement = group('my SCRIPTS')
            replacement['buttons'][0]['command'] = 'pwd'
            self.assertEqual('pwd', merge(original, [replacement], replace=True)[0]['buttons'][0]['command'])
            self.assertEqual([first], original)
            for invalid in ('{"format":"bashdock-command-presets","version":2,"groups":[]}',
                            '{not json}', json.dumps(dict(format='bashdock-command-presets', version=1,
                                                     groups=[group('Git essentials')]))):
                path.write_text(invalid, encoding='utf-8')
                with self.assertRaises(ValueError):
                    read_import(path)
            path.write_bytes(b' ' * (1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, '1 MB'):
                read_import(path)

    def test_manager_edits_copy_builtins_and_applies_only_on_save(self):
        saved = []
        manager = PresetManager([group()], lambda groups: saved.append(copy.deepcopy(groups)) or True)
        self.assertEqual(GROUPS[0].name, manager.name.text())
        self.assertTrue(manager.name.isReadOnly())
        manager.copy_group()
        self.assertEqual(2, len(manager.personal))
        self.assertIn('(copy)', manager.name.text())
        manager.name.setText('Personal Git')
        manager.buttons.setCurrentRow(0)
        self.assertIn(GROUPS[0].buttons[0].command, manager.preview.toPlainText())
        manager.groups.setCurrentRow(len(GROUPS))
        self.assertIn('printf "café"', manager.preview.toPlainText())
        manager.name.setText('Renamed group')
        self.assertEqual('Renamed group', manager.personal[0]['name'])
        editor = PresetButtonEditor(manager.personal[0]['buttons'][0])
        self.assertTrue(editor.timing.isChecked())
        self.assertTrue(editor.confirm.isChecked())
        editor.command.setPlainText('pwd')
        editor.commit()
        self.assertEqual('pwd', editor.result_data['command'])
        self.assertIn('printf "café"', manager.personal[0]['buttons'][0]['command'])
        manager.commit()
        self.assertEqual(QDialog.DialogCode.Accepted, manager.result())
        self.assertEqual(manager.personal, saved[0])

    def test_manager_import_preview_and_export_keeps_commands_literal(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'from-friend.json', Path(folder) / 'mine.json'
            source.write_bytes(export_bytes([group()]))
            manager = PresetManager([])
            def review(dialog):
                self.assertIn('printf "café"', dialog.findChild(QPlainTextEdit).toPlainText())
                return QDialog.DialogCode.Accepted
            with patch.object(QDialog, 'exec', review):
                self.assertTrue(manager.import_file(source))
            self.assertEqual([group()], manager.personal)
            self.assertTrue(manager.export_file(target, [manager.personal[0]]))
            self.assertEqual([group()], read_import(target))
            self.assertTrue(manager.export_file(target, [manager.personal[0]]))
            self.assertEqual(1, len(manager.personal))

    def test_import_cancel_and_failed_save_leave_personal_library_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.json'
            source.write_bytes(export_bytes([group('Friend')]))
            existing = [group()]
            manager = PresetManager(existing, lambda groups: False)
            with patch.object(QDialog, 'exec', return_value=QDialog.DialogCode.Rejected):
                self.assertFalse(manager.import_file(source))
            self.assertEqual(existing, manager.personal)
            manager.copy_group()
            self.assertEqual(2, len(manager.personal))
            manager.commit()
            self.assertNotEqual(QDialog.DialogCode.Accepted, manager.result())
            self.assertEqual([group()], existing)

    def test_picker_managed_groups_preserve_selection_and_apply_independent_copies(self):
        original = group()
        saved = []
        picker = PresetPicker([], personal_groups=[original], save_groups=lambda groups: saved.append(copy.deepcopy(groups)) or True)
        picker.entries.item(0).setCheckState(Qt.CheckState.Checked)
        def manage(dialog):
            dialog.personal.append(group('Shared scripts'))
            dialog.commit()
            return dialog.result()
        with patch.object(PresetManager, 'exec', manage):
            picker.manage_groups()
        self.assertEqual(1, len(saved))
        self.assertIn((0, 0), picker.selected)
        self.assertEqual(len(GROUPS) + 2, picker.groups.count())
        picker.groups.setCurrentRow(len(GROUPS) + 1)
        picker.entries.item(0).setCheckState(Qt.CheckState.Checked)
        picker.commit()
        self.assertEqual(2, len(picker.result_data['buttons']))
        self.assertTrue(all(button.get('timing', False) for button in picker.result_data['buttons'][1:]))
        picker.result_data['buttons'][0]['command'] = 'edited'
        self.assertIn('printf "café"', saved[0][0]['buttons'][0]['command'])

    def test_manager_add_edit_delete_button_updates_only_personal_group(self):
        manager = PresetManager([group()])
        manager.groups.setCurrentRow(len(GROUPS))
        def add(editor):
            editor.label.setText('Second')
            editor.command.setPlainText('echo another')
            editor.commit()
            return editor.result()
        with patch.object(PresetButtonEditor, 'exec', add):
            manager.add_button()
        self.assertEqual(2, len(manager.personal[0]['buttons']))
        self.assertEqual('Second', manager.buttons.currentItem().text())
        def edit(editor):
            editor.command.setPlainText('echo revised')
            editor.commit()
            return editor.result()
        with patch.object(PresetButtonEditor, 'exec', edit):
            manager.edit_button()
        self.assertEqual('echo revised', manager.personal[0]['buttons'][1]['command'])
        manager.delete_button()
        self.assertEqual(1, len(manager.personal[0]['buttons']))
        with patch('bashdock.preset_manager.QMessageBox.warning') as warning:
            manager.delete_button()
        warning.assert_called_once()
        self.assertEqual(1, len(manager.personal[0]['buttons']))
