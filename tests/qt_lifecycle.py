"""Keep test-owned Qt destruction and cyclic collection on the GUI thread."""
import gc
import threading
import unittest

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

_application = None


def drain_gui_garbage(app):
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('Qt test cleanup must run on the main thread.')
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


class GuiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        global _application
        _application = QApplication.instance() or QApplication([])
        cls.app = _application
        enabled = gc.isenabled()
        # Reader-thread allocations can otherwise collect an unreachable
        # Terminal/Bridge cycle and destroy a WebEngine view on that thread.
        gc.disable()

        def restore_collection():
            try:
                drain_gui_garbage(cls.app)
            finally:
                if enabled:
                    gc.enable()

        cls.addClassCleanup(restore_collection)
        drain_gui_garbage(cls.app)

    def setUp(self):
        super().setUp()
        self._gui_disposed = False
        self._existing_windows = set(self.app.topLevelWidgets())
        self.addCleanup(self._dispose_gui)

    def _dispose_gui(self):
        if self._gui_disposed:
            return
        # close() does not delete a QWidget. Keep cleanup deterministic even
        # when a fixture retains Python cycles or a test exits early.
        for widget in self.app.topLevelWidgets():
            if widget not in self._existing_windows:
                widget.deleteLater()
        widget = None  # Release the loop's last Python wrapper before collecting.
        drain_gui_garbage(self.app)
        self._existing_windows.clear()
        self._gui_disposed = True
