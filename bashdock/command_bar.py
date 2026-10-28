"""Wrapping command buttons with bounded space for unusually large bars."""
from PySide6.QtCore import QEvent, QRect, QSize, Qt, QTimer
from PySide6.QtWidgets import QLayout, QPushButton, QScrollArea, QStyle, QStyleOptionButton, QStylePainter


class CommandButton(QPushButton):
    def minimumSizeHint(self):
        return QSize(0, self.sizeHint().height())

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        content = self.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, self)
        option.text = self.fontMetrics().elidedText(option.text, Qt.TextElideMode.ElideRight,
                                                   max(0, content.width()))
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)


class CommandFlowLayout(QLayout):
    def __init__(self, parent):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(6)

    def addItem(self, item):
        self.items.append(item)
        self.invalidate()

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        if 0 <= index < len(self.items):
            item = self.items.pop(index)
            self.invalidate()
            return item
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.arrange(QRect(0, 0, width, 0), apply=False)

    def minimumSize(self):
        return QSize(0, max((item.sizeHint().height() for item in self.items), default=0))

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.arrange(rect, apply=True)

    def arrange(self, rect, *, apply):
        x, y, row_height = rect.x(), rect.y(), 0
        width = max(1, rect.width())
        for item in self.items:
            hint = item.sizeHint()
            button_width = min(width, hint.width())
            if x > rect.x() and x + button_width > rect.x() + width:
                x = rect.x()
                y += row_height + self.spacing()
                row_height = 0
            if apply:
                item.setGeometry(QRect(x, y, button_width, hint.height()))
            x += button_width + self.spacing()
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y()


class CommandScrollArea(QScrollArea):
    """Fit wrapped rows, with vertical overflow only when they crowd the terminal."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.viewport().installEventFilter(self)
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.fit_height)
        if parent is not None:
            parent.installEventFilter(self)

    def schedule_fit(self):
        # Defer size changes so hidden-tab and viewport resize layouts finish first.
        self.fit_timer.start(0)

    def fit_height(self):
        if self.widget() is None:
            return
        flow = self.widget().layout()
        needed = max(1, flow.heightForWidth(self.viewport().width()))
        row_height = max(1, flow.minimumSize().height())
        limit = max(row_height, int(self.parentWidget().height() * 0.4))
        height = min(needed, limit)
        if self.widget().minimumHeight() != needed:
            self.widget().setMinimumHeight(needed)
        if self.height() != height:
            self.setFixedHeight(height)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Resize, QEvent.Type.Show):
            self.schedule_fit()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_fit()
