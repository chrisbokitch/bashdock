/* Search stays inside this local page: queries never enter Bash or diagnostics. */
function createTerminalSearch(terminal) {
  const limit = 1000;
  const addon = new SearchAddon.SearchAddon({highlightLimit: limit});
  terminal.loadAddon(addon);
  const bar = document.getElementById('terminal-search');
  const input = document.getElementById('search-input');
  const status = document.getElementById('search-status');
  const previous = document.getElementById('search-previous');
  const next = document.getElementById('search-next');
  const close = document.getElementById('search-close');
  let pending;
  const decorations = {
    matchBorder: '#a77b2e', activeMatchBorder: '#f0bd50',
    matchOverviewRuler: '#a77b2e', activeMatchColorOverviewRuler: '#f0bd50'
  };
  function cancelPending() { clearTimeout(pending); pending = undefined; }
  function clear() {
    addon.clearDecorations();
    terminal.clearSelection();
    status.textContent = '';
    input.setAttribute('aria-invalid', 'false');
    previous.disabled = next.disabled = true;
  }
  addon.onDidChangeResults(result => {
    if (bar.hidden || !input.value) return;
    const count = result.resultCount;
    status.textContent = !count ? 'No matches' : count >= limit ? `${limit}+ matches` :
      `${result.resultIndex + 1} of ${count}`;
    input.setAttribute('aria-invalid', String(count === 0));
    previous.disabled = next.disabled = count === 0;
  });
  function find(backwards = false, incremental = false) {
    cancelPending();
    if (bar.hidden) return;
    if (!input.value) { clear(); return; }
    const normal = terminal.buffer.active.type === 'normal';
    const options = {incremental, caseSensitive: false, regex: false,
      ...(normal ? {decorations} : {})};
    const found = backwards ? addon.findPrevious(input.value, options) : addon.findNext(input.value, options);
    // Alternate screens have no scrollback markers/decorations, but their
    // currently visible text is still searchable using the ordinary selection.
    if (!normal) {
      status.textContent = found ? 'Match found' : 'No matches';
      input.setAttribute('aria-invalid', String(!found));
      previous.disabled = next.disabled = !found;
    }
  }
  function open() {
    bar.hidden = false;
    input.focus();
    input.select();
    find(false, true);
  }
  function hide() {
    cancelPending();
    bar.hidden = true;
    clear();
    terminal.focus();
  }
  input.addEventListener('input', event => {
    cancelPending();
    if (event.isComposing) return;
    if (!input.value) { clear(); return; }
    pending = setTimeout(() => find(false, true), 100);
  });
  previous.addEventListener('click', () => { find(true); input.focus(); });
  next.addEventListener('click', () => { find(); input.focus(); });
  close.addEventListener('click', hide);
  document.addEventListener('keydown', event => {
    if (event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey && event.code === 'KeyF') {
      event.preventDefault(); event.stopImmediatePropagation(); open();
    } else if (!bar.hidden && event.key === 'Escape') {
      event.preventDefault(); event.stopImmediatePropagation(); hide();
    } else if (!bar.hidden && event.target === input && event.key === 'Enter' && !event.isComposing) {
      event.preventDefault(); event.stopImmediatePropagation(); find(event.shiftKey);
    }
  }, true);
  terminal.buffer.onBufferChange(() => {
    if (!bar.hidden) { addon.clearDecorations(); terminal.clearSelection(); find(false, true); }
  });
  clear();
  return {open, isOpen: () => !bar.hidden};
}
