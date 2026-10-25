import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_release import package


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
