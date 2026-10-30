"""Confirm the button's message, with optional inspection of its literal command."""
from math import ceil

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QToolButton, QVBoxLayout


class CommandConfirmation(QDialog):
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.setWindowTitle(entry['label'])
        self.resize(620, 1)
        layout = QVBoxLayout(self)
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setText(entry['confirmation_message'])
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.details = QToolButton()
        self.details.setText("Show command")
        self.details.setCheckable(True)
        self.details.setArrowType(Qt.ArrowType.RightArrow)
        self.details.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.details.setStyleSheet("""
            QToolButton { border: 0; background: transparent; padding: 2px; }
            QToolButton:hover, QToolButton:focus { color: #70dcc2; }
        """)
        self.details.toggled.connect(self.toggle_command)
        layout.addWidget(self.details, 0, Qt.AlignmentFlag.AlignLeft)
        self.command = QPlainTextEdit()
        self.command.setAccessibleName("Command to run")
        self.command.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.command.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.command.setReadOnly(True)
        self.command.setPlainText(entry['command'])
        self.command.horizontalScrollBar().rangeChanged.connect(self.update_command_height)
        self.update_command_height()
        self.command.hide()
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

    def toggle_command(self, expanded):
        self.details.setText("Hide command" if expanded else "Show command")
        self.details.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.command.setVisible(expanded)
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())

    def update_command_height(self, *args):
        height = (14 * self.command.fontMetrics().lineSpacing()
                  + ceil(2 * self.command.document().documentMargin())
                  + 2 * self.command.frameWidth() + 1)
        horizontal = self.command.horizontalScrollBar()
        if horizontal.maximum() > horizontal.minimum():
            height += horizontal.sizeHint().height()
        self.command.setFixedHeight(height)
