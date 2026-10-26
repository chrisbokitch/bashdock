# Independent helper with bundled native TLS support; no files loaded from the app being replaced.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'scripts/launch_updater.py')], pathex=[str(root)],
             binaries=[], datas=[(str(root / 'bashdock/assets/update-key.json'), 'bashdock/assets')],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='bashdock-updater',
          debug=False, strip=False, upx=False, console=False)
