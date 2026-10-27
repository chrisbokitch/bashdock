"""Updater failure boundaries: real files, injected OS/network failures, no user install."""
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from PySide6.QtWidgets import QApplication
from bashdock import config, updates
from bashdock.update_controller import UpdateController
from test_updates import metadata, zip_bytes


class UpdateOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_u5_interruption_and_cancellation_remove_only_partial_download_and_allow_retry(self):
        content = zip_bytes()
        manifest = metadata(content=content)
        discovered = manifest, json.dumps(manifest).encode(), b'signature'
        for failure in ('connection', 'cancel'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                cache = Path(temp)
                existing = cache / 'pending-existing'
                existing.mkdir()
                (existing / 'keep').write_bytes(b'previous ready update')
                cancel = threading.Event()

                class Interrupted(io.BytesIO):
                    reads = 0

                    def read(self, size=-1):
                        self.reads += 1
                        if self.reads == 1:
                            return super().read(32)
                        if failure == 'connection':
                            raise ConnectionResetError('fixture connection interrupted')
                        cancel.set()
                        return super().read(size)

                with self.assertRaises((ConnectionResetError, ValueError)):
                    updates.download_update(discovered, cache, cancel,
                                            opener=lambda url: Interrupted(content))
                self.assertEqual([existing], list(cache.iterdir()))
                self.assertEqual(b'previous ready update', (existing / 'keep').read_bytes())
                ready = updates.download_update(discovered, cache, threading.Event(),
                                                opener=lambda url: io.BytesIO(content))
                self.assertEqual(content, (ready.directory / 'package.zip').read_bytes())

    def test_u2_u3_launch_failures_never_spawn_or_modify_install_and_success_is_detached(self):
        for failure in ('permission', 'copy', 'backup', 'dll', 'spawn', None):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                target, pending = root / 'installed app', root / 'pending update'
                (target / '_internal').mkdir(parents=True)
                pending.mkdir()
                exe = target / 'bashdock.exe'
                exe.write_bytes(b'unchanged installation')
                (target / 'bashdock-updater.exe').write_bytes(b'fixture helper')
                settings = root / 'profile/settings.json'
                config.save(config.defaults(), settings)
                original = settings.read_bytes()
                controller = UpdateController(installation=target)
                controller.local_timer.stop()
                controller.ready = updates.ReadyUpdate({'version': '0.15.0'}, pending)
                parent = Mock()
                parent.snapshot.return_value = config.defaults()
                kernel = Mock()
                kernel.SetDllDirectoryW.return_value = 0 if failure == 'dll' else 1
                real_open = Path.open

                def open_file(path, *args, **kwargs):
                    if failure == 'permission' and path.name.startswith('.bashdock-write-test-'):
                        raise PermissionError('fixture denied write')
                    return real_open(path, *args, **kwargs)

                from contextlib import ExitStack
                with ExitStack() as stack:
                    stack.enter_context(patch('bashdock.update_controller.sys.executable', str(exe)))
                    stack.enter_context(patch('bashdock.update_controller.sys._MEIPASS',
                                             str(target / '_internal'), create=True))
                    remaining_path = os.pathsep.join((str(target / '_internal-other'), os.defpath))
                    stack.enter_context(patch.dict(os.environ, PATH=os.pathsep.join((
                        str(target / '_internal'), str(target / '_internal/Qt'), remaining_path))))
                    stack.enter_context(patch('bashdock.config.config_path', return_value=settings))
                    stack.enter_context(patch.object(controller, 'parent', return_value=parent))
                    stack.enter_context(patch.object(Path, 'open', open_file))
                    stack.enter_context(patch('bashdock.update_controller.ctypes.WinDLL',
                                             return_value=kernel, create=True))
                    spawn = stack.enter_context(patch('bashdock.update_controller.subprocess.Popen'))
                    if failure == 'copy':
                        stack.enter_context(patch('bashdock.update_controller.shutil.copyfile',
                                                 side_effect=OSError('fixture copy failed')))
                    if failure == 'backup':
                        stack.enter_context(patch('bashdock.config.archive_workspace',
                                                 side_effect=OSError('fixture backup failed')))
                    if failure == 'spawn':
                        spawn.side_effect = OSError('fixture spawn failed')
                    if failure:
                        with self.assertRaises(OSError) as error:
                            controller.launch_install()
                        if failure == 'permission':
                            self.assertIn('writable folder', str(error.exception))
                            parent.snapshot.assert_not_called()
                        if failure != 'spawn':
                            spawn.assert_not_called()
                    else:
                        controller.launch_install()
                        args, kwargs = spawn.call_args
                        self.assertEqual([str(pending / 'bashdock-updater.exe'), '--install',
                                          str(pending / 'plan.json')], args[0])
                        self.assertEqual(0x208, kwargs['creationflags'])
                        self.assertTrue(kwargs['close_fds'])
                        self.assertEqual('1', kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'])
                        self.assertEqual(remaining_path, kwargs['env']['PATH'])
                        plan = json.loads((pending / 'plan.json').read_text())
                        self.assertEqual(str(target), plan['install'])
                        self.assertEqual(parent.snapshot.return_value['tabs'],
                                         config.read(Path(plan['settings_backup']))['tabs'])
                    if failure in ('spawn', None):
                        self.assertEqual([call(None), call(str(target / '_internal'))],
                                         kernel.SetDllDirectoryW.call_args_list)
                self.assertEqual(b'unchanged installation', exe.read_bytes())
                self.assertEqual(original, settings.read_bytes())
                self.assertFalse(list(root.glob('.bashdock-write-test-*')))
                self.assertIsNotNone(controller.ready)
                self.assertFalse(controller.cancelled.is_set())
                controller.cancel()

    def test_u5_check_without_download_does_not_fetch_package_or_launch_helper(self):
        controller = UpdateController()
        self.addCleanup(controller.cancel)
        found = metadata(), b'manifest', b'signature'
        events = []
        controller.changed.connect(lambda state, value: events.append((state, value)))
        with patch.object(controller, '_check_local', return_value=False), \
                patch('bashdock.update_controller.load_key', return_value={}), \
                patch('bashdock.update_controller.discover', return_value=found), \
                patch('bashdock.update_controller.download_update') as download, \
                patch.object(controller, 'launch_install') as launch:
            controller._check(False)
        self.assertEqual([('checking', None), ('available', '0.12.0')], events)
        self.assertEqual(found, controller.available)
        self.assertIsNone(controller.ready)
        download.assert_not_called()
        launch.assert_not_called()
