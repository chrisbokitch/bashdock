/* All resources are local. Shell output goes to xterm.write, never innerHTML. */
const terminal = new Terminal({
  cursorBlink: true, fontFamily: 'Cascadia Mono, Consolas, monospace',
  fontSize: 15, scrollback: 10000, allowProposedApi: false,
  theme: {background: '#10141c', foreground: '#dde4ef', cursor: '#70dcc2'}
});
const fit = new FitAddon.FitAddon();
terminal.loadAddon(fit);
terminal.open(document.getElementById('terminal'));
new QWebChannel(qt.webChannelTransport, channel => {
  const bridge = channel.objects.bridge;
  let preferences = {copy_on_select: false, right_click_paste: false};
  terminal.parser.registerOscHandler(777, data => {
    const prefix = 'bashdock-cwd;';
    if (!data.startsWith(prefix)) return false;
    bridge.directory(data.slice(prefix.length));
    return true;
  });
  terminal.onData(data => bridge.input(data));
  terminal.onResize(size => bridge.resize(size.cols, size.rows));
  bridge.output.connect(data => terminal.write(data));
  // Buttons represent typed commands, not clipboard pastes. Send the command
  // and Enter together so stale bracketed-paste mode cannot add escape markers.
  bridge.paste.connect(command => bridge.input(command.replace(/\r?\n/g, '\r') + '\r'));
  bridge.clipboardPaste.connect(text => terminal.paste(text));
  bridge.focus.connect(() => terminal.focus());
  terminal.attachCustomKeyEventHandler(event => {
    if (event.ctrlKey && event.shiftKey && event.code === 'KeyC') {
      if (event.type === 'keydown') bridgeCopy();
      return false;
    }
    if (event.ctrlKey && event.shiftKey && event.code === 'KeyV') {
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
