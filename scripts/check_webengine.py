"""Run frozen rendering/resource checks with fresh profiles and display scales."""
import argparse
import json
import os
from pathlib import Path
import subprocess

if __package__:
    from .check_startup_health import temporary_work_directory
    from .probe_job import probe_job
else:
    from check_startup_health import temporary_work_directory
    from probe_job import probe_job


def verify_webengine(executable, report_directory):
    executable, report_directory = Path(executable).resolve(), Path(report_directory).resolve()
    report_directory.mkdir(parents=True, exist_ok=True)
    results = []
    with temporary_work_directory(prefix='BashDock WebEngine check ') as root:
        for mode, scale in (('default', '1'), ('software', '1'), ('software', '1.25'), ('software', '1.5')):
            label = mode+'-'+scale
            profile = root / label
            env = dict(os.environ, APPDATA=str(profile / 'roaming'), LOCALAPPDATA=str(profile / 'local'),
                       PYINSTALLER_RESET_ENVIRONMENT='1', QT_QPA_PLATFORM='windows', QT_SCALE_FACTOR=scale)
            env.pop('QTWEBENGINE_RESOURCES_PATH', None)
            env.pop('QTWEBENGINE_LOCALES_PATH', None)
            env.pop('QTWEBENGINEPROCESS_PATH', None)
            env.pop('QTWEBENGINE_DISABLE_SANDBOX', None)
            env.pop('BASHDOCK_WEBENGINE_JOB_GATE', None)
            if mode == 'default':
                env.pop('QTWEBENGINE_CHROMIUM_FLAGS', None)
            else:
                env['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu'
            report = report_directory / ('webengine-'+label+'.json')
            report.unlink(missing_ok=True)
            with probe_job() as job:
                gate = root / (label + '.start')
                if job is not None:
                    env['BASHDOCK_WEBENGINE_JOB_GATE'] = str(gate)
                process = subprocess.Popen([str(executable), '--webengine-smoke-test', str(report)], cwd=root, env=env)
                try:
                    if job is not None:
                        # The probe waits before creating Qt or shell children,
                        # so even a fast startup cannot escape job containment.
                        job.assign(process.pid)
                        gate.touch()
                    process.wait(timeout=90)
                finally:
                    if job is not None:
                        # Closing the owned job also kills descendants whose
                        # parent has already exited, including console hosts.
                        job.close()
                    elif process.poll() is None:
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], timeout=20,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=20)
            result = json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {}
            if process.returncode or not result.get('ok') or not result.get('frozen'):
                raise ValueError(f'Packaged WebEngine failed for {label}: {result}')
            results.append(dict(mode=mode, scale=scale, **result))
            print(f'Packaged WebEngine rendered real shell output: {label}', flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--report-directory', type=Path, default=Path('build'))
    args = parser.parse_args()
    results = verify_webengine(args.executable, args.report_directory)
    (args.report_directory / 'webengine-checks.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
