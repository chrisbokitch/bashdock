"""Read-only reference for application shortcuts and context-specific keys."""
from html import escape

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout


SHORTCUT_GROUPS = (
    ('BashDock', (
        ('Ctrl+Shift+T', 'New tab'),
        ('Ctrl+Shift+W', 'Close current tab'),
        ('Ctrl+F', 'Find in the current terminal'),
        ('Ctrl++ / Ctrl+=', 'Increase terminal font size'),
        ('Ctrl+-', 'Decrease terminal font size'),
        ('Ctrl+0', "Reset to the tab’s configured font size"),
        ('Ctrl+Shift+C', 'Copy selected terminal text'),
        ('Ctrl+Shift+V', 'Paste into the terminal'),
    )),
    ('While searching', (
        ('Enter', 'Next match'),
        ('Shift+Enter', 'Previous match'),
        ('Escape', 'Close search and return to the terminal'),
    )),
    ('In the Bash command editor', (
        ('Enter', 'Insert a new line'),
        ('Tab', 'Insert a literal tab'),
        ('Ctrl+Tab / Ctrl+Shift+Tab', 'Move focus out of the command field, forward / backward'),
        ('Escape', 'Cancel the command editor'),
    )),
    ('In the Configure tab button list', (
        ('F2 / Enter', 'Edit the selected command button'),
    )),
)


class KeyboardShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Keyboard shortcuts')
        self.resize(640, 630)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        note = QLabel('Shortcuts are shown for reference and cannot be remapped here.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.reference = QTextBrowser()
        self.reference.setAccessibleName('Keyboard shortcut reference')
        self.reference.setOpenExternalLinks(False)
        self.reference.setStyleSheet('QTextBrowser { background:#10141c;color:#dde4ef;border:0; }')
        sections = []
        for title, rows in SHORTCUT_GROUPS:
            cells = ''.join(f'<tr><td width="38%" style="white-space:nowrap;padding-right:20px">'
                            f'<b>{escape(key)}</b></td><td>{escape(action)}</td></tr>'
                            for key, action in rows)
            sections.append(f'<h3>{escape(title)}</h3><table cellspacing="0" cellpadding="4" width="100%">'
                            f'{cells}</table>')
        self.reference.setHtml(''.join(sections))
        layout.addWidget(self.reference, 1)
        shell = QLabel('Terminal programs handle their own keys, including Ctrl+C to interrupt, '
                       'arrow keys and Tab. Their behavior depends on the running shell or program. '
                       'Font zoom is temporary and applies only to the current tab.')
        shell.setWordWrap(True)
        layout.addWidget(shell)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
