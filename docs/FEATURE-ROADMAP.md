# BashDock feature roadmap

BashDock 1.3.0 is released; the 1.0 acceptance checks remain complete. The owner
prioritized the smaller UI quality-of-life improvements first on 2026-10-27.
This is an investigation and sequencing document, not a commitment to dates or
release numbers.

## Agreed next sequence

On 2026-10-28, the owner prioritized three focused additions to BashDock's existing
command-button workflow, then a reassessment before taking on broader features.

| Order | Feature | Scope |
| --- | --- | --- |
| Complete | Workspace submenu: Replace current toggle | Released in 1.3.0; owner visual check passed. |
| Complete | Wrapping command buttons | Released in 1.3.0; owner visual check passed. |
| Complete | Tab icons and compact overflow | Released in 1.3.0; owner visual check passed. |
| 1 | Multiline command editor | Implemented in development 1.4.0; owner visual check pending. |
| 2 | Per-button command confirmation | Add an optional Confirm before using toggle. |
| 3 | Command-button preset bundles | Preview and apply useful starter sets; destructive preset buttons enable confirmation. |
| Candidate | Prompted command variables | Reassess after the three focused additions; not scheduled. |
| Candidate | Variables with choices | Depends on prompted variables; not scheduled. |
| Candidate | Different shells per tab | Broader architectural work; not scheduled. |

Deliver each of the three additions separately with automated regression checks,
actual Windows shell tests where relevant, and a short owner visual or interaction
check. Use focused release checks appropriate to the change; broaden testing when
its scope warrants it. No release dates or version numbers are committed here.

Confirmation comes before presets so destructive starter commands can use that
behavior from their first release. After presets, reassess whether additional
features justify their complexity and maintenance cost. Web/LAN access remains
an exploratory idea outside this implementation plan.

If command templates are pursued later, investigate shell support and quoting
before implementation, even if additional shells ship afterward. Keep current
data-model extensions compatible with that possibility without implementing
the deferred features in advance.

## Workspace submenu: Replace current toggle

Implemented in development **1.1.0**: a checkable **Replace current** item at the bottom of
**Manage → Workspaces**, separated from the saved workspace entries by a separator.

- Unchecked: choosing a saved workspace adds its missing tabs, preserving the
  current behavior for overlapping tab identities.
- Checked: choosing a saved workspace replaces the current workspace instead of
  adding tabs, using the existing replacement confirmation and backup behavior.
- Toggling the item only changes the opening mode; it does not immediately open
  a workspace or close any tabs.
- Additive behavior is the default for new and existing settings. The selected
  mode persists across launches and settings export/import/backup recovery.
- Failed preference saves restore the prior mode and checkmark. The workspace
  manager’s explicit Open/Replace controls retain their existing behavior.

Acceptance: submenu entries respect the selected mode; the checked state is
clear; cancelling replacement preserves current shells and settings.

## Wrapping command buttons

Implemented in development **1.3.0**. Owner visual check passed. When a window
is too narrow for all command buttons, they wrap onto additional rows.

- Keep button order and each tab's independent command bar.
- Grow the footer to fit complete rows and return space to the terminal when
  the window widens. Keep Configure tab accessible beside the command area.
- Refit the terminal as the footer height changes, preserving the running shell,
  directory, environment and scrollback.
- Cover restored hidden tabs, tab switches, long labels, window resizing and
  fractional display scaling; avoid reintroducing the clipped-footer regression.
- Long labels shorten visually while retaining the full label and command in
  the tooltip. Large command areas are capped at 40% of the tab height (at least
  one complete row) and scroll vertically to retain usable terminal space.

Acceptance: buttons remain fully visible/clickable across row changes, order and
focus restoration are preserved, and narrowing/widening does not restart shells
or submit commands.

## Tab icons and compact overflow

Implemented in development **1.2.0**, moved ahead of button wrapping at the
owner's request. Owner visual check passed.

- New and legacy tabs receive generic shapes automatically: use each of the 12
  shapes before repeating the least-used shape. Assignments persist; shared legacy
  saved/open tab identities receive the same initial icon.
- **Configure tab → Tab icon → Choose icon…** offers 36 original bundled line
  icons, including folders, servers, branches, tools and geometric shapes.
  Selection is staged until Configure tab is saved. Icons follow tab theme colors.
- When full labels exceed the space beside the New tab control, tabs show icons
  and close controls. Widening restores labels. Names remain available through
  tooltips and accessibility; native scroll arrows handle further overflow.
- Existing settings without icons remain valid. Icons persist through saved
  workspaces, export/import and recovery without changing tab identity or shells.

Acceptance: resizing changes the presentation without changing the selected tab
or shell; rename/reorder/close remain usable, and old settings without icons
continue to restore normally.

## Multiline commands attached to buttons

Implemented in development **1.4.0**; owner visual check pending. Add and Edit…
open a dedicated label/body editor; double-click and F2/Enter also open existing
buttons. The table keeps a compact preview, with full commands in tooltips. Inner
Save stages edits until Configure tab is saved. Literal tabs are quoted at the
button write boundary to preserve them with standard Bash Readline bindings.
Automated checks cover editing/cancellation, persistence, and real-shell syntax
and state. Windows compatibility CI includes the multiline case in its repeated
button execution sequence.

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


## Command-button preset bundles

Queued at the owner's request. Goal: help people start with useful command
buttons by applying a curated bundle to a tab. This adds a roadmap item; it does
not change the current implementation. Presets follow the multiline editor and
per-button confirmation in the agreed next sequence.

Proposed first iteration:

- Add **Presets…** to Configure tab, with bundle descriptions and a preview of
  every button label and exact command before applying.
- Let users select individual buttons from a bundle. Default to **Append**;
  offer **Replace existing buttons** as an explicit choice with a clear preview
  of what will be removed.
- Stage the changes in Configure tab. Save persists them; Cancel leaves existing
  buttons and running shells untouched. Applying, saving, importing or restoring
  a preset never executes its commands.
- Copy the selected definitions into ordinary, editable per-tab buttons.
  Preserve button order, tab identity, focus restoration and wrapping behavior.
  Later catalog changes must not silently overwrite customized buttons.
- Describe required tools and shell/platform compatibility for each bundle.
  Applying a preset must not install tools. The initial examples target Git Bash
  on Windows; "Universal" describes broad usefulness, not cross-shell portability.
- Clearly mark destructive commands in previews and explain their scope before
  users add them. Destructive preset buttons enable the per-button **Confirm
  before using** option described below; users can review or change that setting.
- Decide how repeat applications expose duplicates without silently removing or
  replacing existing definitions. User-saved/shared bundles are a possible later
  extension; the first iteration can ship a small bundled catalog.

### Initial catalog candidates

Preserve the owner's starting examples for review before implementation:

| Bundle | Button | Command |
| --- | --- | --- |
| AI Rescue Pack (Universal) | Git Undo | `git checkout -- .` |
| AI Rescue Pack (Universal) | Nuke Untracked | `git clean -fd` |
| AI Rescue Pack (Universal) | Diff Context | `git diff \| clip` |
| Python / Backend Developer | Run Pytest | `pytest -v` |
| Python / Backend Developer | Lint & Fix | `black . && ruff check --fix .` |
| Python / Backend Developer | Freeze Deps | `pip freeze > requirements.txt` |
| Web Dev (Node/Ecosystem) | Dev Server | `npm run dev` |
| Web Dev (Node/Ecosystem) | Quick Test | `npm test` |
| Web Dev (Node/Ecosystem) | Nuke Modules | `rm -rf node_modules package-lock.json && npm install` |

Catalog review should distinguish inspection from destructive recovery:
Git Undo discards tracked working-tree edits in its path scope; Nuke Untracked
deletes untracked files/directories; both can remove work unrelated to an AI.
Offer an untracked-file preview (`git clean -nd`) as another candidate.
Diff Context copies the unstaged tracked diff and uses Windows' `clip`; it does
not include all possible repository changes. Freeze Deps overwrites its output
file, while Nuke Modules removes the lockfile as well as installed modules.
Consider a separate lockfile-preserving reinstall option rather than presenting
lockfile deletion as routine maintenance.

Other bundle ideas to curate later: Git inspection, Docker/Compose,
.NET, Rust/Cargo, and project diagnostics. Catalog size is open; prioritize useful,
documented sets over filling the picker with near-duplicates.

Acceptance: previews match the saved commands exactly; append/replace,
individual selection and cancellation work predictably; applying any bundle
sends no shell input. Applied buttons survive workspaces/export/import/recovery
and remain editable, with no changes to running shells. Cover duplicate review,
long labels, wrapped rows and commands whose required tools are unavailable.

## Per-button command confirmation

Queued at the owner's request. Add a **Confirm before using** toggle to each
button's definition in Configure tab, available for manually authored buttons
as well as applied presets.

- Existing buttons migrate with confirmation off, preserving their behavior.
  Ordinary new buttons default to off; known destructive buttons in bundled
  presets enable it by default, visibly in the preset preview and editor.
- This is explicit, editable button metadata. Do not attempt to decide whether
  arbitrary shell commands are destructive through keyword detection.
- When enabled, clicking the command button opens a confirmation dialog showing
  its label, exact command (including multiline content), and target tab.
  Make **Cancel** the default; **Run command** explicitly accepts execution.
- Confirm before sending any part of the command, including a first character,
  newline or queued startup submission. Cancel or closing the dialog sends no
  input. Acceptance submits the reviewed command once to the reviewed tab;
  do not silently redirect it if selection changes.
- If command templates are added, show the resolved command after value entry
  and before execution. Avoid duplicate confirmation prompts for one invocation.
- Stage toggle edits until Configure tab is saved. Cancel or a failed save
  leaves the saved definition and running shell unchanged.
- Preserve the flag with buttons through reordering, saved workspaces, settings
  export/import and recovery. Applying presets or restoring settings never runs
  commands or opens execution-confirmation dialogs.
- Keep normal terminal typing and clipboard behavior unchanged. Confirmation
  covers this button's invocation, not commands typed directly into the shell.

Acceptance: unchecked buttons retain existing execution behavior; enabled
buttons require explicit acceptance. Test Cancel, dialog close, default action,
target-tab binding, exactly-once execution, multiline command previews, saved
flag round trips and legacy defaults. Neither previews nor diagnostics should
introduce command-content logging.

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
