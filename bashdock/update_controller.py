"""Qt orchestration; network and archive work stays off the UI thread."""
import ctypes
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from . import config
from ._version import __version__
from .updates import cache_directory, discover, download_update, update_error_message
from .update_security import load_key


class UpdateController(QObject):
    changed = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.busy = False
        self.cancelled = threading.Event()
        self.available = None
        self.ready = None

    def check(self, download=True):
        if self.busy or self.ready is not None:
            return
        self._start(lambda: self._check(download))

    def _check(self, download):
        self._emit('checking', None)
        found = discover(__version__, load_key())
        if found is None:
            self._emit('current', None)
            return
        self.available = found
        if download:
            self._download()
        else:
            self._emit('available', found[0]['version'])

    def download(self):
        if not self.busy and self.available is not None:
            self._start(self._download)

    def _download(self):
        self._emit('downloading', self.available[0]['version'])
        self.ready = download_update(self.available, cache_directory(), self.cancelled)
        self._emit('ready', self.ready.manifest['version'])

    def _emit(self, state, value):
        if not self.cancelled.is_set():
            try:
                self.changed.emit(state, value)
            except RuntimeError:
                pass

    def _start(self, operation):
        self.busy = True
        def work():
            try:
                operation()
            except Exception as error:
                self._emit('error', update_error_message(error))
            finally:
                self.busy = False
                self._emit('finished', None)
        threading.Thread(target=work, name='BashDock update download', daemon=True).start()

    def launch_install(self):
        if self.ready is None:
            raise ValueError('The update is not ready.')
        target = Path(sys.executable).resolve().parent
        helper = target / 'bashdock-updater.exe'
        if not helper.is_file() or not (target / '_internal').is_dir():
            raise OSError('This installation does not contain the update helper. Download the complete application ZIP.')
        # Confirm writability before asking the app to exit; never request elevation.
        probe = target.parent / ('.bashdock-write-test-' + secrets.token_hex(8))
        try:
            with probe.open('xb'):
                pass
        except OSError:
            raise OSError('This folder cannot be updated without administrator access. Download the update to a writable folder.') from None
        finally:
            probe.unlink(missing_ok=True)
        directory = self.ready.directory
        executable = directory / 'bashdock-updater.exe'
        shutil.copyfile(helper, executable)
        backup = config.archive_workspace(self.parent().snapshot(), 'before-update')
        original_backup = directory / 'previous-settings.bak'
        if config.backup_path().is_file():
            shutil.copyfile(config.backup_path(), original_backup)
        plan = {'install': str(target), 'pending': str(directory), 'pid': os.getpid(),
                'settings': str(config.config_path()), 'settings_backup': str(backup),
                'automatic_backup': str(original_backup),
                'token': secrets.token_hex(32)}
        path = directory / 'plan.json'
        path.write_text(json.dumps(plan), encoding='utf-8')
        # PyInstaller changes the DLL lookup directory. Do not pass it to the helper.
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        runtime = getattr(sys, '_MEIPASS', None)
        if not kernel.SetDllDirectoryW(None):
            raise OSError('Could not prepare the independent updater.')
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')
        if runtime:
            env['PATH'] = os.pathsep.join(p for p in env.get('PATH', '').split(os.pathsep)
                                        if p and not Path(p).resolve().is_relative_to(Path(runtime).resolve()))
        try:
            subprocess.Popen([str(executable), '--install', str(path)], cwd=directory, env=env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=0x00000008 | 0x00000200, close_fds=True)
        finally:
            kernel.SetDllDirectoryW(runtime)

    def cancel(self):
        self.cancelled.set()
