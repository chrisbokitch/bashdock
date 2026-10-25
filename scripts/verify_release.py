"""Check a release ZIP, then exercise its extracted executable in a fresh settings directory."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    version = json.loads((ROOT / "package.json").read_text())["version"]
    archive = ROOT / "release" / f"bashdock-{version}-windows-x64.zip"
    expected, filename = archive.with_suffix(".sha256").read_text().strip().split("  ", 1)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected or filename != archive.name:
        raise ValueError("Release ZIP checksum does not match.")
    import zipfile
    with tempfile.TemporaryDirectory(prefix="BashDock release test ") as folder:
        root = Path(folder)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(root)
        executable = root / "bashdock/bashdock.exe"
        report = ROOT / "build/archive-shell-smoke.json"
        report.unlink(missing_ok=True)
        env = dict(os.environ, APPDATA=str(root / "fresh appdata"))
        subprocess.run([str(executable), "--shell-smoke-test", str(report)], env=env,
                       cwd=root, timeout=60, check=True)
        if json.loads(report.read_text(encoding="utf-8")).get("ok") is not True:
            raise ValueError(f"Extracted executable smoke test failed: {report}")
    print(f"Checksum and extracted executable verified: {archive.name}")


if __name__ == "__main__":
    main()
