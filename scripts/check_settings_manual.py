"""Guide installed-app settings acceptance using a disposable APPDATA profile."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from bashdock import config


DAMAGED = b'BASHDOCK_M7_DISPOSABLE_DAMAGED_SETTINGS'


def exercise(executable, profile, *, launch=subprocess.run):
    executable, profile = Path(executable).resolve(), Path(profile).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    if any(profile.iterdir()):
        raise ValueError('The disposable APPDATA folder must be empty.')
    settings = profile / 'bashdock' / 'settings.json'
    backup = config.backup_path(settings)
    environment = dict(os.environ, APPDATA=str(profile))

    def open_app(instructions):
        print(f'\n{instructions}', flush=True)
        result = launch([str(executable)], env=environment.copy(), cwd=str(executable.parent), check=False)
        if result.returncode:
            raise RuntimeError(f'BashDock exited with code {result.returncode}; stopping this check.')

    print(f'Disposable APPDATA: {profile}\nSettings/archives: {settings.parent}\n'
          'Your normal APPDATA is not changed.', flush=True)
    open_app('1. Export/import smoke: create a recognisable tab, export settings, rename it, '
             'cancel an import, then import the export. Inspect the separate before-import backup. '
             'Close this disposable BashDock window when finished.')
    # Never damage a file until this isolated app has produced both valid files.
    config.read(settings)
    backup_data = config.read(backup)
    backup_bytes = backup.read_bytes()
    settings.write_bytes(DAMAGED)
    open_app('2. Recovery cancellation: choose Cancel in Recover settings, then close BashDock '
             'without saving tab changes. The damaged disposable file must remain unchanged.')
    if settings.read_bytes() != DAMAGED or backup.read_bytes() != backup_bytes:
        raise RuntimeError('Cancelling recovery changed the damaged settings or its backup.')
    open_app('3. Recovery restore: choose Restore backup, confirm replacement, inspect the recovered '
             'tabs/settings and dialog presentation, then close BashDock.')
    restored = config.read(settings)
    if [tab['id'] for tab in restored['tabs']] != [tab['id'] for tab in backup_data['tabs']]:
        raise RuntimeError('The recovered tab identities do not match the backup; use Restore backup, not Start fresh.')
    archives = list((settings.parent / 'backups').glob('settings-damaged-*.json'))
    if not any(path.read_bytes() == DAMAGED for path in archives):
        raise RuntimeError('Recovery did not preserve the original damaged bytes.')
    print('\nFile checks passed: cancellation preserved both files; recovery restored backup tab identities '
          'and archived the damaged bytes. Confirm the visual/manual results separately.\n'
          f'Evidence is kept in: {profile}', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installation', type=Path, help='Installed BashDock folder or bashdock.exe')
    arguments = parser.parse_args(argv)
    if sys.platform != 'win32':
        parser.error('The installed-app manual check requires Windows.')
    executable = arguments.installation.resolve()
    if executable.is_dir():
        executable /= 'bashdock.exe'
    if not executable.is_file() or executable.name.lower() != 'bashdock.exe':
        parser.error('Choose an existing installed bashdock.exe or its folder.')
    profile = Path(tempfile.mkdtemp(prefix='bashdock-m7-'))
    try:
        exercise(executable, profile)
    except (OSError, ValueError, RuntimeError) as error:
        print(f'Check stopped: {error}\nDisposable evidence is kept in: {profile}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
