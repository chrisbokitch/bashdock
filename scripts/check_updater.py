"""Ensure the one-file helper runs without the app's _internal directory."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='BashDock independent updater ') as temp:
    directory = Path(temp)
    helper = directory / 'bashdock-updater.exe'
    shutil.copyfile(ROOT / 'dist/bashdock/bashdock-updater.exe', helper)
    report = directory / 'self-test.json'
    subprocess.run([str(helper), '--self-test', str(report)], cwd=directory, timeout=60, check=True)
    result = json.loads(report.read_text())
    if result != {'ok': True, 'frozen': True}:
        raise ValueError('The independent updater failed its packaged self-test.')
print('Independent updater verified outside the application folder.')
