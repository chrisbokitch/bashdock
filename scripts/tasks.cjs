// Use the project's Python directly: no venv activation or shell-specific paths.
const { spawnSync } = require('node:child_process');
const { existsSync, readFileSync, rmSync, copyFileSync } = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const windows = process.platform === 'win32';
const python = path.join(root, '.venv', windows ? 'Scripts/python.exe' : 'bin/python');
const task = process.argv[2];

function run(executable, args, options = {}) {
  const result = spawnSync(executable, args, { cwd: root, stdio: 'inherit', timeout: options.timeout });
  if ((result.error || result.status !== 0) && options.report && existsSync(options.report)) {
    console.error(readFileSync(options.report, 'utf8'));
  }
  if (result.error) {
    console.error(`Could not run ${executable}: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) {
    if (result.signal) console.error(`Stopped by ${result.signal}.`);
    process.exit(result.status || 1);
  }
}

if (!['setup', 'test', 'preview', 'compile', 'package', 'package-check', 'update-keygen'].includes(task)) {
  console.error('Use npm run setup, npm test, npm run preview, npm run compile, or npm run package.');
  process.exit(1);
}

if (['preview', 'compile', 'package', 'package-check'].includes(task) && !windows) {
  console.error(`${task} requires Windows. Build Windows executables on Windows.`);
  process.exit(1);
}

if (task === 'setup') {
  if (!existsSync(python)) {
    run(windows ? 'py' : 'python3', windows ? ['-3', '-m', 'venv', '.venv'] : ['-m', 'venv', '.venv']);
  }
  run(python, ['-m', 'pip', 'install', '-e', '.']);
  console.log('Ready. Use npm test, npm run go, npm run preview, or npm run compile.');
  process.exit(0);
}

if (!existsSync(python)) {
  console.error('Project Python environment not found. Run npm run setup first.');
  process.exit(1);
}

if (task === 'update-keygen') {
  run(python, ['scripts/update_keys.py']);
} else if (task === 'test') {
  run(python, ['-m', 'unittest', 'discover', '-s', 'tests', '-v']);
  run(process.execPath, ['--test', 'tests/terminal-settings.test.cjs']);
} else if (task === 'preview') {
  run(python, ['-m', 'bashdock']);
} else if (task === 'compile') {
  // Install the optional build tools before invoking PyInstaller in the same venv.
  if (process.env.BASHDOCK_LOCKED_BUILD === '1') {
    run(python, ['-m', 'pip', 'check']);
  } else {
    run(python, ['-m', 'pip', 'install', '-e', '.[build]']);
  }
  run(python, ['-m', 'PyInstaller', '--clean', '--noconfirm', 'bashdock.spec']);
  run(python, ['-m', 'PyInstaller', '--clean', '--noconfirm', 'updater.spec']);
  copyFileSync(path.join(root, 'dist', 'bashdock-updater.exe'), path.join(root, 'dist', 'bashdock', 'bashdock-updater.exe'));
  run(python, ['scripts/check_updater.py']);
  const executable = path.join(root, 'dist', 'bashdock', 'bashdock.exe');
  if (!existsSync(executable)) {
    console.error(`Build completed without the expected executable: ${executable}`);
    process.exit(1);
  }
  console.log('Checking the compiled app can run an interactive Git Bash command…');
  const report = path.join(root, 'build', 'packaged-shell-smoke.json');
  rmSync(report, { force: true });
  run(executable, ['--shell-smoke-test', report], { timeout: 60000, report });
  console.log(`Built ${executable}\nKeep the entire dist/bashdock folder together when copying the app.`);
} else if (task === 'package') {
  run(python, ['-u', 'scripts/package_release.py']);
} else if (task === 'package-check') {
  run(python, ['scripts/package_release.py', '--check']);
}
