"""Stage the current local package for a named installed copy of BashDock."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bashdock.local_updates import check_target, disable, stage_package
from bashdock.update_security import load_key
if __package__:
    from .update_keys import openssl, modulus
    from .package_release import check_source_tree
else:
    from update_keys import openssl, modulus
    from package_release import check_source_tree


def development_key():
    private = ROOT / '.secrets/local-update-signing-key.pem'
    private.parent.mkdir(mode=0o700, exist_ok=True)
    if not private.exists():
        subprocess.run([openssl(), 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
            'rsa_keygen_bits:3072', '-out', str(private)], check=True, stderr=subprocess.PIPE)
        os.chmod(private, 0o600)
        if os.name == 'nt':
            import csv
            user = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
            sid = next(csv.reader(user.splitlines()))[1]
            subprocess.run(['icacls', str(private), '/inheritance:r', '/grant:r', '*' + sid + ':(F)'],
                           check=True, stdout=subprocess.DEVNULL)
    public = dict(algorithm='RSA-PKCS1-SHA256', exponent=65537, modulus=modulus(private))
    # Validate the generated public key with the same rules as the installed app.
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'public.json'
        path.write_text(json.dumps(public), encoding='utf-8')
        load_key(path)
    return private, public


def sign(raw, private):
    with tempfile.TemporaryDirectory(prefix='bashdock-local-sign-') as directory:
        path = Path(directory) / 'manifest.json'
        signature = Path(directory) / 'manifest.sig'
        path.write_bytes(raw)
        subprocess.run([openssl(), 'dgst', '-sha256', '-sign', str(private),
                        '-out', str(signature), str(path)], check=True, stderr=subprocess.PIPE)
        return signature.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path, help='Installed BashDock folder to update')
    parser.add_argument('--reuse-package', action='store_true', help='Reuse the exact current-commit package')
    parser.add_argument('--disable', action='store_true', help='Disable local staging for this installation')
    parser.add_argument('--check-target', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if sys.platform != 'win32':
            raise ValueError('Local update staging requires Windows.')
        target = args.target.resolve()
        if args.disable:
            disable(target)
            print(f'Local update staging disabled for {target}. Public updates are unchanged.')
            return
        if target == (ROOT / 'dist/bashdock').resolve():
            raise ValueError('Choose your installed copy, not the dist/bashdock build output folder.')
        check_target(target)
        if args.check_target:
            return
        commit = check_source_tree(ROOT)
        version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
        archive = ROOT / 'release' / f'bashdock-{version}-windows-x64.zip'
        if not archive.is_file():
            raise ValueError('The current package is missing. Run stage-update without --reuse-package.')
        private, public = development_key()
        ready = stage_package(target, archive, public, lambda raw: sign(raw, private),
                              expected_version=version, expected_commit=commit)
        print(f'Local build {version} staged for {target}.')
        print('The installed app will verify the staged package and offer Restart to update.')
        print('Finish running work, then confirm the restart in BashDock. No running files were replaced.')
        print(f'Staged files: {ready.directory}')
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Local update staging stopped: {error}\n')


if __name__ == '__main__':
    main()
