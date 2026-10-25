import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.package_release import package
from scripts import verify_release


class ReleasePackagingTests(unittest.TestCase):
    def test_portable_zip_contains_complete_runtime_and_matching_checksum_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "dist/bashdock"
            (source / "_internal/nested").mkdir(parents=True)
            (source / "bashdock.exe").write_bytes(b"executable fixture")
            (source / "_internal/nested/runtime.dll").write_bytes(b"runtime fixture")
            (source / "_internal/.hidden").write_bytes(b"hidden runtime fixture")
            report = root / "smoke.json"
            report.write_text('{"ok": true}')
            commit = "a" * 40
            archive, checksum, info = package(source, root / "release", report, "0.6.4", commit,
                                               {"dependencies": {"PySide6": "6.10.3"}})
            expected = hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n"
            self.assertEqual(expected, checksum.read_text())
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(b"runtime fixture", bundle.read("bashdock/_internal/nested/runtime.dll"))
                self.assertIn("bashdock/_internal/.hidden", bundle.namelist())
                self.assertIn("bashdock/bashdock.exe", bundle.namelist())
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
                    patch.object(verify_release.subprocess, "run", side_effect=smoke) as launch:
                verify_release.main()
                launch.assert_called_once()
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
