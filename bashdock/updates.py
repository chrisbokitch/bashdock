"""Signed stable-release discovery, bounded downloads and safe ZIP staging."""
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from .update_security import load_key, verify_signature

REPOSITORY = 'chrisbokitch/bashdock'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
RELEASE_ROOT = f'https://github.com/{REPOSITORY}/releases'
MAX_DOWNLOAD = 1024 * 1024 * 1024


def version_tuple(version):
    if not isinstance(version, str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
        raise ValueError('Updates require a stable semantic version.')
    return tuple(map(int, version.split('.')))


def unique_json(raw):
    def pairs(items):
        result = {}
        for name, value in items:
            if name in result:
                raise ValueError('Duplicate update metadata field.')
            result[name] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def parse_manifest(raw, signature, key, verify=verify_signature):
    if len(raw) > 65536:
        raise ValueError('Update metadata is too large.')
    verify(raw, signature, key)
    data = unique_json(raw)
    if not isinstance(data, dict):
        raise ValueError('Update metadata must be an object.')
    version_tuple(data.get('version'))
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data.get('schema') != 1 or data.get('platform') != 'windows-x64':
        raise ValueError('Unsupported update package.')
    filename = f"bashdock-{data['version']}-windows-x64.zip"
    expected = f"{RELEASE_ROOT}/download/v{data['version']}/{filename}"
    if data.get('filename') != filename or data.get('url') != expected:
        raise ValueError('Unexpected update download location.')
    if type(data.get('size')) is not int or not 0 < data['size'] <= MAX_DOWNLOAD:
        raise ValueError('Invalid update download size.')
    if not isinstance(data.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', data['sha256']):
        raise ValueError('Invalid update checksum.')
    return data


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        if urllib.parse.urlsplit(url).scheme != 'https':
            raise ValueError('An update download attempted an insecure redirect.')
        return super().redirect_request(request, fp, code, message, headers, url)


def open_url(url):
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('Update downloads require HTTPS.')
    request = urllib.request.Request(url, headers={'User-Agent': 'BashDock-Updater', 'Accept': 'application/vnd.github+json'})
    return urllib.request.build_opener(HTTPSRedirect()).open(request, timeout=20)


def read_url(url, limit, opener=open_url):
    with opener(url) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Update response exceeds its size limit.')
    return data


def discover(current_version, key, reader=read_url, verify=verify_signature):
    try:
        release = unique_json(reader(API_URL, 2 * 1024 * 1024))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None  # Private repositories/no public release: no credentials are requested.
        raise
    if release.get('draft') or release.get('prerelease'):
        return None
    version = release.get('tag_name', '').removeprefix('v')
    if version_tuple(version) <= version_tuple(current_version):
        return None
    base = f'{RELEASE_ROOT}/download/v{version}/'
    assets = {item['name']: item for item in release.get('assets', [])}
    for name in ('bashdock-update.json', 'bashdock-update.sig'):
        if name not in assets or assets[name].get('browser_download_url') != base + name:
            raise ValueError('This release does not include signed update metadata.')
    raw = reader(base + 'bashdock-update.json', 65536)
    signature = reader(base + 'bashdock-update.sig', 1024)
    manifest = parse_manifest(raw, signature, key, verify)
    if manifest['version'] != version:
        raise ValueError('Release and signed update versions differ.')
    asset = assets.get(manifest['filename'], {})
    if asset.get('browser_download_url') != manifest['url'] or asset.get('size') != manifest['size']:
        raise ValueError('Release and signed download information differ.')
    return manifest, raw, signature


def digest_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extract_package(archive, destination):
    """Reject traversal, Windows aliases, links, duplicates and oversized archives."""
    seen, total = set(), 0
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            name = item.filename
            path = PurePosixPath(name)
            if (path.is_absolute() or '\\' in name or ':' in name or '..' in path.parts
                    or not path.parts or path.parts[0] != 'bashdock'):
                raise ValueError('Unsafe path in update archive.')
            for part in path.parts:
                if (part.rstrip(' .') != part or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)):
                    raise ValueError('Unsafe Windows filename in update archive.')
            canonical = '/'.join(path.parts).casefold()
            if canonical in seen:
                raise ValueError('Duplicate path in update archive.')
            seen.add(canonical)
            mode = stat.S_IFMT(item.external_attr >> 16)
            if mode not in (0, stat.S_IFREG, stat.S_IFDIR) or item.flag_bits & 1:
                raise ValueError('Unsupported link or encrypted update entry.')
            total += item.file_size
            if total > 4 * 1024**3 or len(seen) > 30000:
                raise ValueError('Update archive exceeds extraction limits.')
        if 'bashdock/bashdock.exe' not in seen or not any(n.startswith('bashdock/_internal/') for n in seen):
            raise ValueError('Update archive lacks the complete application runtime.')
        for item in bundle.infolist():
            target = destination.joinpath(*PurePosixPath(item.filename).parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
    return destination / 'bashdock'


@dataclass(frozen=True)
class ReadyUpdate:
    manifest: dict
    directory: Path


def download_update(discovered, cache, cancel=None, opener=open_url):
    manifest, raw, signature = discovered
    cache.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='pending-', dir=cache))
    try:
        archive = directory / 'package.zip'
        downloaded = 0
        with opener(manifest['url']) as response, archive.open('wb') as output:
            while block := response.read(1024 * 1024):
                if cancel is not None and cancel.is_set():
                    raise ValueError('Update download cancelled.')
                downloaded += len(block)
                if downloaded > manifest['size']:
                    raise ValueError('Update exceeds its signed download size.')
                output.write(block)
        if downloaded != manifest['size'] or digest_file(archive) != manifest['sha256']:
            raise ValueError('Update download is incomplete or its checksum does not match.')
        extract_package(archive, directory / 'checked')
        shutil.rmtree(directory / 'checked')
        (directory / 'manifest.json').write_bytes(raw)
        (directory / 'manifest.sig').write_bytes(signature)
        return ReadyUpdate(manifest, directory)
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def cache_directory():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'BashDock/updates'
