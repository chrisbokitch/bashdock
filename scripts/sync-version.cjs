// package.json is authoritative; setuptools and the frozen app use this generated module.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const version = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version;
const output = '# Generated from package.json by scripts/sync-version.cjs; do not edit directly.\n' +
               `__version__ = ${JSON.stringify(version)}\n`;
const target = path.join(root, 'gitbasher', '_version.py');
if (process.argv.includes('--check')) {
  const actual = fs.existsSync(target) ? fs.readFileSync(target, 'utf8').replace(/\r\n/g, '\n') : '';
  const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf8'));
  if (actual !== output || lock.version !== version || lock.packages[''].version !== version) {
    console.error('Version files disagree. Run npm install --package-lock-only --ignore-scripts and node scripts/sync-version.cjs.');
    process.exit(1);
  }
} else {
  fs.writeFileSync(target, output);
  console.log(`App version synchronized to ${version}.`);
}
