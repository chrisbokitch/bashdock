"""Safety and orchestration of the opt-in disposable VM harness."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from bashdock import update_acceptance as acceptance
from test_updates import metadata, zip_bytes


class AcceptanceTests(unittest.TestCase):
    def test_changed_byte_preserves_length_and_changes_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'file'
            path.write_bytes(b'abc')
            before = acceptance.inventory(path.parent)
            acceptance.changed_byte(path)
            self.assertEqual(3, path.stat().st_size)
            self.assertNotEqual(before, acceptance.inventory(path.parent))

    def test_refuses_existing_output_and_nested_output_without_writing(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(acceptance.sys, 'platform', 'win32'):
            root = Path(temp)
            baseline, assets = root / 'baseline', root / 'assets'
            baseline.mkdir()
            assets.mkdir()
            for output in (root, baseline / 'test', assets / 'test'):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    acceptance.run_acceptance(baseline, assets, output)
            self.assertEqual([], list(baseline.iterdir()))
            self.assertEqual([], list(assets.iterdir()))

    def test_disposable_harness_rejects_tampering_restores_files_and_isolates_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline, assets, output = root / 'baseline', root / 'assets', root / 'new test output'
            (baseline / '_internal').mkdir(parents=True)
            (baseline / 'bashdock.exe').write_bytes(b'baseline executable')
            (baseline / '_internal/old.dll').write_bytes(b'baseline runtime')
            (baseline / 'BUILD-INFO.json').write_text('{"version":"0.11.4"}')
            assets.mkdir()
            content = zip_bytes()
            raw, signature = json.dumps(metadata(content=content)).encode(), b'original signature'
            (assets / 'bashdock-update.json').write_bytes(raw)
            (assets / 'bashdock-update.sig').write_bytes(signature)
            (assets / metadata()['filename']).write_bytes(content)
            original_files = acceptance.inventory(root)
            environment = dict(os.environ)
            real_parse = acceptance.parse_manifest
            def verify(raw_bytes, signature_bytes, key):
                if raw_bytes != raw or signature_bytes != signature:
                    raise ValueError('signature rejected')
            def parse(*args):
                return real_parse(*args, verify=verify)
            launches = []
            def launch(target, health, token):
                launches.append(target)
                self.assertEqual((output / 'profile/Roaming').resolve(), Path(os.environ['APPDATA']).resolve())
                if len(launches) == 1:
                    self.assertIn(b'Not a Windows executable', (target / 'bashdock.exe').read_bytes())
                    raise OSError('Windows could not start replacement executable')
                self.assertEqual(b'baseline executable', (target / 'bashdock.exe').read_bytes())
                return Mock(pid=12345)
            # These mocks test harness orchestration only. The VM command uses
            # real production-key CNG verification and real Windows processes.
            with patch.object(acceptance.sys, 'platform', 'win32'), patch.object(
                    acceptance, 'load_key', return_value={}), patch.object(
                    acceptance, 'parse_manifest', side_effect=parse), patch.object(
                    acceptance.helper, 'parse_manifest', side_effect=parse), patch.object(
                    acceptance.helper, 'processes_in', return_value=[]), patch.object(
                    acceptance.helper, 'start_app', side_effect=launch), patch.object(
                    acceptance.helper, 'wait_for_health', return_value=True):
                # Default function arguments are bound at definition time.
                original_install = acceptance.helper.install
                def install(*args, **kwargs):
                    return original_install(*args, other_processes=lambda p: [], **kwargs)
                with patch.object(acceptance.helper, 'install', side_effect=install):
                    result = acceptance.run_acceptance(baseline, assets, output)
            self.assertTrue(result['ok'])
            self.assertEqual(6, len(result['cases']))
            self.assertEqual(2, len(launches))
            self.assertEqual(environment, dict(os.environ))
            for relative, digest in original_files.items():
                self.assertEqual(digest, acceptance.digest_file(root / relative))
            self.assertFalse(list(output.rglob('package.zip')))
            self.assertTrue(json.loads((output / 'acceptance-results.json').read_text())['ok'])
