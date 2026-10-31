"""Command authoring, validation and keyboard behavior without a shell."""
import os
import sys
from unittest.mock import patch

if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel
from bashdock.command_editor import CommandEditor
from bashdock.command_confirmation import CommandConfirmation
from qt_lifecycle import GuiTestCase


class CommandEditorTests(GuiTestCase):
    def test_literal_body_is_preserved_without_trimming_or_execution(self):
        body = '\n  printf "%s" "café 世界"\n\n\t# indentation\nprintf end\n'
        editor = CommandEditor(' Build ', body)
        self.assertEqual(body, editor.command.toPlainText())
        editor.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
        self.assertEqual(QDialog.DialogCode.Accepted, editor.result())
        self.assertEqual({'label': ' Build ', 'command': body, 'description': '',
                          'confirm': False, 'timing': False,
                          'confirmation_message': 'Are you sure?'}, editor.result_data)

    def test_optional_description_is_editable_and_validated_on_one_line(self):
        from bashdock.config import validate_buttons
        editor = CommandEditor('Build', 'npm run build', description='Build the web app')
        self.assertEqual('Build the web app', editor.description.text())
        editor.description.setText('Build for deployment')
        editor.commit()
        self.assertEqual('Build for deployment', editor.result_data['description'])
        validate_buttons([dict(label='Legacy', command='pwd')])
        for value in (None, 42, 'a\nb', 'x' * 501):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'descriptions'):
                validate_buttons([dict(label='Build', command='npm run build', description=value)])

    def test_timing_is_opt_in_and_round_trips_without_affecting_confirmation(self):
        from bashdock.config import validate_buttons
        editor = CommandEditor('Test', 'npm test')
        self.assertFalse(editor.timing.isChecked())
        editor.timing.setChecked(True)
        editor.commit()
        self.assertTrue(editor.result_data['timing'])
        self.assertFalse(editor.result_data['confirm'])
        restored = CommandEditor('Test', 'npm test', timing=True)
        self.assertTrue(restored.timing.isChecked())
        restored.timing.setChecked(False)
        restored.commit()
        self.assertFalse(restored.result_data['timing'])
        for value in (0, 1, 'true', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'execution time'):
                validate_buttons([dict(label='Test', command='npm test', timing=value)])

    def test_confirmation_toggle_disables_message_and_retains_custom_text(self):
        editor = CommandEditor('Build', 'pwd')
        self.assertFalse(editor.confirm.isChecked())
        self.assertFalse(editor.confirmation_message.isEnabled())
        self.assertFalse(editor.confirmation_hint.isEnabled())
        self.assertEqual('Are you sure?', editor.confirmation_message.text())
        editor.confirm.setChecked(True)
        self.assertTrue(editor.confirmation_message.isEnabled())
        self.assertTrue(editor.confirmation_hint.isEnabled())
        editor.confirmation_message.setText('Deploy this version?')
        editor.confirm.setChecked(False)
        self.assertFalse(editor.confirmation_message.isEnabled())
        editor.commit()
        self.assertFalse(editor.result_data['confirm'])
        self.assertEqual('Deploy this version?', editor.result_data['confirmation_message'])
        restored = CommandEditor('Build', 'pwd', confirm=True,
                                 confirmation_message=editor.result_data['confirmation_message'])
        self.assertTrue(restored.confirmation_message.isEnabled())
        self.assertEqual('Deploy this version?', restored.confirmation_message.text())
        restored.confirmation_message.clear()
        restored.commit()
        self.assertEqual('Are you sure?', restored.result_data['confirmation_message'])

    def test_confirmation_shows_literal_text_and_cancel_is_default(self):
        entry = {'label': '<b>Build</b>', 'command': '\n  echo "café"\n\tpwd\n',
                 'confirmation_message': '<b>Are you sure?</b>'}
        for action in ('enter', 'escape', 'close', 'run'):
            with self.subTest(action=action):
                dialog = CommandConfirmation(entry)
                self.assertEqual(entry['label'], dialog.windowTitle())
                self.assertTrue(dialog.command.isReadOnly())
                self.assertEqual(entry['command'], dialog.command.toPlainText())
                labels = dialog.findChildren(QLabel)
                self.assertEqual(entry['confirmation_message'], labels[0].text())
                self.assertEqual(1, len(labels))
                self.assertTrue(all(label.textFormat() == Qt.TextFormat.PlainText for label in labels))
                self.assertTrue(dialog.cancel_button.isDefault())
                self.assertFalse(dialog.run_button.isDefault())
                dialog.show()
                self.app.processEvents()
                self.assertTrue(dialog.command.isHidden())
                if action == 'enter':
                    QTest.keyClick(dialog, Qt.Key.Key_Return)
                elif action == 'escape':
                    QTest.keyClick(dialog, Qt.Key.Key_Escape)
                elif action == 'close':
                    dialog.close()
                else:
                    dialog.run_button.click()
                expected = QDialog.DialogCode.Accepted if action == 'run' else QDialog.DialogCode.Rejected
                self.assertEqual(expected, dialog.result())
                self.assertFalse(dialog.isVisible())

    def test_command_disclosure_expands_and_collapses_without_accepting_or_changing_body(self):
        body = '\n'.join(f'printf "café {i}"' for i in range(20))
        dialog = CommandConfirmation(dict(label='Clean up', command=body,
                                          confirmation_message='Delete untracked files and folders?'))
        dialog.show()
        self.app.processEvents()
        collapsed = dialog.height()
        self.assertFalse(dialog.details.isChecked())
        self.assertEqual('Show command', dialog.details.text())
        for _ in range(2):
            dialog.details.setFocus()
            QTest.keyClick(dialog.details, Qt.Key.Key_Space)
            self.app.processEvents()
            self.assertTrue(dialog.command.isVisible())
            self.assertTrue(dialog.details.isChecked())
            self.assertEqual('Hide command', dialog.details.text())
            self.assertGreater(dialog.height(), collapsed)
            self.assertEqual(Qt.ArrowType.DownArrow, dialog.details.arrowType())
            self.assertGreater(dialog.command.verticalScrollBar().maximum(), 0)
            dialog.command.verticalScrollBar().setValue(dialog.command.verticalScrollBar().maximum())
            dialog.details.click()
            self.app.processEvents()
            self.assertTrue(dialog.command.isHidden())
            self.assertEqual(collapsed, dialog.height())
            self.assertEqual(Qt.ArrowType.RightArrow, dialog.details.arrowType())
            self.assertTrue(dialog.isVisible())
            self.assertNotEqual(QDialog.DialogCode.Accepted, dialog.result())
            self.assertTrue(dialog.cancel_button.isDefault())
            self.assertEqual(body, dialog.command.toPlainText())
        dialog.cancel_button.click()
        self.assertEqual(QDialog.DialogCode.Rejected, dialog.result())

    def test_enter_and_tab_edit_body_and_escape_cancels(self):
        editor = CommandEditor('Build', 'first')
        editor.show()
        editor.command.setFocus()
        self.app.processEvents()
        self.assertTrue(editor.command.hasFocus())
        editor.command.moveCursor(editor.command.textCursor().MoveOperation.End)
        QTest.keyClick(editor.command, Qt.Key.Key_Return)
        QTest.keyClick(editor.command, Qt.Key.Key_Tab)
        QTest.keyClicks(editor.command, 'second')
        self.assertEqual('first\n\tsecond', editor.command.toPlainText())
        self.assertIsNone(editor.result_data)
        QTest.keyClick(editor.command, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(editor.confirm.hasFocus())
        editor.command.setFocus()
        QTest.keyClick(editor.command, Qt.Key.Key_Tab,
                       Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(editor.description.hasFocus())
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.assertEqual(QDialog.DialogCode.Rejected, editor.result())
        self.assertIsNone(editor.result_data)

    def test_invalid_definitions_remain_open_and_cancel_or_close_has_no_result(self):
        for label, body in (('', 'pwd'), ('Build', '\n \t'), ('Build', 'echo\x1b[31m')):
            with self.subTest(label=label, body=body):
                editor = CommandEditor(label, body)
                with patch('bashdock.command_editor.QMessageBox.warning') as warning:
                    editor.commit()
                warning.assert_called_once()
                self.assertIsNone(editor.result_data)
                editor.close()
                self.assertEqual(QDialog.DialogCode.Rejected, editor.result())
        editor = CommandEditor('Build', 'pwd')
        editor.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()
        self.assertIsNone(editor.result_data)
