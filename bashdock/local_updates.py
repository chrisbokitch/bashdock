"""Explicit, installation-scoped local development updates; never a network feed."""
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import tempfile
import zipfile

from .update_security import load_key, verify_signature
from .updates import (ReadyUpdate, cache_directory, digest_file, extract_package,
                      parse_manifest, version_tuple, RELEASE_ROOT, MAX_DOWNLOAD)

CHANNEL = 'local-development'
MINIMUM_VERSION = (0, 14, 0)


def installation_id(target):
    return hashlib.sha256(str(Path(target).resolve()).casefold().encode('utf-8')).hexdigest()


def inbox_root(target):
    return (cache_directory().parent / 'local-updates' / installation_id(target)).resolve()


def installed_info(target):
    target = Path(target).resolve()
    if not (target / 'bashdock.exe').is_file() or not (target / '_internal').is_dir():
        raise ValueError('Target must be a complete installed BashDock folder.')
    info = json.loads((target / 'BUILD-INFO.json').read_text(encoding='utf-8'))
    if not isinstance(info, dict):
        raise ValueError('Installed build information is invalid.')
    version_tuple(info.get('version'))
    return info


def check_target(target):
    info = installed_info(target)
    if version_tuple(info['version']) < MINIMUM_VERSION:
        raise ValueError('Install BashDock 0.14.0 or newer once using copy.sh before staging local updates.')
    return info


def atomic_json(path, data):
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        temporary.write_text(json.dumps(data, sort_keys=True) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def disable(target):
    root = inbox_root(target)
    (root / 'ready.json').unlink(missing_ok=True)
    (root / 'trusted-key.json').unlink(missing_ok=True)


def candidate(target):
    """Read only a small atomic pointer on the UI thread; no ZIP hashing here."""
    root = inbox_root(target)
    pointer = root / 'ready.json'
    if not (root / 'trusted-key.json').is_file() or not pointer.is_file():
        return None
    if pointer.stat().st_size > 4096:
        raise ValueError('Local update pointer is too large.')
    data = json.loads(pointer.read_text(encoding='utf-8'))
    name = data.get('directory') if isinstance(data, dict) else None
    if not isinstance(name, str) or not re.fullmatch(r'pending-[a-zA-Z0-9_-]+', name):
        raise ValueError('Invalid local update pointer.')
    pending = (root / name).resolve()
    if pending.parent != root.resolve():
        raise ValueError('Local update directory is outside its installation inbox.')
    return pending


def read_local_manifest(target, pending, *, verify=verify_signature):
    root = inbox_root(target).resolve()
    pending = Path(pending).resolve()
    if pending.parent != root or not re.fullmatch(r'pending-[a-zA-Z0-9_-]+', pending.name):
        raise ValueError('Local update directory is outside its installation inbox.')
    key_path = root / 'trusted-key.json'
    if key_path.stat().st_size > 4096:
        raise ValueError('Local signing key is too large.')
    try:
        key = load_key(key_path)
    except (TypeError, AttributeError):
        raise ValueError('The enrolled local signing key is invalid.') from None
    manifest_path, signature_path = pending / 'manifest.json', pending / 'manifest.sig'
    if manifest_path.stat().st_size > 65536 or signature_path.stat().st_size > 1024:
        raise ValueError('Local update metadata is too large.')
    manifest = parse_manifest(manifest_path.read_bytes(), signature_path.read_bytes(), key, verify)
    if manifest.get('channel') != CHANNEL or manifest.get('installation') != installation_id(target):
        raise ValueError('Local update was not signed for this installation.')
    if not isinstance(manifest.get('commit'), str) or not re.fullmatch('[0-9a-f]{40}', manifest['commit']):
        raise ValueError('Local update requires an exact source commit.')
    return manifest


def verify_pending(target, pending, *, verify=verify_signature):
    manifest = read_local_manifest(target, pending, verify=verify)
    current = installed_info(target)
    if version_tuple(manifest['version']) < version_tuple(current['version']):
        raise ValueError('Local staging does not allow version downgrades.')
    archive = Path(pending) / 'package.zip'
    if archive.stat().st_size != manifest['size'] or digest_file(archive) != manifest['sha256']:
        raise ValueError('Local update package changed. Nothing has been installed.')
    with zipfile.ZipFile(archive) as bundle:
        if 'bashdock/bashdock-updater.exe' not in bundle.namelist():
            raise ValueError('Local update package is missing its independent helper.')
        info_entry = bundle.getinfo('bashdock/BUILD-INFO.json')
        if info_entry.file_size > 1024 * 1024:
            raise ValueError('Local build information is too large.')
        info = json.loads(bundle.read(info_entry))
        if not isinstance(info, dict) or info.get('version') != manifest['version'] or info.get('commit') != manifest['commit']:
            raise ValueError('Local package build identity does not match its signed metadata.')
    return ReadyUpdate(manifest, Path(pending))


def discover_local(target, pending=None, *, verify=verify_signature):
    pending = candidate(target) if pending is None else Path(pending)
    if pending is None:
        return None
    manifest = read_local_manifest(target, pending, verify=verify)
    current = installed_info(target)
    if (current.get('version'), current.get('commit')) == (manifest['version'], manifest['commit']):
        return None
    ready = verify_pending(target, pending, verify=verify)
    # The same safe archive checks as public downloads, before offering restart.
    with tempfile.TemporaryDirectory(prefix='checked-', dir=pending) as directory:
        extract_package(pending / 'package.zip', Path(directory))
    return ready


def acknowledge(target, pending):
    # Never consume a newer package staged while this update was installing.
    if candidate(target) == Path(pending).resolve():
        (inbox_root(target) / 'ready.json').unlink(missing_ok=True)


def stage_package(target, archive, public, sign, *, expected_version, expected_commit, verify=verify_signature):
    target, archive = Path(target).resolve(), Path(archive).resolve()
    current = check_target(target)
    if version_tuple(expected_version) < version_tuple(current['version']):
        raise ValueError('Local staging does not allow version downgrades.')
    if not 0 < archive.stat().st_size <= MAX_DOWNLOAD:
        raise ValueError('Local update package has an invalid size.')
    with zipfile.ZipFile(archive) as bundle:
        entry = bundle.getinfo('bashdock/BUILD-INFO.json')
        if entry.file_size > 1024 * 1024:
            raise ValueError('Local build information is too large.')
        info = json.loads(bundle.read(entry))
        if not isinstance(info, dict) or info.get('version') != expected_version or info.get('commit') != expected_commit:
            raise ValueError('Package is stale. Build/package the current source commit first.')
    if (current['version'], current.get('commit')) == (expected_version, expected_commit):
        raise ValueError('This version and source commit are already installed.')
    root = inbox_root(target)
    root.mkdir(parents=True, exist_ok=True)
    key_path = root / 'trusted-key.json'
    enrolled = False
    if key_path.exists():
        if load_key(key_path) != public:
            raise ValueError('This installation trusts a different local key. Disable local staging before enrolling a new key.')
    else:
        # Running the explicit stage command opts only this installation in.
        with key_path.open('x', encoding='utf-8') as stream:
            json.dump(public, stream)
        enrolled = True
    pending = Path(tempfile.mkdtemp(prefix='pending-', dir=root))
    try:
        shutil.copyfile(archive, pending / 'package.zip')
        filename = f'bashdock-{expected_version}-windows-x64.zip'
        manifest = dict(schema=1, version=expected_version, platform='windows-x64', filename=filename,
            url=f'{RELEASE_ROOT}/download/v{expected_version}/{filename}',
            size=(pending / 'package.zip').stat().st_size, sha256=digest_file(pending / 'package.zip'),
            channel=CHANNEL, installation=installation_id(target), commit=expected_commit)
        raw = (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
        (pending / 'manifest.json').write_bytes(raw)
        (pending / 'manifest.sig').write_bytes(sign(raw))
        discover_local(target, pending, verify=verify)
        atomic_json(root / 'ready.json', {'directory': pending.name})
        return ReadyUpdate(manifest, pending)
    except BaseException:
        shutil.rmtree(pending, ignore_errors=True)
        if enrolled:
            key_path.unlink(missing_ok=True)
        raise
