const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
  const elements = {};
  const element = id => elements[id] ||= {hidden: id === 'terminal-search', value: '', events: {}, attrs: {},
    addEventListener(name, fn) {this.events[name] = fn;},
    setAttribute(name, value) {this.attrs[name] = value;}, focus() {this.focused = true;},
    select() {this.selected = true;}};
  const document = {events: {}, getElementById: element, addEventListener(name, fn) {this.events[name] = fn;}};
  const terminal = {buffer: {active: {type: 'normal'}, onBufferChange(fn) {terminal.changed = fn;}},
    loadAddon(a) {this.addon = a;}, clears: 0, focuses: 0,
    clearSelection() {this.clears++;}, focus() {this.focuses++;}};
  let callback, pending, options, calls = [];
  const context = vm.createContext({document, SearchAddon: {SearchAddon: class {
    constructor(value) {options = value;}
    onDidChangeResults(fn) {callback = fn;}
    clearDecorations() {calls.push('clear');}
    findNext(query, opts) {calls.push({query, opts, direction: 'next'}); callback({resultIndex: 0, resultCount: 2}); return true;}
    findPrevious(query, opts) {calls.push({query, opts, direction: 'previous'}); callback({resultIndex: 1, resultCount: 2}); return true;}
  }}, setTimeout(fn) {pending = fn; return 1;}, clearTimeout() {pending = undefined;}});
  vm.runInContext(fs.readFileSync('bashdock/assets/terminal-search.js', 'utf8'), context);
  const ui = context.createTerminalSearch(terminal);
  function key(event) {
    let prevented = false, stopped = false;
    document.events.keydown({...event, preventDefault() {prevented = true;}, stopImmediatePropagation() {stopped = true;}});
    return {prevented, stopped};
  }
  return {ui, element, terminal, key, calls, result: value => callback(value),
    input(query, composing = false) {element('search-input').value = query; element('search-input').events.input({isComposing: composing});},
    flush() {if (pending) pending();}, options};
}

test('live literal search, navigation, count, close and tab independence', () => {
  const s = setup(), other = setup();
  assert.deepEqual(s.key({ctrlKey: true, code: 'KeyF'}), {prevented: true, stopped: true});
  assert.equal(s.ui.isOpen(), true);
  assert.equal(other.ui.isOpen(), false);
  s.input('café <literal>');
  assert.equal(s.calls.filter(c => c.query).length, 0, 'Typing is debounced');
  s.flush();
  assert.equal(s.calls.at(-1).query, 'café <literal>');
  assert.equal(s.calls.at(-1).opts.regex, false);
  assert.equal(s.calls.at(-1).opts.caseSensitive, false);
  assert.equal(s.element('search-status').textContent, '1 of 2');
  s.key({key: 'Enter', shiftKey: true, target: s.element('search-input')});
  assert.equal(s.calls.at(-1).direction, 'previous');
  s.element('search-next').events.click();
  assert.equal(s.calls.at(-1).direction, 'next');
  s.input('late pending query');
  s.key({key: 'Escape'});
  const count = s.calls.length;
  s.flush();
  assert.equal(s.calls.length, count, 'Closing cancels the pending query');
  assert.equal(s.ui.isOpen(), false);
  assert.equal(s.terminal.focuses, 1);
  s.ui.open();
  assert.equal(s.element('search-input').value, 'late pending query');
  assert.equal(other.element('search-input').value, '');
});

test('empty, absent and capped results, IME, and alternate-screen transitions', () => {
  const s = setup();
  s.ui.open(); s.input('needle'); s.flush();
  s.result({resultIndex: -1, resultCount: 0});
  assert.equal(s.element('search-status').textContent, 'No matches');
  assert.equal(s.element('search-next').disabled, true);
  assert.equal(s.element('search-input').attrs['aria-invalid'], 'true');
  s.result({resultIndex: -1, resultCount: 1000});
  assert.equal(s.element('search-status').textContent, '1000+ matches');
  const count = s.calls.length;
  s.input('composing', true); s.flush();
  assert.equal(s.calls.length, count);
  s.key({key: 'Enter', isComposing: true, target: s.element('search-input')});
  assert.equal(s.calls.length, count);
  s.terminal.buffer.active.type = 'alternate'; s.terminal.changed();
  assert.equal(s.calls.at(-1).opts.decorations, undefined);
  assert.equal(s.element('search-status').textContent, 'Match found');
  s.input('');
  assert.equal(s.element('search-status').textContent, '');
  assert.equal(s.element('search-previous').disabled, true);
  assert.equal(s.key({ctrlKey: true, altKey: true, code: 'KeyF'}).prevented, false);
});
