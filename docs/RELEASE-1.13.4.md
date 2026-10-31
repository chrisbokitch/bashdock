# BashDock 1.13.4 release record

Release preparation for the next public version after 1.12.1. This record does not claim a tagged build, owner acceptance or publication until those steps occur.

## Scope

- Personal command preset groups, import/export, and creation from current-tab buttons in the group manager.
- Optional descriptions on regular command buttons, preserved in presets and shown as hover help.
- Message-first command confirmation with optional scrollable script disclosure.
- Timing and confirmation indicators in the tab configuration list.
- Confirmation when closing the final tab; restoration of terminal focus after the Manage menu closes.

The updater protocol, signing key, dependency lock, portable installation layout and license/source packaging are unchanged. This is a focused UI and local settings release.

## Automated evidence

- Candidate before release-note preparation: `25e07417ee8c73934162ea10e68f922ec2cf6016`.
- Local `npm test` at that revision: 344 Python tests passed (32 Windows-only skipped), and 22 JavaScript tests passed.
- Windows build/package workflow run [41178557929](https://github.com/chrisbokitch/bashdock/actions/runs/41178557929) and four-job input compatibility run [41178557923](https://github.com/chrisbokitch/bashdock/actions/runs/41178557923) succeeded at that revision.
- The release-note/record commit must pass its own main Windows workflows before tagging. The tagged build must then pass and create a signed draft with the ZIP, checksum, build provenance, source archives and notices.

## Focused owner acceptance of exact draft ZIP

1. Download the draft Windows ZIP and `.sha256`; run `sha256sum -c bashdock-1.13.4-windows-x64.sha256` in their download folder.
2. Extract the ZIP and launch the executable. Check version 1.13.4, type a short shell command and run one command button.
3. Check a personal preset group's creation from current tab, description hover help, import/export, and the command confirmation disclosure. Confirm the last-tab close prompt, then reopen. These can be checked together on a disposable tab/group; inspect any imported commands before using them.

Before publication, verify signed metadata, exact draft asset/source inventory and hashes. After publication, check public downloads and update discovery, then update the website's versioned links. The complete 1.0 recovery matrix is outside this focused scope because updater and packaging behavior did not change.
