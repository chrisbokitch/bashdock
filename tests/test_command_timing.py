"""Timing protocol validation and complete scripts in a real Bash shell."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bashdock.command_timing import CommandTiming
from bashdock.config import find_bash
from bashdock.shell_integration import INIT_SCRIPT

BASH = find_bash() if os.name == 'nt' else shutil.which('bash')


class CommandTimingTests(unittest.TestCase):
    def test_only_matching_started_execution_can_complete_and_duplicate_events_are_ignored(self):
        timing = CommandTiming()
        timing.prepare('not logged', 'Update and Test', 'session')
        token = timing.token
        self.assertIsNone(timing.event(f'session;{token};done;0;100.000001'))
        for event in (f'old;{token};start;100.000001', 'session;wrong;start;100.000001',
                      f'session;{token};start;bad', f'session;{token};start;nan'):
            self.assertIsNone(timing.event(event))
        self.assertEqual('Update and Test running…', timing.event(f'session;{token};start;100.000001'))
        self.assertIsNone(timing.event(f'session;{token};start;101.000000'))
        self.assertIsNone(timing.event(f'session;{token};done;256;150.691001'))
        self.assertEqual('Update and Test completed in 50.691s', timing.event(f'session;{token};done;0;150.691001'))
        self.assertIsNone(timing.event(f'session;{token};done;0;150.691001'))
        self.assertIsNone(timing.token)

    def test_failure_interrupt_reset_and_clock_adjustment(self):
        for status, expected in ((1, 'Test failed after 0.123s · exit code 1'),
                                 (130, 'Test interrupted after 0.123s · exit code 130')):
            timing = CommandTiming()
            timing.prepare('false', 'Test', 's')
            token = timing.token
            timing.event(f's;{token};start;100.000000')
            self.assertEqual(expected, timing.event(f's;{token};done;{status};100.123456'))
            timing.prepare('pwd', 'Test', 's')
            token = timing.token
            timing.event(f's;{token};start;100.000000')
            self.assertIn('duration unavailable', timing.event(f's;{token};done;0;99.000000'))
            timing.prepare('pwd', 'Test', 'old')
            token = timing.token
            timing.reset()
            self.assertIsNone(timing.event(f'old;{token};done;0;101.000000'))

    def test_startup_wait_has_no_elapsed_time_and_busy_input_keeps_its_literal_command(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from bashdock.terminal import Terminal
        from bashdock.command_startup import CommandStartup
        startup = CommandStartup()
        startup.begin()
        state = SimpleNamespace(process=object(), at_prompt=False, command_startup=startup,
                                command_timing=CommandTiming(), trace=Mock(),
                                focus_terminal=Mock(), dispatch_command=Mock())
        Terminal.run_command(state, 'sleep 1', label='Test')
        self.assertIsNone(state.command_timing.started)
        self.assertEqual(1, len(startup.pending))
        self.assertIn("eval -- 'sleep 1'", startup.pending[0][1])
        state.dispatch_command.assert_not_called()
        Terminal.shell_ready(state, startup.session_id)
        state.dispatch_command.assert_called_once()
        state.command_timing.reset()
        state.dispatch_command.reset_mock()
        Terminal.run_command(state, 'echo remote', label='Remote')
        self.assertIsNone(state.command_timing.token)
        self.assertEqual('echo remote', state.dispatch_command.call_args.args[1])

    @unittest.skipUnless(BASH, 'Requires Bash')
    def test_real_multiline_script_keeps_state_quotes_heredoc_aliases_and_captures_status_before_user_hooks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'child').mkdir()
            (root / '.bash_profile').write_text("PROMPT_COMMAND=('printf USER_HOOK; false')\n")
            rc = root / 'init.bash'
            rc.write_text(INIT_SCRIPT.replace('source /etc/profile', ':'), encoding='utf-8')
            timing = CommandTiming()
            body = ("cd -- \"$HOME/child\"\nexport BASHDOCK_TIMING_TEST=kept\n"
                    "alias timing_alias='printf alias-ok'\ntiming_alias\n"
                    "cat <<'DATA'\nquotes ' and \" and $(printf SHOULD_NOT_RUN)\nDATA\n"
                    "printf '%s' 'café\tλ' > unicode.txt\nsleep 0.12\nprintf success > receipt.txt\ntrue")
            wrapped = timing.prepare(body, 'Multiline', 'test-session')
            token = timing.token
            # Run a second script with status 7 after the first prompt. Both
            # marker pairs must occur exactly once, despite many script lines.
            second = CommandTiming()
            failure = second.prepare('(exit 7)', 'Failure', 'test-session')
            result = subprocess.run([BASH, '--noprofile', '--rcfile', rc.as_posix(), '-i'],
                input=wrapped.replace('\t', '\x16\t') + '\nprintf "STATE:%s\\n" "$BASHDOCK_TIMING_TEST"\n' + failure + '\nexit\n',
                env=dict(os.environ, HOME=root.as_posix(), BASHDOCK_SESSION='test-session'),
                text=True, encoding='utf-8', capture_output=True, timeout=10)
            self.assertEqual('success', (root / 'child' / 'receipt.txt').read_text())
            self.assertEqual('café\tλ', (root / 'child' / 'unicode.txt').read_text(encoding='utf-8'))
            self.assertIn('STATE:kept', result.stdout)
            self.assertIn('alias-ok', result.stdout)
            self.assertIn('$(printf SHOULD_NOT_RUN)', result.stdout)
            events = re.findall(r'\x1b\]777;bashdock-command;([^\x07]+)\x07', result.stdout)
            self.assertEqual(4, len(events), result.stdout)
            messages = [timing.event(event) for event in events[:2]]
            self.assertEqual('Multiline running…', messages[0])
            self.assertRegex(messages[1], r'Multiline completed in [0-9]+\.[0-9]{3}s')
            self.assertGreaterEqual(float(messages[1].split()[-1][:-1]), 0.12)
            self.assertTrue(events[1].startswith(f'test-session;{token};done;0;'), result.stdout)
            self.assertTrue(events[3].startswith(f'test-session;{second.token};done;7;'), result.stdout)
