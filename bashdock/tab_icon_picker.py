"""Keyboard-accessible selection of bundled tab icons."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QLabel, QListWidget,
    QListWidgetItem, QVBoxLayout,
)
from . import tab_icons
from .workspaces import LIST_STYLE


class TabIconPicker(QDialog):
    def __init__(self, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Choose tab icon')
        self.resize(600, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Choose a shape or symbol for this tab.'))
        self.icons = QListWidget()
        self.icons.setAccessibleName('Tab icons')
        self.icons.setStyleSheet(LIST_STYLE)
        self.icons.setViewMode(QListWidget.ViewMode.IconMode)
        self.icons.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.icons.setMovement(QListWidget.Movement.Static)
        self.icons.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.icons.setIconSize(QSize(28, 28))
        self.icons.setGridSize(QSize(88, 72))
        self.icons.setWordWrap(True)
        self.icons.setSpacing(2)
        for key, (name, _) in tab_icons.CATALOG.items():
            item = QListWidgetItem(tab_icons.icon(key), name, self.icons)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(name)
            if key == selected:
                self.icons.setCurrentItem(item)
        self.icons.itemDoubleClicked.connect(lambda item: self.accept())
        layout.addWidget(self.icons)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_icon(self):
        return self.icons.currentItem().data(Qt.ItemDataRole.UserRole)
