"""Read-only pre-publication audit. Reports contain locations, never secret values."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path.cwd()
OUT = ROOT / 'audit-results'
SCANNER_SHA = '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'
ARTIFACTS = [{'id': 12629062400, 'digest': 'sha256:cff55965aefe859ee3e6460961724d70773bc2e51c37361d99decfc794b99eee', 'size': 1625458706}, {'id': 12628325406, 'digest': 'sha256:e9f89ca823176e9fef5195b95e560b45bbec775a63bdd2827ba13feced8b74e8', 'size': 1625454478}, {'id': 12628881953, 'digest': 'sha256:45ca1c042ac6ec8462ded616f6bb0b03f59385f6c331266d37d753b9c8f64f3c', 'size': 1625455775}, {'id': 12628292256, 'digest': 'sha256:3e8dcb5d31c493ededf82ee63e2d71c6f47d5edc9aed98419e4b518cbd5262cf', 'size': 1625456160}, {'id': 12628656400, 'digest': 'sha256:6b88ba1a84645aafe390178bd2dbc2c583b0fecf9376e52a9594c54454dfcdf8', 'size': 1625455425}, {'id': 12628534847, 'digest': 'sha256:1467858f4fa1b0255e3363977fc81eb4c556020b5088dd215f5df81ec7cb8a40', 'size': 1625458709}, {'id': 12627576196, 'digest': 'sha256:62bec9385b45cc2c4eb390bf579b04421bd276637268c4a63e295a3669e8dbc1', 'size': 1625452856}, {'id': 12625125776, 'digest': 'sha256:95f6c81ff3e95e136ee323a8fbae6704eaa26f2a2f8fef1ccc243e10cd3b6884', 'size': 1620481807}, {'id': 12623586056, 'digest': 'sha256:0de54437940c3acd7ca98c4d363b1573f58e088f9abf9dfe23b12a6f3f5bd088', 'size': 1620480517}, {'id': 12624748540, 'digest': 'sha256:627f623b8cc2eb35e364ce2ed8d3a387c3c59ae96607ce8450f74e5b61484b0f', 'size': 1620484096}, {'id': 12625039231, 'digest': 'sha256:ecfcb41111bfa8d6729549d3e541a007e72cc05cb0fb53e23ef6da62fb6bab14', 'size': 1620484487}, {'id': 12626085481, 'digest': 'sha256:0ad23439d56d7c2c29b600f1ecb0219ad387de6610e4979ab0d11934630834ba', 'size': 1620484456}, {'id': 12619025018, 'digest': 'sha256:91789877a40484ba883c6dbc8c4d589b23c1676d1e0d37132ea04e7725b92636', 'size': 1611129955}, {'id': 12617885294, 'digest': 'sha256:124873a6fa5d845b6b9f8ff0ac1df1d29c6e5bb199f82bf1d75409c9e0c9da3e', 'size': 1611116234}, {'id': 12617632011, 'digest': 'sha256:0eba5d38e6d0285f357b3b1327679dadf878e940dcfa92036796ad6ab56032ad', 'size': 1611128235}, {'id': 12618238494, 'digest': 'sha256:0e361f9ed5a8092ba40ec84dcfccb6f1fce12299f4232c21d2ffb898f9083db1', 'size': 1611130484}]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extract(bundle, target):
    members = bundle.infolist()
    if sum(m.file_size for m in members) > 5 * 1024**3:
        raise ValueError('Unexpected archive expansion size')
    for member in members:
        name = PurePosixPath(member.filename)
        if name.is_absolute() or '..' in name.parts or '\\' in member.filename:
            raise ValueError('Unsafe archive member')
        if ((member.external_attr >> 16) & 0o170000) == 0o120000:
            raise ValueError('Archive contains a symbolic link')
    bundle.extractall(target)


def audit(item):
    artifact_id = item['id']
    result = {'artifact_id': artifact_id}
    try:
        with tempfile.TemporaryDirectory(prefix='bashdock-artifact-audit-') as temp:
            work = Path(temp)
            archive = work / 'artifact.zip'
            with archive.open('wb') as stream:
                subprocess.run(['gh', 'api', f'/repos/chrisbokitch/bashdock/actions/artifacts/{artifact_id}/zip'],
                               stdout=stream, stderr=subprocess.PIPE, check=True, timeout=600)
            actual = digest(archive)
            if item.get('digest') and item['digest'] != 'sha256:' + actual:
                raise ValueError('Artifact digest mismatch')
            result['artifact_sha256'] = actual
            wrapper = work / 'wrapper'
            with zipfile.ZipFile(archive) as bundle:
                extract(bundle, wrapper)
            scan = work / 'scan'
            scan.mkdir()
            verified = []
            expected = {e['filename']: e['sha256'] for e in
                        json.loads((ROOT / 'requirements/release-sources.json').read_text())}
            for path in wrapper.iterdir():
                if path.name in expected:
                    if digest(path) != expected[path.name]:
                        raise ValueError('Upstream archive digest mismatch')
                    verified.append(path.name)
                elif path.name.endswith(('-windows-x64.zip', '-source.zip')):
                    with zipfile.ZipFile(path) as bundle:
                        extract(bundle, scan / path.stem)
                elif path.suffix.lower() in ('.json', '.txt', '.sha256'):
                    shutil.copyfile(path, scan / path.name)
                elif path.name.endswith('-rust-sources.zip'):
                    # Cargo.lock-pinned public crates: verify each upstream crate's checksum.
                    with zipfile.ZipFile(path) as bundle:
                        entries = json.loads(bundle.read('sources.json'))
                        for entry in entries:
                            content = bundle.read('crates/' + entry['filename'])
                            if hashlib.sha256(content).hexdigest() != entry['sha256']:
                                raise ValueError('Rust crate digest mismatch')
                    verified.append(path.name)
                else:
                    raise ValueError('Unexpected top-level artifact file')
            raw = work / 'findings.json'
            subprocess.run(['/tmp/bashdock-gitleaks', 'dir', str(scan), '--redact=100', '--no-banner',
                            '--exit-code', '0', '--report-format', 'json', '--report-path', str(raw)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=600)
            findings = json.loads(raw.read_text())
            safe = []
            for finding in findings:
                safe.append({'rule': finding['RuleID'], 'file': str(Path(finding['File']).relative_to(scan)),
                             'line': finding['StartLine'], 'entropy': finding.get('Entropy')})
            names = [str(p.relative_to(scan)) for p in scan.rglob('*') if p.is_file() and
                     (any(t in str(p.relative_to(scan)).lower() for t in ('.secrets/', '.ssh/', 'id_rsa', 'id_ed25519'))
                      or p.suffix.lower() in ('.pem', '.ppk', '.key'))]
            result.update(status='inspected', findings=safe, sensitive_filenames=names,
                          verified_upstream_archives=verified,
                          scanned_files=sum(p.is_file() for p in scan.rglob('*')))
    except Exception as error:
        # Do not print subprocess stderr, URLs, environment variables, or candidate values.
        result.update(status='failed', error_type=type(error).__name__)
    (OUT / f'artifact-{artifact_id}.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'artifact': artifact_id, 'status': result['status'],
                      'findings': len(result.get('findings', []))}), flush=True)
    return result


def main():
    OUT.mkdir(exist_ok=True)
    url = 'https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz'
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / 'scanner.tar.gz'
        with urllib.request.urlopen(url, timeout=60) as response, archive.open('wb') as stream:
            shutil.copyfileobj(response, stream)
        if digest(archive) != SCANNER_SHA:
            raise ValueError('Scanner digest mismatch')
        with tarfile.open(archive) as bundle:
            Path('/tmp/bashdock-gitleaks').write_bytes(bundle.extractfile('gitleaks').read())
        Path('/tmp/bashdock-gitleaks').chmod(0o700)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(audit, ARTIFACTS))
    summary = {'artifacts': len(results), 'inspected': sum(r['status'] == 'inspected' for r in results),
               'failed': [r['artifact_id'] for r in results if r['status'] != 'inspected'],
               'findings': sum(len(r.get('findings', [])) for r in results)}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
