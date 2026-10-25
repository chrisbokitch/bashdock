const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const signal = () => ({connect(fn) {this.handler = fn;}, emit(value) {this.handler(value);}});
  const initial = {font_family: 'Cascadia Mono', font_size: 15, scrollback: 10000,
    cursor_style: 'block', cursor_blink: true, foreground: '#dde4ef', background: '#10141c',
    cursor_color: '#70dcc2', selection_color: '#365e66', copy_on_select: false, right_click_paste: false};
  const bridge = {output: signal(), paste: signal(), clipboardPaste: signal(), focus: signal(),
    settingsChanged: signal(), input() {}, resize() {}, directory() {}, ready() {},
    copies: [], copy(text) {this.copies.push(text);}, pastes: 0, requestPaste() {this.pastes++;},
    requestSettings() {this.settingsChanged.emit(JSON.stringify(initial));}};
  const host = {clientWidth: 800, clientHeight: 600, events: {}, addEventListener(name, fn) {this.events[name] = fn;}};
  let terminal, fits = 0;
  const context = vm.createContext({
    Terminal: class {
      constructor(options) {terminal = this; this.options = options; this.cols = 80; this.rows = 24;
        this.modes = {mouseTrackingMode: 'none'}; this.selection = '';}
      loadAddon() {} open() {} write() {} paste() {} focus() {}
      onData() {} onResize() {} attachCustomKeyEventHandler(fn) {this.key = fn;}
      onSelectionChange(fn) {this.selectionChanged = fn;}
      getSelection() {return this.selection;} hasSelection() {return this.selection.length > 0;}
      parser = {registerOscHandler() {}};
    },
    FitAddon: {FitAddon: class {fit() {fits++;}}},
    ResizeObserver: class {observe() {}},
    QWebChannel: function(_, fn) {fn({objects: {bridge}});}, qt: {webChannelTransport: {}},
    document: {getElementById() {return host;}, body: {style: {}}, fonts: {ready: Promise.resolve()}},
    requestAnimationFrame(fn) {fn();}
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../bashdock/assets/terminal.js'), 'utf8'), context);
  return {terminal, bridge, host, context, initial, fits: () => fits};
}

test('initial and live preferences reach terminal options and surrounding background', () => {
  const s = setup();
  assert.equal(s.terminal.options.fontSize, 15);
  const updated = {...s.initial, font_family: 'Font With Spaces', font_size: 22,
    background: '#223344', scrollback: 500, cursor_style: 'bar', cursor_blink: false};
  s.bridge.settingsChanged.emit(JSON.stringify(updated));
  assert.equal(s.terminal.options.fontFamily, '"Font With Spaces", Consolas, monospace');
  assert.equal(s.terminal.options.fontSize, 22);
  assert.equal(s.terminal.options.cursorStyle, 'bar');
  assert.equal(s.terminal.options.cursorBlink, false);
  assert.equal(s.terminal.options.scrollback, 500);
  assert.equal(s.context.document.body.style.backgroundColor, '#223344');
  assert.ok(s.fits() > 1);
});

test('copy-on-selection is optional and clearing selection leaves clipboard intact', () => {
  const s = setup();
  s.terminal.selection = 'selected text';
  s.terminal.selectionChanged();
  assert.equal(s.bridge.copies.length, 0);
  s.bridge.settingsChanged.emit(JSON.stringify({...s.initial, copy_on_select: true}));
  s.terminal.selectionChanged();
  assert.deepEqual(s.bridge.copies, ['selected text']);
  s.terminal.selection = '';
  s.terminal.selectionChanged();
  assert.equal(s.bridge.copies.length, 1);
});

test('right-click paste respects mouse-aware programs and uses the confirmed native paste path', () => {
  const s = setup();
  const event = {button: 2, shiftKey: false, preventDefault() {}, stopImmediatePropagation() {}};
  s.host.events.mousedown(event);
  assert.equal(s.bridge.pastes, 0);
  s.bridge.settingsChanged.emit(JSON.stringify({...s.initial, right_click_paste: true}));
  s.host.events.mousedown(event);
  assert.equal(s.bridge.pastes, 1);
  s.terminal.modes.mouseTrackingMode = 'vt200';
  s.host.events.mousedown(event);
  assert.equal(s.bridge.pastes, 1);
  s.host.events.mousedown({...event, shiftKey: true});
  assert.equal(s.bridge.pastes, 2);
  assert.equal(s.terminal.key({ctrlKey: true, shiftKey: true, code: 'KeyV', type: 'keydown'}), false);
  assert.equal(s.bridge.pastes, 3);
});
