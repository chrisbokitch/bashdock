# Build on Windows with npm run compile. Qt's WebEngine hooks collect its helper
# executable, plugins, and resources. Application HTML/JS/CSS is included below.
from pathlib import Path
from PyInstaller.utils.hooks import get_package_paths

root = Path(SPECPATH)
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
    datas=[(str(root / "gitbasher" / "assets"), "gitbasher/assets")],
    hiddenimports=["winpty._winpty", "winpty.ptyprocess", "winpty.enums"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="gitbasher",
    icon=str(root / "gitbasher" / "assets" / "gitbasher.ico"),
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="gitbasher")
