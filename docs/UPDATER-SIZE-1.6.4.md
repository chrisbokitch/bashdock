# Independent updater optimization — 1.6.4

The updater no longer reaches Qt rendering through settings validation. Icon
definitions and assignment live in GUI-free `tab_icon_catalog.py`; settings
imports that catalog directly. `tab_icons.py` retains the existing UI API and
Qt renderer. No main-application DLLs, locale packs or resources were excluded.

PyInstaller analyzes imports inside functions, including the updater's optional
acceptance mode. Merely making the renderer's imports lazy was insufficient:
`update_helper → update_acceptance → config → tab_icons` still collected Qt.
No blanket PyInstaller exclusions were used to conceal that dependency.

## Candidate and baseline

- Windows build source: `5d8b4b257b01fca1793e877006797b8de0ca81fc`.
- CI: <https://github.com/chrisbokitch/bashdock/actions/runs/40779113557>.
- Published comparison: checksum-verified 1.6.0 ZIP, described in
  [the measurement baseline](PACKAGE-SIZE-1.6.0.md).
- Baseline updater: 47,719,191 bytes as an EXE, 45.17 MiB inside the ZIP,
  including 140 packed Qt/PySide entries occupying 31.49 MiB inside the EXE.
- Dependency pins, updater trust/signature policy, install/rollback transaction
  and startup health protocol are unchanged. The helper keeps its own Python
  and TLS runtime, independent of the installation being replaced.

## Measured result

| Measurement | Published 1.6.0 | CI 1.6.4 |
| --- | ---: | ---: |
| Updater EXE | 45.51 MiB | 11.01 MiB |
| Updater contribution to ZIP | 45.17 MiB | 10.82 MiB |
| Full application download | 267.61 MiB | 233.29 MiB |
| Installed file contents | 620.58 MiB | 586.10 MiB |
| Updater Qt/PySide CArchive entries | 140 | 0 |

The download is **34.33 MiB smaller (12.8%)**.
The updater's ZIP contribution is **76.1% smaller**.
All 2,929 outer file paths remain present. Qt/WebEngine resource, library, QML
and translation groups retain their baseline sizes/counts; only the updater and
main app EXE have different installed byte lengths. The main EXE is 27,039 bytes
larger, reflecting intervening app changes as well as this refactor. These are
actual package comparisons, not a claim that the two source revisions differ
only in the helper.

Exact candidate measurements from CI's `windows-build-diagnostics` artifact:

- ZIP: `bashdock-1.6.4-windows-x64.zip`, **244,617,312 bytes**.
- ZIP SHA-256: `7bff59a9c94ee065a0fa8a94f1a80a7bfded9542f7d4b5a24c12d8ef3646324b`.
- Installed file contents: **614,574,925 bytes**.
- Updater: **11,544,279 bytes**; compressed ZIP entry **11,343,063 bytes**.
- Updater SHA-256: `745f8e9c522008488347f12f145e53ced78baf8dbe256db83cee61047f8a939c`.
- Embedded updater entries: 87; Python modules: 429;
  Qt/PySide/shiboken entries across both native and Python archives: zero.

The complete per-file and component inventory is `build/package-size.json`;
helper inspection/self-test results are `build/updater-size.json`. CI logs also
print the size table. The report uses MiB (1,048,576 bytes) and distinguishes
ZIP contribution from raw EXE size. This candidate is a development CI artifact,
not a newly published public release.

## Validation

- Local suite: 271 Python tests, with 26 Windows-only skips, and 17 JavaScript
  tests passed.
- All four Windows compatibility jobs passed:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40779113489>.
- The first full Windows attempt stopped at the previously observed M4 prompt
  timeout after Ctrl+C (`test_m4_history_editing_completion_interrupt_and_unicode`).
  Its updater/dependency tests passed. One controlled retry of the unchanged
  commit passed the full suite, followed by the native terminal/UI checks.
  The failure is retained as evidence; no test assertion was relaxed or skipped.
- The source import-graph test follows imports inside functions and package
  initializers across every updater mode. Actual frozen validation inspects
  both the CArchive contents and the embedded Python module archive for Qt,
  PySide6 and shiboken6; the old public helper is correctly rejected.
- The packaged self-test now also exercises settings defaults/validation, in
  addition to the embedded key, native TLS configuration and Windows status
  window, while running outside the app folder.

- The retry's complete Windows build/package job `123138784560` passed. The
  actual frozen helper has zero Qt entries and passed its independent self-test.
- Compiled app startup confirmation passed for public and local update caches,
  both from the build directory and the extracted portable ZIP. ZIP checksum,
  packaging/source/license checks and extracted-executable shell checks passed.
- The existing install/rollback and local-update transaction tests passed; their
  assertions were unchanged. No new manual end-to-end installed update/rollback
  pass is claimed.
