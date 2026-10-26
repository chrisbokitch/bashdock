"""Assemble version-matched dependency sources and notices for a release.

Upstream source archives are mirrored as release assets, not committed to Git.
The notice collection is deliberately a superset: Qt's complete source archive
contains optional components that may not occur in the frozen application.
"""
import hashlib
import importlib.metadata
import json
import re
import shutil
import sys
import tarfile
import time
import tomllib
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

if __package__:
    from .release_progress import progress
else:
    from release_progress import progress

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(item, cache):
    """Only promote complete, hash-verified downloads to the reusable cache."""
    if Path(item['filename']).name != item['filename']:
        raise ValueError('Invalid source archive filename.')
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / item['filename']
    if target.is_file():
        with progress(f"Verifying cached source {target.name}"):
            verified = digest(target) == item['sha256']
        if verified:
            return target
    partial = target.with_suffix(target.suffix + '.partial')
    for attempt in range(3):
        try:
            with progress(f"Downloading source {item['filename']} (attempt {attempt + 1}/3)"):
                with urllib.request.urlopen(item['url'], timeout=60) as response, partial.open('wb') as stream:
                    shutil.copyfileobj(response, stream, 1024 * 1024)
            with progress(f"Verifying downloaded source {item['filename']}"):
                if digest(partial) != item['sha256']:
                    raise ValueError(f"Source checksum mismatch: {item['filename']}")
            partial.replace(target)
            return target
        except (OSError, ValueError):
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def notice_file(name):
    path = PurePosixPath(name)
    base = path.name.lower()
    return (base in ('readme.chromium', 'qt_attribution.json') or
            'license' in base or 'licence' in base or base.startswith('readme') or
            re.match(r'^(mit|bsd|cc-by|mpl|lgpl|gpl)([._-]|$)', base) is not None or
            re.match(r'^(licen[cs]e|copying|copyright|notice|authors)([._-]|$)', base) is not None or
            ('licenses' in (p.lower() for p in path.parts) and path.suffix.lower() in ('.txt', '.md')))


def safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError(f'Unsafe archive member: {name}')
    return path


def collect_tar_notices(archive, destination):
    count = 0
    index = {}
    # Stream mode avoids retaining hundreds of thousands of Qt tar entries.
    with tarfile.open(archive, mode='r|*') as bundle:
        for member in bundle:
            if not member.isfile() or not notice_file(member.name):
                continue
            relative = safe_member(member.name)
            # Chromium has deeply nested names; keep Windows paths short while
            # preserving every original name in an index beside the notices.
            key = hashlib.sha256(member.name.encode('utf-8')).hexdigest()[:24]
            filename = key + '-' + relative.name[:100]
            target = destination / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            count += 1
            index[filename] = member.name
    if not count:
        raise ValueError(f'No license/notice files in {archive.name}')
    (destination / (archive.name + '.index.json')).write_text(
        json.dumps(index, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return count


def rust_sources(pywinpty_source, cache, output, notices):
    with tarfile.open(pywinpty_source) as bundle:
        lock_member = next(m for m in bundle if m.name.endswith('/Cargo.lock'))
        lock = bundle.extractfile(lock_member).read()
    packages = tomllib.loads(lock.decode('utf-8'))['package']
    version = next(p['version'] for p in packages if p['name'] == 'pywinpty')
    entries = []
    for crate in packages:
        if 'source' not in crate:
            continue
        if crate['source'] != 'registry+https://github.com/rust-lang/crates.io-index':
            raise ValueError('Review a non-registry Rust source before releasing.')
        filename = f"{crate['name']}-{crate['version']}.crate"
        entries.append(dict(name=crate['name'], version=crate['version'], filename=filename,
                            url=f"https://static.crates.io/crates/{crate['name']}/{filename}",
                            sha256=crate['checksum']))
    with ThreadPoolExecutor(max_workers=5) as pool:
        paths = list(pool.map(lambda item: download(item, cache), entries))
    target = output / f'pywinpty-{version}-rust-sources.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_STORED) as bundle:
        bundle.writestr('Cargo.lock', lock)
        bundle.writestr('README.txt',
            'Unmodified crate source archives pinned by pywinpty Cargo.lock.\n'
            'Extract each .crate (a gzip tar archive) to inspect, modify, or vendor it.\n'
            'See pywinpty source README.md for its Rust/maturin build instructions.\n')
        for entry, path in zip(entries, paths):
            bundle.write(path, 'crates/' + path.name)
            collect_tar_notices(path, notices / 'rust')
        bundle.writestr('sources.json', json.dumps(entries, indent=2) + '\n')
    return target


def collect_environment_notices(destination, distributions=None, python_license=None):
    records = []
    distributions = list(distributions if distributions is not None else importlib.metadata.distributions())
    for dist in sorted(distributions, key=lambda d: d.metadata['Name'].lower()):
        name = dist.metadata['Name']
        if name.lower() == 'bashdock':
            continue
        files = []
        for item in dist.files or []:
            if notice_file(str(item)):
                path = Path(dist.locate_file(item))
                if path.is_file():
                    relative = safe_member(str(item).replace('\\', '/'))
                    target = destination / 'python-packages' / name / Path(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
                    files.append(target.relative_to(destination).as_posix())
        records.append(dict(name=name, version=dist.version, notices=files,
                            declared_license=dist.metadata.get('License-Expression') or dist.metadata.get('License')))
    python_license = python_license or Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise ValueError(f'CPython runtime license not found: {python_license}')
    (destination / 'CPython').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(python_license, destination / 'CPython/LICENSE.txt')
    return records


def validate_environment(root=None, *, qt_version=None, distribution_version=None):
    """Check installed runtimes without writing files or downloading sources."""
    root = root or ROOT
    manifest = json.loads((root / 'requirements/release-sources.json').read_text())
    versions = {e['name']: e['version'] for e in manifest}
    if qt_version is None:
        try:
            from PySide6.QtCore import qVersion
            qt_version = qVersion()
        except ImportError:
            qt_version = 'not installed'
    distribution_version = distribution_version or importlib.metadata.version
    mismatches = []
    if qt_version != versions['Qt']:
        mismatches.append(f"Qt runtime: installed {qt_version}; required {versions['Qt']}")
    for name, expected in [('PySide6', versions['PySide6']), ('PySide6_Essentials', versions['PySide6']),
                           ('PySide6_Addons', versions['PySide6']), ('shiboken6', versions['PySide6']),
                           ('pywinpty', versions['pywinpty'])]:
        try:
            installed = distribution_version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = 'not installed'
        if installed != expected:
            mismatches.append(f'{name}: installed {installed}; required {expected}')
    if mismatches:
        raise ValueError('Release runtime versions do not match the reviewed sources:\n  '
                         + '\n  '.join(mismatches)
                         + '\nRun npm run setup to install the matching runtime versions, '
                           'then rerun npm run package.\n'
                           'Official CI release builds use requirements/windows-build.lock with Python 3.12 x64.')
    return manifest


def prepare(runtime, output, version, commit):
    manifest = validate_environment()
    native = json.loads((ROOT / 'requirements/native-runtime.json').read_text())
    for filename, expected in native['files'].items():
        path = runtime / '_internal/winpty' / filename
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f'Native helper {filename} differs from the reviewed Windows x64 wheel; review its sources/notices.')
    cache = ROOT / 'build/source-cache'
    output.mkdir(parents=True, exist_ok=True)
    notices = runtime / 'licenses'
    if notices.exists():
        shutil.rmtree(notices)
    shutil.copytree(ROOT / 'licenses', notices)
    for filename in ('LICENSE', 'COPYRIGHT', 'THIRD-PARTY-NOTICES.md'):
        shutil.copyfile(ROOT / filename, runtime / filename)
    (notices / 'xterm').mkdir()
    shutil.copyfile(ROOT / 'bashdock/assets/LICENSE', notices / 'xterm/LICENSE')
    with progress('Collecting installed runtime license notices'):
        records = collect_environment_notices(notices)
    with ThreadPoolExecutor(max_workers=3) as pool:
        paths = list(pool.map(lambda item: download(item, cache), manifest))
    artifacts = []
    for entry, path in zip(manifest, paths):
        with progress(f'Scanning license notices in {path.name}'):
            count = collect_tar_notices(path, notices / entry['name'])
        print(f'  Collected {count} notices from {path.name}', flush=True)
        target = output / path.name
        with progress(f'Copying and verifying source asset {path.name}'):
            shutil.copyfile(path, target)
            artifacts.append(dict(entry, sha256=digest(target)))
    with progress('Assembling Rust dependency sources and notices'):
        rust = rust_sources(paths[next(i for i, e in enumerate(manifest) if e['name'] == 'pywinpty')],
                            cache, output, notices)
    artifacts.append(dict(name='pywinpty Rust dependencies', filename=rust.name, sha256=digest(rust)))
    (notices / 'manifest.json').write_text(json.dumps(dict(
        application_version=version, source_commit=commit, python=sys.version,
        dependencies=records, source_archives=artifacts,
        notice_scope='Superset of notices from exact source releases; optional unshipped components may appear.'
    ), indent=2, sort_keys=True) + '\n', encoding='utf-8')
    source_name = f'bashdock-{version}-source.zip'
    (runtime / 'SOURCE.txt').write_text(
        f'BashDock {version} — source and licenses\nSource commit: {commit}\n\n'
        'BashDock is licensed under GNU GPL version 3 only. See LICENSE and COPYRIGHT.\n'
        'Third-party components keep their own licenses; see THIRD-PARTY-NOTICES.md\n'
        'and licenses/. Qt/PySide are used under their open-source license options.\n\n'
        f'The matching application source and build scripts are in {source_name}.\n'
        'Dependency sources are provided as separate archives beside the executable ZIP:\n'
        + ''.join(f"  {a['filename']}\n" for a in artifacts)
        + '\nObtain all source assets from the same download location as this executable.\n'
        'The source ZIP contains README.md and docs/RELEASING.md with build instructions.\n'
        'No activation, signature verification, or license key prevents modified builds\n'
        'or replacement of dynamically loaded libraries. Rebuild from source if needed.\n'
        'Redistributors must preserve notices and provide source access under the\n'
        'applicable licenses. A private repository link alone is not source access.\n', encoding='utf-8')
    return [output / a['filename'] for a in artifacts]
