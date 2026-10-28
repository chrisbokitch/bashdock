"""Recovery-safe retention, legacy journal migration, and cleanup failures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from bashdock import local_updates, update_cleanup as cleanup, update_helper
from qt_lifecycle import GuiTestCase
from test_updates import metadata, zip_bytes


class UpdateCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / 'installed app'
        self.app(self.target)
        self.cache = self.root / 'BashDock/updates'
        for module in (cleanup, local_updates):
            p = patch.object(module, 'cache_directory', return_value=self.cache)
            p.start()
            self.addCleanup(p.stop)

    def app(self, directory):
        (directory / '_internal').mkdir(parents=True)
        (directory / 'bashdock.exe').write_bytes(b'old executable')

    def journal(self, previous, *, index=1, phase='healthy', install=None, local=False):
        root = local_updates.inbox_root(self.target) if local else self.cache
        path = root / f'pending-{index}/transaction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(phase=phase, install=str(install or self.target),
                                        previous=str(previous))))
        os.utime(path, ns=(index * 1_000_000_000, index * 1_000_000_000))
        return path

    def backup(self, index, *, dotted=True, **kwargs):
        path = self.root / (('.' if dotted else '') + f'bashdock-previous-{index:016x}')
        self.app(path)
        self.journal(path, index=index, **kwargs)
        return path

    def prune(self, **kwargs):
        return cleanup.prune_previous_installations(self.target, other_processes=lambda p: [], **kwargs)

    def test_legacy_public_and_local_backups_pruned_but_latest_and_settings_kept(self):
        a = self.backup(1)
        b = self.backup(2, dotted=False, local=True)
        latest = self.backup(3)
        settings = self.root / 'settings.json'
        settings.write_text('user settings')
        self.assertCountEqual([a, b], self.prune())
        self.assertTrue(latest.is_dir())
        self.assertTrue((self.target / 'bashdock.exe').is_file())
        self.assertEqual('user settings', settings.read_text())
        self.assertTrue((self.cache / 'pending-1/transaction.json').is_file())
        self.assertEqual([], self.prune())

    def test_no_name_only_deletion_or_cross_installation_or_unfinished_recovery(self):
        other = self.root / 'other app'
        unfinished = [self.backup(i, phase=phase) for i, phase in enumerate(
            ('staged', 'previous-retained', 'installed-awaiting-startup', 'rolled-back'), 1)]
        foreign = self.backup(5, install=other)
        orphan = self.root / ('.bashdock-previous-' + 'a' * 16)
        self.app(orphan)
        malformed = self.backup(6)
        (self.cache / 'pending-6/transaction.json').write_text('{broken')
        latest = self.backup(7)
        self.assertEqual([], self.prune())
        for path in unfinished + [foreign, orphan, malformed, latest]:
            self.assertTrue(path.is_dir(), str(path))
        # A conflicting unfinished transaction protects an otherwise healthy copy.
        self.journal(latest, index=8, phase='installed-awaiting-startup')
        self.backup(9)
        self.assertEqual([], self.prune())

    def test_journal_cannot_authorize_current_install_parent_outside_or_named_project(self):
        outside = self.root / 'outside'
        outside.mkdir()
        cases = [self.target, self.root, outside, self.root / 'bashdock-previous-my-project',
                 self.root / '.bashdock-previous-1234',
                 self.root / 'subdir' / ('.bashdock-previous-' + 'c' * 16)]
        for index, path in enumerate(cases, 1):
            path.mkdir(parents=True, exist_ok=True)
            self.journal(path, index=index)
        self.backup(9)
        self.assertEqual([], self.prune())
        self.assertTrue(all(p.is_dir() for p in cases))

    def test_busy_backups_and_locked_partial_removals_retry_without_failing_startup(self):
        busy = self.backup(1)
        locked = self.backup(2)
        latest = self.backup(3)
        def partial(path):
            (path / 'bashdock.exe').unlink()
            raise PermissionError('locked runtime')
        with patch.object(cleanup.shutil, 'rmtree', side_effect=partial):
            self.assertEqual([], cleanup.prune_previous_installations(self.target,
                other_processes=lambda p: [42] if p == busy else []))
        self.assertTrue(busy.is_dir())
        self.assertFalse((locked / 'bashdock.exe').exists())
        self.assertCountEqual([busy, locked], self.prune())
        self.assertTrue(latest.exists())

    def test_process_inspection_failure_is_conservative(self):
        old = self.backup(1)
        self.backup(2)
        self.assertEqual([], cleanup.prune_previous_installations(self.target,
            other_processes=Mock(side_effect=OSError('enumeration unavailable'))))
        self.assertTrue(old.exists())

    def test_missing_current_installation_prevents_all_cleanup(self):
        old = self.backup(1)
        self.backup(2)
        (self.target / 'bashdock.exe').unlink()
        self.assertEqual([], self.prune())
        self.assertTrue(old.exists())

    def test_symlink_backup_never_follows_or_deletes_external_tree(self):
        outside = self.root / 'external'
        self.app(outside)
        linked = self.root / ('.bashdock-previous-' + 'd' * 16)
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Directory symlinks require Windows developer mode or permission')
        self.journal(linked)
        old = self.backup(2)
        (old / 'external link').symlink_to(outside, target_is_directory=True)
        self.backup(3)
        self.assertEqual([old], self.prune())
        self.assertTrue(linked.is_symlink())
        self.assertEqual(b'old executable', (outside / 'bashdock.exe').read_bytes())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows directory junctions')
    def test_windows_junctions_are_not_traversed(self):
        outside = self.root / 'outside'
        self.app(outside)
        top = self.root / ('.bashdock-previous-' + 'e' * 16)
        old = self.backup(2)
        nested = old / 'external junction'
        for link in (top, nested):
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                           check=True, capture_output=True)
            self.addCleanup(lambda p=link: p.rmdir() if p.exists() else None)
        self.journal(top)
        self.backup(3)
        self.assertEqual([old], self.prune())
        self.assertTrue(top.exists())
        self.assertTrue((outside / 'bashdock.exe').is_file())

    def plan(self):
        pending = self.cache / 'pending-new'
        pending.mkdir(parents=True)
        content = zip_bytes()
        (pending / 'package.zip').write_bytes(content)
        (pending / 'manifest.json').write_text(json.dumps(metadata(content=content)))
        (pending / 'manifest.sig').write_bytes(b'signature')
        settings = self.root / 'settings.json'
        settings.write_text('settings')
        return dict(install=str(self.target), pending=str(pending), pid=12, token='a'*64,
                    settings=str(settings), settings_backup=str(settings))

    def test_helper_prunes_only_after_health_and_cleanup_error_cannot_roll_back(self):
        old = self.backup(1)
        plan = self.plan()
        def health(*args):
            self.assertTrue(old.is_dir())
            self.assertEqual(2, len(list(self.root.glob('.bashdock-previous-*'))))
            return True
        remove = shutil.rmtree
        def locked(path, **kwargs):
            if path == old:
                raise PermissionError('locked')
            return remove(path, **kwargs)
        with patch.object(cleanup.shutil, 'rmtree', side_effect=locked):
            result = update_helper.install(plan, {}, verify=lambda *a: None, wait=Mock(),
                other_processes=lambda p: [], launch=Mock(return_value=Mock()), healthy=health)
        self.assertTrue(result['ok'])
        self.assertEqual(b'new executable', (self.target / 'bashdock.exe').read_bytes())
        self.assertEqual('healthy', json.loads((Path(plan['pending']) / 'transaction.json').read_text())['phase'])
        self.assertEqual([old], self.prune())
        self.assertTrue(Path(result['previous']).is_dir())

    def test_cleanup_exception_never_rolls_back_successful_update(self):
        # The installer also isolates unexpected maintenance failures.
        process = Mock()
        with patch.object(update_helper, 'prune_previous_installations', side_effect=RuntimeError('cleanup')), self.assertLogs(level='WARNING'):
            result = update_helper.install(self.plan(), {}, verify=lambda *a: None, wait=Mock(),
                other_processes=lambda p: [], launch=Mock(return_value=process), healthy=lambda *a: True)
        self.assertTrue(result['ok'])
        self.assertEqual(b'new executable', (self.target / 'bashdock.exe').read_bytes())
        process.terminate.assert_not_called()

    def test_failed_health_never_prunes_and_restores_original_installation(self):
        old = self.backup(1)
        process = Mock()
        with patch.object(update_helper, 'prune_previous_installations') as prune:
            with self.assertRaisesRegex(OSError, 'did not start'):
                update_helper.install(self.plan(), {}, verify=lambda *a: None, wait=Mock(),
                    other_processes=lambda p: [], launch=Mock(return_value=process), healthy=lambda *a: False)
        prune.assert_not_called()
        self.assertTrue(old.exists())
        self.assertEqual(b'old executable', (self.target / 'bashdock.exe').read_bytes())

    def test_startup_skips_maintenance_during_an_install(self):
        from contextlib import contextmanager
        @contextmanager
        def busy(*args, **kwargs):
            yield False
        with patch.object(cleanup, 'installation_guard', busy), patch.object(
                cleanup, 'prune_previous_installations') as prune:
            cleanup.cleanup_previous_installations(self.target)
        prune.assert_not_called()

    def test_helper_waits_for_cleanup_lock_and_closes_rejected_handles(self):
        kernel = Mock()
        kernel.CreateMutexW.side_effect = [11, 12]
        with patch.object(cleanup.ctypes, 'WinDLL', return_value=kernel, create=True), patch.object(
                cleanup.ctypes, 'get_last_error', side_effect=[183, 0], create=True), patch.object(
                cleanup.time, 'sleep'):
            with cleanup.installation_guard(self.target, timeout=60) as acquired:
                self.assertTrue(acquired)
                kernel.CloseHandle.assert_called_once_with(11)
        self.assertEqual([11, 12], [c.args[0] for c in kernel.CloseHandle.call_args_list])

    @unittest.skipUnless(sys.platform == 'win32', 'Native named mutex coordination')
    def test_cleanup_and_helper_share_installation_lock_and_release_it_on_failure(self):
        with cleanup.installation_guard(self.target) as first:
            self.assertTrue(first)
            with cleanup.installation_guard(self.root / 'other app') as independent:
                self.assertTrue(independent)
            with cleanup.installation_guard(self.target) as second:
                self.assertFalse(second)
            cleanup.cleanup_previous_installations(self.target)
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            with cleanup.installation_guard(self.target) as acquired:
                self.assertTrue(acquired)
                raise RuntimeError('fixture')
        with cleanup.installation_guard(self.target) as acquired:
            self.assertTrue(acquired)


class UpdateCleanupControllerTests(GuiTestCase):
    def test_packaged_startup_schedules_background_cleanup_and_cancel_prevents_it(self):
        from bashdock import update_controller
        target = Path(tempfile.gettempdir()) / "BashDock cleanup controller fixture"
        with patch.object(update_controller.sys, 'platform', 'win32'), patch.object(
                update_controller.sys, 'frozen', True, create=True), patch.object(
                update_controller.QTimer, 'singleShot') as timer:
            controller = update_controller.UpdateController(installation=target)
        timer.assert_called_once_with(5000, controller.cleanup_previous)
        with patch.object(update_controller.threading, 'Thread') as thread:
            controller.cleanup_previous()
            thread.assert_called_once_with(target=cleanup.cleanup_previous_installations,
                args=(target,), name='BashDock previous installation cleanup', daemon=True)
            thread.return_value.start.assert_called_once()
            controller.cancel()
            thread.reset_mock()
            controller.cleanup_previous()
            thread.assert_not_called()
        controller.deleteLater()
        self.app.processEvents()
