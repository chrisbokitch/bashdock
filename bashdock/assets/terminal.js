/* All resources are local. Shell output goes to xterm.write, never innerHTML. */
function scrollbarColors(background) {
  const channels = background.slice(1).match(/../g).map(channel => parseInt(channel, 16));
  // Lighten dark terminal themes. Near-white themes need darker relatives so
  // the thumb remains visible rather than disappearing into a white track.
  const target = channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722 > 190 ? 0 : 255;
  const mix = amount => '#' + channels.map(channel =>
    Math.round(channel + (target - channel) * amount).toString(16).padStart(2, '0')).join('');
  return {track: mix(0.06), thumb: mix(0.22), hover: mix(0.30), active: mix(0.38)};
}

const terminal = new Terminal({
  cursorBlink: true, fontFamily: 'Cascadia Mono, Consolas, monospace',
  fontSize: 15, scrollback: 10000, allowProposedApi: false,
  theme: {background: '#10141c', foreground: '#dde4ef', cursor: '#70dcc2'}
});
const fit = new FitAddon.FitAddon();
terminal.loadAddon(fit);
terminal.open(document.getElementById('terminal'));
const scrollToBottom = document.getElementById('scroll-to-bottom');
const updateScrollButton = () => {
  const buffer = terminal.buffer.active;
  scrollToBottom.hidden = buffer.type !== 'normal' || buffer.viewportY >= buffer.baseY;
};
terminal.onScroll(updateScrollButton);
// xterm suppresses onScroll for native viewport scrolling to avoid feedback
// loops. Rendering runs after that viewport position has been applied.
terminal.onRender(updateScrollButton);
terminal.onWriteParsed(updateScrollButton);
terminal.onResize(updateScrollButton);
terminal.buffer.onBufferChange(updateScrollButton);
// Mouse activation should not blur the shell or disturb its text selection.
scrollToBottom.addEventListener('mousedown', event => event.preventDefault());
scrollToBottom.addEventListener('click', () => {
  terminal.scrollToBottom();
  updateScrollButton();
  terminal.focus();
});
updateScrollButton();
new QWebChannel(qt.webChannelTransport, channel => {
  const bridge = channel.objects.bridge;
  let preferences = {copy_on_select: false, right_click_paste: false};
  const readySessions = [];
  const commandEvents = [];
  terminal.parser.registerOscHandler(777, data => {
    const commandPrefix = 'bashdock-command;';
    if (data.startsWith(commandPrefix)) {
      commandEvents.push(data.slice(commandPrefix.length));
      return true;
    }
    const readyPrefix = 'bashdock-ready;';
    if (data.startsWith(readyPrefix)) {
      readySessions.push(data.slice(readyPrefix.length));
      return true;
    }
    const prefix = 'bashdock-cwd;';
    if (!data.startsWith(prefix)) return false;
    bridge.directory(data.slice(prefix.length));
    return true;
  });
  terminal.onData(data => bridge.input(data));
  terminal.onResize(size => bridge.resize(size.cols, size.rows));
  bridge.output.connect(data => terminal.write(data, () => {
    // xterm parses output asynchronously. Release queued buttons only after
    // startup output (including terminal queries) has actually been processed.
    while (commandEvents.length) bridge.commandEvent(commandEvents.shift());
    while (readySessions.length) bridge.shellReady(readySessions.shift());
  }));
  // Buttons represent typed commands, not clipboard pastes. Send the command
  // and Enter together so stale bracketed-paste mode cannot add escape markers.
  bridge.paste.connect((commandId, command) => {
    // Finish focus reporting before injecting text. A focus transition after
    // the command write can interleave ConPTY's input handling with that text.
    terminal.focus();
    bridge.commandInput(commandId, command.replace(/\r?\n/g, '\r') + '\r');
  });
  // A private Readline binding reads the staged script without typing an
  // implementation wrapper into the terminal or adding it to shell history.
  bridge.timedButton.connect(commandId => {
    terminal.focus();
    bridge.commandInput(commandId, '\x18\x02');
  });
  bridge.clipboardPaste.connect(text => terminal.paste(text));
  bridge.focus.connect(() => terminal.focus());
  terminal.attachCustomKeyEventHandler(event => {
    // Handle these in the renderer too: WebEngine may consume Qt shortcuts.
    // Suppress Chromium page zoom and never send the chord to the shell.
    if (event.ctrlKey && !event.altKey && !event.metaKey) {
      let zoom;
      if (['Equal', 'NumpadAdd'].includes(event.code) || event.key === '+') zoom = 1;
      else if (!event.shiftKey && ['Minus', 'NumpadSubtract'].includes(event.code)) zoom = -1;
      else if (!event.shiftKey && ['Digit0', 'Numpad0'].includes(event.code)) zoom = 0;
      if (zoom !== undefined) {
        event.preventDefault();
        if (event.type === 'keydown') bridge.zoomFont(zoom);
        return false;
      }
    }
    if (event.ctrlKey && event.shiftKey && event.code === 'KeyC') {
      event.preventDefault();
      if (event.type === 'keydown') bridgeCopy();
      return false;
    }
    if (event.ctrlKey && event.shiftKey && event.code === 'KeyV') {
      // Returning false only stops xterm; Chromium can still perform its own
      // paste, duplicating text and bypassing the native confirmation route.
      event.preventDefault();
      // Qt handles paste through the native clipboard, including multiline confirmation.
      if (event.type === 'keydown') bridge.requestPaste();
      return false;
    }
    return true;
  });
  function bridgeCopy() { bridge.copy(terminal.getSelection()); }
  terminal.onSelectionChange(() => {
    if (preferences.copy_on_select && terminal.hasSelection()) bridgeCopy();
  });
  const rightPaste = event => preferences.right_click_paste &&
    (event.shiftKey || terminal.modes.mouseTrackingMode === 'none');
  const host = document.getElementById('terminal');
  host.addEventListener('focusin', () => bridge.viewFocus(true));
  host.addEventListener('focusout', () => bridge.viewFocus(false));
  host.addEventListener('mousedown', event => {
    if (event.button === 2 && rightPaste(event)) {
      event.preventDefault();
      event.stopImmediatePropagation();
      bridge.requestPaste();
      terminal.focus();
    }
  }, true);
  host.addEventListener('contextmenu', event => {
    if (rightPaste(event)) event.preventDefault();
  });
  const fitVisible = () => {
    const host = document.getElementById('terminal');
    if (host.clientWidth > 30 && host.clientHeight > 30) fit.fit();
  };
  new ResizeObserver(fitVisible).observe(document.getElementById('terminal'));
  bridge.settingsChanged.connect(json => {
    preferences = JSON.parse(json);
    terminal.options = {
      fontFamily: `${JSON.stringify(preferences.font_family)}, Consolas, monospace`,
      fontSize: preferences.font_size, scrollback: preferences.scrollback,
      cursorStyle: preferences.cursor_style, cursorBlink: preferences.cursor_blink,
      theme: {background: preferences.background, foreground: preferences.foreground,
              cursor: preferences.cursor_color, selectionBackground: preferences.selection_color,
              selectionInactiveBackground: preferences.selection_color}
    };
    document.body.style.backgroundColor = preferences.background;
    document.body.style.setProperty('--terminal-foreground', preferences.foreground);
    for (const [part, color] of Object.entries(scrollbarColors(preferences.background))) {
      document.body.style.setProperty(`--scrollbar-${part}`, color);
    }
    fitVisible();
    requestAnimationFrame(fitVisible);
    document.fonts.ready.then(fitVisible);
  });
  bridge.requestSettings();
  // Hidden restored tabs must initialize too; requestAnimationFrame pauses while hidden.
  fitVisible();
  bridge.ready(terminal.cols, terminal.rows);
  terminal.focus();
});
