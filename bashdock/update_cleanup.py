"""Bounded retention of previous installations identified by update journals."""
from contextlib import contextmanager
import ctypes
import json
import logging
from pathlib import Path
import re
import shutil
import stat
import time

from .local_updates import inbox_root, installation_id
from .updates import cache_directory


def linked(path):
    """Reject both symlinks and Windows reparse points, including junctions."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


@contextmanager
def installation_guard(target, *, timeout=0):
    # Match older helpers' existence-based mutex, including those which did not
    # own the mutex. Close each rejected handle so it cannot keep the lock alive.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    deadline = time.monotonic() + timeout
    handle = None
    while True:
        candidate = kernel.CreateMutexW(None, False, 'Local\\BashDock-Update-' + installation_id(target))
        if not candidate:
            raise OSError('Could not lock the BashDock installation.')
        if ctypes.get_last_error() != 183:
            handle = candidate
            break
        kernel.CloseHandle(candidate)
        if time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    try:
        yield handle is not None
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)


def prune_previous_installations(installation, *, retained=None, other_processes=None):
    """Caller holds installation_guard; only healthy, attributable backups qualify.

    Retain the latest successful rollback copy. Never infer ownership from a
    sibling's name alone. Journals and settings are kept for diagnosis/recovery.
    """
    target = Path(installation).resolve()
    if not (target / 'bashdock.exe').is_file() or not (target / '_internal').is_dir():
        return []
    if other_processes is None:
        from .update_helper import processes_in
        other_processes = processes_in
    backups, protected = {}, set()
    for root in (cache_directory(), inbox_root(target)):
        if not root.exists() or linked(root):
            continue
        for pending in root.glob('pending-*'):
            try:
                journal = pending / 'transaction.json'
                if linked(pending) or linked(journal) or journal.stat().st_size > 16384:
                    continue
                data = json.loads(journal.read_text(encoding='utf-8'))
                if not isinstance(data, dict) or Path(data['install']).resolve() != target:
                    continue
                previous = Path(data['previous'])
                if (not previous.is_absolute() or previous.parent != target.parent or
                        not re.fullmatch(r'\.?bashdock-previous-[0-9a-f]{16}', previous.name) or
                        linked(previous) or not previous.is_dir()):
                    continue
                if data.get('phase') != 'healthy':
                    protected.add(previous)
                else:
                    backups[previous] = max(backups.get(previous, 0), journal.stat().st_mtime_ns)
            except (OSError, ValueError, KeyError, TypeError):
                continue  # Missing/malformed/ambiguous evidence is not deletion authority.
    if not backups:
        return []
    retained = Path(retained) if retained is not None else max(backups, key=backups.get)
    removed = []
    for previous in backups:
        if previous == retained or previous in protected:
            continue
        try:
            if linked(previous) or other_processes(previous):
                continue
            # rmtree does not follow directory symlinks or Windows junctions.
            # Keep the journal if a lock/permissions error leaves partial files;
            # the next startup retries this same attributable directory.
            shutil.rmtree(previous)
            removed.append(previous)
        except OSError:
            logging.info('Previous BashDock installation cleanup deferred; files may be in use.')
    if removed:
        logging.info('Cleaned up %d superseded BashDock installation(s).', len(removed))
    return removed


def cleanup_previous_installations(installation):
    """Best effort startup maintenance; never race an update or block the UI."""
    try:
        with installation_guard(installation) as acquired:
            if acquired:
                prune_previous_installations(installation)
    except (OSError, ValueError):
        logging.info('Previous BashDock installation cleanup deferred.')
