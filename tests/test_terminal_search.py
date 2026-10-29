"""Search requests survive page startup without entering shell input."""
import os
import sys

if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from bashdock.terminal import Terminal
from qt_lifecycle import GuiTestCase


class TerminalSearchTests(GuiTestCase):
    def test_find_requested_before_page_ready_opens_once_after_startup(self):
        terminal = Terminal()
        requests = []
        terminal.bridge.findRequested.connect(lambda: requests.append('find'))
        terminal.open_search()
        self.assertEqual([], requests)
        terminal.bridge.ready(80, 24)
        self.assertEqual(['find'], requests)
        terminal.bridge.ready(80, 24)
        self.assertEqual(['find'], requests)
        terminal.open_search()
        self.assertEqual(['find', 'find'], requests)
        self.assertIsNone(terminal.process)
        terminal.timer.stop()
