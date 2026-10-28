"""Regression checks for the thread boundary used by the WebEngine harness."""
import gc
import os
import sys
import threading
import weakref
import unittest

if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QWidget
from qt_lifecycle import GuiTestCase, drain_gui_garbage


class QtLifecycleTests(GuiTestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Real Windows WebEngine lifecycle')
    def test_cyclic_webengine_view_is_deleted_on_gui_thread_before_worker_collection(self):
        from bashdock.terminal import Terminal
        destroyed = []
        view = Terminal()
        view.destroyed.connect(lambda: destroyed.append(threading.get_ident()))
        reference = weakref.ref(view)
        view.close()
        del view
        self._dispose_gui()
        self.assertEqual([threading.get_ident()], destroyed)
        self.assertIsNone(reference())
        worker = threading.Thread(target=gc.collect)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(1, len(destroyed))

    def test_cyclic_widget_is_disposed_before_worker_collection(self):
        owner = threading.get_ident()
        destroyed = []
        widget = QWidget()
        widget.cycle = widget
        reference = weakref.ref(widget)
        widget.destroyed.connect(lambda: destroyed.append(threading.get_ident()))
        widget.close()
        del widget
        self._dispose_gui()
        self.assertEqual([owner], destroyed)
        self.assertIsNone(reference())
        worker = threading.Thread(target=gc.collect)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual([owner], destroyed)

    def test_worker_cleanup_is_rejected_and_automatic_collection_is_disabled(self):
        self.assertFalse(gc.isenabled())
        errors = []

        def worker():
            try:
                drain_gui_garbage(self.app)
            except RuntimeError as error:
                errors.append(str(error))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=5)
        self.assertEqual(['Qt test cleanup must run on the main thread.'], errors)
