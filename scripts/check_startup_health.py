"""Exercise real compiled GUI startup receipts with isolated user directories."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bashdock import config
from bashdock.local_updates import installation_id
from bashdock.update_helper import wait_for_health


def verify_startup_health(executable, root, version):
    executable, root = Path(executable).resolve(), Path(root).resolve()
    sandbox = root / 'startup health sandbox'
    env = dict(os.environ, APPDATA=str(sandbox / 'roaming'), LOCALAPPDATA=str(sandbox / 'local'),
               PYINSTALLER_RESET_ENVIRONMENT='1')
    settings = config.defaults()
    settings['updates'] = dict(automatic=False, download=False)
    settings['confirm_on_exit'] = False
    config.save(settings, Path(env['APPDATA']) / 'bashdock/settings.json')
    cache = Path(env['LOCALAPPDATA']) / 'BashDock'
    locations = {'public': cache / 'updates/pending-startup-smoke/health.json',
                 'local': cache / 'local-updates' / installation_id(executable.parent) /
                          'pending-startup-smoke/health.json'}
    for channel, health in locations.items():
        health.parent.mkdir(parents=True, exist_ok=True)
        health.unlink(missing_ok=True)
        token = secrets.token_hex(32)
        process = subprocess.Popen([str(executable), '--update-health', str(health), '--update-token', token],
            cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if not wait_for_health(process, health, token, version):
                raise ValueError(f'Compiled app did not confirm {channel} update startup.')
            print(f'Compiled {channel} update startup confirmation passed.', flush=True)
        finally:
            if process.poll() is None:
                # This process and its WebEngine children belong to the isolated
                # smoke run, never the user's installed/running BashDock.
                try:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
                finally:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=20)
            else:
                process.wait(timeout=20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    try:
        with tempfile.TemporaryDirectory(prefix='BashDock startup check ') as folder:
            verify_startup_health(args.executable, Path(folder), version)
        result = dict(ok=True, version=version, channels=['public', 'local'])
    except Exception as error:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(dict(ok=False, error=str(error))), encoding='utf-8')
        raise
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result), encoding='utf-8')


if __name__ == '__main__':
    main()
