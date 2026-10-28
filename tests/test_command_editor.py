"""Command authoring, validation and keyboard behavior without a shell."""
import os
import sys
from unittest.mock import patch

if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox
from bashdock.command_editor import CommandEditor
from qt_lifecycle import GuiTestCase


class CommandEditorTests(GuiTestCase):
    def test_literal_body_is_preserved_without_trimming_or_execution(self):
        body = '\n  printf "%s" "café 世界"\n\n\t# indentation\nprintf end\n'
        editor = CommandEditor(' Build ', body)
        self.assertEqual(body, editor.command.toPlainText())
        editor.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
        self.assertEqual(QDialog.DialogCode.Accepted, editor.result())
        self.assertEqual({'label': ' Build ', 'command': body}, editor.result_data)

    def test_enter_and_tab_edit_body_and_escape_cancels(self):
        editor = CommandEditor('Build', 'first')
        editor.show()
        editor.command.setFocus()
        editor.command.moveCursor(editor.command.textCursor().MoveOperation.End)
        QTest.keyClick(editor.command, Qt.Key.Key_Return)
        QTest.keyClick(editor.command, Qt.Key.Key_Tab)
        QTest.keyClicks(editor.command, 'second')
        self.assertEqual('first\n\tsecond', editor.command.toPlainText())
        self.assertIsNone(editor.result_data)
        QTest.keyClick(editor.command, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(editor.command.hasFocus())
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
