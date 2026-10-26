"""Generate an update-signing key locally. Never commit the private key."""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def openssl():
    found = shutil.which('openssl') or shutil.which('openssl.exe')
    if not found:
        for root in (Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git',
                     Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Git'):
            candidate = root / 'usr/bin/openssl.exe'
            if candidate.is_file():
                return str(candidate)
        raise ValueError('OpenSSL was not found. Run this command from Git Bash with Git for Windows installed.')
    return found


def modulus(private):
    value = subprocess.check_output([openssl(), 'rsa', '-in', str(private), '-noout', '-modulus'], text=True).strip()
    if not value.startswith('Modulus='):
        raise ValueError('Could not read the RSA public modulus.')
    return value.split('=', 1)[1].lower()


def main():
    secret = ROOT / '.secrets/update-signing-key.pem'
    public = ROOT / 'bashdock/assets/update-key.json'
    if secret.exists() or json.loads(public.read_text())['modulus']:
        raise ValueError('An update key already exists. Back it up; key rotation is a separate release decision.')
    secret.parent.mkdir(mode=0o700, exist_ok=True)
    subprocess.run([openssl(), 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:3072',
                    '-pkeyopt', 'rsa_keygen_pubexp:65537', '-out', str(secret)], check=True)
    os.chmod(secret, 0o600)
    if os.name == 'nt':
        import csv
        user = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
        sid = next(csv.reader(user.splitlines()))[1]
        subprocess.run(['icacls', str(secret), '/inheritance:r', '/grant:r', '*' + sid + ':(F)'],
                       check=True, stdout=subprocess.DEVNULL)
    public.write_text(json.dumps({'algorithm': 'RSA-PKCS1-SHA256', 'exponent': 65537,
                                 'modulus': modulus(secret)}, indent=2) + '\n', encoding='utf-8')
    print('Generated .secrets/update-signing-key.pem (private; ignored) and bashdock/assets/update-key.json (public).')
    print('Back up the private key securely. Add its contents to GitHub Actions secret BASHDOCK_UPDATE_SIGNING_KEY.')
    print('Commit only the public key before creating a signed release.')


if __name__ == '__main__':
    main()
