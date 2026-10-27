# BashDock 1.0 acceptance status

Reconciled through **0.14.6**. This is the current status record for
[issue #2](https://github.com/chrisbokitch/bashdock/issues/2).
[RELEASING.md](RELEASING.md#validate-the-draft-before-publishing) and
[AUTO-UPDATES.md](AUTO-UPDATES.md#required-windows-vm-validation) remain the
reusable test procedures.

**Passed** below means the named scope has recorded evidence. **Outstanding**
means the specific manual check has no recorded result; it does not mean it
failed. Automated coverage is identified separately and does not count as
manual testing of a compiled ZIP. Historical passes remain valid for their
tested versions; the eventual 1.0 candidate still needs its own exact-package
smoke check and any retests warranted by changes.

## Evidence already recorded

| ID | Completed scope | Evidence and limits |
| --- | --- | --- |
| E1 | Public signing configuration, tag build, signed draft assets and stable publication | [Closed release milestone #1](https://github.com/chrisbokitch/bashdock/issues/1). Published 0.11.11/0.11.12 assets and real updates demonstrate working signing configuration; secure private-key backup is a separate unrecorded confirmation. |
| E2 | Exact-ZIP checksum, VM launch, typing/buttons, restored tabs/folders/buttons/settings/geometry, About/notices and close/reopen smoke | Owner-reported 0.11.11 and 0.11.12 checks in #1. These focused smoke results do not certify every workspace, clipboard, recovery or scaling case. |
| E3 | Real public updates 0.11.4 → 0.11.11 → 0.11.12, restart cancellation and fresh-shell restoration | Owner reports in #1. The second-instance wait completed without forcibly closing unrelated processes, using the older helper. The later visible waiting guidance remains outstanding (U1). |
| E4 | Compiled-helper tamper rejection and OS launch-failure rollback | The VM report recorded in #1 passed altered manifest, altered signature, changed ZIP, truncated ZIP, deliberate Windows launch failure with prior files/settings restored, and restored real-app version/token acknowledgment. It did not test every post-launch crash/hang or normal running-app handoff. |
| E5 | Microsoft runtime publisher confirmation and inventory review | Owner's Visual Studio Community installation/accepted terms and packaged-runtime provenance review recorded in #1. Do not reopen this as unconfirmed for the unchanged release dependencies. Reassess relevant dependency/runtime changes. |
| E6 | Public download, install/help, source/license links and screenshots | Live website verification recorded in #1; the website advertises the published 0.11.12 pre-1.0 release. Every future candidate still needs its own asset/link checks. |
| E7 | Local staged-update normal restart after the receipt-path fix | Owner confirmed the 0.14.2 fix in project chat and continued the stage-update workflow. This does not record all local-channel cancellation/offer cases (U7). |
| E8 | Button-command first-character loss resolved in the owner's environment | Owner supplied Git 2.55.0.windows.4, Bash 5.3.15 and MSYS 3.6.9-b4195d69; after the 0.14.6 input guard, owner explicitly replied “Confirmed fixed.” This is a button-command result, not a claim that all upstream terminal input issues are fixed. |

## Automated evidence

The tested 0.14.6 revision is
[`a9c32011c3cd10565f70772061a5d58b4567ea22`](https://github.com/chrisbokitch/bashdock/commit/a9c32011c3cd10565f70772061a5d58b4567ea22).

- [Windows build and release](https://github.com/chrisbokitch/bashdock/actions/runs/40449076351)
  passed tests, compilation, packaged/extracted executable checks and packaging.
- [Windows input compatibility](https://github.com/chrisbokitch/bashdock/actions/runs/40449076413)
  passed 216 button executions across Git 2.55.0.windows.4 and runner Git,
  Python 3.12/3.14, three fresh test runs per combination, using native Windows Qt.
- Workspace/config tests cover tab persistence, workspaces, defaults/overrides,
  export/import/recovery, missing-Git guidance and cancellation/save failures.
  These use fake terminal processes; see
  [test_workspace.py](../tests/test_workspace.py) and
  [test_config.py](../tests/test_config.py).
- Real Windows ConPTY/WebEngine tests cover shell input, directory/state,
  resizing, button routing/focus and scrolling:
  [test_windows.py](../tests/test_windows.py).
  The restored-first-tab footer regression also passes Qt tests at
  100%/125%/150% scale. This does not establish manual Windows display-DPI acceptance.
- Update tests cover discovery/version filtering, exact downloads, signatures,
  archives, rollback, cancellation/save/helper-launch failures, local target
  binding/enrollment/revocation and startup receipts. See
  [test_updates.py](../tests/test_updates.py),
  [test_update_acceptance.py](../tests/test_update_acceptance.py),
  [test_local_updates.py](../tests/test_local_updates.py),
  [test_local_update_controller.py](../tests/test_local_update_controller.py),
  [test_update_health.py](../tests/test_update_health.py), and the update-related
  cases in test_workspace.py.
- Compiled GUI startup receipts are tested for public and scoped-local update
  paths, including the extracted ZIP. An extraction/startup check in a path
  containing spaces is not evidence of a complete GUI update between spaced paths.

## Completed M2: tab operations and footer

The real Qt UI tests in [test_workspace.py](../tests/test_workspace.py) use
isolated settings and fake terminal processes:

- `test_new_tab_button_creates_independent_profile_in_active_directory_and_autosaves`:
  the actual New Tab button creates/selects an independent tab, inherits the
  active directory, leaves the original shell alone, and saves through the timer.
- `test_tab_rename_dialog_accept_cancel_and_blank_preserve_saved_identity`:
  double-click opens the real rename dialog; accepting trims the name, cancelling
  and blank input preserve it, and saved tab identity/settings remain intact.
- `test_reordered_tab_close_button_cancels_then_closes_its_own_shell_and_autosaves`:
  Qt's `moveTab` operation saves order/selection; an inactive moved tab's actual
  close control cancels without changes, then closes only its own shell and saves.
- Existing tests verify saved names/order/folders/buttons and active-tab restoration,
  close-icon positioning through tab switches, cancelled-rename drag state,
  and full button height/vertical viewport containment after reopening on tab two,
  selecting tab one, and repeatedly resizing with normal and long button labels.

These tests run under `npm test`. The Windows workflow also runs tab-related
tests with the native Qt Windows backend at scale factors 1, 1.25 and 1.5.
Simulated scaling does not replace M9's actual display-setting check. The
reorder test exercises Qt's move operation, not a physical mouse drag; fake
shells also do not certify the packaged WebEngine composition.

**Passed — owner confirmation, 2026-10-27**, following the requested installed
0.14.6 checks. Both manual scenarios below passed; combined with the automated
coverage above, M2 is complete. No separate package checksum or display-scaling
matrix was supplied for this confirmation.

The exercised manual scope was:

1. With two or more tabs, **drag a tab** to another position, switch tabs and
   click the moved tab's close control. Check that the intended tab closes and
   the controls look aligned and are easy to click.
2. Leave a nonfirst tab selected, close/reopen BashDock, then select the first tab.
   Narrow and widen the window and visually check the command-button row for
   cropping, overlap or a gap. Existing horizontal overflow remains expected;
   wrapping buttons and customizable tab icons are future features, not M2 gates.

No separate manual create/rename/cancel/persistence matrix is required for M2.
The owner confirmed both checks passed. M9's actual Windows display-scaling
checks remain separate.

## Completed M3: saved workspace workflows

Existing [workspace tests](../tests/test_workspace.py) cover selected-tab order
and active-tab mapping, add versus replace/cancel, preservation of unrelated
shells/global settings, backup before replacement, overlapping identities,
independent saved/live copies, update/rename/delete, menu routing, and
export/import/recovery. [Config tests](../tests/test_config.py) cover saved
library validation, migration and round trips.

Additional M3 regressions exercise:

- `test_m3_workspace_picker_validates_then_saves_subset_through_real_dialog_and_cancel_is_inert`:
  the real modal picker rejects a blank name/empty selection, saves the selected
  subset through its Save control, and cancels without modifying disk or shells.
- `test_m3_workspace_manager_cancel_invalid_names_and_write_failures_keep_library_and_shells`:
  cancelled update/delete/rename, invalid or duplicate names, and failed writes
  preserve the library, saved file, manager list and live shells.
- `test_m3_workspace_ssh_buttons_never_run_on_add_replace_import_or_reopen`:
  saved SSH commands remain idle through all four routes, edits do not mutate
  the saved copy, and only an explicit button click submits a command. This uses
  fake processes and never makes an SSH connection.
- `test_saved_workspace_buttons_require_click_after_add_replace_and_reopen`
  in [test_windows.py](../tests/test_windows.py): real Git Bash/WebEngine startup
  reaches readiness without submitting a saved button; an explicit click writes
  a file receipt. This uses a harmless command, not a network connection.

`npm test` includes these cases, with the real-shell case requiring Windows.
The Windows workflow additionally runs the new dialogs and real-shell test
using the native Qt Windows backend. Source tests do not inspect the installed
package's visual presentation or certify an actual SSH session.

**Passed — owner confirmation, 2026-10-27**, following the requested installed
0.14.6 checks. Both manual scenarios below passed; combined with the automated
coverage above, M3 is complete. No separate package checksum was supplied for
this confirmation.

The exercised manual scope was:

1. In **Manage → Workspaces → Configure…**, save a small selection of tabs,
   including one with a saved SSH/Connect button. Check that the selection list,
   workspace details and action buttons are readable and usable. Close that
   saved tab, then open the workspace using its menu entry. Confirm the tab
   opens at a fresh shell prompt and **does not connect or run the SSH button**.
2. In the workspace manager, choose **Replace current tabs…** and cancel:
   current shells should remain usable. Then confirm replacement and check
   that the intended saved tabs appear as fresh shells, with the SSH button
   still idle and the dialog/menus behaving normally.

The owner confirmed both installed-app checks passed. No separate manual
update/rename/delete or export/import matrix is required for M3; M7 retains
its distinct settings/recovery manual scope.

## Outstanding manual Windows checks

Use a disposable VM/profile for destructive recovery and updater-failure cases.
Preserve E1–E8; do not rerun completed historical checks merely because an older
checklist left them unchecked. The IDs below identify the remaining scope.

| ID | Check to finish | Existing evidence / result still needed |
| --- | --- | --- |
| M1 | Clean-machine setup | Confirm compiled missing-Git guidance and detecting an installation after restart; run as a standard user without Python/Node. Missing-Git UI logic is automated; this complete manual setup result is unrecorded. |
| M2 | Packaged tab interaction and visual smoke | Automated cases cover creation, rename acceptance/cancellation/blank input, Qt reordering, closing/cancelling after reorder, autosave/restoration, close-icon geometry and restored-footer bounds through resizing. Only a short compiled-app smoke remains: drag a tab with the mouse, use its close control, and visually inspect the restored first-tab footer while narrowing/widening the window. See the scope below; do not repeat the complete functional matrix manually. |
| M3 | Packaged workspace dialog and fresh-shell smoke | Functional save/subset/add/replace/cancel, overlapping IDs, independent copies, library edits, persistence/export/import and no automatic button submission are automated. Remaining manual scope is the short installed-app dialog and fresh-shell check below, including a saved SSH button staying idle. No complete manual functional matrix is required. |
| M4 | Packaged terminal input and pager visual smoke | History/editing keys, completion, foreground Ctrl+C/recovery, Unicode transport/rendered text, real pager navigation/resize/exit and persistent directory/environment have automated Windows coverage. Remaining manual scope is native Unicode entry and a short installed-app pager/rendering check below. Basic typing/buttons and the clipping fix already passed (E2/E8). |
| M5 | Clipboard and optional mouse preferences | Selection/copy, paste, multiline confirmation/cancel, copy-on-select and right-click paste, including mouse-aware programs. JavaScript/Qt coverage is not a recorded manual clipboard result. |
| M6 | Terminal defaults and per-tab overrides | Inheritance, returning to defaults, cancel/save failure behavior, preservation through workspaces/settings, and applying appearance without restarting shells. Appearance restoration has focused owner evidence; this complete scenario is unrecorded. |
| M7 | Settings export/import and recovery | Restore an export and inspect the separate pre-import backup; cancel/invalid import must keep shells. In a disposable profile, verify damaged-settings recovery, damaged-file preservation, cancellation and starting fresh. Existing owner smoke checked settings restoration; these broader manual recovery cases are not recorded. |
| M8 | External shell and exit lifecycle | External shell opens in the expected folder and survives BashDock closing; verify quit confirmation/opt-out and embedded process cleanup. Automated UI/launch tests do not establish this full manual lifecycle result. |
| M9 | Actual Windows display scaling | Inspect resize/maximize, menus, footer/buttons, update notice and restored tabs at 100%, 125% and 150% Windows display scaling. Existing Qt scale-factor tests do not replace this check. |

### M4 automated coverage and remaining manual smoke

[test_windows.py](../tests/test_windows.py) adds real Qt/WebEngine/xterm/ConPTY
regressions, included in `npm test` on Windows and run separately with native
Windows Qt in CI:

- `test_m4_history_editing_completion_interrupt_and_unicode`: Qt key events
  exercise Up/Down history, Home/End/Right/Delete editing and unique filename
  completion. File receipts verify execution; Ctrl+C interrupts a foreground
  `sleep` and the next command succeeds. Unicode travels through xterm's input
  API and WebChannel into Bash, is verified as UTF-8 file content, then appears
  as a rendered terminal-buffer line. This Unicode path does not simulate a
  native keyboard layout or IME composition. The fixture uses standard Emacs
  Readline mode and an isolated history file/prompt.
- `test_m4_real_pager_navigation_resize_exit_preserves_shell_state`: real `less`
  enters the alternate screen, pages forward/back, survives a resize, accepts
  navigation and exits to the normal buffer. A subsequent file receipt verifies
  the same shell retains its exported variable and changed working directory.

Existing tests cover persistent shell environment/directory and reported
terminal size, application cwd reports, visible row bounds after resize,
button routing/focus, and startup/hidden-tab button input. Their automated
results do not inspect native font glyphs or the installed app's visual output.

For M4, only these installed-app checks remain; record the app version:

1. Enter a few non-ASCII characters using your normal Windows input method
   (for example accented text, or IME input if you use it), and run a harmless
   `printf`/`echo` command containing them. Check that entry and output look right
   with your configured font. Native composition and glyph appearance are the
   focus; no separate manual history/completion/Ctrl+C matrix is required.
2. Open a long text file in `less` (or use your usual Git pager), page through it,
   narrow/widen the window, and press `q`. Check for broken drawing, overlap or
   a damaged prompt; run a simple command afterward to confirm normal input.

Both checks remain outstanding until an owner result is recorded. Clipboard
behavior stays in M5; actual Windows display-scaling checks stay in M9.

## Outstanding updater checks

| ID | Check to finish | Existing evidence / result still needed |
| --- | --- | --- |
| U1 | Visible waiting guidance with the newer helper | During a normal signed update from 0.11.12 or later, leave another instance minimized/behind a window; verify visible instructions, progress after closing it, useful locked-file/timeout guidance, and no forced termination of unrelated processes. Older-helper waiting passed (E3); native status-window tests are automated. No dummy public release is needed. |
| U2 | Unwritable installation | Confirm useful failure/manual-install guidance with no elevation or forced closure. A compiled-app manual result is unrecorded. |
| U3 | Settings-save and helper-launch failures | Confirm restart failure leaves current shells usable and the ready notice available. Injected Qt tests pass; a reviewed disposable compiled-app procedure/result is still needed. |
| U4 | Version replay and recipient source access | Version filtering/replay rejection is automated. Record the remaining compiled-path replay check and anonymous access to all matching application/source assets for the chosen public candidate. Manifest/signature/ZIP tamper checks already passed E4; do not repeat those unchanged checks as if unperformed. |
| U5 | Download interruption and automation preferences | Interrupt a download and verify usable current installation/cleanup; verify download-disabled and all-checks-disabled behavior. Verify source preview makes no implicit update/install attempt. Automated coverage is separate from these unrecorded manual results. |
| U6 | Complete update with paths containing spaces | Compiled extraction/startup checks cover spaced paths; a complete normal GUI update in that installation path is unrecorded. |
| U7 | Remaining local stage-update UI checks | Stage, cancel restart and continue using shells, confirm restart, check About/restored configuration/second launch, verify the old offer is consumed and another staging command appears. Normal successful staging/restart is E7; cancellation and the complete offer lifecycle need explicit results. Trust binding/revocation/tamper cases have automated coverage. |

The normal public update and compiled rollback/tamper milestones are complete.
Do not reinterpret U1–U7 as requiring a second first-public-release exercise.
If code/dependencies change the tested behavior, record a targeted retest with
its reason.

## Publisher confirmation and final candidate

- [ ] P1: Confirm an existing secure backup of the production update signing key.
  Configuration/signing is proven by E1; backup is not recorded. Never attach
  the key, paste it into an issue/chat, or regenerate the live channel key for
  this checklist.
- [ ] F1: Resolve outstanding blockers and deliberately select 1.0.0 with the owner.
- [ ] F2: Record the exact candidate tag/commit/ZIP SHA-256 and run its final
  launch/shell/restoration/About/close-reopen smoke plus targeted change-based
  retests. Historical evidence is not a checksum or smoke result for a new ZIP.
- [ ] F3: Review notes and all application/source/checksum/update assets, verify
  recipient access, publish the approved release, and update public website links.

Optional package-size reduction and the post-1.0 feature roadmap are separate
work; neither is newly made a release gate by this reconciliation.

## Recording a result

For each outstanding ID, record pass/fail, exact scope, app version/commit,
ZIP SHA-256 when applicable, Windows build, Git/Bash/MSYS versions, display
scaling, installation path and whether the run used a standard account.
Attach relevant diagnostics without command/output secrets. Link the evidence
and close only that ID's exercised scope. A test failure remains open until
fixed and verified; an absent report stays outstanding, not failed.
