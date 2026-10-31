"""Curated definitions and the preset picker never execute commands."""
import copy
import os
import sys
from unittest.mock import patch

if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QMessageBox, QScrollArea
from bashdock.command_presets import GROUPS
from bashdock.config import validate_buttons
from bashdock.preset_picker import PresetPicker
from qt_lifecycle import GuiTestCase


class CommandPresetTests(GuiTestCase):
    def test_catalog_definitions_are_valid_independent_and_keep_confirmation_messages(self):
        self.assertEqual(5, len(GROUPS))
        definitions = [button.definition() for group in GROUPS for button in group.buttons]
        self.assertEqual(18, len(definitions))
        validate_buttons(definitions)
        self.assertEqual(GROUPS[0].buttons[0].description, definitions[0]['description'])
        self.assertEqual(18, len({(entry['label'], entry['command']) for entry in definitions}))
        expected = {'git restore --worktree .', 'git clean -fd', 'black . && ruff check --fix .',
                    'python -m pip freeze > requirements.txt', 'npm ci', 'docker compose stop'}
        self.assertEqual(expected, {entry['command'] for entry in definitions if entry['confirm']})
        for entry in definitions:
            if entry['confirm']:
                self.assertNotEqual('Are you sure?', entry['confirmation_message'])
        definitions[0]['command'] = 'edited copy'
        self.assertEqual('git status --short --branch', GROUPS[0].buttons[0].command)

    def test_group_selection_survives_navigation_and_previews_exact_commands(self):
        picker = PresetPicker([])
        self.assertFalse(picker.apply_button.isEnabled())
        self.assertIsNone(picker.result_data)
        self.assertEqual(GROUPS[0].buttons[0].command, picker.command.toPlainText())
        self.assertTrue(picker.command.isReadOnly())
        self.assertIn('Requires:', picker.requirements.text())
        picker.select_all.click()
        self.assertEqual({(0, row) for row in range(4)}, picker.selected)
        picker.groups.setCurrentRow(1)
        picker.entries.setCurrentRow(2)
        self.assertEqual('git clean -fd', picker.command.toPlainText())
        self.assertIn(GROUPS[1].buttons[2].message, picker.confirmation.text())
        self.assertIn('Confirmation enabled', picker.entries.item(2).text())
        picker.entries.item(2).setCheckState(Qt.CheckState.Checked)
        picker.groups.setCurrentRow(0)
        self.assertTrue(all(picker.entries.item(row).checkState() == Qt.CheckState.Checked for row in range(4)))
        picker.apply_button.click()
        self.assertEqual(QDialog.DialogCode.Accepted, picker.result())
        self.assertFalse(picker.result_data['replace'])
        self.assertEqual([b.definition() for b in GROUPS[0].buttons] + [GROUPS[1].buttons[2].definition()],
                         picker.result_data['buttons'])

    def test_exact_duplicates_are_marked_skipped_by_group_select_but_can_be_added_explicitly(self):
        existing = [GROUPS[0].buttons[0].definition()]
        existing[0]['confirmation_message'] = 'A user customization'
        original = copy.deepcopy(existing)
        picker = PresetPicker(existing)
        self.assertIn('Already added', picker.entries.item(0).text())
        self.assertEqual(Qt.CheckState.Unchecked, picker.entries.item(0).checkState())
        picker.select_all.click()
        self.assertEqual({(0, 1), (0, 2), (0, 3)}, picker.selected)
        picker.entries.item(0).setCheckState(Qt.CheckState.Checked)
        picker.commit()
        self.assertEqual(4, len(picker.result_data['buttons']))
        self.assertEqual(original, existing)
        picker.result_data['buttons'][0]['command'] = 'customized copy'
        self.assertEqual('git status --short --branch', GROUPS[0].buttons[0].command)

    def test_partial_selection_and_group_clear_and_no_selection_cannot_apply(self):
        picker = PresetPicker([])
        picker.commit()
        self.assertIsNone(picker.result_data)
        picker.entries.item(1).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(Qt.CheckState.PartiallyChecked, picker.select_all.checkState())
        picker.select_all.click()
        self.assertEqual(4, len(picker.selected))
        picker.select_all.click()
        self.assertEqual(set(), picker.selected)
        self.assertFalse(picker.apply_button.isEnabled())
        picker.commit()
        self.assertIsNone(picker.result_data)

    def test_replacement_previews_removals_and_requires_explicit_confirmation(self):
        existing = [dict(label='<Custom>', command='echo "café"\nprintf next', confirm=True,
                         confirmation_message='Keep this?')]
        original = copy.deepcopy(existing)
        picker = PresetPicker(existing)
        picker.entries.item(1).setCheckState(Qt.CheckState.Checked)
        picker.replace.setChecked(True)
        self.assertIn('1 will be removed', picker.replace.text())
        self.assertEqual('<Custom>\necho "café"\nprintf next', picker.removals.toPlainText())
        self.assertEqual('Replace with selected buttons', picker.apply_button.text())
        with patch('bashdock.preset_picker.QMessageBox.question', return_value=QMessageBox.StandardButton.No) as question:
            picker.commit()
            self.assertEqual(QMessageBox.StandardButton.No, question.call_args.args[-1])
        self.assertIsNone(picker.result_data)
        self.assertEqual(original, existing)
        with patch('bashdock.preset_picker.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            picker.commit()
        self.assertEqual(dict(replace=True, buttons=[GROUPS[0].buttons[1].definition()]), picker.result_data)

    def test_cancel_and_close_return_no_definitions_and_checkbox_keyboard_works(self):
        for close in (False, True):
            picker = PresetPicker([])
            picker.show()
            picker.entries.setFocus()
            self.app.processEvents()
            QTest.keyClick(picker.entries, Qt.Key.Key_Space)
            self.assertIn((0, 0), picker.selected)
            if close:
                picker.close()
            else:
                QTest.keyClick(picker, Qt.Key.Key_Escape)
            self.assertEqual(QDialog.DialogCode.Rejected, picker.result())
            self.assertIsNone(picker.result_data)

    def test_short_picker_keeps_actions_visible_and_scrolls_the_review_content(self):
        picker = PresetPicker([GROUPS[0].buttons[0].definition()])
        picker.groups.setCurrentRow(1)
        picker.select_all.click()
        picker.replace.setChecked(True)
        picker.resize(580, 400)
        picker.show()
        for _ in range(8):
            self.app.processEvents()
        button = picker.apply_button
        bounds = QRect(button.mapTo(picker, QPoint(0, 0)), button.size())
        self.assertTrue(picker.rect().contains(bounds))
        self.assertTrue(button.isVisible())
        scroll = picker.findChild(QScrollArea)
        self.assertTrue(scroll.verticalScrollBar().isVisible())
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        self.app.processEvents()
        self.assertTrue(picker.removals.isVisible())
