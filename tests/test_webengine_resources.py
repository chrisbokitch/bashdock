"""Remove only known debug packs after validating a complete release set."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from bashdock.webengine_resources import (
    DEBUG_RESOURCES, RELEASE_RESOURCES, select_release_resources, validate_runtime_resources,
)
from scripts import check_webengine


class WebEngineResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='BashDock resource fixtures ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entries = []
        for name in RELEASE_RESOURCES + DEBUG_RESOURCES:
            path = self.root / name
            path.write_bytes(b'nonempty resource fixture')
            self.entries.append(('PySide6\\resources\\'+name, str(path), 'DATA'))

    def test_only_five_debug_resources_removed_and_release_devtools_and_dpi_kept(self):
        unrelated = ('app/resources/example.debug.bin', '/not-read', 'DATA')
        self.entries.append(unrelated)
        kept, removed = select_release_resources(self.entries, debug_build=False)
        self.assertEqual(set(DEBUG_RESOURCES), {Path(e[1]).name for e in removed})
        self.assertEqual(set(RELEASE_RESOURCES), {Path(e[1]).name for e in kept if e != unrelated})
        self.assertIn(unrelated, kept)
        self.assertTrue(all((self.root / n).is_file() for n in DEBUG_RESOURCES))
        self.assertEqual((kept, []), select_release_resources(kept, debug_build=False))

    def test_debug_qt_unknown_build_or_missing_and_empty_release_files_abort_selection(self):
        for build in (True, None):
            with self.subTest(build=build), self.assertRaisesRegex(ValueError, 'release Qt'):
                select_release_resources(self.entries, debug_build=build)
        release = self.root / RELEASE_RESOURCES[0]
        release.write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'Missing release'):
            select_release_resources(self.entries, debug_build=False)
        release.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing release'):
            select_release_resources(self.entries, debug_build=False)

    def test_unrecognized_debug_resource_requires_review(self):
        self.entries.append(('PySide6/resources/new.debug.pak', '/not-read', 'DATA'))
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            select_release_resources(self.entries, debug_build=False)

    def test_runtime_requires_release_files_and_no_debug_leftovers(self):
        with self.assertRaisesRegex(ValueError, 'debug='):
            validate_runtime_resources(self.root, debug_build=False)
        for name in DEBUG_RESOURCES:
            (self.root / name).unlink()
        self.assertEqual(list(RELEASE_RESOURCES), validate_runtime_resources(self.root, debug_build=False))
        with self.assertRaisesRegex(ValueError, 'release Qt'):
            validate_runtime_resources(self.root, debug_build=True)

    def test_packaged_checks_use_fresh_profiles_default_and_software_rendering_and_three_scales(self):
        environments = []
        def launch(args, **options):
            environments.append(options['env'])
            Path(args[2]).write_text(json.dumps(dict(ok=True, frozen=True)))
            return type('Result', (), dict(returncode=0, wait=lambda self, **kwargs: None))()
        with patch.object(check_webengine.subprocess, 'Popen', side_effect=launch):
            results = check_webengine.verify_webengine(self.root / 'app.exe', self.root / 'reports')
        self.assertEqual(4, len(results))
        self.assertEqual(4, len({e['APPDATA'] for e in environments}))
        self.assertNotIn('QTWEBENGINE_CHROMIUM_FLAGS', environments[0])
        self.assertEqual(['1', '1', '1.25', '1.5'], [e['QT_SCALE_FACTOR'] for e in environments])
        self.assertTrue(all(e['QT_QPA_PLATFORM'] == 'windows' for e in environments))
        self.assertTrue(all('QTWEBENGINE_RESOURCES_PATH' not in e for e in environments))

    def test_timeout_terminates_only_the_owned_probe_tree(self):
        process = Mock(pid=4321)
        process.wait.side_effect = [check_webengine.subprocess.TimeoutExpired('fixture', 90), None]
        process.poll.return_value = None
        with patch.object(check_webengine.subprocess, 'Popen', return_value=process), patch.object(
                check_webengine.subprocess, 'run') as stop:
            with self.assertRaises(check_webengine.subprocess.TimeoutExpired):
                check_webengine.verify_webengine(self.root / 'app.exe', self.root / 'reports')
        self.assertEqual(['taskkill', '/PID', '4321', '/T', '/F'], stop.call_args.args[0])
        process.kill.assert_called_once()
