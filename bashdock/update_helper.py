"""Independent updater. Runs from a temporary directory after BashDock closes."""
import argparse
import ctypes
import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import re
from pathlib import Path
from .updates import parse_manifest, digest_file, extract_package
from .update_security import load_key
from . import local_updates
from .update_cleanup import installation_guard, prune_previous_installations


def wait_for_pid(pid, timeout=120):
    if sys.platform != 'win32':
        raise OSError('Installing updates requires Windows.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:
            return
        raise OSError('Could not wait for BashDock to close.')
    try:
        if kernel.WaitForSingleObject(handle, timeout * 1000) != 0:
            raise OSError('BashDock did not close. The update has not been installed.')
    finally:
        kernel.CloseHandle(handle)


def processes_in(directory):
    """Find other app/WebEngine processes without terminating unrelated shells."""
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)

    class Entry(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
                    ('heap', ctypes.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                    ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD), ('name', w.WCHAR * 260)]

    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise OSError('Could not check for other BashDock processes.')
    found = []
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.pid != os.getpid():
                handle = kernel.OpenProcess(0x1000, False, entry.pid)
                if handle:
                    try:
                        name, length = ctypes.create_unicode_buffer(32768), w.DWORD(32768)
                        if kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)):
                            if Path(name.value).resolve().is_relative_to(directory):
                                found.append(entry.pid)
                    finally:
                        kernel.CloseHandle(handle)
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return found


def retry(operation, timeout=60, *, blocked=None):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return operation()
        except OSError:
            if blocked:
                blocked()
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def start_app(target, health=None, token=None):
    args = [str(target / 'bashdock.exe')]
    if health is not None:
        args += ['--update-health', str(health), '--update-token', token]
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')
    runtime = getattr(sys, '_MEIPASS', None)
    if runtime:
        env['PATH'] = os.pathsep.join(p for p in env.get('PATH', '').split(os.pathsep)
                                    if p and not Path(p).resolve().is_relative_to(Path(runtime).resolve()))
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    if not kernel.SetDllDirectoryW(None):
        raise OSError('Could not reset DLL lookup before restarting BashDock.')
    try:
        return subprocess.Popen(args, cwd=target.parent, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=0x00000008 | 0x00000200, close_fds=True)
    finally:
        kernel.SetDllDirectoryW(runtime)


def wait_for_health(process, health, token, version, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if health.is_file():
            try:
                data = json.loads(health.read_text(encoding='utf-8'))
                if data == {'token': token, 'version': version}:
                    return True
            except (OSError, ValueError):
                pass
        if process.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def install(plan, key, *, verify=None, wait=wait_for_pid, other_processes=processes_in,
            launch=start_app, healthy=wait_for_health, status=lambda text: None):
    status('Verifying the downloaded update…')
    target = Path(plan['install']).resolve()
    pending = Path(plan['pending']).resolve()
    if type(plan.get('pid')) is not int or not 0 < plan['pid'] < 2**32 or not re.fullmatch('[0-9a-f]{64}', plan.get('token', '')):
        raise ValueError('Invalid update process handoff.')
    if target == target.parent or target == Path.home().resolve() or not (target / 'bashdock.exe').is_file() or not (target / '_internal').is_dir():
        raise ValueError('The update target is not a BashDock installation.')
    arguments = {} if verify is None else {'verify': verify}
    channel = plan.get('channel', 'public')
    if channel == local_updates.CHANNEL:
        manifest = local_updates.verify_pending(target, pending, **arguments).manifest
    elif channel == 'public':
        manifest = parse_manifest((pending / 'manifest.json').read_bytes(),
                                  (pending / 'manifest.sig').read_bytes(), key, **arguments)
    else:
        raise ValueError('Unknown update channel.')
    archive = pending / 'package.zip'
    if archive.stat().st_size != manifest['size'] or digest_file(archive) != manifest['sha256']:
        raise ValueError('The pending update changed. Nothing has been installed.')
    settings = Path(plan['settings']).resolve()
    backup_settings = Path(plan['settings_backup']).resolve()
    if not backup_settings.is_file():
        raise ValueError('The settings backup is missing.')
    # Extract alongside the installation so directory renames stay on one volume.
    stage = Path(tempfile.mkdtemp(prefix='.bashdock-new-', dir=target.parent))
    old = target.with_name('.bashdock-previous-' + secrets.token_hex(8))
    failed = target.with_name('.bashdock-failed-' + secrets.token_hex(8))
    moved_old = moved_new = False
    process = None
    journal = pending / 'transaction.json'
    def record(phase):
        temporary = journal.with_suffix('.tmp')
        temporary.write_text(json.dumps({'phase': phase, 'install': str(target), 'previous': str(old),
                                         'failed': str(failed), 'settings_backup': str(backup_settings)}), encoding='utf-8')
        temporary.replace(journal)
    try:
        status('Preparing the new version…')
        replacement = extract_package(archive, stage)
        record('staged')
        status('Waiting for BashDock to close…')
        wait(plan['pid'])
        deadline = time.monotonic() + 60
        while other_processes(target):
            status('Waiting for other BashDock windows to close…\nClose any other BashDock windows, including minimized windows, to continue.')
            if time.monotonic() >= deadline:
                raise OSError('Close the other BashDock windows before updating.')
            time.sleep(0.5)
        status('Installing the update…')
        def locked():
            status('Waiting for files in the installation folder to become available…\nClose programs using this folder. The update will retry for up to one minute.')
        retry(lambda: target.rename(old), blocked=locked)
        moved_old = True
        record('previous-retained')
        retry(lambda: replacement.rename(target), blocked=locked)
        moved_new = True
        record('installed-awaiting-startup')
        health = pending / 'health.json'
        health.unlink(missing_ok=True)
        status('Starting the new version…')
        process = launch(target, health, plan['token'])
        if not healthy(process, health, plan['token'], manifest['version']):
            raise OSError('The new version did not start successfully.')
        record('healthy')
        if channel == local_updates.CHANNEL:
            try:
                local_updates.acknowledge(target, pending)
            except (OSError, ValueError):
                pass  # A healthy installed build must not roll back over inbox cleanup.
        try:
            prune_previous_installations(target, retained=old, other_processes=other_processes)
        except Exception:
            # Maintenance must never roll back a successfully started update.
            logging.warning('Previous installation cleanup deferred after successful update.')
        status('Update complete.')
        return {'ok': True, 'version': manifest['version'], 'previous': str(old)}
    except BaseException:
        status('The update could not finish. Keeping or restoring the previous version…')
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        if moved_new:
            retry(lambda: target.rename(failed))
        if moved_old:
            retry(lambda: old.rename(target))
            if settings.is_file():
                shutil.copyfile(settings, pending / 'failed-settings.json')
            settings.parent.mkdir(parents=True, exist_ok=True)
            temporary = settings.with_name(settings.name + '.update-restore')
            shutil.copyfile(backup_settings, temporary)
            temporary.replace(settings)
            automatic = Path(plan.get('automatic_backup', pending / 'previous-settings.bak'))
            shutil.copyfile(automatic if automatic.is_file() else backup_settings,
                            settings.with_name(settings.name + '.bak'))
            record('rolled-back')
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--install', type=Path)
    group.add_argument('--self-test', type=Path)
    group.add_argument('--acceptance-test', type=Path, metavar='NEW_OUTPUT_FOLDER')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--assets', type=Path)
    args = parser.parse_args()
    if args.acceptance_test:
        from .update_acceptance import run_acceptance
        from .update_status import UpdateStatus
        if not args.baseline or not args.assets:
            parser.error('--acceptance-test requires --baseline and --assets')
        try:
            with UpdateStatus('BashDock updater acceptance test') as status:
                run_acceptance(args.baseline, args.assets, args.acceptance_test, status=status.set_text)
        except Exception as error:
            ctypes.windll.user32.MessageBoxW(None, str(error), 'Updater acceptance test failed', 0x10)
            raise SystemExit(1)
        ctypes.windll.user32.MessageBoxW(None,
            'All checks passed. Inspect and close the disposable BashDock window.\nResults: ' +
            str(args.acceptance_test / 'acceptance-results.json'), 'Updater acceptance test passed', 0x40)
        return
    if args.self_test:
        from .update_security import KEY_FILE
        json.loads(KEY_FILE.read_text(encoding='utf-8'))
        from .updates import tls_context
        context = tls_context()
        import ssl
        if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError('The update TLS context must verify hostnames and certificates.')
        from .update_status import UpdateStatus
        with UpdateStatus() as status:
            status.set_text('Checking the independent updater…')
            time.sleep(0.2)
        args.self_test.write_text(json.dumps({'ok': True, 'frozen': bool(getattr(sys, 'frozen', False))}))
        return
    # Shared with startup cleanup; wait briefly if maintenance owns the lock.
    plan = json.loads(args.install.read_text(encoding='utf-8'))
    from .updates import cache_directory
    cache = cache_directory()
    cache.mkdir(parents=True, exist_ok=True)
    result_path = cache / 'result.json'
    with installation_guard(plan['install'], timeout=60) as acquired:
        try:
            if not acquired:
                raise OSError('Another BashDock update or cleanup is still running. Try again shortly.')
            from .update_status import UpdateStatus
            with UpdateStatus() as status:
                key = None if plan.get('channel') == local_updates.CHANNEL else load_key()
                result = install(plan, key, status=status.set_text)
            result_path.write_text(json.dumps(result), encoding='utf-8')
        except Exception as error:
            result_path.write_text(json.dumps({'ok': False, 'message': str(error)}), encoding='utf-8')
            target = Path(plan['install'])
            if (target / 'bashdock.exe').is_file():
                try:
                    start_app(target)
                except OSError:
                    pass
            if sys.platform == 'win32':
                ctypes.windll.user32.MessageBoxW(None, str(error) + '\nYour previous installation has been kept or restored.',
                                                'BashDock update could not finish', 0x10)
            raise SystemExit(1)
