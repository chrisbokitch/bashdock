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
  terminal.parser.registerOscHandler(777, data => {
    const prefix = 'bashdock-cwd;';
    if (!data.startsWith(prefix)) return false;
    bridge.directory(data.slice(prefix.length));
    return true;
  });
  terminal.onData(data => bridge.input(data));
  terminal.onResize(size => bridge.resize(size.cols, size.rows));
  bridge.output.connect(data => terminal.write(data));
  bridge.paste.connect(command => { terminal.paste(command); bridge.input('\r'); });
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
  const fitVisible = () => {
    const host = document.getElementById('terminal');
    if (host.clientWidth > 30 && host.clientHeight > 30) fit.fit();
  };
  new ResizeObserver(fitVisible).observe(document.getElementById('terminal'));
  // Hidden restored tabs must initialize too; requestAnimationFrame pauses while hidden.
  fitVisible();
  bridge.ready(terminal.cols, terminal.rows);
  terminal.focus();
});
