"""Save subsets of tabs and manage reusable named workspaces."""
import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

LIST_STYLE = """
    QListWidget { background:#10141c; border:1px solid #3c4b60; border-radius:4px; }
    QListWidget::item { padding:6px 8px; }
    QListWidget::item:selected { background:#273344; color:#dde4ef; }
"""


class SaveWorkspaceDialog(QDialog):
    def __init__(self, tabs, parent=None, name="", updating=False):
        super().__init__(parent)
        self.setWindowTitle("Update workspace" if updating else "Save selected tabs")
        self.resize(460, 380)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Workspace name"))
        self.name = QLineEdit(name)
        self.name.setReadOnly(updating)
        self.name.setPlaceholderText("For example: BashDock Development")
        self.name.setAccessibleName("Workspace name")
        layout.addWidget(self.name)
        note = QLabel("Choose the current tabs to save, in their current order.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs = QListWidget()
        self.tabs.setStyleSheet(LIST_STYLE)
        self.tabs.setAccessibleName("Tabs to save")
        for tab in tabs:
            item = QListWidgetItem(tab["name"], self.tabs)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setToolTip(tab["current_folder"])
        layout.addWidget(self.tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_indexes(self):
        return [i for i in range(self.tabs.count()) if self.tabs.item(i).checkState() == Qt.CheckState.Checked]

    def accept(self):
        if not self.name.text().strip() or not self.selected_indexes():
            QMessageBox.warning(self, "Cannot save workspace", "Enter a name and select at least one tab.")
            return
        super().accept()


class WorkspacesDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Workspaces")
        self.resize(650, 420)
        layout = QVBoxLayout(self)
        intro = QLabel("Save groups of tabs for different projects. Open adds tabs; Replace closes your current tabs after confirmation.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setStyleSheet(LIST_STYLE)
        self.list.setAccessibleName("Saved workspaces")
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.currentRowChanged.connect(self.selection_changed)
        body.addWidget(self.list, 1)
        actions = QVBoxLayout()
        save = QPushButton("Save selected tabs…")
        save.clicked.connect(self.save_new)
        actions.addWidget(save)
        self.update_button = QPushButton("Update from current tabs…")
        self.update_button.clicked.connect(self.update_selected)
        actions.addWidget(self.update_button)
        self.rename_button = QPushButton("Rename…")
        self.rename_button.clicked.connect(self.rename_selected)
        actions.addWidget(self.rename_button)
        self.delete_button = QPushButton("Delete…")
        self.delete_button.clicked.connect(self.delete_selected)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        body.addLayout(actions)
        layout.addLayout(body)
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        note = QLabel("Shells start fresh. Commands and SSH connections are not run automatically.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QHBoxLayout()
        self.open_button = QPushButton("Open — add tabs")
        self.open_button.clicked.connect(lambda: self.open_selected(False))
        buttons.addWidget(self.open_button)
        self.replace_button = QPushButton("Replace current tabs…")
        self.replace_button.clicked.connect(lambda: self.open_selected(True))
        buttons.addWidget(self.replace_button)
        buttons.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.refresh()

    def entries(self):
        return self.window.data.get("workspaces", [])

    def refresh(self, selected=0):
        self.list.clear()
        self.list.addItems([entry["name"] for entry in self.entries()])
        if self.list.count():
            self.list.setCurrentRow(min(max(selected, 0), self.list.count() - 1))
        self.selection_changed()

    def selection_changed(self, *args):
        index = self.list.currentRow()
        exists = 0 <= index < len(self.entries())
        for button in (self.update_button, self.rename_button, self.delete_button,
                       self.open_button, self.replace_button):
            button.setEnabled(exists)
        self.details.setText(
            "Tabs: " + ", ".join(tab["name"] for tab in self.entries()[index]["tabs"])
            if exists else "No saved workspaces yet. Save some of your current tabs to get started.")

    def choose_tabs(self, updating=False):
        index = self.list.currentRow()
        name = self.entries()[index]["name"] if updating else ""
        dialog = SaveWorkspaceDialog(self.window.snapshot()["tabs"], self, name, updating)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            saved = self.window.save_workspace(dialog.name.text(), dialog.selected_indexes(),
                                                index if updating else None)
            if saved:
                self.refresh(index if updating else len(self.entries()) - 1)
                break
        dialog.deleteLater()

    def save_new(self):
        self.choose_tabs()

    def update_selected(self):
        if QMessageBox.question(self, "Update saved workspace?",
                "Replace this saved workspace with a selection of your current tabs? Your running shells will stay open.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.choose_tabs(updating=True)

    def rename_selected(self):
        index = self.list.currentRow()
        name, accepted = QInputDialog.getText(self, "Rename workspace", "Workspace name:",
                                              text=self.entries()[index]["name"])
        if accepted:
            entries = copy.deepcopy(self.entries())
            entries[index]["name"] = name.strip()
            if self.window.store_workspaces(entries):
                self.refresh(index)

    def delete_selected(self):
        index = self.list.currentRow()
        if QMessageBox.question(self, "Delete saved workspace?",
                f"Delete '{self.entries()[index]['name']}'? Your open tabs will stay open.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            entries = copy.deepcopy(self.entries())
            del entries[index]
            if self.window.store_workspaces(entries):
                self.refresh(index)

    def open_selected(self, replace):
        if self.window.open_workspace(self.list.currentRow(), replace=replace):
            self.accept()
