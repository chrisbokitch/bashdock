"""Review the exact command and destination before any shell input is sent."""
from math import ceil

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout


class CommandConfirmation(QDialog):
    def __init__(self, entry, tab_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Run command?")
        self.resize(620, 1)
        layout = QVBoxLayout(self)
        for text in (entry['confirmation_message'],
                     f"Button: {entry['label']}\nTab: {tab_name}"):
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setText(text)
            label.setWordWrap(True)
            layout.addWidget(label)
        self.command = QPlainTextEdit()
        self.command.setAccessibleName("Command to run")
        self.command.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.command.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.command.setReadOnly(True)
        self.command.setPlainText(entry['command'])
        self.command.horizontalScrollBar().rangeChanged.connect(self.update_command_height)
        self.update_command_height()
        layout.addWidget(self.command)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.run_button = self.buttons.addButton("Run command", QDialogButtonBox.ButtonRole.AcceptRole)
        self.run_button.setAutoDefault(False)
        self.cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_button.setDefault(True)
        self.cancel_button.setFocus()
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.resize(620, self.sizeHint().height())

    def update_command_height(self, *args):
        height = (3 * self.command.fontMetrics().lineSpacing()
                  + ceil(2 * self.command.document().documentMargin())
                  + 2 * self.command.frameWidth() + 1)
        horizontal = self.command.horizontalScrollBar()
        if horizontal.maximum() > horizontal.minimum():
            height += horizontal.sizeHint().height()
        self.command.setFixedHeight(height)
