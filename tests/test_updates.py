"""Updater trust, download, archive, and transactional recovery regressions."""
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from bashdock import updates, update_helper


def metadata(version='0.12.0', content=b'zip fixture'):
    filename = f'bashdock-{version}-windows-x64.zip'
    return dict(schema=1, version=version, platform='windows-x64', filename=filename,
                url=f'{updates.RELEASE_ROOT}/download/v{version}/{filename}',
                sha256=hashlib.sha256(content).hexdigest(), size=len(content))


def zip_bytes(extra=()):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('bashdock/bashdock.exe', b'new executable')
        archive.writestr('bashdock/_internal/runtime.dll', b'new runtime')
        archive.writestr('bashdock/bashdock-updater.exe', b'updater')
        for name, content in extra:
            archive.writestr(name, content)
    return stream.getvalue()


class UpdateTests(unittest.TestCase):
    def test_semver_and_signed_manifest_reject_downgrade_ambiguous_and_untrusted_input(self):
        self.assertGreater(updates.version_tuple('0.10.0'), updates.version_tuple('0.9.9'))
        for version in ('v1.0.0', '1.0.0-beta', '01.2.3', '1.0'):
            with self.assertRaises(ValueError):
                updates.version_tuple(version)
        valid = metadata()
        verify = Mock()
        raw = json.dumps(valid).encode()
        self.assertEqual(valid, updates.parse_manifest(raw, b'signature', {}, verify))
        verify.assert_called_once_with(raw, b'signature', {})
        for changes in ({'url': 'https://evil.example/update.zip'}, {'size': True}, {'size': 2**40},
                        {'sha256': 'bad'}, {'version': '0.12.0-beta'}, {'platform': 'linux'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                updates.parse_manifest(json.dumps(dict(valid, **changes)).encode(), b's', {}, lambda *a: None)
        with self.assertRaises(ValueError):
            updates.parse_manifest(raw, b'bad signature', {}, Mock(side_effect=ValueError('signature')))
        with self.assertRaises(ValueError):
            updates.unique_json(b'{"version":"1.0.0","version":"9.0.0"}')

    def test_release_discovery_ignores_drafts_prereleases_and_older_versions(self):
        valid = metadata()
        base = f'{updates.RELEASE_ROOT}/download/v0.12.0/'
        release = dict(tag_name='v0.12.0', draft=False, prerelease=False, assets=[
            dict(name=n, browser_download_url=base + n, size=valid['size'])
            for n in ('bashdock-update.json', 'bashdock-update.sig', valid['filename'])])
        def reader(url, limit):
            if url == updates.API_URL:
                return json.dumps(release).encode()
            return b'signature' if url.endswith('.sig') else json.dumps(valid).encode()
        self.assertEqual(valid, updates.discover('0.11.0', {}, reader, lambda *a: None)[0])
        self.assertIsNone(updates.discover('0.12.0', {}, reader, lambda *a: None))
        self.assertIsNone(updates.discover('1.0.0', {}, reader, lambda *a: None))
        for field in ('draft', 'prerelease'):
            release[field] = True
            self.assertIsNone(updates.discover('0.11.0', {}, reader, lambda *a: None))
            release[field] = False
        release['assets'].pop(0)
        with self.assertRaisesRegex(ValueError, 'signed update'):
            updates.discover('0.11.0', {}, reader, lambda *a: None)

    def test_archive_paths_links_aliases_and_duplicates_cannot_escape_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in ('../outside', 'bashdock/../../outside', '/absolute', 'bashdock/CON.txt',
                         'bashdock/a:stream', 'bashdock/trailing.', 'bashdock\\outside',
                         'bashdock/BASHDOCK.exe'):
                with self.subTest(path=path):
                    archive = root / 'package.zip'
                    archive.write_bytes(zip_bytes([(path, b'bad')]))
                    with self.assertRaises(ValueError):
                        updates.extract_package(archive, root / 'staged')
            archive = root / 'link.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                item = zipfile.ZipInfo('bashdock/link')
                item.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(item, '../../outside')
            with self.assertRaises(ValueError):
                updates.extract_package(archive, root / 'staged')
            self.assertFalse((root / 'staged').exists())

    def test_download_requires_exact_signed_size_and_hash_and_cleans_failed_downloads(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            content = zip_bytes()
            manifest = metadata(content=content)
            found = (manifest, json.dumps(manifest).encode(), b'signature')
            ready = updates.download_update(found, cache, opener=lambda url: io.BytesIO(content))
            self.assertEqual(content, (ready.directory / 'package.zip').read_bytes())
            for bad in (content[:-1], content + b'extra', b'x' * len(content)):
                with self.assertRaises(ValueError):
                    updates.download_update(found, cache, opener=lambda url: io.BytesIO(bad))
            self.assertEqual([ready.directory], list(cache.iterdir()))

    def test_installer_keeps_old_version_until_startup_and_restores_files_and_settings_on_failure(self):
        for healthy in (True, False):
            with self.subTest(healthy=healthy), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                target = root / 'installed'
                (target / '_internal').mkdir(parents=True)
                (target / 'bashdock.exe').write_bytes(b'old executable')
                (target / '_internal/stale.dll').write_bytes(b'old runtime')
                pending = root / 'pending'
                pending.mkdir()
                content = zip_bytes()
                (pending / 'package.zip').write_bytes(content)
                manifest = metadata(content=content)
                (pending / 'manifest.json').write_text(json.dumps(manifest))
                (pending / 'manifest.sig').write_bytes(b'signature')
                settings, backup = root / 'settings.json', root / 'before-update.json'
                settings.write_text('old settings')
                backup.write_text('old settings')
                plan = dict(install=str(target), pending=str(pending), pid=1234,
                            settings=str(settings), settings_backup=str(backup), token='a' * 64)
                process = Mock()
                process.poll.return_value = None
                def launch(directory, health, token):
                    self.assertEqual(b'new executable', (directory / 'bashdock.exe').read_bytes())
                    self.assertFalse((directory / '_internal/stale.dll').exists())
                    settings.write_text('new settings')
                    return process
                def health_check(*args):
                    previous = next(root.glob('.bashdock-previous-*'))
                    self.assertEqual(b'old executable', (previous / 'bashdock.exe').read_bytes())
                    return healthy
                arguments = dict(verify=lambda *a: None, wait=Mock(), other_processes=lambda p: [],
                                 launch=launch, healthy=health_check)
                if healthy:
                    result = update_helper.install(plan, {}, **arguments)
                    self.assertTrue(result['ok'])
                    self.assertEqual('new settings', settings.read_text())
                else:
                    with self.assertRaisesRegex(OSError, 'did not start'):
                        update_helper.install(plan, {}, **arguments)
                    self.assertEqual(b'old executable', (target / 'bashdock.exe').read_bytes())
                    self.assertEqual('old settings', settings.read_text())
                    self.assertEqual('new settings', (pending / 'failed-settings.json').read_text())
                    process.terminate.assert_called_once()

    def test_changed_pending_zip_never_touches_installation_or_waits_for_app_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'app/_internal').mkdir(parents=True)
            (root / 'app/bashdock.exe').write_bytes(b'old')
            (root / 'manifest.json').write_text(json.dumps(metadata()))
            (root / 'manifest.sig').write_bytes(b'signature')
            (root / 'package.zip').write_bytes(b'tampered')
            wait = Mock()
            plan = dict(install=str(root / 'app'), pending=str(root), pid=12, token='a' * 64)
            with self.assertRaisesRegex(ValueError, 'changed'):
                update_helper.install(plan, {}, verify=lambda *a: None, wait=wait)
            wait.assert_not_called()
            self.assertEqual(b'old', (root / 'app/bashdock.exe').read_bytes())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows CNG signature verification')
    def test_windows_cng_verifies_openssl_signature_and_rejects_modified_manifest(self):
        from scripts.update_keys import openssl, modulus
        from bashdock.update_security import verify_signature
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private, message, signature = root / 'key.pem', root / 'manifest.json', root / 'manifest.sig'
            subprocess.run([openssl(), 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:3072',
                            '-out', str(private)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            message.write_bytes(b'{"test":"not a production signing key"}')
            subprocess.run([openssl(), 'dgst', '-sha256', '-sign', str(private), '-out', str(signature), str(message)], check=True)
            key = {'modulus': modulus(private), 'exponent': 65537}
            verify_signature(message.read_bytes(), signature.read_bytes(), key)
            with self.assertRaises(ValueError):
                verify_signature(message.read_bytes() + b'tampered', signature.read_bytes(), key)

    def test_release_signer_generates_matching_metadata_and_never_signs_with_wrong_key(self):
        from scripts.publish_update import sign_release
        from scripts.update_keys import openssl, modulus
        try:
            executable = openssl()
        except ValueError:
            self.skipTest('OpenSSL required for publisher test')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private, public_file = root / 'test-only.pem', root / 'test-only.pub'
            subprocess.run([executable, 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:3072',
                            '-out', str(private)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            public = {'algorithm': 'RSA-PKCS1-SHA256', 'exponent': 65537, 'modulus': modulus(private)}
            archive = root / 'bashdock-0.12.0-windows-x64.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('bashdock/BUILD-INFO.json', '{"version":"0.12.0"}')
                z.writestr('bashdock/bashdock-updater.exe', b'helper fixture')
                z.writestr('bashdock/_internal/bashdock/assets/update-key.json', json.dumps(public))
            manifest, signature = sign_release(root, private, '0.12.0', public)
            self.assertEqual(archive.stat().st_size, json.loads(manifest.read_text())['size'])
            subprocess.run([executable, 'pkey', '-in', str(private), '-pubout', '-out', str(public_file)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([executable, 'dgst', '-sha256', '-verify', str(public_file), '-signature', str(signature), str(manifest)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.assertRaisesRegex(ValueError, 'public key|does not match'):
                sign_release(root, private, '0.12.0', dict(public, modulus='wrong key'))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows process handoff APIs')
    def test_windows_process_detection_and_wait_only_track_owned_test_child(self):
        interpreter = getattr(sys, '_base_executable', sys.executable)
        child = subprocess.Popen([interpreter, '-c', 'import time; time.sleep(15)'])
        try:
            self.assertIn(child.pid, update_helper.processes_in(Path(interpreter).resolve().parent))
            with self.assertRaises(OSError):
                update_helper.wait_for_pid(child.pid, timeout=0)
        finally:
            child.terminate()
            child.wait(timeout=10)
        update_helper.wait_for_pid(child.pid, timeout=1)
