"""Sign release update metadata on the trusted draft-release job only."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
if __package__:
    from .update_keys import ROOT, openssl, modulus
else:
    from update_keys import ROOT, openssl, modulus


def sign_release(folder, private, version, public):
    archive = folder / f'bashdock-{version}-windows-x64.zip'
    with zipfile.ZipFile(archive) as bundle:
        if json.loads(bundle.read('bashdock/BUILD-INFO.json'))['version'] != version:
            raise ValueError('Release archive version does not match signed metadata.')
        if 'bashdock/bashdock-updater.exe' not in bundle.namelist():
            raise ValueError('Release archive does not contain the independent updater.')
        if json.loads(bundle.read('bashdock/_internal/bashdock/assets/update-key.json')) != public:
            raise ValueError('The signing key differs from the public key embedded in the release ZIP.')
    if not 0 < archive.stat().st_size <= 1024**3:
        raise ValueError('Release exceeds the automatic-update download limit.')
    if modulus(private) != public['modulus'] or public['algorithm'] != 'RSA-PKCS1-SHA256' or public['exponent'] != 65537:
        raise ValueError('Signing secret does not match the public key embedded in the application.')
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = dict(schema=1, version=version, platform='windows-x64', filename=archive.name,
                    url=f'https://github.com/chrisbokitch/bashdock/releases/download/v{version}/{archive.name}',
                    size=archive.stat().st_size, sha256=digest)
    path = folder / 'bashdock-update.json'
    path.write_text(json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    signature = folder / 'bashdock-update.sig'
    subprocess.run([openssl(), 'dgst', '-sha256', '-sign', str(private), '-out', str(signature), str(path)], check=True)
    sums = folder / f'bashdock-{version}-SHA256SUMS.txt'
    with sums.open('a', encoding='utf-8', newline='\n') as stream:
        for file in (path, signature):
            stream.write(hashlib.sha256(file.read_bytes()).hexdigest() + '  ' + file.name + '\n')
    return path, signature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, default=ROOT / 'release')
    args = parser.parse_args()
    version = json.loads((ROOT / 'package.json').read_text())['version']
    public = json.loads((ROOT / 'bashdock/assets/update-key.json').read_text())
    if not public.get('modulus'):
        if int(version.split('.')[0]) >= 1:
            raise ValueError('BashDock 1.0 requires a configured update-signing key.')
        print('Pre-1.0 draft: update signing is not configured. Automatic updates remain inactive.')
        return
    secret = os.environ.get('BASHDOCK_UPDATE_SIGNING_KEY')
    if not secret:
        raise ValueError('Set the GitHub Actions secret BASHDOCK_UPDATE_SIGNING_KEY before creating this signed release.')
    with tempfile.TemporaryDirectory(prefix='bashdock-release-key-') as temp:
        private = Path(temp) / 'private.pem'
        private.write_text(secret, encoding='utf-8')
        os.chmod(private, 0o600)
        for path in sign_release(args.artifacts, private, version, public):
            print(path.name)


if __name__ == '__main__':
    main()
