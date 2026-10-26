"""Create the portable release archive after a successful packaged shell check."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if __package__:
    from .release_licenses import validate_environment, prepare, digest
else:
    from release_licenses import validate_environment, prepare, digest


def check_source_tree(root, commit=None):
    private_keys = subprocess.check_output(['git', 'ls-files', '--', '.secrets/'], cwd=root, text=True).strip()
    if private_keys:
        raise ValueError('Private update-signing keys must never be tracked or included in a source archive. Remove .secrets/ from Git tracking.')
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    status = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'],
                                     cwd=root, text=True).strip()
    if (commit is not None and actual != commit) or status:
        raise ValueError('Commit all project changes before packaging so binaries and source match. '
                         'Local copy.sh/copy.bat remain ignored.\n'
                         + (status or 'The requested source commit is not HEAD.'))
    return actual


def create_source_archive(root, output, version, commit):
    check_source_tree(root, commit)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'bashdock-{version}-source.zip'
    # git archive otherwise applies the user's checkout line-ending settings.
    subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
                    'archive', '--format=zip', '--prefix=bashdock-source/',
                    '-o', str(archive.resolve()), commit], cwd=root, check=True)
    with zipfile.ZipFile(archive, 'a', compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('bashdock-source/SOURCE-COMMIT.txt', commit + '\n')
    return archive


def package(source, output, report_path, version, commit, metadata):
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version):
        raise ValueError("Invalid release version.")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A full source commit SHA is required.")
    if not (source / "bashdock.exe").is_file() or not (source / "_internal").is_dir():
        raise ValueError("Build output must contain bashdock.exe and the _internal directory.")
    if not (source / "bashdock-updater.exe").is_file():
        raise ValueError("Build output is missing the independent update helper.")
    if json.loads(report_path.read_text(encoding="utf-8")).get("ok") is not True:
        raise ValueError("The packaged shell smoke test must pass before packaging.")
    for name in ('LICENSE', 'COPYRIGHT', 'THIRD-PARTY-NOTICES.md', 'SOURCE.txt', 'licenses/manifest.json'):
        if not (source / name).is_file():
            raise ValueError(f'Required release licensing file is missing: {name}')
    # Include an inventory of actual frozen files, not only Python distribution metadata.
    inventory = []
    for path in sorted(p for p in source.rglob('*') if p.is_file()):
        if path.is_symlink():
            raise ValueError('Release folders must not contain symbolic links.')
        if path.relative_to(source).as_posix() == 'licenses/runtime-files.json':
            continue
        with path.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        inventory.append(dict(path=path.relative_to(source).as_posix(), sha256=sha))
    (source / 'licenses/runtime-files.json').write_text(
        json.dumps(inventory, indent=2) + '\n', encoding='utf-8')
    files = sorted(p for p in source.rglob("*") if p.is_file())
    if any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("Release folders must not contain symbolic links.")
    output.mkdir(parents=True, exist_ok=True)
    stem = f"bashdock-{version}-windows-x64"
    build_info = dict(metadata, version=version, commit=commit,
                      source=f"https://github.com/chrisbokitch/bashdock/commit/{commit}")
    details = json.dumps(build_info, indent=2, sort_keys=True) + "\n"
    archive = output / f"{stem}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in files:
            bundle.write(path, "bashdock/" + path.relative_to(source).as_posix())
        bundle.writestr("bashdock/BUILD-INFO.json", details)
        bundle.writestr("bashdock/README.txt",
            f"BashDock {version}\n\n"
            "Requires Windows 10 (1809+) or Windows 11, x64, and Git for Windows.\n"
            "Download Git from https://gitforwindows.org/ if it is not installed.\n"
            "Extract the complete bashdock folder, then run bashdock.exe.\n"
            "Keep _internal beside the executable. Python and Node are not required.\n"
            "Close BashDock before replacing an existing installation.\n"
            "Settings are stored in %APPDATA%\\bashdock\\settings.json.\n\n"
            "Licensed under GNU GPL version 3 only; see LICENSE and COPYRIGHT.\n"
            "See SOURCE.txt for the matching application and dependency source archives.\n"
            "Third-party notices and license texts are in licenses/.\n\n"
            "Source and issues: https://github.com/chrisbokitch/bashdock\n")
    info_path = output / f"{stem}-build-info.json"
    info_path.write_text(details, encoding="utf-8")
    checksum = output / f"{stem}.sha256"
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    checksum.write_text(digest + "  " + archive.name + "\n", encoding="utf-8")
    return archive, checksum, info_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "dist/bashdock")
    parser.add_argument("--output", type=Path, default=ROOT / "release")
    parser.add_argument("--report", type=Path, default=ROOT / "build/packaged-shell-smoke.json")
    parser.add_argument("--commit")
    parser.add_argument("--check", action="store_true", help="Check packaging prerequisites without building or writing release files.")
    args = parser.parse_args()
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        parser.error("Release packaging requires Windows x64.")
    version = json.loads((ROOT / "package.json").read_text())["version"]
    tag = os.environ.get("BASHDOCK_RELEASE_TAG", "")
    if tag and tag != "v" + version:
        parser.error(f"Tag {tag} does not match application version v{version}.")
    try:
        commit = check_source_tree(ROOT, args.commit)
        validate_environment(ROOT)
    except ValueError as error:
        parser.exit(2, f'Cannot package BashDock: {error}\n')
    if args.check:
        print('Packaging prerequisites passed: clean source checkout and matching runtime versions.')
        return
    lock = ROOT / "requirements/windows-build.lock"
    metadata = {"python": sys.version, "platform": platform.platform(), "architecture": platform.machine(),
                "git": subprocess.check_output(["git", "--version"], text=True).strip(),
                "dependencies": dict(sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())),
                "build_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest()}
    if os.environ.get("GITHUB_RUN_ID"):
        metadata["workflow_run"] = (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
                                    f"/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    # A private repository is not a source offer: distribute explicit source assets.
    source_archive = create_source_archive(ROOT, args.output, version, commit)
    sources = [source_archive, *prepare(args.source, args.output, version, commit)]
    metadata['license'] = 'GPL-3.0-only'
    metadata['source_assets'] = [dict(filename=p.name, sha256=digest(p)) for p in sources]
    packaged = package(args.source, args.output, args.report, version, commit, metadata)
    sums = args.output / f'bashdock-{version}-SHA256SUMS.txt'
    sums.write_text(''.join(f'{digest(p)}  {p.name}\n' for p in [*packaged, *sources]), encoding='utf-8')
    for path in [*packaged, *sources, sums]:
        print(path)


if __name__ == "__main__":
    main()
