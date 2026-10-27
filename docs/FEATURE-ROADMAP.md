# BashDock feature roadmap

Proposed work after the 1.0 release. This is an investigation and sequencing
document, not a commitment to dates or release numbers. The current release and
automatic-update validation remain the immediate priority.

## Suggested sequence

| Order | Feature | Scope |
| --- | --- | --- |
| 1 | Multiline command editor | Improve the button editor and validate existing multiline transport. |
| 2 | Prompted command variables | Add opt-in templates, one prompt dialog, and predictable substitution. |
| 3 | Variables with choices | Extend the same prompt system with dropdowns and validation. |
| 4 | Different shells per tab | Introduce shell profiles and shell-specific integration. |

Investigate shell support early because quoting and command submission affect
templates, but ship it after its broader compatibility work is validated.
Changes to the data model should account for all four features.

## Multiline commands attached to buttons

Goal: edit and run a short sequence or script from a command button, in that
tab's existing shell.

The stored command is already a string, and the terminal bridge currently sends
embedded newlines as Enter keystrokes. Tests cover multiline transport. The
current table-cell editor is not a proper multiline authoring experience; that
transport alone is not a complete script-execution feature.

Proposed UI and behaviour:

- Keep the command-bar buttons compact. Open a dedicated multiline editor from
  Configure tab, with a clear label, command body, and readable preview.
- Preserve literal newlines, blank lines, indentation, quotes and Unicode through
  editing, saving, workspaces, export/import and recovery.
- Execute in the existing shell, preserving its directory and environment.
- Investigate continuation syntax, functions, loops and heredocs in Git Bash.
  Validate equivalent handling for each additional shell before claiming support.
- Explain that a button receives no automatic stop-on-error behaviour. Shell
  syntax determines whether later commands run after a failure.

Acceptance: real-shell tests confirm execution order, multiline syntax and
preserved state; cancelling edits changes nothing. Commands still require an
appropriate shell prompt and are not a background job queue.

## Prompted command variables

Goal: a button containing `${number}` can ask for a value before sending the
completed command.

Proposed UI and behaviour:

- Make prompting an explicit per-button option, such as **Prompt for values**.
  Existing buttons remain literal commands.
- Discover all placeholders and show one dialog with one field per unique name,
  in first-occurrence order. Repeated names reuse the same value.
- Display a read-only preview of the resolved command in that dialog.
- Validate all fields before sending anything. Cancel sends nothing to the shell.
- Keep entered values transient initially; do not automatically save them into
  button definitions, workspaces, exports or logs.
- Treat a name such as `number` as a label, not an implicit type declaration.
  Investigate optional text/number validation metadata separately.

Important compatibility issue: `${name}` is already valid Bash syntax.
Opt-in templates must define an explicit way to leave native shell expressions
literal. Do not silently reinterpret existing commands such as `${HOME}`.

Before implementation, decide:

- How literal placeholders and native shell expressions are escaped.
- How values are quoted for Bash, PowerShell and cmd, including spaces, quotes,
  dollar signs and shell operators. Do not assume one quoting algorithm works
  for all shells or for placeholders inside existing quotes.
- Whether the first iteration restricts placeholders to complete argument
  positions, and whether raw shell-syntax insertion is an explicit advanced mode.
- Whether multiline input is permitted for individual values.
- How empty values, optional defaults and validation errors are presented.

Acceptance: duplicate variables, cancellation, empty/invalid input, literal
shell expressions, Unicode and shell metacharacters behave predictably.
Nothing is submitted until the complete template is resolved. Previewing does
not evaluate the command.

## Variables with set options

Goal: `${number:1,2,3}` prompts the user to choose **1**, **2** or **3**.

Build on the same opt-in parser and dialog:

- Plain `${name}` uses a text field; `${name:one,two,three}` uses a dropdown.
- A choices field accepts only one of its configured options.
- Multiple text and choice variables can share one dialog and command preview.
- Repeated names share a value; conflicting definitions are a configuration error.
- Decide how commas, colons, braces, whitespace and literal placeholder text are
  escaped before finalizing the syntax.
- Do not preselect an option unless a deliberate default is configured.

The requested syntax is the starting point. Keep its simple cases concise;
consider a structured variable editor if labels, types, defaults or option
values outgrow inline syntax.

Acceptance: malformed templates and empty/conflicting option lists are reported
without changing the saved command or writing partial text to a shell.
Definitions survive workspace and settings round trips; transient answers do not.

## Different shells, configurable per tab

Goal: choose Git Bash, PowerShell or cmd for each tab, and restore that choice
with its workspace.

Proposed design:

- Introduce shell profiles describing shell type, executable and argument list.
  Store executable arguments structurally rather than as an ambiguous command string.
- Keep appearance settings independent of shell choice.
- Add the shell selector to Configure tab and identify the shell in the UI.
- Preserve existing tabs as Git Bash during migration. Retain configured Git Bash
  paths instead of replacing them with guessed defaults.
- Support Git Bash and cmd, and distinguish Windows PowerShell
  (`powershell.exe`) from PowerShell 7+ (`pwsh.exe`).
- Validate executable availability and show actionable setup errors. Git for
  Windows should only be required for tabs that use it.
- Save the shell profile/reference with tabs, workspaces, exports and backups.
  Missing profiles or executables must not silently start a different shell.
- Changing the shell requires restarting that tab with confirmation; it cannot
  convert a running process into another shell.
- Open external shell must use the selected tab's shell and last known directory.

Investigation areas:

- Reuse ConPTY and the terminal renderer while separating shell-specific launch,
  prompt/directory hooks, history behaviour and command submission.
- Git Bash's current directory hook and init file are Bash-specific. Investigate
  reliable equivalents for PowerShell and cmd, and explicit limitations where a
  shell cannot report a new directory. Do not promise identical integration.
- Preserve user profiles/prompts; test startup arguments and executable paths
  containing spaces.
- Define how new tabs inherit shell choice and how shared profiles are edited
  without unexpectedly changing saved workspaces.
- Add actual Windows acceptance tests for each shell: typing, Ctrl+C, Unicode,
  resizing, multiline buttons, templates, directory restoration and external launch.

## Workspace submenu: Replace current toggle

Post-1.0 request: add a checkable **Replace current** item at the bottom of
**Manage → Workspaces**, separated from the saved workspace entries by a separator.

- Unchecked: choosing a saved workspace adds its missing tabs, preserving the
  current behavior for overlapping tab identities.
- Checked: choosing a saved workspace replaces the current workspace instead of
  adding tabs, using the existing replacement confirmation and backup behavior.
- Toggling the item only changes the opening mode; it does not immediately open
  a workspace or close any tabs.
- Start with the existing additive behavior by default. Decide whether the mode
  persists across app launches when implementing the enhancement.

Acceptance: submenu entries respect the selected mode; the checked state is
clear; cancelling replacement preserves current shells and settings.

## Shared foundations and release boundaries

- Extend settings with backward-compatible migrations. Preserve persistent tab
  identities and duplicate-workspace behaviour.
- Treat command bodies and templates as trusted user-authored executable content.
  Do not expand templates or run commands during startup, import or restoration.
- Variables are resolved by BashDock before submission. Shell variables and
  environment variables remain a separate concept.
- Do not imply that an arbitrary foreground program or SSH session has the same
  shell syntax as the tab's locally configured shell. Remote command templates
  need an explicit policy before shell-aware quoting can be promised.
- Each feature needs its own reviewable scope, tests and version decision.
  None of these investigations expands the current 1.0 acceptance gates.
