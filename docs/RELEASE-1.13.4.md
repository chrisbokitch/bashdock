# BashDock 1.13.4 release record

Release preparation for the next public version after 1.12.1. The tagged draft and focused owner acceptance are complete; publication remains pending.

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
- Release-note commit `71bba8660221aa9ce89e71d85d5afa2c11246c29` exposed a receipt-file race in one Python 3.14 compatibility job: the test read a newly created file before Bash wrote its expected contents. The release-preparation follow-up waits for those contents.
- Final preparation commit `b74bb446859d9d1c22a33d8984bf171d85ce028d` passed Windows build/package run [41180364133](https://github.com/chrisbokitch/bashdock/actions/runs/41180364133) and all four input compatibility jobs in run [41180364134](https://github.com/chrisbokitch/bashdock/actions/runs/41180364134). Local `npm test` after the test fix passed.

## Focused owner acceptance of exact draft ZIP

1. Download the draft Windows ZIP and `.sha256`; run `sha256sum -c bashdock-1.13.4-windows-x64.sha256` in their download folder.
2. Extract the ZIP and launch the executable. Check version 1.13.4, type a short shell command and run one command button.
3. Check a personal preset group's creation from current tab, description hover help, import/export, and the command confirmation disclosure. Confirm the last-tab close prompt, then reopen. These can be checked together on a disposable tab/group; inspect any imported commands before using them.

Before publication, verify signed metadata, exact draft asset/source inventory and hashes. After publication, check public downloads and update discovery, then update the website's versioned links. The complete 1.0 recovery matrix is outside this focused scope because updater and packaging behavior did not change.

## Tagged draft and owner acceptance

- Annotated tag `v1.13.4` points to `b74bb446859d9d1c22a33d8984bf171d85ce028d`.
- Tagged workflow [41181061967](https://github.com/chrisbokitch/bashdock/actions/runs/41181061967) passed both the Windows build/package job and signing/draft job.
- Draft release ID 429791624 has all 12 expected binary, checksum, provenance, application/dependency source and signed-metadata assets. The Windows ZIP is 226,491,233 bytes, SHA-256 `01d72826990839d72dfeeedd5bf9a40f0bb53044fabe7fca31f5f4cafc7c6365`.
- The owner confirmed `sha256sum -c` passes for the exact draft ZIP and confirmed the requested app checks pass. No full 1.0 recovery matrix is claimed.
- The owner supplied the draft `bashdock-update.json` and `.sig`. Their SHA-256 digests, respectively `16a40308c9d885d91ffb85cefb1d7b4d4fa30ecf9b349e68a68b43481009f5d8` and `e6fb4f4eb76996731d4d6dfbc27eef0c0502b44e77275e43b85ab55e662466c7`, match the draft asset metadata.
- Independent RSA PKCS#1 v1.5 / SHA-256 verification passed with the 3072-bit production public key in the exact tagged source. The signed manifest identifies version 1.13.4, the GitHub release ZIP URL, and the same ZIP size and SHA-256 as the accepted draft.

Publication, anonymous public asset checks, update discovery and website version links are still pending.
