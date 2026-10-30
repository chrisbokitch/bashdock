"""Edit a command definition without submitting anything to a terminal."""
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QCheckBox,
)

from .config import validate_buttons, DEFAULT_CONFIRMATION_MESSAGE


class CommandBody(QPlainTextEdit):
    leave_editor = Signal(bool)

    def keyPressEvent(self, event):
        if (event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.leave_editor.emit(bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            event.accept()
            return
        super().keyPressEvent(event)


class CommandEditor(QDialog):
    def __init__(self, label, command, parent=None, *, confirm=False,
                 confirmation_message=DEFAULT_CONFIRMATION_MESSAGE, staged=True, timing=False):
        super().__init__(parent)
        self.setWindowTitle("Edit command button")
        self.resize(680, 460)
        self.result_data = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.label = QLineEdit(label)
        form.addRow("Button &label", self.label)
        layout.addLayout(form)
        heading = QLabel("Bash &command")
        self.command = CommandBody()
        self.command.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.command.setTabStopDistance(self.command.fontMetrics().horizontalAdvance(' ') * 4)
        self.command.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.command.setTabChangesFocus(False)
        self.command.setPlainText(command)
        heading.setBuddy(self.command)
        layout.addWidget(heading)
        layout.addWidget(self.command, 1)
        confirmation = QHBoxLayout()
        self.confirm = QCheckBox("Confirm before using")
        self.confirm.setChecked(confirm)
        self.confirmation_message = QLineEdit(confirmation_message)
        self.confirmation_message.setAccessibleName("Confirmation message")
        self.confirmation_message.setToolTip("Message shown before this command button runs")
        self.confirmation_message.setEnabled(confirm)
        self.confirmation_message.setStyleSheet(
            "QLineEdit:disabled { color:#77818f;background:#1b222d; }")
        self.confirm.toggled.connect(self.confirmation_message.setEnabled)
        self.command.leave_editor.connect(lambda backwards:
            self.label.setFocus(Qt.FocusReason.BacktabFocusReason) if backwards else
            self.confirm.setFocus(Qt.FocusReason.TabFocusReason))
        confirmation.addWidget(self.confirm)
        confirmation.addWidget(self.confirmation_message, 1)
        layout.addLayout(confirmation)
        self.confirmation_hint = QLabel("Describe what will happen and any consequences, so the confirmation is useful.")
        self.confirmation_hint.setWordWrap(True)
        self.confirmation_hint.setEnabled(confirm)
        self.confirm.toggled.connect(self.confirmation_hint.setEnabled)
        layout.addWidget(self.confirmation_hint)
        self.timing = QCheckBox("Show execution time")
        self.timing.setChecked(timing)
        self.timing.setToolTip("Show this button's elapsed time and exit status in the footer")
        layout.addWidget(self.timing)
        note = QLabel("Enter adds a line; Tab inserts indentation. Use Ctrl+Tab to leave the editor.\n"
                      "Runs in this tab's existing shell at an empty prompt. Bash syntax controls\n"
                      "whether later commands run after a failure. Saving here only stages edits;\n"
                      "Save Configure tab to keep them. Nothing runs while editing." if staged else
                      "Enter adds a line; Tab inserts indentation. Use Ctrl+Tab to leave the editor.\n"
                      "Save keeps this button immediately. Nothing runs while editing.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def commit(self):
        message = self.confirmation_message.text()
        data = {"label": self.label.text(), "command": self.command.toPlainText(),
                "confirm": self.confirm.isChecked(), "timing": self.timing.isChecked(),
                "confirmation_message": message if message.strip() else DEFAULT_CONFIRMATION_MESSAGE}
        try:
            validate_buttons([data])
        except ValueError as error:
            QMessageBox.warning(self, "Cannot save command button", str(error))
            return
        self.result_data = data
        self.accept()
