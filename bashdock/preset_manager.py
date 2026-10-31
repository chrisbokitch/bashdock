"""Manage app-wide personal command groups without changing running tabs."""
import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from . import config
from .command_presets import GROUPS
from .preset_library import copy_builtin, export_bytes, merge, read_import


class PresetButtonEditor(QDialog):
    def __init__(self, button=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Edit preset button' if button else 'Add preset button')
        self.result_data = None
        button = button or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.label = QLineEdit(button.get('label', ''))
        self.description = QLineEdit(button.get('description', ''))
        self.command = QPlainTextEdit(button.get('command', ''))
        self.command.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.command.setMinimumHeight(140)
        self.timing = QCheckBox('Show execution time')
        self.timing.setChecked(button.get('timing', False))
        self.confirm = QCheckBox('Confirm before using')
        self.confirm.setChecked(button.get('confirm', False))
        self.message = QLineEdit(button.get('confirmation_message', config.DEFAULT_CONFIRMATION_MESSAGE))
        self.message.setEnabled(self.confirm.isChecked())
        self.confirm.toggled.connect(self.message.setEnabled)
        form.addRow('Button label', self.label)
        form.addRow('Description', self.description)
        form.addRow('Bash command', self.command)
        form.addRow(self.timing)
        form.addRow(self.confirm)
        form.addRow('Confirmation message', self.message)
        layout.addLayout(form)
        note = QLabel('A preset only stores a command. Applying it does not run it.')
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(600, 350)

    def commit(self):
        data = dict(label=self.label.text(), command=self.command.toPlainText(),
                    description=self.description.text(), timing=self.timing.isChecked(),
                    confirm=self.confirm.isChecked(),
                    confirmation_message=self.message.text() or config.DEFAULT_CONFIRMATION_MESSAGE)
        try:
            config.validate_buttons([data])
            if len(data['description']) > 500:
                raise ValueError('Preset button description must be at most 500 characters.')
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot save preset button', str(error))
            return
        self.result_data = data
        self.accept()


class PresetManager(QDialog):
    def __init__(self, personal_groups, on_save=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Manage preset groups')
        self.resize(860, 600)
        self.personal = copy.deepcopy(personal_groups)
        self.on_save = on_save
        self.loading = False
        outer = QVBoxLayout(self)
        note = QLabel('Built-in groups can be copied. Save keeps personal groups for all tabs; '
                      'applied buttons remain independent.')
        note.setWordWrap(True)
        outer.addWidget(note)
        columns = QHBoxLayout()
        left = QVBoxLayout()
        self.groups = QListWidget()
        self.groups.setAccessibleName('Built-in and personal preset groups')
        left.addWidget(self.groups, 1)
        for label, method, attr in (('New group…', self.new_group, 'new_group_control'),
                                    ('Copy group', self.copy_group, 'copy_group_control'),
                                    ('Delete group', self.delete_group, 'delete_group_control'),
                                    ('Import groups…', self.import_groups, 'import_control'),
                                    ('Export groups…', self.export_groups, 'export_control')):
            button = QPushButton(label)
            button.clicked.connect(method)
            left.addWidget(button)
            setattr(self, attr, button)
        columns.addLayout(left, 1)
        right = QVBoxLayout()
        form = QFormLayout()
        self.name = QLineEdit()
        self.description = QLineEdit()
        self.requirements = QLineEdit()
        for label, widget in (('Name', self.name), ('Description', self.description), ('Requires', self.requirements)):
            form.addRow(label, widget)
            widget.textChanged.connect(self.metadata_changed)
        right.addLayout(form)
        self.buttons = QListWidget()
        self.buttons.setAccessibleName('Buttons in selected preset group')
        right.addWidget(self.buttons, 1)
        row = QHBoxLayout()
        for label, method, attr in (('Add button…', self.add_button, 'add_button_control'),
                                    ('Edit button…', self.edit_button, 'edit_button_control'),
                                    ('Delete button', self.delete_button, 'delete_button_control')):
            button = QPushButton(label)
            button.clicked.connect(method)
            row.addWidget(button)
            setattr(self, attr, button)
        right.addLayout(row)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName('Exact preset command and confirmation preview')
        self.preview.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        right.addWidget(self.preview, 1)
        columns.addLayout(right, 2)
        outer.addLayout(columns, 1)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(self.commit)
        actions.rejected.connect(self.reject)
        outer.addWidget(actions)
        self.groups.currentRowChanged.connect(self.show_group)
        self.buttons.currentRowChanged.connect(self.show_button)
        self.refresh()

    def current_group(self):
        index = self.groups.currentRow()
        if index < 0:
            return None
        return GROUPS[index] if index < len(GROUPS) else self.personal[index - len(GROUPS)]

    def personal_index(self):
        return self.groups.currentRow() - len(GROUPS)

    def refresh(self, selection=None):
        if selection is None:
            selection = self.groups.currentRow()
        self.loading = True
        self.groups.clear()
        for group in GROUPS:
            self.groups.addItem(group.name + ' · Built-in')
        for group in self.personal:
            self.groups.addItem(group['name'])
        self.loading = False
        self.groups.setCurrentRow(max(0, min(selection, self.groups.count() - 1)))
        self.show_group(self.groups.currentRow())

    def show_group(self, index):
        if self.loading or index < 0:
            return
        group = self.current_group()
        if group is None:
            return
        custom = index >= len(GROUPS)
        self.loading = True
        self.name.setText(group['name'] if custom else group.name)
        self.description.setText(group['description'] if custom else group.description)
        self.requirements.setText(group['requirements'] if custom else group.requirements)
        for widget in (self.name, self.description, self.requirements):
            widget.setReadOnly(not custom)
        self.buttons.clear()
        for button in (group['buttons'] if custom else group.buttons):
            self.buttons.addItem(button['label'] if custom else button.label)
        self.loading = False
        self.buttons.setCurrentRow(0)
        for widget in (self.delete_group_control, self.add_button_control,
                       self.edit_button_control, self.delete_button_control):
            widget.setEnabled(custom)

    def metadata_changed(self):
        if self.loading or self.personal_index() < 0:
            return
        group = self.personal[self.personal_index()]
        group.update(name=self.name.text(), description=self.description.text(),
                     requirements=self.requirements.text())
        self.groups.currentItem().setText(group['name'] or '(unnamed)')

    def show_button(self, row):
        group = self.current_group()
        if group is None or row < 0:
            self.preview.clear()
            return
        button = (group['buttons'][row] if self.personal_index() >= 0 else group.buttons[row])
        command = button['command'] if isinstance(button, dict) else button.command
        description = button.get('description', '') if isinstance(button, dict) else button.description
        confirm = button.get('confirm', False) if isinstance(button, dict) else button.confirm
        timing = button.get('timing', False) if isinstance(button, dict) else button.timing
        message = button.get('confirmation_message', config.DEFAULT_CONFIRMATION_MESSAGE) if isinstance(button, dict) else button.message
        self.preview.setPlainText(f'{description}\n\n{command}\n\nConfirm before using: '
                                  + (message if confirm else 'off') + '\nShow execution time: '
                                  + ('on' if timing else 'off'))

    def unique_name(self, name):
        occupied = {group.name.casefold() for group in GROUPS} | {
            group['name'].strip().casefold() for group in self.personal}
        if name.casefold() not in occupied:
            return name
        index = 2
        while True:
            postfix = f' ({index})'
            candidate = name[:100 - len(postfix)] + postfix
            if candidate.casefold() not in occupied:
                return candidate
            index += 1

    def new_group(self):
        name, accepted = QInputDialog.getText(self, 'New preset group', 'Group name:')
        if not accepted or not name.strip():
            return
        editor = PresetButtonEditor(parent=self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            editor.deleteLater()
            return
        self.personal.append(dict(name=self.unique_name(name.strip()), description='', requirements='',
                                  buttons=[editor.result_data]))
        editor.deleteLater()
        self.refresh(len(GROUPS) + len(self.personal) - 1)

    def copy_group(self):
        group = self.current_group()
        if group is None:
            return
        if self.personal_index() < 0:
            result = copy_builtin(group)
        else:
            result = copy.deepcopy(group)
            result['name'] += ' (copy)'
        result['name'] = self.unique_name(result['name'])
        self.personal.append(result)
        self.refresh(len(GROUPS) + len(self.personal) - 1)

    def delete_group(self):
        index = self.personal_index()
        if index < 0 or index >= len(self.personal):
            return
        if QMessageBox.question(self, 'Delete preset group?',
                                f'Delete the personal preset group “{self.personal[index]["name"]}”? '
                                'Buttons already added to tabs will stay.',
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del self.personal[index]
            self.refresh(min(self.groups.currentRow(), len(GROUPS) + len(self.personal) - 1))

    def add_button(self):
        if self.personal_index() < 0:
            return
        editor = PresetButtonEditor(parent=self)
        if editor.exec() == QDialog.DialogCode.Accepted:
            self.personal[self.personal_index()]['buttons'].append(editor.result_data)
            self.show_group(self.groups.currentRow())
            self.buttons.setCurrentRow(self.buttons.count() - 1)
        editor.deleteLater()

    def edit_button(self):
        index, row = self.personal_index(), self.buttons.currentRow()
        if index < 0 or row < 0:
            return
        editor = PresetButtonEditor(self.personal[index]['buttons'][row], self)
        if editor.exec() == QDialog.DialogCode.Accepted:
            self.personal[index]['buttons'][row] = editor.result_data
            self.show_group(self.groups.currentRow())
            self.buttons.setCurrentRow(row)
        editor.deleteLater()

    def delete_button(self):
        index, row = self.personal_index(), self.buttons.currentRow()
        if index < 0 or row < 0:
            return
        if len(self.personal[index]['buttons']) == 1:
            QMessageBox.warning(self, 'Cannot delete last button', 'A preset group needs at least one button.')
            return
        del self.personal[index]['buttons'][row]
        self.show_group(self.groups.currentRow())
        self.buttons.setCurrentRow(min(row, self.buttons.count() - 1))

    def import_groups(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Import preset groups', '', 'JSON files (*.json)')
        if filename:
            self.import_file(filename)

    def import_file(self, filename):
        try:
            imported = read_import(filename)
        except (ValueError, OSError, UnicodeError) as error:
            QMessageBox.warning(self, 'Cannot import preset groups', str(error))
            return False
        preview = QDialog(self)
        preview.setWindowTitle('Review imported preset groups')
        layout = QVBoxLayout(preview)
        label = QLabel('Review the exact commands and confirmation messages. Importing stores them; it does not run them.')
        label.setWordWrap(True)
        layout.addWidget(label)
        contents = QPlainTextEdit()
        contents.setReadOnly(True)
        contents.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        contents.setPlainText('\n\n'.join(
            f"{group['name']} — {group['description']}\nRequires: {group['requirements']}\n" +
            '\n'.join(f"{button['label']}: {button['command']}\n"
                      f"Confirm: {button.get('confirmation_message', config.DEFAULT_CONFIRMATION_MESSAGE) if button.get('confirm', False) else 'off'}"
                      for button in group['buttons']) for group in imported))
        layout.addWidget(contents, 1)
        replace = QCheckBox('Replace personal groups with matching names (otherwise keep both)')
        replace.setEnabled(any(group['name'].strip().casefold() == old['name'].strip().casefold()
                               for group in imported for old in self.personal))
        layout.addWidget(replace)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton('Import groups', QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(preview.accept)
        buttons.rejected.connect(preview.reject)
        layout.addWidget(buttons)
        preview.resize(700, 500)
        accepted = preview.exec() == QDialog.DialogCode.Accepted
        if accepted:
            try:
                updated = merge(self.personal, imported, replace.isChecked())
            except ValueError as error:
                QMessageBox.warning(self, 'Cannot import preset groups', str(error))
                accepted = False
            else:
                self.personal = updated
                self.refresh(len(GROUPS) + len(updated) - 1)
        preview.deleteLater()
        return accepted

    def export_groups(self):
        if not self.personal:
            QMessageBox.information(self, 'No personal groups', 'Create or import a personal group first.')
            return
        choose = QDialog(self)
        choose.setWindowTitle('Select preset groups to export')
        layout = QVBoxLayout(choose)
        list_widget = QListWidget()
        for index, group in enumerate(self.personal):
            item = QListWidgetItem(group['name'])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if index == self.personal_index() else Qt.CheckState.Unchecked)
            list_widget.addItem(item)
        layout.addWidget(list_widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(choose.accept)
        buttons.rejected.connect(choose.reject)
        layout.addWidget(buttons)
        chosen = []
        if choose.exec() == QDialog.DialogCode.Accepted:
            chosen = [group for index, group in enumerate(self.personal)
                      if list_widget.item(index).checkState() == Qt.CheckState.Checked]
        choose.deleteLater()
        if not chosen:
            return
        filename, _ = QFileDialog.getSaveFileName(self, 'Export preset groups', 'bashdock-presets.json', 'JSON files (*.json)')
        if filename:
            self.export_file(filename, chosen)

    def export_file(self, filename, chosen):
        try:
            target = Path(filename)
            if target.resolve() in (config.config_path().resolve(), config.backup_path().resolve()):
                raise ValueError('Choose a separate file outside the active settings and backup files.')
            config.atomic_write(target, export_bytes(chosen))
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, 'Cannot export preset groups', str(error))
            return False
        return True

    def commit(self):
        try:
            config.validate_preset_groups(self.personal)
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot save preset groups', str(error))
            return
        if self.on_save is not None and not self.on_save(self.personal):
            return
        self.accept()
