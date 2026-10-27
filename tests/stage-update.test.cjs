const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function stage(args, failPreflight = false) {
  const calls = [];
  const script = path.resolve(__dirname, '../scripts/tasks.cjs');
  const context = {
    __filename: script, __dirname: path.dirname(script), console: {error() {}, log() {}},
    process: {argv: ['node', script, 'stage-update', ...args], platform: 'win32', execPath: 'node',
      env: {}, exit(code) {throw new Error(`exit:${code}`);}},
    require(name) {
      if (name === 'node:path') return path;
      if (name === 'node:fs') return {existsSync() {return true;}};
      if (name === 'node:child_process') return {spawnSync(executable, args) {
        calls.push({executable, args});
        return {status: failPreflight ? 1 : 0};
      }};
      throw new Error(name);
    }
  };
  let error;
  try {vm.runInNewContext(fs.readFileSync(script, 'utf8'), context);} catch (caught) {error = caught;}
  return {calls, error};
}

test('stage-update validates target, then builds/packages before staging with path as one argument', () => {
  const target = 'C:/Development/tools/BashDock Test';
  const {calls, error} = stage([target]);
  assert.equal(error, undefined);
  assert.equal(calls.length, 5);
  assert.deepEqual(Array.from(calls[0].args), ['scripts/stage_update.py', target, '--check-target']);
  assert.deepEqual(calls.slice(1, 4).map(call => call.args[1]), ['package-check', 'compile', 'package']);
  assert.deepEqual(Array.from(calls[4].args), ['scripts/stage_update.py', target]);
});

test('reusing an existing package skips compilation and disabling only revokes staging', () => {
  const target = 'C:/Development/tools/bashdock';
  const reuse = stage([target, '--reuse-package']);
  assert.equal(reuse.calls.length, 2);
  assert.ok(reuse.calls.every(call => call.args[0] === 'scripts/stage_update.py'));
  const disable = stage([target, '--disable']);
  assert.equal(disable.calls.length, 1);
  assert.deepEqual(Array.from(disable.calls[0].args), ['scripts/stage_update.py', target, '--disable']);
});

test('an invalid installation stops before any build or staging operation', () => {
  const {calls, error} = stage(['C:/wrong-folder'], true);
  assert.equal(error.message, 'exit:1');
  assert.equal(calls.length, 1);
});
