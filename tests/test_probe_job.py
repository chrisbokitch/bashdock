"""A probe's descendants must not survive its root process or lock its sandbox."""
import ctypes
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.probe_job import ProcessJob
from bashdock.update_helper import retry


@unittest.skipUnless(sys.platform == 'win32', 'Requires Windows job objects')
class ProbeJobTests(unittest.TestCase):
    def test_closing_job_reaps_orphan_child_and_leaves_unrelated_process_running(self):
        with tempfile.TemporaryDirectory(prefix='BashDock job test ') as folder:
            root = Path(folder)
            sandbox = root / 'sandbox'
            sandbox.mkdir()
            gate, receipt = root / 'start', root / 'child-pid'
            child_code = ("import os,sys,time; from pathlib import Path; "
                          "os.chdir(sys.argv[1]); Path(sys.argv[2]).write_text(str(os.getpid())); time.sleep(60)")
            parent_code = ("import subprocess,sys,time; from pathlib import Path\n"
                           "while not Path(sys.argv[1]).exists(): time.sleep(.01)\n"
                           "subprocess.Popen([sys.executable, '-c', sys.argv[3], sys.argv[4], sys.argv[2]])\n"
                           "while not Path(sys.argv[2]).exists(): time.sleep(.01)\n")
            unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
            process = None
            handle = None
            try:
                with ProcessJob() as job:
                    process = subprocess.Popen([sys.executable, '-c', parent_code, str(gate),
                                                str(receipt), child_code, str(sandbox)])
                    job.assign(process.pid)
                    gate.touch()
                    self.assertEqual(0, process.wait(timeout=15))
                    child_pid = int(receipt.read_text())
                    handle = job.kernel.OpenProcess(0x00100000, False, child_pid)  # SYNCHRONIZE
                    self.assertTrue(handle)
                    job.kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
                    job.kernel.WaitForSingleObject.restype = ctypes.c_ulong
                    self.assertEqual(258, job.kernel.WaitForSingleObject(handle, 0))  # WAIT_TIMEOUT: alive
                    job.close()
                    self.assertEqual(0, job.kernel.WaitForSingleObject(handle, 10000))
                    self.assertIsNone(unrelated.poll())
                    retry(sandbox.rmdir, timeout=5)
            finally:
                if handle:
                    job.kernel.CloseHandle(handle)
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                unrelated.kill()
                unrelated.wait(timeout=10)
