"""Native clipboard boundary tests without a shell or WebEngine process."""
import os
import sys
import unittest
from unittest.mock import patch, Mock

if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
from bashdock.terminal import Bridge, Terminal


class ClipboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clipboard = self.app.clipboard()
        self.original = QMimeData()
        mime = self.clipboard.mimeData()
        if mime is not None:
            for kind in mime.formats():
                self.original.setData(kind, mime.data(kind))
        self.parent = QWidget()
        self.bridge = Bridge(self.parent)
        self.pasted = []
        self.bridge.clipboardPaste.connect(self.pasted.append)

    def tearDown(self):
        if self.app.platformName() == 'offscreen':
            # This clipboard is process-local. Leaving Python-created MIME
            # data owned by the offscreen plugin can crash Qt at shutdown.
            self.clipboard.clear()
        else:
            self.clipboard.setMimeData(self.original)
        self.parent.deleteLater()
        self.app.processEvents()

    def test_copy_and_single_line_paste_preserve_unicode_and_do_not_add_enter(self):
        value = 'caf\u00e9 \u03bb \u4e2d\u6587 \U0001f600'
        self.bridge.copy(value)
        self.assertEqual(value, self.clipboard.text())
        with patch('bashdock.terminal.QMessageBox.question') as question:
            self.bridge.requestPaste()
            question.assert_not_called()
        self.assertEqual([value], self.pasted)
        self.assertEqual(value, self.clipboard.text())

    def test_multiline_lf_crlf_and_cr_require_confirmation_and_preserve_exact_text(self):
        for separator in ('\n', '\r\n', '\r'):
            for answer in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes):
                with self.subTest(separator=repr(separator), answer=answer):
                    self.pasted.clear()
                    value = f'first{separator}caf\u00e9{separator}'
                    self.clipboard.setText(value)
                    with patch('bashdock.terminal.QMessageBox.question', return_value=answer) as question:
                        self.bridge.requestPaste()
                    arguments = question.call_args.args
                    self.assertIs(self.parent, arguments[0])
                    self.assertEqual('Paste multiple lines?', arguments[1])
                    self.assertEqual(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     arguments[3])
                    self.assertEqual(QMessageBox.StandardButton.No, arguments[4])
                    self.assertEqual([value] if answer == QMessageBox.StandardButton.Yes else [], self.pasted)
                    self.assertEqual(value, self.clipboard.text())

    def test_empty_clipboard_does_not_prompt_or_inject_a_newline(self):
        self.clipboard.clear()
        with patch('bashdock.terminal.QMessageBox.question') as question:
            self.bridge.requestPaste()
            question.assert_not_called()
        self.assertEqual([''], self.pasted)

    def test_only_button_writes_quote_literal_tabs_and_keep_the_first_character_guard(self):
        from types import SimpleNamespace
        receiver = SimpleNamespace(process=Mock(), trace=Mock(), problem=Mock())
        text = "printf '%s' 'literal\ttab'\r"
        Terminal.write(receiver, text, command_id=7)
        receiver.process.write.assert_called_once_with(" \x7fprintf '%s' 'literal\x16\ttab'\r")
        receiver.process.write.reset_mock()
        Terminal.write(receiver, text)
        receiver.process.write.assert_called_once_with(text)
