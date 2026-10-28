"""Measure a portable ZIP without executing or extracting its application."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile


def component(name):
    path = name.removeprefix('bashdock/')
    if path == 'bashdock-updater.exe':
        return 'Independent updater'
    if path == 'third-party-licenses.zip' or path.startswith('licenses/'):
        return 'License notices'
    if path.startswith('_internal/PySide6/'):
        qt = path.removeprefix('_internal/PySide6/')
        if qt.startswith('resources/'):
            if '.debug.' in qt:
                return 'WebEngine debug resource packs'
            if 'devtools' in qt:
                return 'WebEngine release developer-tools resources'
            return 'Other WebEngine resources'
        if qt.startswith('translations/'):
            return 'Qt / WebEngine translations'
        if qt.startswith('qml/'):
            return 'QML files and plugins'
        if 'WebEngine' in qt:
            return 'WebEngine libraries and helper'
        return 'Other Qt / PySide runtime'
    if path.startswith('_internal/bashdock/') or not path.startswith('_internal/'):
        return 'Application executable, assets and metadata'
    return 'Python and other runtime dependencies'


def measure(archive):
    archive = Path(archive)
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    with zipfile.ZipFile(archive) as bundle:
        entries = [dict(path=i.filename, compressed=i.compress_size, installed=i.file_size,
                        component=component(i.filename)) for i in bundle.infolist() if not i.is_dir()]
    groups = {}
    for entry in entries:
        group = groups.setdefault(entry['component'], dict(compressed=0, installed=0, files=0))
        group['compressed'] += entry['compressed']
        group['installed'] += entry['installed']
        group['files'] += 1
    payload = sum(e['compressed'] for e in entries)
    return dict(filename=archive.name, sha256=digest, archive_bytes=archive.stat().st_size,
                payload_bytes=payload, archive_overhead_bytes=archive.stat().st_size-payload,
                installed_bytes=sum(e['installed'] for e in entries), file_count=len(entries),
                components=groups, files=sorted(entries, key=lambda e: e['compressed'], reverse=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--json', type=Path, help='Write exact byte counts and the complete file inventory.')
    parser.add_argument('--csv', type=Path, help='Write the complete per-file inventory.')
    args = parser.parse_args()
    data = measure(args.archive)
    print(f"{data['filename']}: {data['archive_bytes']/2**20:.2f} MiB download, "
          f"{data['installed_bytes']/2**20:.2f} MiB file contents, {data['file_count']} files")
    print('Compressed MiB | Installed MiB | Files | Component')
    for name, group in sorted(data['components'].items(), key=lambda item: item[1]['compressed'], reverse=True):
        print(f"{group['compressed']/2**20:14.2f} | {group['installed']/2**20:13.2f} | {group['files']:5} | {name}")
    print(f"ZIP headers / directory / other overhead: {data['archive_overhead_bytes']:,} bytes")
    if args.json:
        args.json.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    if args.csv:
        with args.csv.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['path', 'component', 'compressed', 'installed'])
            writer.writeheader()
            writer.writerows(data['files'])


if __name__ == '__main__':
    main()
