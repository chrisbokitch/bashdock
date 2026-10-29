"""Isolate native Windows terminal tests from the preceding GUI/mock suite."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def without_native_tests(suite):
    """Keep every discovered case except the separately executed Windows file."""
    result = unittest.TestSuite()
    for entry in suite:
        if isinstance(entry, unittest.TestSuite):
            result.addTests(without_native_tests(entry))
        elif entry.__class__.__module__ != 'test_windows':
            result.addTest(entry)
    return result


def run_unit_suite():
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    return 0 if unittest.TextTestRunner(verbosity=2).run(without_native_tests(suite)).wasSuccessful() else 1


def main(arguments=None, *, windows=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if arguments == ['--unit-suite']:
        return run_unit_suite()
    windows = sys.platform == 'win32' if windows is None else windows
    if not windows:
        return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=ROOT).returncode
    # Both child processes exit fully, including their Qt/Chromium instances,
    # before the next group begins. Never change the caller/app environment.
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--unit-suite'], cwd=ROOT)
    if result.returncode:
        return result.returncode
    environment = dict(os.environ, QT_QPA_PLATFORM='windows')
    flags = environment.get('QTWEBENGINE_CHROMIUM_FLAGS', '').split()
    if '--disable-gpu' not in flags:
        flags.append('--disable-gpu')
    environment['QTWEBENGINE_CHROMIUM_FLAGS'] = ' '.join(flags)
    print('Running real terminal checks in a fresh native Windows GUI process (test-only --disable-gpu).', flush=True)
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                           '-p', 'test_windows.py', '-v'], cwd=ROOT, env=environment).returncode


if __name__ == '__main__':
    raise SystemExit(main())
