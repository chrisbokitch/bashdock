const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup(TerminalClass) {
  const signal = () => ({connect(fn) {this.handler = fn;}, emit(...values) {this.handler(...values);}});
  const initial = {font_family: 'Cascadia Mono', font_size: 15, scrollback: 10000,
    cursor_style: 'block', cursor_blink: true, foreground: '#dde4ef', background: '#10141c',
    cursor_color: '#70dcc2', selection_color: '#365e66', copy_on_select: false, right_click_paste: false};
  const bridge = {output: signal(), paste: signal(), clipboardPaste: signal(), focus: signal(),
    settingsChanged: signal(), inputs: [], input(text) {this.inputs.push(text);}, resize() {}, directory() {}, ready() {},
    readySessions: [], shellReady(token) {this.readySessions.push(token);},
    commands: [], commandInput(id, text) {this.commands.push({id, text}); this.inputs.push(text);},
    focusEvents: [], viewFocus(focused) {this.focusEvents.push(focused);},
    copies: [], copy(text) {this.copies.push(text);}, pastes: 0, requestPaste() {this.pastes++;},
    requestSettings() {this.settingsChanged.emit(JSON.stringify(initial));}};
  const host = {clientWidth: 800, clientHeight: 600, events: {}, addEventListener(name, fn) {this.events[name] = fn;}};
  const scrollButton = {hidden: true, events: {}, addEventListener(name, fn) {this.events[name] = fn;}};
  let terminal, fits = 0;
  const context = vm.createContext({
    Terminal: TerminalClass ? class extends TerminalClass {
      constructor(options) {super(options); terminal = this;}
      open() {} loadAddon() {} focus() {}
    } : class {
      constructor(options) {terminal = this; this.options = options; this.cols = 80; this.rows = 24;
        this.modes = {mouseTrackingMode: 'none', bracketedPasteMode: false}; this.selection = ''; this.pasteCalls = [];
        this.buffer = {active: {type: 'normal', viewportY: 0, baseY: 0},
          onBufferChange(fn) {terminal.bufferChanged = fn;}};}
      outputWrites = [];
      focusCalls = 0;
      loadAddon() {} open() {} write(data, callback) {this.outputWrites.push({data, callback});}
      focus() {this.focusCalls++;}
      onScroll(fn) {this.scrolled = fn;} onWriteParsed(fn) {this.parsed = fn;}
      onRender(fn) {this.rendered = fn;}
      scrollToBottom() {this.buffer.active.viewportY = this.buffer.active.baseY; this.scrolled();}
      paste(text) {
        this.pasteCalls.push(text);
        this.data(this.modes.bracketedPasteMode ? `\x1b[200~${text}\x1b[201~` : text);
      }
      onData(fn) {this.data = fn;} onResize() {} attachCustomKeyEventHandler(fn) {this.key = fn;}
      onSelectionChange(fn) {this.selectionChanged = fn;}
      getSelection() {return this.selection;} hasSelection() {return this.selection.length > 0;}
      parser = {registerOscHandler(_, fn) {terminal.osc = fn;}};
    },
    FitAddon: {FitAddon: class {fit() {fits++;}}},
    ResizeObserver: class {observe() {}},
    QWebChannel: function(_, fn) {fn({objects: {bridge}});}, qt: {webChannelTransport: {}},
    document: {getElementById(id) {return id === 'scroll-to-bottom' ? scrollButton : host;}, body: {style: {
      setProperty(name, value) {this[name] = value;}
    }}, fonts: {ready: Promise.resolve()}},
    requestAnimationFrame(fn) {fn();}
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../bashdock/assets/terminal.js'), 'utf8'), context);
  return {terminal, bridge, host, scrollButton, context, initial, fits: () => fits};
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
  assert.equal(s.context.document.body.style['--terminal-foreground'], updated.foreground);
  assert.ok(s.fits() > 1);
});

test('scroll button follows each tab viewport, hides in alternate screen and restores terminal focus', () => {
  const first = setup(), second = setup();
  assert.equal(first.scrollButton.hidden, true);
  first.terminal.buffer.active.baseY = 40;
  first.terminal.parsed();
  assert.equal(first.scrollButton.hidden, false);
  assert.equal(second.scrollButton.hidden, true);
  first.terminal.buffer.active.type = 'alternate';
  first.terminal.bufferChanged();
  assert.equal(first.scrollButton.hidden, true);
  first.terminal.buffer.active.type = 'normal';
  first.terminal.bufferChanged();
  assert.equal(first.scrollButton.hidden, false);
  const focusCalls = first.terminal.focusCalls;
  let prevented = false;
  first.scrollButton.events.mousedown({preventDefault() {prevented = true;}});
  assert.equal(prevented, true);
  first.scrollButton.events.click();
  assert.equal(first.terminal.buffer.active.viewportY, 40);
  assert.equal(first.scrollButton.hidden, true);
  assert.equal(first.terminal.focusCalls, focusCalls + 1);
});

test('scroll button reappears after repeated native scrolls without output or onScroll events', () => {
  const s = setup();
  s.terminal.buffer.active.baseY = 80;
  s.terminal.buffer.active.viewportY = 80;
  s.terminal.parsed();
  for (let i = 0; i < 3; i++) {
    assert.equal(s.scrollButton.hidden, true);
    // Native viewport scrolling suppresses xterm's public onScroll event.
    s.terminal.buffer.active.viewportY = 60;
    s.terminal.rendered();
    assert.equal(s.scrollButton.hidden, false);
    s.scrollButton.events.click();
    assert.equal(s.terminal.buffer.active.viewportY, 80);
    assert.equal(s.scrollButton.hidden, true);
  }
});

test('scrollbars follow each terminal background on startup and live theme changes', () => {
  const first = setup(), second = setup();
  const colors = session => Object.fromEntries(['track', 'thumb', 'hover', 'active'].map(part =>
    [part, session.context.document.body.style[`--scrollbar-${part}`]]));
  const defaults = colors(second);
  first.bridge.settingsChanged.emit(JSON.stringify({...first.initial, background: '#341527'}));
  const purple = colors(first);
  assert.notDeepEqual(purple, defaults);
  assert.deepEqual(colors(second), defaults);
  const rgb = hex => hex.slice(1).match(/../g).map(channel => parseInt(channel, 16));
  let previous = rgb('#341527');
  for (const color of Object.values(purple)) {
    const current = rgb(color);
    assert.ok(current.every((value, i) => value > previous[i]));
    previous = current;
  }
  // Extreme light/dark backgrounds must still produce distinct, valid shades.
  for (const background of ['#000000', '#ffffff']) {
    first.bridge.settingsChanged.emit(JSON.stringify({...first.initial, background}));
    const shades = Object.values(colors(first));
    assert.ok(shades.every(value => /^#[0-9a-f]{6}$/.test(value)));
    assert.equal(new Set([background, ...shades]).size, 5);
  }
  first.bridge.settingsChanged.emit(JSON.stringify(first.initial));
  assert.deepEqual(colors(first), defaults);
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

test('first and repeated command buttons send plain commands and Enter in one write even with stale paste mode', () => {
  for (const bracketedPasteMode of [false, true]) {
    const s = setup();
    s.terminal.modes.bracketedPasteMode = bracketedPasteMode;
    s.bridge.paste.emit(1, 'pwd');
    s.bridge.paste.emit(2, "printf 'café\\n'\nprintf 'done\\n'");
    s.bridge.paste.emit(3, 'git status\r\ngit diff');
    assert.deepEqual(s.bridge.inputs, [
      'pwd\r', "printf 'café\\n'\rprintf 'done\\n'\r", 'git status\rgit diff\r'
    ]);
    assert.deepEqual(s.terminal.pasteCalls, []);
    assert.deepEqual(s.bridge.commands.map(command => command.id), [1, 2, 3]);
    assert.ok(s.bridge.inputs.every(text => !text.includes('\x1b')));
  }
});

test('web focus diagnostics contain only focus state', () => {
  const s = setup();
  s.host.events.focusin();
  s.host.events.focusout();
  assert.deepEqual(s.bridge.focusEvents, [true, false]);
  assert.deepEqual(s.bridge.inputs, []);
});

test('button input follows focus-generated terminal replies', () => {
  const s = setup();
  s.terminal.focus = () => s.terminal.data('\x1b[I');
  s.bridge.paste.emit(1, 'printf intact');
  assert.deepEqual(s.bridge.inputs, ['\x1b[I', 'printf intact\r']);
});

test('clipboard input still uses bracketed paste without adding Enter', () => {
  const s = setup();
  s.terminal.modes.bracketedPasteMode = true;
  s.bridge.clipboardPaste.emit('clipboard text');
  assert.deepEqual(s.terminal.pasteCalls, ['clipboard text']);
  assert.deepEqual(s.bridge.inputs, ['\x1b[200~clipboard text\x1b[201~']);
});

test('readiness waits for output completion while control replies remain immediate', () => {
  const s = setup();
  s.bridge.output.emit('\x1b]777;bashdock-ready;session-1\x07');
  assert.deepEqual(s.bridge.readySessions, []);
  assert.equal(s.terminal.osc('bashdock-ready;session-1'), true);
  assert.deepEqual(s.bridge.readySessions, []);
  s.terminal.data('\x1b[1;1R');
  assert.deepEqual(s.bridge.inputs, ['\x1b[1;1R']);
  s.terminal.outputWrites[0].callback();
  assert.deepEqual(s.bridge.readySessions, ['session-1']);
  s.bridge.output.emit('later output');
  s.terminal.outputWrites[1].callback();
  assert.deepEqual(s.bridge.readySessions, ['session-1']);
});

test('bundled xterm parses a split startup marker and answers queries before readiness', async () => {
  global.self = global;
  const {Terminal} = require('../bashdock/assets/xterm.js');
  const s = setup(Terminal);
  const parsed = () => new Promise(resolve => s.terminal.write('', resolve));
  try {
    s.bridge.output.emit('\x1b[6n\x1b]777;bashdock-rea');
    await parsed();
    assert.deepEqual(s.bridge.inputs, ['\x1b[1;1R']);
    assert.deepEqual(s.bridge.readySessions, []);
    s.bridge.output.emit('dy;session-1\x07');
    await parsed();
    assert.deepEqual(s.bridge.readySessions, ['session-1']);
  } finally {
    s.terminal.dispose();
  }
});
