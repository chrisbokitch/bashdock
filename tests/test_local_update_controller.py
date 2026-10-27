"""Local polling is independent of remote checks and never applies an update itself."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bashdock.update_controller import UpdateController
from bashdock.updates import ReadyUpdate
from bashdock import local_updates


class LocalControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use QApplication if a GUI already exists; QCoreApplication alone
        # must not be created before the UI tests' QApplication.
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def controller(self):
        controller = UpdateController(installation=Path(tempfile.gettempdir()) / 'local-install')
        controller.local_timer.stop()
        self.addCleanup(controller.cancel)
        return controller

    def test_poll_discovers_once_and_only_offers_restart(self):
        controller = self.controller()
        pending = Path(tempfile.gettempdir()) / 'pending-fixture'
        ready = ReadyUpdate(dict(channel=local_updates.CHANNEL, version='0.14.0'), pending)
        events = []
        controller.changed.connect(lambda state, value: events.append((state, value)))
        with patch.object(local_updates, 'candidate', return_value=pending), \
                patch.object(local_updates, 'discover_local', return_value=ready) as discover, \
                patch.object(controller, '_start', side_effect=lambda work: work()), \
                patch.object(controller, 'launch_install') as install:
            controller.poll_local()
            controller.poll_local()
        discover.assert_called_once_with(controller.installation, pending)
        self.assertIs(ready, controller.ready)
        self.assertEqual([('local-ready', '0.14.0')], events)
        install.assert_not_called()

    def test_local_package_is_checked_before_public_network(self):
        controller = self.controller()
        ready = ReadyUpdate(dict(channel=local_updates.CHANNEL, version='0.14.0'), Path('pending'))
        with patch.object(local_updates, 'discover_local', return_value=ready), \
                patch('bashdock.update_controller.discover') as remote:
            controller._check(download=True)
        remote.assert_not_called()
        self.assertIs(ready, controller.ready)

    def test_source_preview_has_no_implicit_installation_and_disabled_staging_clears_offer(self):
        with patch('bashdock.update_controller.sys.frozen', False, create=True):
            source = UpdateController()
        self.addCleanup(source.cancel)
        self.assertIsNone(source.installation)
        self.assertFalse(source.local_timer.isActive())
        controller = self.controller()
        controller.ready = ReadyUpdate(dict(channel=local_updates.CHANNEL), Path('pending'))
        with patch.object(local_updates, 'candidate', return_value=None):
            controller.poll_local()
        self.assertIsNone(controller.ready)

    def test_busy_or_cancelled_poll_never_touches_disk(self):
        controller = self.controller()
        with patch.object(local_updates, 'candidate') as candidate:
            controller.busy = True
            controller.poll_local()
            controller.busy = False
            controller.cancel()
            controller.poll_local()
        candidate.assert_not_called()
