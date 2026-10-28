# Build on Windows with npm run compile. Qt's WebEngine hooks collect its helper
# executable, plugins, and resources. Application HTML/JS/CSS is included below.
from pathlib import Path
import json
import sys
from PyInstaller.utils.hooks import get_package_paths
from PyInstaller.utils.hooks.qt import pyside6_library_info

root = Path(SPECPATH)
sys.path.insert(0, str(root))
from bashdock.webengine_resources import select_release_resources
# These are loaded/launched by native code, so Python import analysis misses them.
_, winpty_package = get_package_paths("winpty")
winpty_native = [(str(p), "winpty") for p in Path(winpty_package).iterdir()
                 if p.suffix.lower() in (".dll", ".exe")]
for required in ("conpty.dll", "OpenConsole.exe"):
    if not (Path(winpty_package) / required).is_file():
        raise RuntimeError(f"pywinpty is missing {required}. Reinstall pywinpty>=3.0.5.")

a = Analysis(
    [str(root / "scripts" / "launch_app.py")],
    pathex=[str(root)],
    binaries=winpty_native,
    datas=[(str(root / "bashdock" / "assets"), "bashdock/assets")],
    hiddenimports=["winpty._winpty", "winpty.ptyprocess", "winpty.enums"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
_, removed = select_release_resources([*a.datas, *a.binaries],
                                       debug_build=pyside6_library_info.is_debug_build)
removed_names = {entry[0] for entry in removed}
a.datas = [entry for entry in a.datas if entry[0] not in removed_names]
a.binaries = [entry for entry in a.binaries if entry[0] not in removed_names]
resource_report = dict(qt_version=pyside6_library_info.version, debug_build=False,
                      removed=[dict(path=e[0], bytes=Path(e[1]).stat().st_size) for e in removed])
(root / 'build').mkdir(exist_ok=True)
(root / 'build/webengine-resource-selection.json').write_text(
    json.dumps(resource_report, indent=2)+'\n', encoding='utf-8')
print('Release WebEngine resource selection: ' + json.dumps(resource_report), flush=True)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bashdock",
    icon=str(root / "bashdock" / "assets" / "bashdock.ico"),
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="bashdock")
