"""Real startup receipt writes and helper reads for both update cache layouts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from bashdock import local_updates, update_health
from bashdock.input_diagnostics import Recorder
from bashdock.update_helper import wait_for_health


class UpdateHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cache = self.root / 'BashDock/updates'
        self.installation = self.root / 'installed app'
        self.recorder = Recorder()
        for module in (update_health, local_updates):
            patcher = patch.object(module, 'cache_directory', return_value=self.cache)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(update_health, 'recorder', self.recorder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def arguments(self, path, token='a' * 64):
        return ['bashdock.exe', '--update-health', str(path), '--update-token', token]

    def test_public_and_installation_scoped_local_receipts_are_accepted_by_real_helper(self):
        paths = [self.cache / 'pending-public/health.json',
                 local_updates.inbox_root(self.installation) / 'pending-local/health.json']
        process = Mock()
        process.poll.return_value = None
        for path in paths:
            with self.subTest(path=path):
                path.parent.mkdir(parents=True)
                self.assertTrue(update_health.acknowledge_startup(self.arguments(path),
                    installation=self.installation, version='0.14.2'))
                self.assertTrue(wait_for_health(process, path, 'a' * 64, '0.14.2', timeout=1))
                self.assertEqual(dict(token='a' * 64, version='0.14.2'), json.loads(path.read_text()))
                self.assertEqual([], list(path.parent.glob('.health-*.tmp')))
        events = self.recorder.snapshot()['events']
        self.assertTrue(all(e['accepted'] and e['written'] for e in events))
        self.assertEqual([False, True], [e['local'] for e in events])
        self.assertNotIn('a' * 64, json.dumps(self.recorder.snapshot()))
        self.assertNotIn(str(self.root), json.dumps(self.recorder.snapshot()))

    def test_other_installations_and_arbitrary_files_are_not_written(self):
        paths = [local_updates.inbox_root(self.root / 'other app') / 'pending-local/health.json',
                 self.root / 'unrelated/health.json',
                 local_updates.inbox_root(self.installation) / 'not-a-pending-directory/health.json',
                 self.cache / 'pending-public/settings.json']
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.assertFalse(update_health.acknowledge_startup(self.arguments(path),
                             installation=self.installation, version='0.14.2'))
            self.assertFalse(path.exists())

    def test_incomplete_or_invalid_tokens_are_not_acknowledged(self):
        path = self.cache / 'pending-test/health.json'
        path.parent.mkdir(parents=True)
        for args in ([], ['--update-health'], self.arguments(path, 'wrong-token'),
                     ['--update-health', str(path), '--update-token']):
            self.assertFalse(update_health.acknowledge_startup(args,
                             installation=self.installation, version='0.14.2'))
            self.assertFalse(path.exists())

    def test_helper_still_rejects_wrong_version_or_token(self):
        path = self.cache / 'pending-test/health.json'
        path.parent.mkdir(parents=True)
        update_health.acknowledge_startup(self.arguments(path), installation=self.installation, version='0.14.2')
        process = Mock()
        process.poll.return_value = 1
        self.assertFalse(wait_for_health(process, path, 'b' * 64, '0.14.2', timeout=1))
        self.assertFalse(wait_for_health(process, path, 'a' * 64, '0.14.1', timeout=1))

    def test_write_failure_is_reported_without_private_paths_or_tokens(self):
        path = self.cache / 'pending-missing/health.json'
        with self.assertRaises(OSError):
            update_health.acknowledge_startup(self.arguments(path),
                                             installation=self.installation, version='0.14.2')
        event = self.recorder.snapshot()['events'][-1]
        self.assertTrue(event['accepted'])
        self.assertFalse(event['written'])
        self.assertNotIn(str(path), json.dumps(event))
