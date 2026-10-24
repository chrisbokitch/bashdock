// Use the project's Python directly: no venv activation or shell-specific paths.
const { spawnSync } = require('node:child_process');
const { existsSync } = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const windows = process.platform === 'win32';
const python = path.join(root, '.venv', windows ? 'Scripts/python.exe' : 'bin/python');
const task = process.argv[2];

function run(executable, args) {
  const result = spawnSync(executable, args, { cwd: root, stdio: 'inherit' });
  if (result.error) {
    console.error(`Could not run ${executable}: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) {
    if (result.signal) console.error(`Stopped by ${result.signal}.`);
    process.exit(result.status || 1);
  }
}

if (!['setup', 'test', 'preview', 'compile'].includes(task)) {
  console.error('Use npm run setup, npm test, npm run preview, or npm run compile.');
  process.exit(1);
}

if ((task === 'preview' || task === 'compile') && !windows) {
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

if (task === 'test') {
  run(python, ['-m', 'unittest', 'discover', '-s', 'tests', '-v']);
} else if (task === 'preview') {
  run(python, ['-m', 'gitbasher']);
} else if (task === 'compile') {
  // Install the optional build tools before invoking PyInstaller in the same venv.
  run(python, ['-m', 'pip', 'install', '-e', '.[build]']);
  run(python, ['-m', 'PyInstaller', '--clean', '--noconfirm', 'gitbasher.spec']);
  const executable = path.join(root, 'dist', 'gitbasher', 'gitbasher.exe');
  if (!existsSync(executable)) {
    console.error(`Build completed without the expected executable: ${executable}`);
    process.exit(1);
  }
  console.log(`Built ${executable}\nKeep the entire dist/gitbasher folder together when copying the app.`);
}
