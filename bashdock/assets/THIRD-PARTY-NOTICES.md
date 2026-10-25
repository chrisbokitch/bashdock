# Third-party software in BashDock

BashDock's original code is GPL-3.0-only. That license does not replace the
licenses or copyright notices of the components below. Third-party material
keeps its upstream terms. The release's `licenses/` directory contains full
texts and attribution files; `licenses/manifest.json` records the actual
build environment and source archive checksums.

| Component | Release baseline | License / notice location |
| --- | --- | --- |
| xterm.js and addon-fit | 5.5.0 and 0.10.0 | MIT; `bashdock/assets/LICENSE` in source, `licenses/xterm/LICENSE` in release |
| PySide6 and shiboken6 | 6.10.3 | LGPLv3 / GPL alternatives; open-source terms and third-party notices collected from matching PySide source |
| Qt libraries and plugins | 6.10.3 | LGPLv3 / GPL alternatives and component-specific terms; matching Qt source license and attribution files |
| Qt WebEngine / Chromium | Qt 6.10.3 | Qt open-source terms plus Chromium's many component licenses, including BSD, MIT, Apache, and LGPL; matching Qt source notices, README.chromium files, and attribution metadata |
| Mesa llvmpipe software renderer / LLVM | Mesa 11.2.2 / LLVM 3.6.2 identified in pinned Qt wheel | MIT, Boost 1.0, and University of Illinois/NCSA terms; `licenses/Mesa-11.2.2-license.html`, `Boost-1.0.txt`, and `LLVM-3.6.2.txt` |
| Microsoft Visual C++ runtime DLLs | Actual frozen-file inventory | Microsoft proprietary redistributable terms; see publisher requirements below |
| CPython and bundled standard-library components | Actual build version | PSF and incorporated component licenses; `licenses/CPython/LICENSE.txt` |
| pywinpty | 3.0.5 | MIT; wheel and source notices |
| Rust libraries incorporated into pywinpty | Its source Cargo.lock | Per-crate MIT, Apache, BSD, Unicode, and other terms; full crate sources and collected notices |
| Microsoft ConPTY / OpenConsole | 1.24.260512001 in pinned pywinpty x64 wheel | MIT; `licenses/Microsoft-Terminal-MIT.txt` and `Microsoft-Terminal-NOTICE.txt` |
| Legacy winpty DLL / agent in pywinpty | Upstream winpty | MIT; `licenses/winpty-MIT.txt` |
| MinGW / GCC runtime in legacy winpty binaries | GCC 5.3.0 (MSYS2 Rev5) | MinGW permissive terms and GCC GPL with Runtime Library Exception; `licenses/mingw-w64-COPYING.txt` and `GCC-Runtime-Exception.txt` |
| PyInstaller bootloader | 6.16.0 | GPL with its bootloader exception; `licenses/python-packages/pyinstaller/` |
| Build tools and any collected Python packages | Actual build versions | Their own license files, including vendored notices, under `licenses/python-packages/` |

The Qt and PySide commercial-license texts may also appear in upstream archives.
BashDock uses the open-source options, not a commercial Qt license. Some Qt
modules have GPL-only options. BashDock's GPLv3 application license permits
compatible GPLv3 components; this is not a claim that every file in the full Qt
source archive is LGPL licensed.

The notice collection intentionally includes optional/unshipped source
components and build tools. Their presence in this collection does not mean
those components are loaded by BashDock. Exact frozen-file hashes and dependency
versions are recorded in the release inventory and build information.

## Source and modification rights

Each release provides the matching BashDock source ZIP and separate, unmodified
Qt, PySide, pywinpty, and locked Rust crate source archives beside its executable
ZIP. See `SOURCE.txt` and the release asset checksums. Source includes copyright
and attribution notices that are not duplicated into the application UI.

BashDock uses dynamically loaded Qt/PySide libraries in an onedir distribution.
Recipients may modify/rebuild the application and replace those libraries under
the applicable licenses. No license key or signature check prevents this.
Reverse engineering for debugging modifications to LGPL components is not
restricted. Source and build instructions are supplied so a replacement build
can be made when binary/ABI compatibility prevents replacing an individual DLL.

Git for Windows is a separately installed prerequisite. BashDock neither bundles
nor relicenses Git, Bash, or Git for Windows. Windows system libraries retain
their own terms. The CPython license contains its incorporated-library notices;
Microsoft runtime files, when present, retain Microsoft's terms.

## Upstream references

- <https://github.com/xtermjs/xterm.js>
- <https://doc.qt.io/qt-6.10/licensing.html>
- <https://doc.qt.io/qt-6.10/qtwebengine-licensing.html>
- <https://doc.qt.io/qtforpython-6/licenses.html>
- <https://www.python.org/psf/license/>
- <https://github.com/andfoy/pywinpty/tree/v3.0.5>
- <https://github.com/andfoy/winpty-rs/tree/v1.0.6>
- <https://www.nuget.org/packages/Microsoft.Windows.Console.ConPTY/1.24.260512001>
- <https://github.com/microsoft/terminal>
- <https://github.com/rprichard/winpty>
- <https://pyinstaller.org/en/v6.16.0/license.html>


## Microsoft runtime redistribution

The pinned Qt Windows wheel includes Microsoft Visual C++ runtime DLLs, and
CPython/PyInstaller may collect additional Microsoft runtime files. They are
not licensed under BashDock's GPL or Qt's open-source licenses. Microsoft states
that distribution of the runtime redistributable package and individual
binaries is limited to licensed Visual Studio users and subject to its license
terms. The publisher must confirm the necessary entitlement before public
distribution; copying this notice does not grant that entitlement. See:
<https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files>.

The Mesa software renderer was identified from version strings in the actual
pinned Windows DLL; its SHA-256 is recorded in `requirements/native-runtime.json`.
Mesa and LLVM retain their own notices, including applicable Boost terms.
