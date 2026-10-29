"""The public test command must retain coverage and propagate native failures."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('run_tests', Path(__file__).resolve().parents[1] / 'scripts/run_tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestRunnerTests(unittest.TestCase):
    def test_windows_groups_finish_sequentially_and_native_failure_propagates(self):
        environment = {'QT_QPA_PLATFORM': 'offscreen', 'QTWEBENGINE_CHROMIUM_FLAGS': '--existing-flag'}
        with patch.dict(os.environ, environment, clear=True), patch.object(runner.subprocess, 'run',
                side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=7)]) as run:
            self.assertEqual(7, runner.main([], windows=True))
            self.assertEqual('offscreen', os.environ['QT_QPA_PLATFORM'])
            self.assertEqual('--existing-flag', os.environ['QTWEBENGINE_CHROMIUM_FLAGS'])
        first, native = run.call_args_list
        self.assertEqual('--unit-suite', first.args[0][-1])
        self.assertEqual(['-p', 'test_windows.py', '-v'], native.args[0][-3:])
        self.assertEqual('windows', native.kwargs['env']['QT_QPA_PLATFORM'])
        self.assertEqual('--existing-flag --disable-gpu', native.kwargs['env']['QTWEBENGINE_CHROMIUM_FLAGS'])

    def test_unit_failure_stops_before_native_process(self):
        with patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=3)) as run:
            self.assertEqual(3, runner.main([], windows=True))
        self.assertEqual(1, run.call_count)

    def test_other_platforms_keep_original_discovery_and_return_code(self):
        with patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=4)) as run:
            self.assertEqual(4, runner.main([], windows=False))
        self.assertEqual(['-m', 'unittest', 'discover', '-s', 'tests', '-v'], run.call_args.args[0][1:])

    def test_partition_keeps_every_other_case_exactly_once_in_discovery_order(self):
        class Case(unittest.TestCase):
            def runTest(self):
                pass
        native_type = type('Native', (Case,), {'__module__': 'test_windows'})
        first, second, native = Case(), Case(), native_type()
        suite = unittest.TestSuite([first, unittest.TestSuite([native, second])])
        self.assertEqual([first, second], list(runner.without_native_tests(suite)))
