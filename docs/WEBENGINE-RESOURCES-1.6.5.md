# Release WebEngine resources — 1.6.5

This change omits five debug-build resource files from the portable application.
It does not modify installed wheels, main Qt libraries, locales, QML files, the
release developer-tools pack or the release high-DPI packs.

## Why these files can be excluded

Qt 6.10.3's [build configuration](https://github.com/qt/qtwebengine/blob/v6.10.3/src/core/CMakeLists.txt)
defines `QT_USE_DEBUG_RESOURCES` for the Debug configuration. Its
[resource loader](https://github.com/qt/qtwebengine/blob/v6.10.3/src/core/web_engine_library_info.cpp)
selects the corresponding debug or release filenames, and its
[deployment support](https://github.com/qt/qtwebengine/blob/v6.10.3/src/core/api/Qt6WebEngineCoreDeploySupport.cmake)
lists separate resource sets. [Qt's deployment documentation](https://doc.qt.io/qt-6/qtwebengine-deploying.html)
also distinguishes debug/release V8 snapshots.

The pinned PyInstaller hook collects the whole resources directory. After
analysis, BashDock now requires `is_debug_build == False` and all six nonempty
release files, then removes only these exact resource entries from its build:

- `qtwebengine_devtools_resources.debug.pak`
- `qtwebengine_resources.debug.pak`
- `qtwebengine_resources_100p.debug.pak`
- `qtwebengine_resources_200p.debug.pak`
- `v8_context_snapshot.debug.bin`

Missing release counterparts, unknown build type, debug Qt, or unexpected debug
resource names stop packaging for review. The source files remain untouched.

## Candidate identity and measurements

- Source: `34dd0c18b6a596df3abf7542caa33934e5f5d73e`.
- Windows CI: <https://github.com/chrisbokitch/bashdock/actions/runs/40784034633>.
- Compatibility: <https://github.com/chrisbokitch/bashdock/actions/runs/40784034585>.
- Comparison: [1.6.4 updater optimization](UPDATER-SIZE-1.6.4.md), whose ZIP was
  244,617,312 bytes (233.29 MiB), containing 18,197,037 compressed bytes
  (17.35 MiB) / 86,304,333 installed bytes (82.31 MiB) in these five files.

| Measurement | 1.6.4 CI baseline | 1.6.5 CI candidate |
| --- | ---: | ---: |
| Application ZIP | 233.29 MiB | 215.94 MiB |
| Installed file contents | 586.10 MiB | 503.80 MiB |
| File count | 2,929 | 2,924 |
| Debug resource packs in ZIP | 5 | 0 |

Net download saving: **17.35 MiB** (18,191,846 bytes).
Net installed-content saving: **82.30 MiB**.
Exactly the five listed file paths were removed; no outer file paths were added.
The main EXE grew by 6,576 bytes for the rendering probe, while its generated
runtime inventory shrank by 862 bytes. Release resources, Qt DLLs, QML and
translation groups remain present. The independent updater still has zero Qt
entries and the same 11,544,279-byte EXE size as 1.6.4.

Compared with the original public 1.6.0 ZIP, the combined updater/resource
optimizations reduce the download from 267.61 to
**215.94 MiB**, a **19.3%** net reduction.

Candidate ZIP: `bashdock-1.6.5-windows-x64.zip`, **226,425,466 bytes**. SHA-256:
`8ae8d0ad630596a1097fe004d9b5df84f678d5bfe908f99b50aa3cf29d92b40a`. Installed file contents:
**528,276,306 bytes**. These identify the CI artifact from the source
commit above; this is not a newly published public release.

All eight actual frozen rendering reports passed: four from the compiled folder
and four from the extracted ZIP. Both Qt and WebEngine report version 6.10.3.

| Mode / requested scale | Built-folder DPR / colors | Extracted-ZIP DPR / colors |
| --- | ---: | ---: |
| default-1 | 1 / 1,565 | 1 / 1,663 |
| software-1 | 1 / 926 | 1 / 1,025 |
| software-1.25 | 1.25 / 872 | 1.25 / 955 |
| software-1.5 | 1.5 / 1,769 | 1.5 / 1,859 |

Each report also confirms the frozen application, all six release files, terminal
and shell readiness, the expected real-shell Unicode marker and a saved frame.
The complete Windows workflow passed on its first attempt, including package
integrity/source/license, independent-helper and startup-health checks.

## Validation scope

- Local suite: 277 Python tests, with 26 Windows-only skips, and 17 JavaScript
  tests passed. Tests cover precise selection, complete release counterparts,
  unknown/debug Qt, missing/empty resources, retained source files, isolated
  profiles, display-scale selection and termination of only owned probe processes.
- An additional Linux source-renderer probe passed with a simulated shell
  backend (not Windows ConPTY and not a frozen build). It validated the new
  probe's WebChannel/buffer/pixel capture path; this does not substitute for
  the candidate's packaged Windows checks.
- All four compatibility jobs and the full Windows/native UI suite passed.
- The candidate's new `--webengine-smoke-test` must validate resources inside
  its own frozen bundle, load the terminal page, submit a command through
  WebChannel to real Git Bash, observe ANSI/Unicode output in xterm, and capture
  a nonuniform rendered frame. JSON results include Qt/WebEngine versions,
  readiness, terminal dimensions, device-pixel ratio and color counts.
- `scripts/check_webengine.py` runs this in fresh profiles with default rendering
  at 100%, plus GPU-disabled rendering at 100%, 125% and 150%. The extracted ZIP
  repeats all four cases. Overrides that could point at external resources or
  helper executables are cleared. No sandbox-disabling flags are added; inherited disable overrides are cleared.
- Existing independent-updater, backend shell, source/license, ZIP integrity and
  public/local startup-health checks remain in place. No new manual full 1.0
  acceptance matrix is claimed.

Windows build diagnostics retain `webengine-resource-selection.json`,
`package-size.json`, `updater-size.json`, the rendering JSON reports and PNGs,
including the extracted-package checks. Default rendering on hosted Windows is
not a claim of testing every physical GPU/driver combination.
