"""Keyboard-accessible selection of bundled tab icons."""
from PySide6.QtCore import Qt, QSize, QEvent, QSignalBlocker, Slot
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QLabel, QListWidget,
    QListWidgetItem, QVBoxLayout, QLineEdit,
)
from . import tab_icons
from .tab_icon_catalog import search_text
from .workspaces import LIST_STYLE


class TabIconPicker(QDialog):
    def __init__(self, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Choose tab icon')
        self.resize(600, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Choose a shape or symbol for this tab.'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search icons…')
        self.search.setAccessibleName('Search icons')
        self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)
        self.empty_state = QLabel('No matching icons. Try a different search.')
        self.empty_state.setWordWrap(True)
        self.empty_state.hide()
        layout.addWidget(self.empty_state)
        self._selected_key = selected if selected in tab_icons.CATALOG else next(iter(tab_icons.CATALOG))
        self._items = {}
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
            self._items[key] = item
            if key == self._selected_key:
                self.icons.setCurrentItem(item)
        self.icons.itemDoubleClicked.connect(lambda item: self.accept())
        layout.addWidget(self.icons)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.icons.currentItemChanged.connect(self.remember_selection)
        self.search.textChanged.connect(self.filter_icons)
        self.search.setFocus(Qt.FocusReason.OtherFocusReason)

    @Slot(str)
    def filter_icons(self, text):
        terms = text.casefold().split()
        with QSignalBlocker(self.icons):
            for key, item in self._items.items():
                item.setHidden(not all(term in search_text(key) for term in terms))
            # Filtering must not silently choose a different icon. Keep the
            # remembered choice so clearing the search restores its selection.
            current = self._items[self._selected_key]
            current = None if current.isHidden() else current
            self.icons.clearSelection()
            self.icons.setCurrentItem(current)
            if current is not None:
                current.setSelected(True)
        self.empty_state.setVisible(all(item.isHidden() for item in self._items.values()))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(current is not None)

    @Slot(QListWidgetItem, QListWidgetItem)
    def remember_selection(self, current, previous):
        if current is not None and not current.isHidden():
            self._selected_key = current.data(Qt.ItemDataRole.UserRole)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            current is not None and not current.isHidden())

    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Down:
            visible = [item for item in self._items.values() if not item.isHidden()]
            if visible:
                if self.icons.currentItem() is None:
                    self.icons.setCurrentItem(visible[0])
                self.icons.setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return super().eventFilter(watched, event)

    @Slot()
    def accept(self):
        current = self.icons.currentItem()
        if current is not None and not current.isHidden():
            super().accept()

    def selected_icon(self):
        current = self.icons.currentItem()
        return current.data(Qt.ItemDataRole.UserRole) if current is not None and not current.isHidden() else None
