"""Terminal defaults and optional per-tab appearance and interaction presets."""
import copy
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, QFontComboBox,
                              QSpinBox, QComboBox, QCheckBox, QPushButton, QColorDialog,
                              QDialogButtonBox, QMessageBox, QWidget)
from . import terminal_preferences


class TerminalSettingsDialog(QDialog):
    def __init__(self, settings, parent=None, *, defaults=None, inherit=False):
        super().__init__(parent)
        per_tab = defaults is not None
        self.default_values = terminal_preferences.validated(defaults) if per_tab else terminal_preferences.defaults()
        self.custom_values = copy.deepcopy(terminal_preferences.validated(settings))
        self.setWindowTitle("Tab Terminal Settings" if per_tab else "Terminal Defaults")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        note = QLabel("Applies to this tab when you save Configure tab. Its shell keeps running."
                      if per_tab else "Applies to tabs using terminal defaults. Tabs with custom settings keep their own preferences.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.use_defaults = QCheckBox("Use terminal defaults") if per_tab else None
        if per_tab:
            layout.addWidget(self.use_defaults)
        self.controls = QWidget()
        form = QFormLayout(self.controls)
        form.setContentsMargins(0, 0, 0, 0)
        self.font = QFontComboBox()
        self.font.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        form.addRow("Font", self.font)
        self.size = QSpinBox()
        self.size.setRange(8, 48)
        self.size.setSuffix(" px")
        form.addRow("Font size", self.size)
        self.colors = {}
        self.color_buttons = {}
        for key, label in (("foreground", "Text colour"), ("background", "Background colour"),
                           ("cursor_color", "Cursor colour"), ("selection_color", "Selection colour")):
            button = QPushButton()
            button.clicked.connect(lambda checked=False, key=key: self.choose_color(key))
            self.color_buttons[key] = button
            form.addRow(label, button)
        self.cursor = QComboBox()
        for label, value in (("Block", "block"), ("Underline", "underline"), ("Bar", "bar")):
            self.cursor.addItem(label, value)
        form.addRow("Cursor style", self.cursor)
        self.blink = QCheckBox("Blink cursor")
        form.addRow("", self.blink)
        self.scrollback = QSpinBox()
        self.scrollback.setRange(0, 100000)
        self.scrollback.setSuffix(" lines")
        form.addRow("Scrollback", self.scrollback)
        self.copy_selection = QCheckBox("Copy selected text automatically")
        form.addRow("", self.copy_selection)
        self.right_paste = QCheckBox("Paste on right-click")
        form.addRow("", self.right_paste)
        layout.addWidget(self.controls)
        help_text = QLabel("Ctrl+Shift+C / Ctrl+Shift+V always copy and paste. Multiline pastes "
                           "still ask for confirmation. Hold Shift to select text in mouse-aware "
                           "programs. Reducing scrollback discards older lines.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                  QDialogButtonBox.StandardButton.Cancel |
                                  QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.restore_button = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        if per_tab:
            self.restore_button.setText("Use defaults")
            self.restore_button.clicked.connect(lambda: self.use_defaults.setChecked(True))
        else:
            self.restore_button.clicked.connect(lambda: self.set_values(terminal_preferences.defaults()))
        layout.addWidget(buttons)
        self.set_values(terminal_preferences.validated(settings))
        if per_tab:
            self.use_defaults.toggled.connect(self.toggle_defaults)
            self.use_defaults.setChecked(inherit)

    def toggle_defaults(self, checked):
        if checked:
            self.custom_values = self.raw_values()
            self.set_values(self.default_values)
        else:
            self.set_values(self.custom_values)
        self.controls.setEnabled(not checked)
        self.restore_button.setEnabled(not checked)

    def set_values(self, settings):
        self.font.setCurrentFont(QFont(settings["font_family"]))
        self.font.setCurrentText(settings["font_family"])
        self.size.setValue(settings["font_size"])
        for key in self.color_buttons:
            self.set_color(key, settings[key])
        self.cursor.setCurrentIndex(self.cursor.findData(settings["cursor_style"]))
        self.blink.setChecked(settings["cursor_blink"])
        self.scrollback.setValue(settings["scrollback"])
        self.copy_selection.setChecked(settings["copy_on_select"])
        self.right_paste.setChecked(settings["right_click_paste"])

    def set_color(self, key, value):
        self.colors[key] = value
        self.color_buttons[key].setText(value.upper())
        text = "#10141c" if QColor(value).lightness() > 128 else "#dde4ef"
        self.color_buttons[key].setStyleSheet(f"background:{value};color:{text};")

    def choose_color(self, key):
        color = QColorDialog.getColor(QColor(self.colors[key]), self, "Choose terminal colour")
        if color.isValid():
            self.set_color(key, color.name())

    def raw_values(self):
        return dict(self.colors,
            font_family=self.font.currentText(), font_size=self.size.value(),
            cursor_style=self.cursor.currentData(), cursor_blink=self.blink.isChecked(),
            scrollback=self.scrollback.value(), copy_on_select=self.copy_selection.isChecked(),
            right_click_paste=self.right_paste.isChecked())

    def values(self):
        return terminal_preferences.validated(self.raw_values())

    def accept(self):
        try:
            self.values()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid terminal settings", str(error))
            return
        super().accept()
