"""The updater's static import graph must stay independent of the Qt UI."""
import ast
import importlib.util
from pathlib import Path
import unittest

from scripts.check_updater import reject_gui_payload

ROOT = Path(__file__).resolve().parent.parent


class UpdaterDependencyTests(unittest.TestCase):
    def test_all_updater_modes_have_a_gui_free_static_import_graph(self):
        # Inspect imports inside functions too: PyInstaller collects lazy imports
        # even when ordinary import-time sys.modules checks appear GUI-free.
        pending = [('bashdock.update_helper', ['scripts.launch_updater'])]
        visited = set()
        while pending:
            module, chain = pending.pop()
            if module in visited:
                continue
            visited.add(module)
            self.assertFalse(module.startswith(('PySide6', 'shiboken6')), ' -> '.join(chain+[module]))
            path = ROOT.joinpath(*module.split('.')).with_suffix('.py')
            is_package = False
            if not path.is_file():
                path = ROOT.joinpath(*module.split('.'), '__init__.py')
                is_package = True
            if not path.is_file():
                continue
            package = module if is_package else module.rpartition('.')[0]
            if '.' in module:
                pending.append((module.rpartition('.')[0], chain+[module]))
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = importlib.util.resolve_name('.'*node.level+(node.module or ''), package) if node.level else node.module
                    names = [base]+[base+'.'+alias.name for alias in node.names]
                else:
                    continue
                pending.extend((name, chain+[module]) for name in names if name)
        self.assertIn('bashdock.update_acceptance', visited)
        self.assertIn('bashdock.config', visited)
        self.assertIn('bashdock.tab_icon_catalog', visited)
        self.assertNotIn('bashdock.tab_icons', visited)

    def test_archive_guard_checks_both_native_paths_and_python_module_names(self):
        reject_gui_payload(['python312.dll', 'truststore._windows', 'bashdock.config'])
        for name in ('PySide6\\Qt6Gui.dll', 'PySide6.QtCore', 'shiboken6.Shiboken', 'other/Qt6Core.dll'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'bundles Qt'):
                reject_gui_payload([name])
