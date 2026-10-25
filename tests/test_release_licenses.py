import hashlib
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
            with patch('scripts.release_licenses.urllib.request.urlopen', side_effect=AssertionError('cached')):
                self.assertEqual(path, download(entry, cache))
            path.write_bytes(b'corrupt cache')
            original.write_bytes(b'changed upstream')
            with patch('scripts.release_licenses.time.sleep'):
                with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                    download(entry, cache)
            self.assertFalse(path.with_suffix('.xz.partial').exists())
