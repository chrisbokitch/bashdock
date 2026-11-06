"""Special button lines are separate from the Bash sent to the shell."""
import unittest

from bashdock.command_sequence import command_steps


class CommandSequenceTests(unittest.TestCase):
    def test_interrupt_line_preserves_surrounding_scripts(self):
        self.assertEqual([
            ('command', 'printf first'), ('interrupt', None),
            ('command', 'printf second\nprintf third'),
        ], command_steps('printf first\r\n  <<interrupt>>  \r\nprintf second\nprintf third'))
        self.assertEqual([('interrupt', None), ('command', 'npm run dev')],
                         command_steps('<<interrupt>>\nnpm run dev'))

    def test_only_correctly_spelled_standalone_marker_is_special(self):
        self.assertEqual([('command', 'echo <<interrupt>>\n<<interupt>>')],
                         command_steps('echo <<interrupt>>\n<<interupt>>'))
        self.assertEqual([('interrupt', None)], command_steps('<<interrupt>>'))
