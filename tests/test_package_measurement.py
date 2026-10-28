"""Account for ZIP payloads once and keep compressed/installed sizes distinct."""
import tempfile
import unittest
from pathlib import Path
import zipfile

from scripts.measure_package import measure


class PackageMeasurementTests(unittest.TestCase):
    def test_accounting_matches_zip_and_overlapping_resource_names_are_disjoint(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'fixture.zip'
            contents = {
                'bashdock/bashdock.exe': b'app',
                'bashdock/bashdock-updater.exe': b'helper',
                'bashdock/_internal/PySide6/Qt6WebEngineCore.dll': b'engine' * 1000,
                'bashdock/_internal/PySide6/resources/qtwebengine_devtools_resources.debug.pak': b'debug' * 1000,
                'bashdock/_internal/PySide6/resources/qtwebengine_devtools_resources.pak': b'devtools' * 1000,
                'bashdock/_internal/PySide6/resources/icudtl.dat': b'icu',
                'bashdock/_internal/PySide6/qml/Example.qml': b'qml',
                'bashdock/_internal/PySide6/translations/en-US.pak': b'locale',
                'bashdock/_internal/PySide6/Qt6Gui.dll': b'gui',
                'bashdock/_internal/python312.dll': b'python',
                'bashdock/licenses/LICENSE': b'license',
            }
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr('bashdock/empty/', '')
                for name, data in contents.items():
                    bundle.writestr(name, data)
            result = measure(archive)
            self.assertEqual(len(contents), result['file_count'])
            self.assertEqual(sum(map(len, contents.values())), result['installed_bytes'])
            self.assertLess(result['payload_bytes'], result['installed_bytes'])
            self.assertEqual(archive.stat().st_size,
                             result['payload_bytes'] + result['archive_overhead_bytes'])
            self.assertEqual(result['payload_bytes'], sum(g['compressed'] for g in result['components'].values()))
            for name in ('WebEngine debug resource packs', 'WebEngine release developer-tools resources',
                         'Other WebEngine resources'):
                self.assertEqual(1, result['components'][name]['files'])
