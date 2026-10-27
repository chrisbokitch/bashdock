import hashlib
import json
import tempfile
import unittest
import zipfile
import subprocess
from pathlib import Path
from unittest.mock import patch

from scripts.package_release import package, create_source_archive
from scripts import verify_release
from scripts.release_licenses import archive_notices


class ReleasePackagingTests(unittest.TestCase):
    def test_startup_smoke_cleanup_retries_transient_windows_dll_locks(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from scripts import check_startup_health
        cleanup = Mock(side_effect=[PermissionError('DLL still mapped'), None])
        directory = SimpleNamespace(name='isolated smoke folder', cleanup=cleanup)
        with patch.object(check_startup_health.tempfile, 'TemporaryDirectory', return_value=directory), \
                patch('bashdock.update_helper.time.sleep') as pause:
            with check_startup_health.temporary_work_directory(prefix='BashDock test ') as root:
                self.assertEqual(Path(directory.name), root)
        self.assertEqual(2, cleanup.call_count)
        pause.assert_called_once_with(0.5)

    def test_portable_zip_contains_complete_runtime_and_matching_checksum_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "dist/bashdock"
            (source / "_internal/nested").mkdir(parents=True)
            (source / "bashdock.exe").write_bytes(b"executable fixture")
            (source / "bashdock-updater.exe").write_bytes(b"independent updater fixture")
            (source / "_internal/nested/runtime.dll").write_bytes(b"runtime fixture")
            (source / "_internal/.hidden").write_bytes(b"hidden runtime fixture")
            report = root / "smoke.json"
            report.write_text('{"ok": true}')
            (source / "licenses").mkdir()
            for filename in ('LICENSE', 'COPYRIGHT', 'THIRD-PARTY-NOTICES.md', 'SOURCE.txt'):
                (source / filename).write_text('license fixture')
            (source / 'licenses/manifest.json').write_text('{}')
            (source / 'licenses/Qt').mkdir()
            (source / 'licenses/Qt/LICENSE').write_bytes(b'complete original Qt notice fixture')
            archive_notices(source)
            source_asset = root / 'release/source-fixture.zip'
            source_asset.parent.mkdir()
            source_asset.write_bytes(b'source fixture')
            commit = "a" * 40
            archive, checksum, info = package(source, root / "release", report, "0.6.4", commit,
                                               {"dependencies": {"PySide6": "6.10.3"}, "source_assets": [
                                                   {"filename": source_asset.name,
                                                    "sha256": hashlib.sha256(source_asset.read_bytes()).hexdigest()}]})
            expected = hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n"
            self.assertEqual(expected, checksum.read_text())
            self.assertEqual(expected.encode('utf-8'), checksum.read_bytes())
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(b"runtime fixture", bundle.read("bashdock/_internal/nested/runtime.dll"))
                self.assertIn("bashdock/_internal/.hidden", bundle.namelist())
                self.assertIn("bashdock/bashdock.exe", bundle.namelist())
                self.assertIn('bashdock/third-party-licenses.zip', bundle.namelist())
                self.assertNotIn('bashdock/licenses/Qt/LICENSE', bundle.namelist())
                inventory = json.loads(bundle.read('bashdock/licenses/runtime-files.json'))
                archived = next(p for p in inventory if p['path'] == 'third-party-licenses.zip')
                self.assertEqual(archived['sha256'], hashlib.sha256(
                    bundle.read('bashdock/third-party-licenses.zip')).hexdigest())
                details = json.loads(bundle.read("bashdock/BUILD-INFO.json"))
                self.assertEqual(json.loads(info.read_text()), details)
                self.assertEqual(commit, details["commit"])
                self.assertEqual("0.6.4", details["version"])
                self.assertIn("Git for Windows", bundle.read("bashdock/README.txt").decode())
            (root / "package.json").write_text('{"version": "0.6.4"}')
            # An older local archive must not prevent verification of this version.
            (root / "release/bashdock-0.6.3-windows-x64.zip").touch()

            def smoke(args, **options):
                executable = Path(args[0])
                self.assertEqual(b"executable fixture", executable.read_bytes())
                self.assertTrue((executable.parent / "_internal/nested/runtime.dll").is_file())
                self.assertIn(" ", options["env"]["APPDATA"])
                result = Path(args[2])
                result.parent.mkdir(parents=True, exist_ok=True)
                result.write_text('{"ok": true}')

            with patch.object(verify_release, "ROOT", root), \
                    patch.object(verify_release, "verify_startup_health") as health, \
                    patch.object(verify_release.subprocess, "run", side_effect=smoke) as launch:
                verify_release.main()
                launch.assert_called_once()
                health.assert_called_once()
                self.assertEqual('0.6.4', health.call_args.args[2])
                source_asset.write_bytes(b'corrupted source')
                with self.assertRaisesRegex(ValueError, 'Source asset checksum'):
                    verify_release.main()
                self.assertEqual(1, launch.call_count)
                source_asset.unlink()
                with self.assertRaisesRegex(ValueError, 'Missing release source'):
                    verify_release.main()
                self.assertEqual(1, launch.call_count)
                archive.write_bytes(b"corrupted download")
                with self.assertRaisesRegex(ValueError, "checksum"):
                    verify_release.main()
                self.assertEqual(1, launch.call_count)

    def test_failed_smoke_test_or_incomplete_runtime_does_not_produce_a_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "smoke.json"
            report.write_text('{"ok": false}')
            source = root / "source"
            source.mkdir()
            output = root / "release"
            for complete in (False, True):
                if complete:
                    (source / "bashdock.exe").touch()
                    (source / "_internal").mkdir()
                with self.assertRaises(ValueError):
                    package(source, output, report, "0.6.4", "a" * 40, {})
                self.assertFalse(output.exists())

    def test_source_archive_matches_committed_revision_and_excludes_local_helpers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
            git('init', '-q')
            git('config', 'user.name', 'Release test')
            git('config', 'user.email', 'release-test@example.invalid')
            git('config', 'core.autocrlf', 'true')
            (root / '.gitignore').write_text('/copy.sh\n/release/\n')
            (root / 'app.py').write_text('print("committed")\n')
            (root / 'copy.sh').write_text('private local helper')
            git('add', '.')
            git('commit', '-qm', 'fixture')
            commit = git('rev-parse', 'HEAD')
            archive = create_source_archive(root, root / 'release', '0.10.2', commit)
            with zipfile.ZipFile(archive) as bundle:
                committed = subprocess.check_output(['git', 'show', 'HEAD:app.py'], cwd=root)
                self.assertEqual(committed, bundle.read('bashdock-source/app.py'))
                self.assertEqual(commit, bundle.read('bashdock-source/SOURCE-COMMIT.txt').decode().strip())
                self.assertFalse(any('copy.sh' in n for n in bundle.namelist()))
            (root / 'app.py').write_text('uncommitted change')
            with self.assertRaisesRegex(ValueError, 'Commit all project changes'):
                create_source_archive(root, root / 'release', '0.10.2', commit)

    def test_missing_license_information_blocks_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'bashdock.exe').touch()
            (root / 'bashdock-updater.exe').touch()
            (root / '_internal').mkdir()
            report = root / 'smoke.json'
            report.write_text('{"ok": true}')
            with self.assertRaisesRegex(ValueError, 'licensing file'):
                package(root, root / 'release', report, '0.10.2', 'a' * 40, {})

    def test_preflight_checks_checkout_and_dependencies_before_any_release_output(self):
        from scripts import package_release
        import os
        with patch.object(package_release.sys, 'argv', ['package_release.py', '--check']), \
                patch.object(package_release.sys, 'platform', 'win32'), \
                patch.object(package_release.platform, 'machine', return_value='AMD64'), \
                patch.dict(os.environ, {'BASHDOCK_RELEASE_TAG': ''}), \
                patch.object(package_release, 'check_source_tree', return_value='a' * 40) as checkout, \
                patch.object(package_release, 'validate_environment') as environment, \
                patch.object(package_release, 'create_source_archive', side_effect=AssertionError('no output')):
            package_release.main()
            checkout.assert_called_once()
            environment.assert_called_once()
            checkout.reset_mock()
            checkout.side_effect = ValueError('untracked local backup.sh')
            environment.reset_mock()
            with self.assertRaises(SystemExit) as failure:
                package_release.main()
            self.assertEqual(2, failure.exception.code)
            environment.assert_not_called()

    def test_even_a_clean_commit_cannot_package_tracked_signing_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
            git('init', '-q')
            git('config', 'user.name', 'Release test')
            git('config', 'user.email', 'release-test@example.invalid')
            (root / '.secrets').mkdir()
            (root / '.secrets/key.pem').write_text('test fixture; not a real signing key')
            git('add', '.')
            git('commit', '-qm', 'fixture')
            with self.assertRaisesRegex(ValueError, 'must never be tracked'):
                create_source_archive(root, root / 'release', '0.11.0', git('rev-parse', 'HEAD'))
            self.assertFalse((root / 'release').exists())
