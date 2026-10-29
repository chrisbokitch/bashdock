# BashDock 1.12.1 release record

Status: release preparation. No tag, draft assets, checksum, signature verification
or public publication is claimed by this record yet.

## Scope since public 1.6.8

- 96 original generic tab icons and live icon-picker filtering.
- Tab and command-button context menus, fresh-shell tab duplication,
  middle-click tab closing, and reliable Explorer folder dispatch.
- Optional per-button timing, disabled by default, with footer elapsed time and
  exit status, quiet execution, interruption handling and multiline prompt restoration.
- Temporary per-tab font zoom with increase/decrease/reset shortcuts.
- Live per-tab scrollback search with match navigation, Unicode/wrapped text,
  current alternate-screen search and terminal focus restoration.
- Read-only Help → Keyboard shortcuts reference and Help menu grouping polish.

The signed updater format, production signing key, Python/Qt dependency pins,
settings schema and portable installation layout are unchanged. The local
terminal page additionally bundles the MIT-licensed xterm search add-on 0.15.0;
its copyright/license is included and attribution is updated.

## Validation already completed

- Application changes through `b2ece30f3ec4649f5095ae27625096fa7f601082`.
- Local `npm test`: 324 Python tests, 32 Windows-only skips; 22 JavaScript tests pass.
- Owner confirmed the latest local tests pass and requested a public release.
- Owner interaction checks confirmed the new icons/context menus, timing,
  font zoom, prompt restoration and scrollback search during development.
- The main revision's Windows input compatibility run passed all four Git/Python
  jobs: <https://github.com/chrisbokitch/bashdock/actions/runs/40940815302>.
- Its full Windows build/package run passed tests, scaling checks, compilation,
  package creation, update-startup checks and all extracted rendering probes,
  then failed removing a temporary extracted folder because an orphaned
  OpenConsole process retained a file lock. This is not a successful package
  verification result. The failed job was retried. The release-preparation commit supersedes that
  retry with a fresh package build, which must pass before tagging. Original run:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40940815377>.

## Remaining release checks

Use the focused UI-release procedure in RELEASING.md. The previously completed
1.0 acceptance matrix remains historical evidence; do not repeat that entire
matrix for this candidate unless a new failure warrants broader testing.

1. Obtain a successful Windows build/package check for the release source.
2. Tag the prepared, tested source as v1.12.1. Let the tagged workflow build,
   validate, sign update metadata and attach the complete asset set to a draft.
3. Record the exact source/tag, tagged run, ZIP size and SHA-256.
4. Owner checks the downloaded draft ZIP: checksum; launch/version; typed and
   button commands; icon/context menus; timing footer and normal prompt; zoom;
   live search/navigation/Escape; Help reference; close/reopen.
5. Independently verify the draft manifest/signature with the embedded public
   key, and check all required binary/source/checksum/provenance assets.
6. Publish after exact-draft acceptance. Check public asset access, updater
   discovery and website download links; record final evidence here.

Development preview/staged-install checks are not acceptance of the exact draft ZIP.
