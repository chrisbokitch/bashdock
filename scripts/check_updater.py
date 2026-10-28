"""Verify a GUI-free one-file helper independently of the installed app."""
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def reject_gui_payload(names):
    offenders = []
    for name in names:
        normalized = name.replace('\\', '/').casefold()
        if (normalized.startswith(('pyside6', 'shiboken6')) or
                (normalized.rsplit('/', 1)[-1].startswith('qt6') and normalized.endswith('.dll'))):
            offenders.append(name)
    if offenders:
        raise ValueError('The independent updater unexpectedly bundles Qt: ' + ', '.join(offenders[:5]))


def inspect_helper(helper):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(helper))
    modules = archive.open_embedded_archive('PYZ.pyz').toc
    reject_gui_payload([*archive.toc, *modules])
    with helper.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(bytes=helper.stat().st_size, sha256=digest, qt_entries=0,
                embedded_files=len(archive.toc), python_modules=len(modules),
                packed_payload_bytes=sum(entry[1] for entry in archive.toc.values()))


def main():
    source = ROOT / 'dist/bashdock/bashdock-updater.exe'
    details = inspect_helper(source)
    with tempfile.TemporaryDirectory(prefix='BashDock independent updater ') as temp:
        directory = Path(temp)
        helper = directory / 'bashdock-updater.exe'
        shutil.copyfile(source, helper)
        report = directory / 'self-test.json'
        subprocess.run([str(helper), '--self-test', str(report)], cwd=directory, timeout=60, check=True)
        if json.loads(report.read_text()) != {'ok': True, 'frozen': True}:
            raise ValueError('The independent updater failed its packaged self-test.')
    details['independent_self_test'] = 'passed'
    output = ROOT / 'build/updater-size.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(details, indent=2)+'\n', encoding='utf-8')
    print('Independent updater verified outside the application folder; zero Qt entries.')
    print('Updater size: ' + json.dumps(details), flush=True)


if __name__ == '__main__':
    main()
