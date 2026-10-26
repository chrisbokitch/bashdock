"""Opt-in compiled-helper checks using signed assets and disposable installations.

Never accepts an installation plan: all writable paths are created under a new
output folder. No signature bypass, test signing key, or production startup flag.
"""
import json
import os
import secrets
import shutil
import sys
from pathlib import Path
from . import update_helper as helper
from .updates import digest_file, parse_manifest
from .update_security import load_key


def inventory(directory):
    return {str(p.relative_to(directory)): digest_file(p)
            for p in sorted(directory.rglob('*')) if p.is_file()}


def changed_byte(path):
    with path.open('r+b') as stream:
        first = stream.read(1)
        if not first:
            raise ValueError('Cannot alter an empty test asset.')
        stream.seek(0)
        stream.write(bytes([first[0] ^ 1]))


def run_acceptance(baseline, assets, output, *, status=lambda text: None):
    if sys.platform != 'win32':
        raise OSError('Run compiled update acceptance tests in a disposable Windows VM.')
    baseline, assets, output = (Path(p).resolve() for p in (baseline, assets, output))
    if output.exists() or not output.parent.is_dir():
        raise ValueError('Choose a new output folder with an existing parent. Existing folders are never reused.')
    if output.is_relative_to(baseline) or output.is_relative_to(assets):
        raise ValueError('The test output must be outside the baseline and assets folders.')
    if not (baseline / 'bashdock.exe').is_file() or not (baseline / '_internal').is_dir():
        raise ValueError('Baseline must be a complete extracted BashDock installation.')
    baseline_info = json.loads((baseline / 'BUILD-INFO.json').read_text(encoding='utf-8'))
    key = load_key()
    raw = (assets / 'bashdock-update.json').read_bytes()
    signature = (assets / 'bashdock-update.sig').read_bytes()
    manifest = parse_manifest(raw, signature, key)
    archive = assets / manifest['filename']
    if archive.stat().st_size != manifest['size'] or digest_file(archive) != manifest['sha256']:
        raise ValueError('The original release ZIP does not match its signed metadata.')
    output.mkdir()  # Refuse a concurrent invocation selecting the same directory.
    result_path = output / 'acceptance-results.json'
    results = dict(ok=False, baseline_version=baseline_info['version'],
                   update_version=manifest['version'], cases=[], output=str(output))
    environment = {name: os.environ.get(name) for name in ('APPDATA', 'LOCALAPPDATA')}
    try:
        # Both old and replacement app processes inherit only this test profile.
        os.environ['APPDATA'] = str(output / 'profile/Roaming')
        os.environ['LOCALAPPDATA'] = str(output / 'profile/Local')
        target = output / 'installation/bashdock'
        status('Copying the baseline into the disposable test folder…')
        shutil.copytree(baseline, target)
        before = inventory(target)
        from .config import defaults
        data = defaults()
        data['tabs'][0]['name'] = 'Rollback test — disposable copy'
        data['tabs'][0]['startup_folder'] = data['tabs'][0]['current_folder'] = str(output)
        data['updates'] = dict(automatic=False, download=False)
        data['confirm_on_exit'] = False
        settings = Path(os.environ['APPDATA']) / 'bashdock/settings.json'
        settings.parent.mkdir(parents=True)
        original_settings = json.dumps(data, indent=2).encode()
        settings.write_bytes(original_settings)
        settings.with_suffix('.json.bak').write_bytes(original_settings)
        backup = output / 'before-update.json'
        backup.write_bytes(original_settings)
        cases = ('altered-manifest', 'altered-signature', 'altered-zip', 'truncated-zip', 'startup-rollback')
        for case in cases:
            status('Testing ' + case + '…')
            pending = Path(os.environ['LOCALAPPDATA']) / 'BashDock/updates' / case
            pending.mkdir(parents=True)
            (pending / 'manifest.json').write_bytes(raw)
            (pending / 'manifest.sig').write_bytes(signature)
            shutil.copyfile(archive, pending / 'package.zip')
            if case == 'altered-manifest':
                # Valid JSON with different bytes must still fail its signature.
                with (pending / 'manifest.json').open('ab') as stream:
                    stream.write(b'\n')
            elif case == 'altered-signature':
                changed_byte(pending / 'manifest.sig')
            elif case == 'altered-zip':
                changed_byte(pending / 'package.zip')  # Same length, wrong hash.
            elif case == 'truncated-zip':
                with (pending / 'package.zip').open('r+b') as stream:
                    stream.truncate(manifest['size'] - 1)
            plan = dict(install=str(target), pending=str(pending), pid=os.getpid(),
                        settings=str(settings), settings_backup=str(backup), token=secrets.token_hex(32))
            launched = False
            reached_wait = False
            def no_app_handoff(pid):
                # There is no running baseline in this isolated copy.
                nonlocal reached_wait
                reached_wait = True
            def fail_launch(directory, health, token):
                nonlocal launched
                launched = True
                # This occurs AFTER signature/hash validation and extraction,
                # exclusively inside our disposable installation. Exercise the
                # real Windows CreateProcess error, not a mocked health callback.
                (directory / 'bashdock.exe').write_bytes(b'Not a Windows executable: acceptance test')
                settings.write_text('{"test": "new version changed settings"}', encoding='utf-8')
                return helper.start_app(directory, health, token)
            try:
                helper.install(plan, key, wait=no_app_handoff, launch=fail_launch, status=status)
            except (ValueError, OSError) as error:
                rejection = str(error)
            else:
                raise AssertionError(case + ': update unexpectedly succeeded')
            if inventory(target) != before or settings.read_bytes() != original_settings:
                raise AssertionError(case + ': previous installation/settings were not preserved')
            if settings.with_suffix('.json.bak').read_bytes() != original_settings:
                raise AssertionError(case + ': automatic settings backup was not restored')
            if case == 'startup-rollback':
                transaction = json.loads((pending / 'transaction.json').read_text())
                if not launched or transaction['phase'] != 'rolled-back':
                    raise AssertionError('The actual folder-swap/launch/rollback path did not run')
                if not (pending / 'failed-settings.json').is_file():
                    raise AssertionError('Failed settings were not retained')
            elif reached_wait or launched or (pending / 'transaction.json').exists():
                raise AssertionError(case + ': rejection happened after installation began')
            results['cases'].append(dict(name=case, ok=True, message=rejection))
            result_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
            # Keep the small diagnostic files, avoid retaining five large ZIPs.
            (pending / 'package.zip').unlink()
        status('Checking that the restored previous app starts…')
        pending = Path(os.environ['LOCALAPPDATA']) / 'BashDock/updates/restored-startup'
        pending.mkdir(parents=True)
        health, token = pending / 'health.json', secrets.token_hex(32)
        process = helper.start_app(target, health, token)
        if not helper.wait_for_health(process, health, token, baseline_info['version']):
            if process.poll() is None:
                process.terminate()  # Only the test process we just launched.
                process.wait(timeout=15)
            raise AssertionError('Restored app did not acknowledge startup')
        results['cases'].append(dict(name='restored-app-startup', ok=True, pid=process.pid))
        results['ok'] = True
        status('All checks passed. Close the disposable BashDock window after inspecting it.')
        return results
    except Exception as error:
        results['error'] = str(error)
        raise
    finally:
        result_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
        for name, value in environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
