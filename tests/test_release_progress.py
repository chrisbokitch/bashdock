import unittest
from threading import Event, enumerate as threads

from scripts.release_progress import progress


class ReleaseProgressTests(unittest.TestCase):
    def test_reports_while_operation_is_blocked_and_stops_when_it_finishes(self):
        messages = []
        tick = Event()

        def capture(message):
            messages.append(message)
            if 'Still working:' in message:
                tick.set()

        with progress('Scanning Qt notices', interval=0.01, emit=capture):
            self.assertTrue(tick.wait(2), 'No progress while the packaging step was blocked')
            self.assertFalse(any(m.startswith('Done:') for m in messages))
        self.assertTrue(messages[0].startswith('Scanning Qt notices'))
        self.assertTrue(messages[-1].startswith('Done: Scanning Qt notices'))
        self.assertFalse(any(t.name == 'release-progress' for t in threads()))

    def test_failure_or_cancel_is_not_reported_as_success_and_leaves_no_worker(self):
        for error in (ValueError('checksum mismatch'), KeyboardInterrupt()):
            messages = []
            with self.assertRaises(type(error)):
                with progress('Verifying download', emit=messages.append):
                    raise error
            self.assertTrue(messages[-1].startswith('Stopped: Verifying download'))
            self.assertFalse(any(m.startswith('Done:') for m in messages))
            self.assertFalse(any(t.name == 'release-progress' for t in threads()))
