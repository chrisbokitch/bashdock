"""Desktop window and transactional command/settings editor."""
import base64
import copy
import logging
import sys
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QTimer, Qt, Signal, QSize, QEvent, QUrl, QObject, QRectF, QPoint, QDir
from PySide6.QtGui import QAction, QIcon, QMouseEvent, QDesktopServices, QPainterPath, QRegion, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPlainTextEdit, QStyle,
    QHeaderView, QAbstractItemView, QTabWidget, QInputDialog, QCheckBox, QToolButton, QTabBar, QStatusBar, QMenu, QStyleOptionTab,
)

from . import config, terminal_preferences
from .input_diagnostics import recorder as input_recorder
from ._version import __version__
from .window_theme import install_titlebar_theme
from .external_shell import open_external
from .terminal_settings import TerminalSettingsDialog
from .workspaces import WorkspacesDialog

APP_ICON = Path(__file__).parent / "assets" / "bashdock.ico"


def create_terminal(parent):
    from .terminal import Terminal
    return Terminal(parent)


class MenuShadow(QWidget):
    """A click-through shadow outside the popup's clipped native window."""
    margin = 8

    def __init__(self, menu):
        super().__init__(menu, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint
                         | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("background:transparent;border:0;")

    def sync(self, menu):
        origin = menu.mapToGlobal(QPoint(0, 0))
        self.setGeometry(origin.x() - self.margin, origin.y() - self.margin,
                         menu.width() + 2 * self.margin, menu.height() + 2 * self.margin)
        if menu.isVisible():
            self.show()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel = QRectF(self.rect()).adjusted(self.margin, self.margin, -self.margin, -self.margin)
        outside = QPainterPath()
        outside.addRect(QRectF(self.rect()))
        inside = QPainterPath()
        inside.addRoundedRect(panel, 10, 10)
        painter.setClipPath(outside.subtracted(inside))
        painter.setPen(Qt.PenStyle.NoPen)
        # Layer faint rounded silhouettes into a soft, slightly lowered shadow.
        for spread in range(self.margin - 2, -1, -1):
            painter.setBrush(QColor(0, 0, 0, 10))
            painter.drawRoundedRect(panel.adjusted(-spread, 2 - spread, spread, 2 + spread),
                                    10 + spread, 10 + spread)


class PopupMenu(QMenu):
    """Use the existing left padding for ticks instead of a second text gutter."""
    def initStyleOption(self, option, action):
        super().initStyleOption(option, action)
        option.menuHasCheckableItems = False

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for action in self.actions():
            if not action.isVisible() or not action.isCheckable() or not action.isChecked():
                continue
            rect = self.actionGeometry(action)
            painter.setPen(QPen(QColor('#dde4ef' if action.isEnabled() else '#8995a7'), 1.5))
            x, y = rect.left() - 10, rect.center().y()
            painter.drawLine(x, y, x + 3, y + 3)
            painter.drawLine(x + 3, y + 3, x + 8, y - 3)


def add_popup(parent, title):
    menu = PopupMenu(title, parent)
    parent.addMenu(menu)
    return menu


class MenuCorners(QObject):
    """Keep native rounded clipping and the app-drawn shadow in sync."""
    def __init__(self, parent):
        super().__init__(parent)
        self.shadows = {}

    def attach(self, menu):
        self.shadows[menu] = MenuShadow(menu)
        menu.installEventFilter(self)

    def apply_mask(self, menu):
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(menu.rect()), 10, 10)
        menu.setMask(QRegion(shape.toFillPolygon().toPolygon()))
        if menu.isVisible():
            self.shadows[menu].sync(menu)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show:
            self.apply_mask(watched)
        elif event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            # Run after QMenu installs the native style's resize mask.
            QTimer.singleShot(0, watched, lambda: self.apply_mask(watched))
        elif event.type() == QEvent.Type.Hide:
            self.shadows[watched].hide()
        return False


class FooterBar(QStatusBar):
    """Keep the version at the left even while status/error messages are displayed."""
    update_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("footerVersion")
        self.version_label.setToolTip("BashDock version")
        self.message_label = QLabel()
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.addWidget(self.version_label)
        self.update_button = QPushButton()
        self.update_button.setObjectName("footerUpdate")
        self.update_button.setFlat(True)
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self.update_requested)
        self.update_button.hide()
        self.addWidget(self.update_button)
        self.addWidget(self.message_label, 1)
        self.clear_timer = QTimer(self)
        self.clear_timer.setSingleShot(True)
        self.clear_timer.timeout.connect(self.clearMessage)

    def show_update(self, version, ready=True, local=False):
        label = 'Local build' if local else 'Version'
        text = f"{label} {version} is ready — Restart to update" if ready else f"{label} {version} is available — Download update"
        self.update_button.setText(text)
        self.update_button.setToolTip("Save your workspace and restart to install the update." if ready else "Download the verified update in the background.")
        self.update_button.setAccessibleName(text)
        self.update_button.show()

    def showMessage(self, text, timeout=0):
        self.clear_timer.stop()
        self.message_label.setText(text)
        self.message_label.setToolTip(text)
        self.messageChanged.emit(text)
        if timeout > 0:
            self.clear_timer.start(timeout)

    def currentMessage(self):
        return self.message_label.text()

    def clearMessage(self):
        self.showMessage("")


class SettingsDialog(QDialog):
    def __init__(self, data, parent=None, *, terminal_defaults=None):
        super().__init__(parent)
        self.setWindowTitle("Configure tab")
        self.resize(780, 520)
        self.result_data = None
        self.original = copy.deepcopy(data)
        self.terminal_defaults = terminal_preferences.validated(
            terminal_preferences.defaults() if terminal_defaults is None else terminal_defaults)
        self.terminal_override = copy.deepcopy(data.get("terminal"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(data["name"])
        form.addRow("Tab name", self.name)
        self.bash = QLineEdit(QDir.toNativeSeparators(data["bash_path"] or config.find_bash()))
        self.folder = QLineEdit(QDir.toNativeSeparators(data["startup_folder"]))
        for label, edit, is_folder in (("Git Bash executable", self.bash, False),
                                        ("Startup folder", self.folder, True)):
            row = QHBoxLayout()
            row.addWidget(edit)
            browse = QPushButton("Browse…")
            browse.clicked.connect(lambda checked=False, e=edit, f=is_folder: self.browse(e, f))
            row.addWidget(browse)
            form.addRow(label, row)
        terminal_row = QHBoxLayout()
        terminal_button = QPushButton("Terminal settings…")
        terminal_button.clicked.connect(self.configure_terminal)
        terminal_row.addWidget(terminal_button)
        self.terminal_summary = QLabel()
        self.update_terminal_summary()
        terminal_row.addWidget(self.terminal_summary, 1)
        form.addRow("Terminal", terminal_row)
        layout.addLayout(form)
        note = QLabel("Buttons send commands to the active terminal. Use them at an empty shell prompt.\n"
                      "Buttons belong to this tab. The Git Bash executable is shared by all tabs.\n"
                      "Startup folder changes apply when you restart this shell.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Button label", "Bash command"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for button in data["buttons"]:
            self.add_row(button["label"], button["command"])
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        for label, callback in (("Add", lambda: self.add_row("New button", "pwd")),
                                ("Delete", self.delete_row),
                                ("Move left", lambda: self.move_row(-1)),
                                ("Move right", lambda: self.move_row(1))):
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_terminal_summary(self):
        self.terminal_summary.setText("Using terminal defaults" if self.terminal_override is None else "Custom settings for this tab")

    def configure_terminal(self):
        settings = terminal_preferences.effective({"terminal": self.terminal_override}, self.terminal_defaults)
        dialog = TerminalSettingsDialog(settings, self, defaults=self.terminal_defaults,
                                        inherit=self.terminal_override is None)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.terminal_override = None if dialog.use_defaults.isChecked() else dialog.values()
            self.update_terminal_summary()
        dialog.deleteLater()

    def browse(self, edit, folder):
        selected = (QFileDialog.getExistingDirectory(self, "Choose startup folder", edit.text())
                    if folder else QFileDialog.getOpenFileName(self, "Choose Git's bash.exe",
                        edit.text(), "Bash executable (bash.exe);;Executables (*.exe)")[0])
        if selected:
            edit.setText(QDir.toNativeSeparators(selected))

    def add_row(self, label, command):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(label))
        self.table.setItem(row, 1, QTableWidgetItem(command))
        self.table.selectRow(row)

    def delete_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def move_row(self, delta):
        row = self.table.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self.table.rowCount():
            return
        for col in range(2):
            first = self.table.takeItem(row, col)
            second = self.table.takeItem(target, col)
            self.table.setItem(row, col, second)
            self.table.setItem(target, col, first)
        self.table.selectRow(target)

    def commit(self):
        data = {"name": self.name.text().strip(), "bash_path": QDir.toNativeSeparators(self.bash.text().strip()),
                "current_folder": self.original["current_folder"],
                "terminal": copy.deepcopy(self.terminal_override),
                "startup_folder": QDir.toNativeSeparators(self.folder.text().strip()), "buttons": []}
        for row in range(self.table.rowCount()):
            data["buttons"].append({key: self.table.item(row, col).text()
                                    for col, key in enumerate(("label", "command"))})
        try:
            config.validate_tab(data)
            if not Path(data["bash_path"]).is_file() or Path(data["bash_path"]).name.lower() != "bash.exe":
                raise ValueError("Select Git for Windows' bash.exe (usually Git/bin/bash.exe).")
            if not Path(data["startup_folder"]).is_dir():
                raise ValueError("Select an existing startup folder.")
            if QDir.fromNativeSeparators(data["startup_folder"]) != QDir.fromNativeSeparators(self.original["startup_folder"]):
                data["current_folder"] = data["startup_folder"]
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Cannot save settings", str(error))
            return
        self.result_data = data
        self.accept()


class CommandScrollArea(QScrollArea):
    """Fit the button height, reserving scrollbar space only when needed."""
    def fit_height(self):
        if self.widget() is None:
            return
        size = self.widget().minimumSizeHint()
        height = max(1, size.height())
        if size.width() > self.viewport().width():
            height += self.horizontalScrollBar().sizeHint().height()
        if self.height() != height:
            self.setFixedHeight(height)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Resize):
            self.fit_height()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_height()


class ShellTopBorder(QWidget):
    """One shell-wide rule, open beneath the selected tab's interior."""
    def __init__(self, tab_bar, background, parent):
        super().__init__(parent)
        self.tab_bar = tab_bar
        self.background = background
        self.setFixedHeight(1)
        tab_bar.currentChanged.connect(self.refresh)
        tab_bar.tabMoved.connect(self.refresh)
        tab_bar.layout_changed.connect(self.refresh)

    def refresh(self, *args):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#3c4b60'))
        index = self.tab_bar.currentIndex()
        if index >= 0:
            tab = self.tab_bar.tabRect(index)
            left = self.mapFromGlobal(self.tab_bar.mapToGlobal(tab.topLeft())).x() + 1
            # The tab stylesheet leaves a 3px gap after each tab.
            right = self.mapFromGlobal(self.tab_bar.mapToGlobal(tab.topRight())).x() - 3
            painter.fillRect(left, 0, max(0, right - left), self.height(), QColor(self.background()))


class ShellTab(QWidget):
    """Each tab owns a shell, its button bar, and its saved profile."""
    configure_requested = Signal()

    def __init__(self, data, parent=None, terminal_factory=create_terminal):
        super().__init__(parent)
        self.data = copy.deepcopy(data)
        self.shell_bash_path = ""
        self.status = "Loading terminal…"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.top_border = ShellTopBorder(parent.tabs.tabBar(), lambda:
            terminal_preferences.effective(self.data, parent.data['terminal'])['background'], self)
        layout.addWidget(self.top_border)
        self.terminal = terminal_factory(self)
        layout.addWidget(self.terminal, 1)
        footer = QHBoxLayout()
        footer.setContentsMargins(3, 6, 3, 6)
        scroll = CommandScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bar = QWidget()
        self.bar_layout = QHBoxLayout(self.bar)
        self.bar_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.bar)
        self.bar.installEventFilter(scroll)
        footer.addWidget(scroll, 1)
        configure = QPushButton()
        configure.setObjectName("configureTab")
        configure.setIcon(QIcon(str(APP_ICON.parent / "settings.svg")))
        configure.setIconSize(QSize(18, 18))
        configure.setFixedWidth(36)
        configure.setToolTip("Configure tab…")
        configure.setAccessibleName("Configure tab…")
        configure.clicked.connect(self.configure_requested.emit)
        footer.addWidget(configure)
        layout.addLayout(footer)
        self.command_buttons = []
        self.build_buttons()

    def build_buttons(self):
        while self.bar_layout.count():
            item = self.bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.command_buttons = []
        for entry in self.data["buttons"]:
            button = QPushButton(entry["label"])
            button.setToolTip(entry["command"])
            # A mouse click should return input to this tab's terminal.
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda checked=False, command=entry["command"]:
                                   self.terminal.run_command(command))
            self.bar_layout.addWidget(button)
            self.command_buttons.append(button)
        self.bar_layout.addStretch()
        self.set_running(bool(self.terminal.process))

    def set_running(self, running):
        for button in self.command_buttons:
            button.setEnabled(running)


class TabStrip(QTabBar):
    """Reserve enough top-row height for the corner control and its padding."""
    layout_changed = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.top_inset = 0
        self.inset_pending = False
        self.selected_background = '#10141c'
        self.selected_foreground = '#dde4ef'
        self.terminal_themes = []
        self.currentChanged.connect(self.position_close_buttons)

    def set_terminal_themes(self, themes):
        self.terminal_themes = [terminal_preferences.inactive_tab_colors(theme) for theme in themes]
        for index, colors in enumerate(self.terminal_themes):
            color = themes[index]['foreground'] if index == self.currentIndex() else colors['foreground']
            self.setTabTextColor(index, QColor(color))
        self.update()

    def paintEvent(self, event):
        # Fill individual inactive tabs beneath Qt's transparent tab shapes.
        # Qt still draws borders, labels, focus, and movable-tab interactions.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(event.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        for index, colors in enumerate(self.terminal_themes):
            if index >= self.count() or index == self.currentIndex():
                continue
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            rect = QRectF(self.tabRect(index)).adjusted(0, self.top_inset, -3, 0)
            path = QPainterPath()
            path.moveTo(rect.left(), rect.bottom())
            path.lineTo(rect.left(), rect.top() + 6)
            path.quadTo(rect.left(), rect.top(), rect.left() + 6, rect.top())
            path.lineTo(rect.right() - 6, rect.top())
            path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + 6)
            path.lineTo(rect.right(), rect.bottom())
            path.closeSubpath()
            painter.setBrush(QColor(colors['hover'] if option.state & QStyle.StateFlag.State_MouseOver
                                    else colors['background']))
            painter.drawPath(path)
        painter.end()
        super().paintEvent(event)

    def set_terminal_colors(self, background, foreground):
        if (background, foreground) != (self.selected_background, self.selected_foreground) or not self.styleSheet():
            self.selected_background, self.selected_foreground = background, foreground
            self.apply_tab_style()

    def apply_tab_style(self):
        # Paint past the bottom clip so fractional scaling cannot antialias
        # the selected tab's edge against the tab-bar background.
        self.setStyleSheet(
            f'QTabBar::tab {{ margin-top:{self.top_inset}px; }} '
            f'QTabBar::tab:selected {{ background:{self.selected_background};'
            f'color:{self.selected_foreground};margin-bottom:-1px; }}')

    def corner_row_height(self):
        parent = self.parentWidget()
        if not isinstance(parent, QTabWidget):
            return 0
        corner = parent.cornerWidget(Qt.Corner.TopRightCorner)
        if corner is None:
            return 0
        # QTabWidget subtracts this style metric from the tab-bar height when
        # sizing corner widgets. Windows styles can reserve more than one pixel.
        base_height = parent.style().pixelMetric(QStyle.PixelMetric.PM_TabBarBaseHeight, None, parent)
        return corner.sizeHint().height() + max(0, base_height)

    def update_tab_inset(self):
        self.inset_pending = False
        parent = self.parentWidget()
        corner = parent.cornerWidget(Qt.Corner.TopRightCorner) if isinstance(parent, QTabWidget) else None
        if self.count() == 0 or corner is None:
            return
        compact_height = max(QTabBar.tabSizeHint(self, i).height() - self.top_inset
                             for i in range(self.count()))
        inset = max(0, self.corner_row_height() - compact_height)
        if inset != self.top_inset:
            self.top_inset = inset
            # Blank space belongs above compact tabs, so their bottoms still meet the shell.
            self.apply_tab_style()
            self.updateGeometry()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) and not self.inset_pending:
            self.inset_pending = True
            QTimer.singleShot(0, self.update_tab_inset)

    def tabLayoutChange(self):
        super().tabLayoutChange()
        self.position_close_buttons()
        self.layout_changed.emit()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            # Qt calls mousePressEvent after tabBarDoubleClicked returns. By
            # then the modal rename dialog has already consumed the release.
            # Finish that press so hovering cannot start dragging the tab.
            release = QMouseEvent(QEvent.Type.MouseButtonRelease, event.position(), event.globalPosition(),
                                  event.button(), Qt.MouseButton.NoButton, event.modifiers())
            super().mouseReleaseEvent(release)
        self.position_close_buttons()

    def position_close_buttons(self, *args):
        # Qt also lays out tab buttons when selection changes, without calling
        # tabLayoutChange. Reapply the same offset after either operation.
        inset = getattr(self, "top_inset", 0)
        for index in range(self.count()):
            close = self.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if close is not None:
                rect = self.tabRect(index)
                visible_top = rect.top() + inset
                visible_height = rect.height() - inset
                close.move(close.x(), visible_top + (visible_height - close.height()) // 2)

    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        size.setHeight(max(size.height(), self.corner_row_height()))
        return size

    def sizeHint(self):
        size = super().sizeHint()
        size.setHeight(max(size.height(), self.corner_row_height()))
        return size

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        size.setHeight(max(size.height(), self.sizeHint().height()))
        return size


class MainWindow(QMainWindow):
    def __init__(self, terminal_factory=create_terminal):
        super().__init__()
        install_titlebar_theme(QApplication.instance())
        self.terminal_factory = terminal_factory
        self.setWindowTitle("BashDock — Git Bash")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.resize(1120, 760)
        self.config_error = ""
        self.restoring = True
        self.closing = False
        self.update_restart = False
        self.updater = None
        try:
            self.data = config.load()
        except (OSError, ValueError) as error:
            self.data = config.defaults()
            self.config_error = str(error)
        self.allow_save = not bool(self.config_error)
        self.data["bash_path"] = self.data["bash_path"] or config.find_bash()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(350)
        self.save_timer.timeout.connect(self.persist)
        self.tabs = QTabWidget()
        self.tabs.setTabBar(TabStrip(self.tabs))
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.tabBar().tabMoved.connect(self.schedule_save)
        self.tabs.tabBar().tabMoved.connect(self.refresh_tab_colors)
        add = QPushButton()
        add.setObjectName("newTab")
        add.setIcon(QIcon(str(APP_ICON.parent / "tab-add.svg")))
        add.setIconSize(QSize(18, 18))
        add.setFixedWidth(36)
        add.setToolTip("New tab")
        add.setAccessibleName("New tab")
        add.clicked.connect(self.new_tab)
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(3, 0, 3, 3)
        corner_layout.addWidget(add)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(3, 3, 3, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        self.setCentralWidget(body)
        self.setStatusBar(FooterBar(self))
        self.statusBar().update_requested.connect(self.restart_for_update)
        # Keep Python wrappers alive as well as Qt ownership. Some supported
        # PySide versions otherwise destroy menus when temporary wrappers expire.
        self.manage_menu = add_popup(self.menuBar(), "Manage")
        menu = self.manage_menu
        for label, callback, shortcut in (
            ("New tab", self.new_tab, "Ctrl+Shift+T"),
            ("Rename tab…", lambda: self.rename_tab(self.tabs.currentIndex()), ""),
            ("Close tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+Shift+W"),
            ("Workspaces", self.manage_workspaces, ""),
            ("", None, ""),
            ("Open external shell", self.open_external, ""),
            ("Restart shell…", self.restart, ""),
            ("Interrupt (Ctrl+C)", self.interrupt, ""),
        ):
            if label == "Workspaces":
                self.workspaces_menu = add_popup(menu, label)
                self.workspaces_menu.aboutToShow.connect(self.refresh_workspaces_menu)
                self.refresh_workspaces_menu()
                continue
            if callback is None:
                menu.addSeparator()
                continue
            action = QAction(label, self)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(shortcut)
            menu.addAction(action)
        self.settings_menu = add_popup(self.menuBar(), "Settings")
        settings = self.settings_menu
        configure_action = QAction("Configure current tab…", self)
        configure_action.triggered.connect(self.configure)
        settings.addAction(configure_action)
        terminal_action = QAction("Terminal Defaults…", self)
        terminal_action.triggered.connect(self.configure_terminal)
        settings.addAction(terminal_action)
        settings.addSeparator()
        for label, callback in (
            ("Export settings…", self.export_settings),
            ("Import settings…", self.import_settings),
            ("Restore automatic backup…", self.restore_backup),
        ):
            action = QAction(label, self)
            action.triggered.connect(callback)
            settings.addAction(action)
        settings.addSeparator()
        self.confirm_exit_action = QAction("Confirm before quitting", self)
        self.confirm_exit_action.setCheckable(True)
        self.confirm_exit_action.setChecked(self.data["confirm_on_exit"])
        self.confirm_exit_action.toggled.connect(self.set_confirm_on_exit)
        settings.addAction(self.confirm_exit_action)
        self.updates_menu = add_popup(settings, "Updates")
        self.automatic_updates_action = QAction("Check automatically", self.updates_menu)
        self.download_updates_action = QAction("Download automatically", self.updates_menu)
        for action, key in ((self.automatic_updates_action, "automatic"), (self.download_updates_action, "download")):
            action.setCheckable(True)
            action.setChecked(self.data.get("updates", {}).get(key, True))
            action.toggled.connect(lambda checked, key=key: self.set_update_preference(key, checked))
            self.updates_menu.addAction(action)
        self.help_menu = add_popup(self.menuBar(), "Help")
        help_menu = self.help_menu
        about_action = QAction("About BashDock…", self)
        about_action.triggered.connect(self.show_about)
        self.check_updates_action = QAction("Check for updates…", self)
        self.check_updates_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(self.check_updates_action)
        diagnostic_action = QAction("Save diagnostic report…", self)
        diagnostic_action.triggered.connect(self.save_diagnostic_report)
        help_menu.addAction(diagnostic_action)
        help_menu.addSeparator()
        help_menu.addAction(about_action)
        # Older PySide bindings can delete a submenu when a temporary action
        # wrapper expires after QAction.menu() is called.
        self.menu_actions = tuple(menu.menuAction() for menu in
                                  (self.manage_menu, self.settings_menu, self.help_menu, self.workspaces_menu, self.updates_menu))
        for profile in self.data["tabs"]:
            self.add_tab(profile)
        self.tabs.setCurrentIndex(self.data["active_tab"])
        self.restoring = False
        self.tab_changed()
        self.setStyleSheet("""
            QMainWindow,QDialog,QWidget { background:#181e29;color:#dde4ef; }
            QMenu {
                background:#253144;color:#dde4ef;border:0;border-radius:10px;
                padding:10px 12px;
            }
            QMenuBar::item { background:transparent;border-radius:5px;padding:2px 6px; }
            QMenuBar::item:selected,QMenuBar::item:pressed { background:#3c4b60;color:#ffffff; }
            QMenu::item { padding:2px 0;background:transparent;border-radius:5px; }
            QMenu::right-arrow { image:url("MENU_ARROW");width:6px;height:10px; }
            QMenu::item:selected { background:#3c4b60;color:#ffffff; }
            QMenu::item:disabled { color:#8995a7; }
            QMenu::separator { height:1px; background:#3c4b60; margin:4px 0; }
            QPushButton { background:#273344;border:1px solid #3c4b60;border-radius:5px;padding:8px 12px; }
            QPushButton:hover { border-color:#70dcc2; }
            QPushButton:disabled { color:#77818f; }
            QPushButton#configureTab,QPushButton#newTab { background:#111b2b;padding:6px; }
            QLineEdit,QTableWidget { background:#10141c;selection-background-color:#365e66; }
            QLineEdit { padding:6px; }
            QStatusBar { background:#111b2b;border-top:1px solid #27384d; }
            QStatusBar::item { border:0; }
            QStatusBar QLabel { background:transparent;padding:3px 6px; }
            QLabel#footerVersion { color:#9baec4; }
            QStatusBar QPushButton#footerUpdate { color:#e7c35d;background:transparent;border:0;padding:3px 6px;text-align:left; }
            QStatusBar QPushButton#footerUpdate:hover { color:#f4dc85;text-decoration:underline;border:0; }
            QTabWidget::pane { border:0;top:0; }
            QTabWidget::tab-bar { left:3px; }
            QTabBar::tab {
                padding:6px 8px 3px;background:transparent;
                border:1px solid #3c4b60;border-bottom:0;
                border-top-left-radius:6px;border-top-right-radius:6px;
                margin-right:3px;margin-top:0;
            }
            QTabBar::tab:!selected:hover { background:transparent; }
            QTabBar::tab:selected {
                background:#181e29;color:#dde4ef;
                border-top:1px solid #53647c;
            }
            QToolButton#tabClose { border:0;padding:0;margin:0;border-radius:3px;background:transparent; }
            QToolButton#tabClose:hover { background:#3c4b60; }
        """.replace("MENU_ARROW", (APP_ICON.parent / "menu-arrow.svg").as_posix()))
        self.menu_corners = MenuCorners(self)
        for popup in (self.manage_menu, self.settings_menu, self.help_menu,
                      self.workspaces_menu, self.updates_menu):
            # Native style polishing can reset popup flags. Finish the inherited
            # stylesheet first, then apply our window-level appearance settings.
            popup.ensurePolished()
            popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            # The app supplies the shadow; suppress any additional native one.
            popup.setWindowFlags(popup.windowFlags() | Qt.WindowType.FramelessWindowHint
                                 | Qt.WindowType.NoDropShadowWindowHint)
            self.menu_corners.attach(popup)
        self.tabs.tabBar().update_tab_inset()
        self.refresh_tab_colors()
        self.restore_window_geometry()
        if self.config_error:
            QTimer.singleShot(0, self.show_config_error)
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            from .update_controller import UpdateController
            self.updater = UpdateController(self)
            self.updater.changed.connect(self.update_state_changed)
            self.update_timer = QTimer(self)
            self.update_timer.setInterval(12 * 60 * 60 * 1000)
            self.update_timer.timeout.connect(self.automatic_update_check)
            self.update_timer.start()
            QTimer.singleShot(5000, self.automatic_update_check)
            QTimer.singleShot(3000, self.show_update_result)
        else:
            self.check_updates_action.setEnabled(False)
            self.check_updates_action.setToolTip("Automatic updates are available in the compiled Windows application.")

    def set_update_preference(self, key, enabled):
        previous = copy.deepcopy(self.data.get("updates", {"automatic": True, "download": True}))
        self.data["updates"] = dict(previous, **{key: enabled})
        if not self.persist():
            self.data["updates"] = previous
            self.sync_update_actions()
            QMessageBox.warning(self, "Settings were not saved", "Could not save the update preference.")

    def sync_update_actions(self):
        for action, key in ((self.automatic_updates_action, "automatic"), (self.download_updates_action, "download")):
            action.blockSignals(True)
            action.setChecked(self.data.get("updates", {}).get(key, True))
            action.blockSignals(False)

    def automatic_update_check(self):
        if self.updater and not self.closing and self.data.get("updates", {}).get("automatic", True):
            # Unconfigured development builds never make automatic network requests.
            from .update_security import load_key
            try:
                load_key()
            except ValueError:
                return
            self.updater.check(self.data.get("updates", {}).get("download", True))

    def check_for_updates(self):
        if self.updater:
            self.updater.check(self.data.get("updates", {}).get("download", True))

    def update_state_changed(self, state, value):
        messages = {"checking": "Checking for updates…", "downloading": "Downloading update…",
                    "current": "BashDock is up to date."}
        if state in messages:
            self.statusBar().showMessage(messages[state])
        if state == "downloading":
            self.statusBar().update_button.hide()
        if state == 'local-disabled':
            self.statusBar().update_button.hide()
            self.statusBar().clearMessage()
        if state in ("ready", "available", "local-ready"):
            self.statusBar().show_update(value, ready=state != "available", local=state == "local-ready")
            self.statusBar().clearMessage()
        if state == "error":
            self.statusBar().showMessage(f"Update check: {value}")
        self.check_updates_action.setEnabled(bool(self.updater and not self.updater.busy))

    def restart_for_update(self):
        if not self.updater:
            return
        if self.updater.ready is None:
            self.updater.download()
            return
        chosen = self.updater.ready
        version = chosen.manifest["version"]
        local = chosen.manifest.get('channel') == 'local-development'
        label = 'locally built BashDock' if local else 'BashDock'
        if QMessageBox.question(self, "Restart to update?",
                f"Install {label} {version} and restart?\n\n"
                "Running commands and shell sessions will close. Tabs, folders, settings, and window position "
                "will be saved, then reopened in fresh shells. Finish any running work first.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if not self.allow_save:
            QMessageBox.warning(self, "Cannot update yet", "Recover your settings before restarting to update.")
            return
        # A local staging worker may finish while the confirmation dialog is
        # open. Install exactly the build named in that confirmation.
        self.updater.install_choice = chosen
        self.update_restart = True
        if not self.close():
            self.update_restart = False

    def show_update_result(self):
        from .updates import cache_directory
        import json
        path = cache_directory() / "result.json"
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            path.unlink()
            self.statusBar().showMessage(f"Updated to version {result['version']}." if result.get("ok")
                                         else "Update could not finish: " + result.get("message", "Previous version restored."))
        except (OSError, ValueError, KeyError):
            pass

    def show_config_error(self):
        if not self.config_error:
            return
        self.statusBar().showMessage("Settings could not be read. Choose a recovery option in Settings.")
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Recover settings")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("BashDock could not read your settings.")
        dialog.setInformativeText(
            "Restore the automatic backup, import an exported settings file, or start fresh. "
            "The damaged file will be preserved when you recover.\n\n"
            "Until then, defaults are in use and automatic saving is paused.\n\n"
            f"File: {config.config_path()}\n{self.config_error}")
        restore = dialog.addButton("Restore backup…", QMessageBox.ButtonRole.ActionRole)
        restore.setEnabled(config.backup_path().is_file())
        imported = dialog.addButton("Import settings…", QMessageBox.ButtonRole.ActionRole)
        fresh = dialog.addButton("Start fresh…", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        clicked = dialog.clickedButton()
        dialog.deleteLater()
        if clicked == restore:
            self.restore_backup()
        elif clicked == imported:
            self.import_settings()
        elif clicked == fresh:
            self.replace_workspace(config.defaults(), "Start with default settings")

    def export_settings(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export settings", str(Path.home() / "bashdock-settings.json"), "JSON settings (*.json)")
        if not filename:
            return
        try:
            path = Path(filename)
            if path.resolve() in (config.config_path().resolve(), config.backup_path().resolve()):
                raise ValueError("Choose a separate file for your export, outside the active settings and automatic backup.")
            config.save(self.snapshot(), path, backup=False)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot export settings", str(error))
            return
        self.statusBar().showMessage(f"Settings exported to {filename}")

    def import_settings(self, checked=False, *, path=None):
        if path is None:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Import settings", str(Path.home()), "Settings files (*.json *.bak);;All files (*)")
            if not filename:
                return
            path = Path(filename)
        try:
            data = config.read(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot import settings", f"The settings file was not imported.\n\n{error}")
            return
        self.replace_workspace(data, f"Import settings from {path}")

    def restore_backup(self):
        self.import_settings(path=config.backup_path())

    def replace_workspace(self, data, description, *, backup_label="before-import"):
        running = sum(bool(self.tabs.widget(i).terminal.process) for i in range(self.tabs.count()))
        contents = "tabs and settings" if backup_label == "before-import" else "tabs"
        if QMessageBox.question(self, "Replace workspace?",
                f"{description}?\n\nThis will replace your {contents} with {len(data['tabs'])} tab(s) "
                f"and close {running} running shell session(s). "
                "Your current workspace will be backed up first."
                + (" Only import settings files you trust." if backup_label == "before-import" else ""),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False
        self.save_timer.stop()
        try:
            if self.allow_save:
                config.archive_workspace(self.snapshot(), backup_label)
            # Commit to disk before touching any live shells. Saving also preserves damaged files.
            config.save(data)
        except (OSError, ValueError) as error:
            self.schedule_save()
            QMessageBox.warning(self, "Cannot replace workspace", f"Your open shells were kept.\n\n{error}")
            return False
        self.restoring = True
        for i in reversed(range(self.tabs.count())):
            tab = self.tabs.widget(i)
            tab.terminal.stop()
            self.tabs.removeTab(i)
            tab.deleteLater()
        self.data = copy.deepcopy(data)
        self.data["bash_path"] = self.data["bash_path"] or config.find_bash()
        self.config_error = ""
        self.allow_save = True
        for profile in self.data["tabs"]:
            self.add_tab(profile)
        self.tabs.setCurrentIndex(self.data["active_tab"])
        self.sync_confirm_action()
        self.sync_update_actions()
        self.restore_window_geometry()
        self.restoring = False
        self.tab_changed()
        self.statusBar().showMessage("Settings restored. Your previous settings were backed up.")
        return True

    def current_tab(self):
        return self.tabs.currentWidget()

    def manage_workspaces(self):
        dialog = WorkspacesDialog(self)
        dialog.exec()
        dialog.deleteLater()

    def refresh_workspaces_menu(self):
        self.workspaces_menu.clear()
        configure = QAction("Configure…", self.workspaces_menu)
        configure.triggered.connect(self.manage_workspaces)
        self.workspaces_menu.addAction(configure)
        workspaces = self.data.get("workspaces", [])
        if workspaces:
            self.workspaces_menu.addSeparator()
            for index, workspace in enumerate(workspaces):
                action = QAction(workspace["name"].replace("&", "&&"), self.workspaces_menu)
                action.triggered.connect(lambda checked=False, index=index: self.open_workspace(index))
                self.workspaces_menu.addAction(action)

    def store_workspaces(self, workspaces):
        try:
            config.validate_workspaces(workspaces)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot save workspace", str(error))
            return False
        previous = self.data.get("workspaces", [])
        self.data["workspaces"] = copy.deepcopy(workspaces)
        if not self.persist():
            self.data["workspaces"] = previous
            QMessageBox.warning(self, "Cannot save workspace", "Changes were not saved. Check the status bar for details.")
            return False
        return True

    def save_workspace(self, name, selected, replace=None):
        snapshot = self.snapshot()
        # Selected indexes always follow the visible tab order.
        selected = sorted(set(selected))
        if not selected or any(type(i) is not int or not 0 <= i < len(snapshot["tabs"]) for i in selected):
            QMessageBox.warning(self, "Cannot save workspace", "Select at least one current tab.")
            return False
        workspace = {"name": name.strip(), "tabs": [snapshot["tabs"][i] for i in selected],
                     "active_tab": selected.index(snapshot["active_tab"]) if snapshot["active_tab"] in selected else 0}
        workspaces = copy.deepcopy(self.data.get("workspaces", []))
        if replace is None:
            workspaces.append(workspace)
        else:
            workspaces[replace] = workspace
        return self.store_workspaces(workspaces)

    def open_workspace(self, index, replace=False):
        workspace = copy.deepcopy(self.data["workspaces"][index])
        data = self.snapshot()
        if replace:
            data.update(tabs=workspace["tabs"], active_tab=workspace["active_tab"])
            opened = self.replace_workspace(data, f"Open saved workspace '{workspace['name']}'",
                                            backup_label="before-workspace")
            if opened:
                self.statusBar().showMessage(f"Opened workspace: {workspace['name']}")
            return opened
        existing = {tab["id"] for tab in data["tabs"]}
        missing = [tab for tab in workspace["tabs"] if tab["id"] not in existing]
        data["tabs"].extend(missing)
        active_id = workspace["tabs"][workspace["active_tab"]]["id"]
        data["active_tab"] = next(i for i, tab in enumerate(data["tabs"]) if tab["id"] == active_id)
        if not missing:
            self.tabs.setCurrentIndex(data["active_tab"])
            self.statusBar().showMessage(f"Workspace tabs are already open: {workspace['name']}")
            return True
        if not self.allow_save:
            QMessageBox.warning(self, "Cannot open workspace", "Recover your settings before opening a saved workspace.")
            return False
        self.save_timer.stop()
        try:
            config.save(data)
        except (OSError, ValueError) as error:
            self.schedule_save()
            QMessageBox.warning(self, "Cannot open workspace", str(error))
            return False
        self.restoring = True
        for profile in missing:
            self.add_tab(profile)
        self.tabs.setCurrentIndex(data["active_tab"])
        self.restoring = False
        self.tab_changed()
        skipped = len(workspace["tabs"]) - len(missing)
        self.statusBar().showMessage(f"Opened workspace: {workspace['name']} — {len(missing)} added, {skipped} already open")
        return True

    def add_tab(self, profile):
        profile = copy.deepcopy(profile)
        profile.setdefault("id", str(uuid4()))
        for i in range(self.tabs.count()):
            existing = self.tabs.widget(i)
            if existing.data["id"] == profile["id"]:
                return existing
        tab = ShellTab(profile, self, self.terminal_factory)
        tab.terminal.apply_settings(terminal_preferences.effective(tab.data, self.data["terminal"]))
        tab.configure_requested.connect(lambda: self.configure(tab))
        tab.terminal.loaded.connect(lambda: self.start_shell(tab))
        tab.terminal.ended.connect(lambda text: self.on_ended(tab, text))
        tab.terminal.problem.connect(lambda text: self.show_status(tab, text))
        tab.terminal.directory_changed.connect(lambda path: self.directory_changed(tab, path))
        index = self.tabs.addTab(tab, profile["name"])
        # Native tab close controls clamp the image size on some Windows styles.
        close = QToolButton()
        close.setObjectName("tabClose")
        close.setIcon(QIcon(str(APP_ICON.parent / "tab-close.svg")))
        close.setIconSize(QSize(12, 12))
        close.setFixedSize(12, 12)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.setToolTip("Close tab")
        close.setAccessibleName("Close tab")
        close.clicked.connect(lambda: self.close_tab(self.tabs.indexOf(tab)))
        inset = QWidget()
        inset_layout = QHBoxLayout(inset)
        inset_layout.setContentsMargins(4, 0, 6, 0)
        inset_layout.addWidget(close)
        self.tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, inset)
        self.refresh_tab_colors()
        return tab

    def new_tab(self):
        profile = config.default_tab(f"Git Bash {self.tabs.count() + 1}")
        current = self.current_tab()
        if current:
            profile["startup_folder"] = current.data["current_folder"]
            profile["current_folder"] = current.data["current_folder"]
        tab = self.add_tab(profile)
        self.tabs.setCurrentWidget(tab)
        self.schedule_save()

    def rename_tab(self, index):
        if index < 0:
            return
        tab = self.tabs.widget(index)
        name, accepted = QInputDialog.getText(self, "Rename tab", "Tab name:", text=tab.data["name"])
        if accepted and name.strip():
            tab.data["name"] = name.strip()
            self.tabs.setTabText(index, tab.data["name"])
            self.schedule_save()

    def tab_changed(self, *args):
        self.refresh_tab_colors()
        tab = self.current_tab()
        if tab:
            trace = getattr(tab.terminal, 'trace', None)
            input_recorder.record('tab_selected', terminal=trace.terminal_id if trace else 0)
            self.statusBar().showMessage(tab.status)
            if tab.terminal.ready:
                tab.terminal.bridge.focus.emit()
        self.schedule_save()

    def refresh_tab_colors(self, *args):
        themes = [terminal_preferences.effective(self.tabs.widget(i).data, self.data['terminal'])
                  for i in range(self.tabs.count())]
        self.tabs.tabBar().set_terminal_themes(themes)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).top_border.update()
        tab = self.current_tab()
        if tab:
            settings = terminal_preferences.effective(tab.data, self.data['terminal'])
            self.tabs.tabBar().set_terminal_colors(settings['background'], settings['foreground'])

    def show_status(self, tab, text):
        tab.status = text
        if tab is self.current_tab():
            self.statusBar().showMessage(text)

    def directory_changed(self, tab, path):
        if tab.data["current_folder"] != path:
            tab.data["current_folder"] = path
            self.schedule_save()

    def snapshot(self):
        return {"version": 2, "bash_path": self.data["bash_path"],
                "window_geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
                "confirm_on_exit": self.data["confirm_on_exit"],
                "updates": copy.deepcopy(self.data.get("updates", {"automatic": True, "download": True})),
                "terminal": copy.deepcopy(self.data["terminal"]),
                "workspaces": copy.deepcopy(self.data.get("workspaces", [])),
                "active_tab": self.tabs.currentIndex(),
                "tabs": [copy.deepcopy(self.tabs.widget(i).data) for i in range(self.tabs.count())]}

    def restore_window_geometry(self):
        # Optional metadata: old workspaces and damaged geometry still load normally.
        encoded = self.data.get("window_geometry")
        if not isinstance(encoded, str) or not encoded:
            return
        try:
            geometry = base64.b64decode(encoded, validate=True)
        except (ValueError, UnicodeError):
            logging.warning("Ignoring invalid saved window geometry")
            return
        # Qt also brings windows back onto an available screen if monitors changed.
        if not self.restoreGeometry(geometry):
            logging.warning("Ignoring unrecognized saved window geometry")

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "save_timer"):
            self.schedule_save()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        input_recorder.record('window_resize', width=event.size().width(), height=event.size().height())
        if hasattr(self, "save_timer"):
            self.schedule_save()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "save_timer"):
            self.schedule_save()

    def schedule_save(self, *args):
        if not self.restoring and not self.closing and self.allow_save:
            self.save_timer.start()

    def persist(self):
        if not self.allow_save:
            return False
        try:
            config.save(self.snapshot())
            return True
        except (ValueError, OSError) as error:
            self.statusBar().showMessage(f"Could not save workspace: {error}")
            return False

    def start_shell(self, tab):
        if self.tabs.indexOf(tab) < 0 or self.closing:
            return
        if not Path(self.data["bash_path"]).is_file():
            # Retry discovery so installing Git does not require restarting BashDock.
            self.data["bash_path"] = config.find_bash()
            if not self.data["bash_path"]:
                self.show_status(tab, "Git Bash not found. Install Git for Windows, then use Manage → Restart shell.")
                tab.set_running(False)
                self.show_git_setup()
                return
            self.schedule_save()
        try:
            folder = tab.data["current_folder"]
            if not Path(folder).is_dir():
                folder = tab.data["startup_folder"]
            if not Path(folder).is_dir():
                folder = str(Path.home())
            if folder != tab.data["current_folder"]:
                tab.data["current_folder"] = folder
                self.schedule_save()
            tab.terminal.start(self.data["bash_path"], folder)
            tab.shell_bash_path = self.data["bash_path"]
        except Exception as error:
            logging.exception("Could not start Git Bash")
            self.show_status(tab, f"Cannot start shell: {error}")
            tab.set_running(False)
            QMessageBox.warning(self, "Cannot start Git Bash", str(error))
            return
        tab.set_running(True)
        self.show_status(tab, "")

    def show_git_setup(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Git for Windows required")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText("BashDock needs Git Bash, which is included with Git for Windows.")
        dialog.setInformativeText(
            "1. Download and install Git for Windows using the default options.\n"
            "2. Return to BashDock and choose Manage → Restart shell.\n\n"
            "Already installed? Open Settings → Configure current tab… and select "
            "bash.exe from your Git installation (usually C:\\Program Files\\Git\\bin\\bash.exe).")
        download = dialog.addButton("Download Git for Windows", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton(QMessageBox.StandardButton.Close)
        dialog.exec()
        if dialog.clickedButton() == download:
            QDesktopServices.openUrl(QUrl("https://gitforwindows.org/"))
        dialog.deleteLater()

    def configure_terminal(self):
        dialog = TerminalSettingsDialog(self.data["terminal"], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            dialog.deleteLater()
            return
        previous = self.data["terminal"]
        self.data["terminal"] = dialog.values()
        dialog.deleteLater()
        if not self.persist():
            self.data["terminal"] = previous
            QMessageBox.warning(self, "Settings were not saved", "Check the status bar for details.")
            return
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if tab.data.get("terminal") is None:
                tab.terminal.apply_settings(terminal_preferences.effective(tab.data, self.data["terminal"]))
        self.refresh_tab_colors()

    def save_diagnostic_report(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save diagnostic report",
            "bashdock-diagnostics.json", "JSON files (*.json)")
        if not filename:
            return
        try:
            input_recorder.save(filename)
        except OSError as error:
            QMessageBox.warning(self, "Cannot save diagnostic report", str(error))
            return
        self.statusBar().showMessage("Diagnostic report saved. Commands and terminal output are excluded.", 8000)

    def show_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("About BashDock")
        dialog.setWindowIcon(self.windowIcon())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        content = QHBoxLayout()
        content.setSpacing(16)
        icon = QLabel()
        icon.setPixmap(self.windowIcon().pixmap(64, 64))
        content.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        details = QVBoxLayout()
        title = QLabel(f"<h2>BashDock</h2><p>Version {__version__}</p>")
        details.addWidget(title)
        description = QLabel("A tabbed Git Bash workspace for Windows, with remembered folders "
                             "and custom command buttons.")
        description.setWordWrap(True)
        details.addWidget(description)
        licensing = QLabel("Copyright © 2026 Chris Bokitch<br>GNU GPL version 3")
        details.addWidget(licensing)
        repository = QLabel('<a href="https://github.com/chrisbokitch/bashdock" '
                            'style="color:#9baec4">BashDock on GitHub</a>')
        repository.setOpenExternalLinks(True)
        details.addWidget(repository)
        license_button = QPushButton("License and notices…")
        license_button.clicked.connect(lambda: self.show_licenses(dialog))
        details.addWidget(license_button, 0, Qt.AlignmentFlag.AlignLeft)
        content.addLayout(details, 1)
        layout.addLayout(content)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(440, dialog.sizeHint().height())
        dialog.exec()
        dialog.deleteLater()

    def show_licenses(self, parent=None):
        dialog = QDialog(parent or self)
        dialog.setWindowTitle("BashDock — License and notices")
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        assets = Path(__file__).parent / "assets"
        for label, filename in (("GPLv3", "GPL-3.0.txt"),
                                ("Third-party software", "THIRD-PARTY-NOTICES.md")):
            text = QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText((assets / filename).read_text(encoding="utf-8"))
            tabs.addTab(text, label)
        layout.addWidget(tabs)
        archive = Path(sys.executable).parent / 'third-party-licenses.zip'
        if getattr(sys, 'frozen', False) and archive.is_file():
            notice = QLabel('Full dependency notices and their index are included in '
                            'third-party-licenses.zip beside the application.')
            notice.setWordWrap(True)
            layout.addWidget(notice)
            open_notices = QPushButton('Open detailed notices…')
            def open_archive():
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(archive))):
                    QMessageBox.warning(dialog, 'Cannot open notices',
                                        f'Open this archive in File Explorer:\n{archive}')
            open_notices.clicked.connect(open_archive)
            layout.addWidget(open_notices, 0, Qt.AlignmentFlag.AlignLeft)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(720, 520)
        dialog.exec()
        dialog.deleteLater()

    def open_external(self):
        tab = self.current_tab()
        if not tab:
            return
        bash_path = tab.shell_bash_path if tab.terminal.process else self.data["bash_path"]
        try:
            open_external(bash_path, tab.data["current_folder"])
        except (OSError, ValueError, RuntimeError) as error:
            self.statusBar().showMessage(f"Could not open external shell: {error}")
            QMessageBox.warning(self, "Cannot open external shell", str(error))

    def configure(self, tab=None):
        if not isinstance(tab, ShellTab):
            tab = self.current_tab()
        if not tab:
            return
        original = copy.deepcopy(tab.data)
        original_bash = self.data["bash_path"]
        dialog = SettingsDialog(dict(tab.data, bash_path=original_bash), self,
                                terminal_defaults=self.data["terminal"])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = copy.deepcopy(dialog.result_data)
            result["id"] = original["id"]
            self.data["bash_path"] = result.pop("bash_path")
            tab.data = result
            previous_allow = self.allow_save
            self.allow_save = True
            if not self.persist():
                tab.data = original
                self.data["bash_path"] = original_bash
                self.allow_save = previous_allow
                QMessageBox.warning(self, "Cannot save tab", "Changes were not saved. Check the status bar for details.")
                return
            self.tabs.setTabText(self.tabs.indexOf(tab), tab.data["name"])
            tab.terminal.apply_settings(terminal_preferences.effective(tab.data, self.data["terminal"]))
            self.refresh_tab_colors()
            tab.build_buttons()
            if not tab.terminal.process and tab.terminal.ready:
                self.start_shell(tab)

    def on_ended(self, tab, text):
        tab.set_running(False)
        self.show_status(tab, text)

    def interrupt(self):
        tab = self.current_tab()
        if tab:
            tab.terminal.write("\x03")

    def restart(self):
        tab = self.current_tab()
        if not tab or not tab.terminal.ready:
            return
        if tab.terminal.process and QMessageBox.question(self, "Restart shell?",
                f"Close the shell in {tab.data['name']} and start a fresh session?") != QMessageBox.StandardButton.Yes:
            return
        tab.terminal.stop()
        tab.set_running(False)
        self.start_shell(tab)

    def close_tab(self, index):
        if index < 0:
            return
        if self.tabs.count() == 1:
            self.close()
            return
        tab = self.tabs.widget(index)
        if tab.terminal.process and QMessageBox.question(self, "Close tab?",
                f"Close {tab.data['name']} and its shell session?") != QMessageBox.StandardButton.Yes:
            return
        tab.terminal.stop()
        self.tabs.removeTab(index)
        tab.deleteLater()
        self.refresh_tab_colors()
        self.schedule_save()

    def set_confirm_on_exit(self, enabled):
        previous = self.data["confirm_on_exit"]
        self.data["confirm_on_exit"] = enabled
        if not self.persist():
            self.data["confirm_on_exit"] = previous
            self.sync_confirm_action()
            QMessageBox.warning(self, "Setting was not saved", "Could not save the confirmation setting. Check the status bar for details.")

    def sync_confirm_action(self):
        self.confirm_exit_action.blockSignals(True)
        self.confirm_exit_action.setChecked(self.data["confirm_on_exit"])
        self.confirm_exit_action.blockSignals(False)

    def confirm_quit(self, running):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Close BashDock?")
        dialog.setText(f"Close {running} shell session(s) and quit?")
        dialog.setInformativeText("Your tabs and folders will be remembered.")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        skip = QCheckBox("Don't show this again", dialog)
        dialog.setCheckBox(skip)
        accepted = dialog.exec() == QMessageBox.StandardButton.Yes
        return accepted, skip.isChecked()

    def closeEvent(self, event):
        if self.closing:
            event.accept()
            return
        running = sum(bool(self.tabs.widget(i).terminal.process) for i in range(self.tabs.count()))
        previous_confirm = self.data["confirm_on_exit"]
        if running and previous_confirm and not self.update_restart:
            accepted, skip = self.confirm_quit(running)
            if not accepted:
                event.ignore()
                return
            if skip:
                self.data["confirm_on_exit"] = False
        self.save_timer.stop()
        if self.allow_save and not self.persist():
            self.data["confirm_on_exit"] = previous_confirm
            self.sync_confirm_action()
            QMessageBox.warning(self, "Workspace was not saved", "Could not save your tabs. Resolve the save error before closing.")
            event.ignore()
            return
        self.sync_confirm_action()
        if self.update_restart:
            try:
                self.updater.launch_install()
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Cannot install update", str(error))
                event.ignore()
                return
        if self.updater:
            self.updater.cancel()
        self.closing = True
        for i in range(self.tabs.count()):
            self.tabs.widget(i).terminal.stop()
        event.accept()


def main():
    from .diagnostics import initialize
    initialize()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("chrisbokitch.bashdock")
    app = QApplication(sys.argv)
    app.setApplicationName("BashDock")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(APP_ICON)))
    if sys.platform != "win32":
        QMessageBox.warning(None, "Windows required", "BashDock currently supports Windows 10/11 with Git for Windows.")
        return
    window = MainWindow()
    window.show()
    if "--update-health" in sys.argv:
        def acknowledge_update():
            from .update_health import acknowledge_startup
            try:
                if not acknowledge_startup(sys.argv, installation=Path(sys.executable).resolve().parent,
                                           version=__version__):
                    logging.error("Update startup confirmation was rejected.")
            except (OSError, ValueError, IndexError):
                logging.exception("Could not acknowledge update startup")
        QTimer.singleShot(1000, acknowledge_update)
    sys.exit(app.exec())


