# Build on Windows with npm run compile. Qt's WebEngine hooks collect its helper
# executable, plugins, and resources. Application HTML/JS/CSS is included below.
from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "scripts" / "launch_app.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "gitbasher" / "assets"), "gitbasher/assets")],
    hiddenimports=[],
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
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="gitbasher")
