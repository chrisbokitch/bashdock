import hashlib
from contextlib import redirect_stdout
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.release_licenses import collect_tar_notices, download, safe_member

ROOT = Path(__file__).resolve().parent.parent


class ReleaseLicenseTests(unittest.TestCase):
    def test_offline_app_notices_match_project_files_and_metadata(self):
        self.assertEqual((ROOT / 'LICENSE').read_bytes(), (ROOT / 'bashdock/assets/GPL-3.0.txt').read_bytes())
        self.assertEqual((ROOT / 'THIRD-PARTY-NOTICES.md').read_bytes(),
                         (ROOT / 'bashdock/assets/THIRD-PARTY-NOTICES.md').read_bytes())
        import tomllib
        metadata = tomllib.loads((ROOT / 'pyproject.toml').read_text())
        self.assertEqual('GPL-3.0-only', metadata['project']['license'])
        self.assertEqual('GPL-3.0-only', json.loads((ROOT / 'package.json').read_text())['license'])

    def test_notices_keep_original_text_and_paths_without_long_windows_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'source.tar.gz'
            files = {'upstream/' + 'nested/' * 50 + 'LICENSE': b'full original copyright and terms',
                     'upstream/qt_attribution.json': b'{"License": "MIT"}',
                     'upstream/MIT_LICENSE.txt': b'nonstandard attribution filename',
                     'upstream/main.c': b'not a notice'}
            with tarfile.open(archive, 'w:gz') as bundle:
                for name, content in files.items():
                    item = tarfile.TarInfo(name)
                    item.size = len(content)
                    bundle.addfile(item, io.BytesIO(content))
            output = root / 'notices'
            self.assertEqual(3, collect_tar_notices(archive, output))
            index = json.loads((output / 'source.tar.gz.index.json').read_text())
            for short, original in index.items():
                self.assertLess(len(short), 130)
                self.assertEqual(files[original], (output / short).read_bytes())
            for unsafe in ('../LICENSE', '/LICENSE', 'C:/LICENSE', 'a\\LICENSE'):
                with self.assertRaises(ValueError):
                    safe_member(unsafe)

    def test_source_hash_is_required_before_a_download_enters_the_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / 'upstream.tar.xz'
            original.write_bytes(b'verified source archive')
            entry = dict(filename='source.tar.xz', url=original.as_uri(),
                         sha256=hashlib.sha256(original.read_bytes()).hexdigest())
            cache = root / 'cache'
            path = download(entry, cache)
            self.assertEqual(original.read_bytes(), path.read_bytes())
            messages = io.StringIO()
            with redirect_stdout(messages), \
                    patch('scripts.release_licenses.urllib.request.urlopen', side_effect=AssertionError('cached')):
                self.assertEqual(path, download(entry, cache))
            self.assertIn('Verifying cached source source.tar.xz', messages.getvalue())
            self.assertNotIn('Downloading source', messages.getvalue())
            path.write_bytes(b'corrupt cache')
            original.write_bytes(b'changed upstream')
            with patch('scripts.release_licenses.time.sleep'):
                with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                    download(entry, cache)
            self.assertFalse(path.with_suffix('.xz.partial').exists())

    def test_runtime_check_reports_actual_expected_and_repair_without_writing_files(self):
        from scripts.release_licenses import validate_environment
        from importlib.metadata import PackageNotFoundError

        def installed(name):
            if name == 'pywinpty':
                raise PackageNotFoundError(name)
            return '6.12.0'

        with patch('scripts.release_licenses.download', side_effect=AssertionError('no download')):
            with self.assertRaises(ValueError) as failure:
                validate_environment(qt_version='6.12.0', distribution_version=installed)
        message = str(failure.exception)
        self.assertIn('Qt runtime: installed 6.12.0; required 6.10.3', message)
        self.assertIn('pywinpty: installed not installed; required 3.0.5', message)
        self.assertIn('npm run setup', message)
        manifest = validate_environment(qt_version='6.10.3', distribution_version=lambda name:
                                        {'pywinpty': '3.0.5', 'truststore': '0.10.4'}.get(name, '6.10.3'))
        self.assertEqual('6.10.3', next(e['version'] for e in manifest if e['name'] == 'Qt'))

    def test_setup_runtime_pins_match_the_reviewed_release_sources(self):
        import tomllib
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
        manifest = {item['name']: item['version'] for item in
                    json.loads((ROOT / 'requirements/release-sources.json').read_text())}
        self.assertIn('PySide6==' + manifest['PySide6'], project['dependencies'])
        self.assertIn('pywinpty==' + manifest['pywinpty'] + "; sys_platform == 'win32'", project['dependencies'])
