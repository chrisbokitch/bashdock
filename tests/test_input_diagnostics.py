"""Input diagnostics must detect corruption without exporting shell contents."""
import json
from pathlib import Path
import tempfile
import unittest

from bashdock.input_diagnostics import CommandTrace, Recorder


class InputDiagnosticsTests(unittest.TestCase):
    def test_export_contains_metadata_but_no_commands_paths_output_or_fingerprints(self):
        recorder = Recorder()
        trace = CommandTrace(recorder)
        secret = "echo super-secret-token C:/private/client-folder"
        command = trace.prepare(secret, ready=True, running=True)
        trace.receive(command, secret + '\r')
        # Reject unexpected fields and all text-valued fields, even when
        # someone accidentally passes sensitive content to the recorder.
        recorder.record('write_failed', errno=5, message=secret, winerror=secret)
        recorder.record('window_resize', width=secret, height=400, path=secret)
        recorder.record(secret, command=secret, terminal=secret)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.json'
            (path.parent / 'bashdock.log').write_text(secret)
            recorder.save(path)
            report = json.loads(path.read_text())
        text = json.dumps(report)
        for private in (secret, 'super-secret-token', 'client-folder', 'fingerprint', 'digest'):
            self.assertNotIn(private, text)
        received = next(e for e in report['recent_activity']['events'] if e['event'] == 'command_received')
        self.assertTrue(received['recognized'])
        self.assertTrue(received['unchanged'])
        self.assertEqual(command, received['command'])
        self.assertIn('bashdock', report['runtime'])
        for event in report['recent_activity']['events']:
            self.assertTrue(all(type(v) in (int, bool) for k, v in event.items() if k != 'event'))

    def test_private_binding_integrity_is_distinguished_without_capturing_script_text(self):
        recorder = Recorder()
        trace = CommandTrace(recorder)
        command = trace.prepare('secret script', ready=True, running=True, wire_text='\x18\x02')
        trace.receive(command, '\x18\x02')
        events = recorder.snapshot()['events']
        self.assertTrue(events[0]['private_binding'])
        self.assertTrue(events[1]['unchanged'])
        self.assertNotIn('secret script', json.dumps(events))

    def test_integrity_checks_detect_first_character_loss_and_handle_unicode_newlines(self):
        recorder = Recorder()
        trace = CommandTrace(recorder)
        text = "printf 'café'\nprintf next\r\npwd"
        normalized = "printf 'café'\rprintf next\rpwd\r"
        command = trace.prepare(text, ready=True, running=True)
        trace.receive(command, normalized)
        command = trace.prepare(text, ready=True, running=True)
        trace.receive(command, normalized[1:])
        events = [e for e in recorder.snapshot()['events'] if e['event'] == 'command_received']
        self.assertEqual([True, False], [e['unchanged'] for e in events])
        self.assertEqual(len(normalized[1:].encode('utf-8')), events[-1]['utf8_bytes'])

    def test_history_and_pending_integrity_checks_are_bounded_and_restart_invalidates_checks(self):
        recorder = Recorder(capacity=3)
        trace = CommandTrace(recorder)
        for i in range(200):
            command = trace.prepare('secret', ready=False, running=True)
        snapshot = recorder.snapshot()
        self.assertEqual(3, len(snapshot['events']))
        self.assertEqual(197, snapshot['dropped_events'])
        self.assertEqual([198, 199, 200], [e['sequence'] for e in snapshot['events']])
        self.assertEqual(128, len(trace._expected))
        self.assertTrue(all(isinstance(value, bytes) for value in trace._expected.values()))
        trace.reset()
        trace.receive(command, 'secret\r')
        self.assertFalse(recorder.snapshot()['events'][-1]['recognized'])

    def test_reports_keep_native_write_counts_and_errors_without_text(self):
        recorder = Recorder()
        recorder.record('write_complete', command=1, reported_count=10)
        recorder.record('write_failed', command=2, errno=5, winerror=10054, error='private error')
        events = recorder.snapshot()['events']
        self.assertEqual(10, events[0]['reported_count'])
        self.assertEqual(10054, events[1]['winerror'])
        self.assertNotIn('error', events[1])
