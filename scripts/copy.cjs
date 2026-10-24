const { cpSync, mkdirSync, statSync } = require('node:fs');
const path = require('node:path');

function copyBuild(source, destination) {
  // Validate before creating/changing the destination, including PyInstaller's runtime folder.
  for (const [name, directory] of [['gitbasher.exe', false], ['_internal', true]]) {
    let info;
    try {
      info = statSync(path.join(source, name));
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      throw new Error(`Build is missing ${name}. Run npm run compile successfully first.`);
    }
    if (directory ? !info.isDirectory() : !info.isFile()) {
      throw new Error(`Invalid build entry ${name}. Run npm run compile again.`);
    }
  }
  mkdirSync(destination, { recursive: true });
  cpSync(source, destination, { recursive: true, force: true });
}

if (require.main === module) {
  if (process.platform !== 'win32') {
    console.error('npm run copy requires Windows.');
    process.exit(1);
  }
  const source = path.resolve(__dirname, '..', 'dist', 'gitbasher');
  const destination = String.raw`C:\Program Files\GitBasher`;
  try {
    copyBuild(source, destination);
    console.log(`Copied the complete app to ${destination}\nLaunch ${path.join(destination, 'gitbasher.exe')}`);
  } catch (error) {
    console.error(`Copy failed: ${error.message}`);
    if (['EACCES', 'EPERM', 'EBUSY'].includes(error.code)) {
      console.error('Close GitBasher and run npm run copy from a terminal opened as administrator.');
    }
    console.error('If copying started, the installed app may be incomplete. Resolve the error and rerun npm run copy.');
    process.exit(1);
  }
}

module.exports = { copyBuild };
