# Windows package size baseline — BashDock 1.6.0

Measured on 2026-10-28. Measurement only: no runtime files removed and no build exclusions changed.

## Package identity

- Published archive: `bashdock-1.6.0-windows-x64.zip`.
- Release: <https://github.com/chrisbokitch/bashdock/releases/tag/v1.6.0>.
- SHA-256 verified after downloading the complete archive: `2ac51716cdb391794169519d111a1d6e8b5a0da9ffa0bbdd0b0986851c6dab13`.
- Build source: `a686d06ea1eb51ae2b80d90506cf85acb931246a`; version `1.6.0`.
- Download: **267.61 MiB** (280,610,070 bytes).
- Installed file contents: **620.58 MiB** (650,722,798 bytes), **2,929 files**.
- Installed bytes exclude filesystem allocation/slack and generated settings/cache files.
- This is the current public release baseline, not a measurement of the later 1.6.2 development ZIP.

## Download contributions

Compressed sizes come directly from ZIP central-directory entries. Groups are disjoint; packed contents inside the updater and license ZIP are counted only in their containing file here. MiB means 1,048,576 bytes.

| Component | Compressed MiB | Installed MiB | Files |
| --- | ---: | ---: | ---: |
| WebEngine libraries and helper | 79.60 | 195.32 | 7 |
| Other Qt / PySide runtime | 58.45 | 151.66 | 172 |
| Independent updater | 45.17 | 45.51 | 1 |
| WebEngine debug resource packs | 17.35 | 82.31 | 5 |
| Qt / WebEngine translations | 12.73 | 49.29 | 210 |
| Python and other runtime dependencies | 11.97 | 34.13 | 88 |
| License notices | 11.89 | 12.39 | 17 |
| WebEngine release developer-tools resources | 10.50 | 10.51 | 1 |
| QML files and plugins | 7.95 | 21.57 | 2,401 |
| Other WebEngine resources | 6.97 | 13.10 | 5 |
| Application executable, assets and metadata | 4.37 | 4.79 | 22 |
| ZIP headers, directory and other overhead | 0.67 | — | — |

## Largest individual entries

| File (relative to bashdock/) | Compressed MiB | Installed MiB |
| --- | ---: | ---: |
| `_internal/PySide6/Qt6WebEngineCore.dll` | 78.71 | 192.97 |
| `bashdock-updater.exe` | 45.17 | 45.51 |
| `_internal/PySide6/resources/qtwebengine_devtools_resources.debug.pak` | 14.62 | 77.80 |
| `third-party-licenses.zip` | 11.74 | 11.74 |
| `_internal/PySide6/resources/qtwebengine_devtools_resources.pak` | 10.50 | 10.51 |
| `_internal/PySide6/opengl32sw.dll` | 7.32 | 19.68 |
| `_internal/PySide6/resources/icudtl.dat` | 4.38 | 9.98 |
| `_internal/PySide6/Qt6Gui.dll` | 4.05 | 9.07 |
| `bashdock.exe` | 4.01 | 4.14 |
| `_internal/PySide6/Qt6Core.dll` | 3.46 | 9.78 |
| `_internal/PySide6/Qt6Widgets.dll` | 2.85 | 6.27 |
| `_internal/PySide6/Qt6Quick.dll` | 2.74 | 6.21 |
| `_internal/PySide6/Qt6Pdf.dll` | 2.72 | 5.26 |
| `_internal/python312.dll` | 2.45 | 6.62 |
| `_internal/PySide6/Qt6Quick3DRuntimeRender.dll` | 2.25 | 4.27 |
| `_internal/PySide6/QtOpenGL.pyd` | 2.13 | 8.36 |
| `_internal/libcrypto-3-x64.dll` | 2.09 | 6.62 |
| `_internal/PySide6/resources/qtwebengine_resources.pak` | 2.07 | 2.11 |
| `_internal/PySide6/resources/qtwebengine_resources.debug.pak` | 2.07 | 2.11 |
| `_internal/PySide6/Qt6Qml.dll` | 2.05 | 5.10 |

## Independent updater inspection

The updater executable was read as a PyInstaller CArchive using PyInstaller 6.22.3. It was not executed. Its outer ZIP contribution is 45.17 MiB; inside it:

- **140 Qt/PySide entries** occupy **31.49 MiB packed**, 81.16 MiB unpacked.
- Includes Qt Gui/Core/Quick/QML/PDF libraries, platform plugins, and software OpenGL.
- **223 embedded entries** are byte-identical (SHA-256 compared) to files in the main installation: 41.48 MiB packed inside the updater, 108.73 MiB unpacked.
- Duplication alone does not make these entries removable. The helper intentionally carries its own Python/TLS runtime so folder replacement cannot break it.
- `update_status.py` uses ctypes/Windows APIs. Source inspection suggests GUI dependencies can enter through shared config/icon imports (including imports inside functions that PyInstaller analyzes). This is a candidate import-boundary investigation, not a validated lean-helper build.
- Packed inner bytes are not additive to the outer ZIP table and are not a promise of equal ZIP savings after rebuilding.

## Follow-up experiments, in suggested order

1. **Isolate the updater from GUI imports.** Investigate its 31.49 MiB of packed Qt/PySide payload while preserving independent Python/TLS support, the status window, install/rollback, startup health, local staging and acceptance modes.
2. **Debug WebEngine resource packs: 17.35 MiB compressed.** Five `.debug.pak` / `.debug.bin` entries are present. Validate release-mode resource loading before excluding them.
3. **QML inventory: 7.95 MiB compressed, 2,401 files.** Audit which QML files/plugins and related libraries are actually needed. Widgets-based application UI alone does not prove WebEngine has no Qt Quick/QML dependencies.
4. **Translations: 12.73 MiB compressed, 210 files.** Measure the tradeoff of retaining a smaller locale set; test fallback on different Windows language settings before deciding.
5. **Release developer-tools resources: 10.50 MiB compressed.** Investigate separately from debug packs; removing them needs validation of WebEngine startup and any developer-tools use.

These are candidate budgets, not validated removable totals. Related DLL/resource requirements may overlap. Do not sum them into a guaranteed saving. Retain current licenses, notices and source access. No files have been deleted from any installation.

## Reproduce or compare a future ZIP

From the checkout in Git Bash on Windows:

```bash
.venv/Scripts/python.exe scripts/measure_package.py "release/bashdock-1.6.0-windows-x64.zip" --json size-report.json --csv size-files.csv
```

The script uses only the Python standard library, hashes the archive, reads ZIP metadata without extracting/executing the application, prints component totals, and optionally writes exact byte counts and a complete per-file CSV/JSON inventory. Point it at a new candidate ZIP to compare changes. Inner updater inspection above was a separate read-only analysis.
