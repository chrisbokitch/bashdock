"""Choose copied, editable command definitions to stage in Configure tab."""
import copy

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
    QScrollArea, QFrame,
)

from .command_presets import GROUPS
from .preset_library import as_group
from .preset_manager import PresetManager


def text_label(text=''):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class ReviewContent(QWidget):
    def heightForWidth(self, width):
        # Scroll only when controls cannot fit, rather than preserving the
        # lists' preferred height and hiding the summary unnecessarily.
        return self.layout().minimumHeightForWidth(width)


class PresetPicker(QDialog):
    def __init__(self, existing, parent=None, *, personal_groups=None, save_groups=None):
        super().__init__(parent)
        self.setWindowTitle('Command presets')
        available = self.screen().availableGeometry()
        self.resize(min(840, available.width() - 60), min(650, available.height() - 80))
        self.result_data = None
        self.existing = copy.deepcopy(existing)
        self.personal_groups = copy.deepcopy(personal_groups or [])
        self.save_groups = save_groups
        self.catalog = tuple(GROUPS) + tuple(as_group(group) for group in self.personal_groups)
        self.existing_pairs = {(entry['label'], entry['command']) for entry in existing}
        self.selected = set()
        self.group_index = -1
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        content = ReviewContent()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.setStyleSheet('''
            QListWidget { background:#10141c;border:1px solid #3c4b60; }
            QListWidget::item { padding:6px; }
            QListWidget::item:selected { background:#365e66;color:#ffffff; }
        ''')
        layout.addWidget(text_label('Choose buttons for this tab. Review them in Configure tab before saving.'))
        columns = QWidget()
        column_layout = QHBoxLayout(columns)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(12)
        self.groups = QListWidget()
        self.groups.setAccessibleName('Preset groups')
        self.groups.setFixedWidth(180)
        for group in self.catalog:
            item = QListWidgetItem(group.name)
            item.setToolTip(group.description)
            self.groups.addItem(item)
        column_layout.addWidget(self.groups)
        panel = QWidget()
        right = QVBoxLayout(panel)
        right.setContentsMargins(0, 0, 0, 0)
        self.description = text_label()
        self.requirements = text_label()
        right.addWidget(self.description)
        right.addWidget(self.requirements)
        self.select_all = QCheckBox('Select all new buttons in this group')
        self.select_all.setTristate(True)
        right.addWidget(self.select_all)
        self.entries = QListWidget()
        self.entries.setAccessibleName('Preset buttons. Press Space to select a button.')
        self.entries.setWordWrap(True)
        self.entries.setMinimumHeight(150)
        self.entries.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.entries.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right.addWidget(self.entries, 2)
        self.preview_title = text_label()
        right.addWidget(self.preview_title)
        self.command = QPlainTextEdit()
        self.command.setAccessibleName('Preset command preview')
        self.command.setReadOnly(True)
        self.command.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.command.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.command.setMinimumHeight(65)
        right.addWidget(self.command, 1)
        self.confirmation = text_label()
        right.addWidget(self.confirmation)
        column_layout.addWidget(panel, 1)
        layout.addWidget(columns, 1)
        self.manage_button = QPushButton('Manage groups…')
        self.manage_button.clicked.connect(self.manage_groups)
        layout.addWidget(self.manage_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.replace = QCheckBox(f'Replace existing buttons ({len(existing)} will be removed)')
        self.replace.setEnabled(bool(existing))
        layout.addWidget(self.replace)
        self.removals = QPlainTextEdit()
        self.removals.setAccessibleName('Existing buttons that will be removed')
        self.removals.setReadOnly(True)
        self.removals.setPlainText('\n\n'.join(f"{entry['label']}\n{entry['command']}" for entry in existing))
        self.removals.setFixedHeight(65)
        self.removals.hide()
        layout.addWidget(self.removals)
        self.summary = text_label()
        layout.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.apply_button = buttons.addButton('Add selected buttons', QDialogButtonBox.ButtonRole.AcceptRole)
        self.apply_button.setEnabled(False)
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.groups.currentRowChanged.connect(self.show_group)
        self.entries.currentRowChanged.connect(self.show_preview)
        self.entries.itemChanged.connect(self.selection_changed)
        self.select_all.clicked.connect(self.toggle_group)
        self.replace.toggled.connect(self.update_selection)
        self.groups.setCurrentRow(0)

    def already_added(self, button):
        return (button.label, button.command) in self.existing_pairs

    def manage_groups(self):
        manager = PresetManager(self.personal_groups, self.save_groups, self)
        if manager.exec() == QDialog.DialogCode.Accepted:
            selected = {(self.catalog[group].name, self.catalog[group].buttons[row].label,
                         self.catalog[group].buttons[row].command)
                        for group, row in self.selected}
            current = self.catalog[self.group_index].name if self.group_index >= 0 else ''
            self.personal_groups = copy.deepcopy(manager.personal)
            self.catalog = tuple(GROUPS) + tuple(as_group(group) for group in self.personal_groups)
            self.selected = {(i, j) for i, group in enumerate(self.catalog)
                             for j, button in enumerate(group.buttons)
                             if (group.name, button.label, button.command) in selected}
            self.groups.clear()
            for group in self.catalog:
                item = QListWidgetItem(group.name)
                item.setToolTip(group.description)
                self.groups.addItem(item)
            self.groups.setCurrentRow(next((i for i, group in enumerate(self.catalog)
                                            if group.name == current), len(GROUPS) if self.personal_groups else 0))
            self.show_group(self.groups.currentRow())
        manager.deleteLater()

    def show_group(self, index):
        if index < 0:
            return
        self.group_index = index
        group = self.catalog[index]
        self.description.setText(group.description)
        self.requirements.setText('Requires: ' + group.requirements)
        blocker = QSignalBlocker(self.entries)
        self.entries.clear()
        for row, button in enumerate(group.buttons):
            suffix = ' — Already added' if self.already_added(button) else ''
            if button.confirm:
                suffix += ' — Confirmation enabled'
            item = QListWidgetItem(button.label + suffix + '\n' + button.description)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if (index, row) in self.selected else Qt.CheckState.Unchecked)
            item.setToolTip(button.command)
            self.entries.addItem(item)
        del blocker
        self.entries.setCurrentRow(0)
        self.show_preview(0)
        self.update_selection()

    def show_preview(self, row):
        if self.group_index < 0 or row < 0:
            return
        button = self.catalog[self.group_index].buttons[row]
        self.preview_title.setText('Command preview: ' + button.label)
        self.command.setPlainText(button.command)
        confirmation = ('Confirm before using: ' + button.message if button.confirm else
                        'Confirm before using: off. You can change this in Edit command button.')
        self.confirmation.setText(confirmation + ('\nShow execution time: on' if button.timing else
                                                   '\nShow execution time: off'))

    def selection_changed(self, item):
        key = (self.group_index, self.entries.row(item))
        if item.checkState() == Qt.CheckState.Checked:
            self.selected.add(key)
        else:
            self.selected.discard(key)
        self.update_selection()

    def toggle_group(self, checked):
        blocker = QSignalBlocker(self.entries)
        for row, button in enumerate(self.catalog[self.group_index].buttons):
            key = (self.group_index, row)
            if not checked:
                self.selected.discard(key)
            elif self.replace.isChecked() or not self.already_added(button):
                self.selected.add(key)
            self.entries.item(row).setCheckState(Qt.CheckState.Checked if key in self.selected else Qt.CheckState.Unchecked)
        del blocker
        self.update_selection()

    def update_selection(self):
        if self.group_index < 0:
            return
        eligible = [(self.group_index, row) for row, button in enumerate(self.catalog[self.group_index].buttons)
                    if self.replace.isChecked() or not self.already_added(button)]
        count = sum(key in self.selected for key in eligible)
        state = (Qt.CheckState.Unchecked if count == 0 else Qt.CheckState.Checked if count == len(eligible)
                 else Qt.CheckState.PartiallyChecked)
        blocker = QSignalBlocker(self.select_all)
        self.select_all.setCheckState(state)
        self.select_all.setEnabled(bool(eligible))
        self.select_all.setText('Select all buttons in this group' if self.replace.isChecked() else
                                'Select all new buttons in this group')
        del blocker
        replacing = self.replace.isChecked()
        self.removals.setVisible(replacing)
        self.apply_button.setText('Replace with selected buttons' if replacing else 'Add selected buttons')
        self.apply_button.setEnabled(bool(self.selected))
        total = len(self.selected) if replacing else len(self.existing) + len(self.selected)
        self.summary.setText(f'{len(self.selected)} selected · {total} buttons after applying. '
                             'Nothing runs; Save Configure tab to keep changes.')

    def commit(self):
        if not self.selected:
            return
        if self.replace.isChecked() and self.existing:
            answer = QMessageBox.question(self, 'Replace command buttons?',
                f'Remove all {len(self.existing)} existing buttons and replace them with '
                f'{len(self.selected)} selected preset buttons?\n\n'
                'Changes will still need to be saved in Configure tab.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        definitions = [self.catalog[group].buttons[row].definition() for group, row in sorted(self.selected)]
        self.result_data = dict(buttons=definitions, replace=self.replace.isChecked())
        self.accept()
