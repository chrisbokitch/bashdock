"""Button startup ordering independent of the desktop/Windows backend."""
import unittest

from bashdock.command_startup import CommandStartup


class CommandStartupTests(unittest.TestCase):
    def test_early_commands_preserve_exact_text_and_order_and_release_once(self):
        startup = CommandStartup()
        token = startup.begin()
        commands = ["pwd", "printf 'café\\n'\nprintf 'done\\n'"]
        for command in commands:
            self.assertFalse(startup.submit(command))
        self.assertEqual(commands, startup.release(token))
        self.assertEqual([], startup.release(token))
        self.assertTrue(startup.submit("git status"))
        self.assertEqual([], startup.pending)

    def test_restart_discards_old_commands_and_ignores_late_readiness(self):
        startup = CommandStartup()
        old = startup.begin()
        startup.submit("old command")
        new = startup.begin()
        self.assertNotEqual(old, new)
        startup.submit("new command")
        self.assertEqual([], startup.release(old))
        self.assertFalse(startup.ready)
        self.assertEqual(["new command"], startup.release(new))

    def test_stop_discards_pending_commands_and_invalidates_readiness(self):
        startup = CommandStartup()
        token = startup.begin()
        startup.submit("pwd")
        startup.reset()
        self.assertEqual([], startup.pending)
        self.assertEqual([], startup.release(token))
        self.assertFalse(startup.ready)
