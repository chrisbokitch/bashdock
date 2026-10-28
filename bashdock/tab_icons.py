"""Original line icons shared by tabs and their picker; no fonts or external files."""
from functools import lru_cache

# Coordinates use a 24-unit canvas. Stable IDs are stored in settings.
GENERIC = {
    'circle': ('Circle', '<circle cx="12" cy="12" r="8"/>'),
    'diamond': ('Diamond', '<path d="m12 3 9 9-9 9-9-9Z"/>'),
    'square': ('Square', '<rect x="4" y="4" width="16" height="16" rx="2"/>'),
    'triangle': ('Triangle', '<path d="m12 3 10 18H2Z"/>'),
    'hexagon': ('Hexagon', '<path d="m7 3 h10l5 9-5 9H7L2 12Z"/>'),
    'star': ('Star', '<path d="m12 2 3 7 7 1-5 5 1 7-6-4-6 4 1-7-5-5 7-1Z"/>'),
    'cross': ('Cross', '<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6Z"/>'),
    'pentagon': ('Pentagon', '<path d="m12 2 10 7-4 12H6L2 9Z"/>'),
    'rings': ('Rings', '<circle cx="8" cy="12" r="6"/><circle cx="16" cy="12" r="6"/>'),
    'grid': ('Grid', '<path d="M4 4h6v6H4Zm10 0h6v6h-6ZM4 14h6v6H4Zm10 0h6v6h-6Z"/>'),
    'target': ('Target', '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>'),
    'cube': ('Cube', '<path d="m12 2 9 5v10l-9 5-9-5V7Zm0 10 9-5M12 12 3 7m9 5v10"/>'),
}
SYMBOLS = {
    'terminal': ('Terminal', '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m6 9 4 3-4 3m7 0h5"/>'),
    'folder': ('Folder', '<path d="M2 6h8l2 3h10v11H2Z"/>'),
    'code': ('Code', '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>'),
    'branch': ('Branch', '<circle cx="6" cy="4" r="2"/><circle cx="6" cy="20" r="2"/><circle cx="18" cy="4" r="2"/><path d="M6 6v12m12-12c0 8-12 4-12 10"/>'),
    'server': ('Server', '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6h1m-1 11h1m5-11h4m-4 11h4"/>'),
    'database': ('Database', '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 4 18 4 18 0V5M3 12c0 4 18 4 18 0"/>'),
    'cloud': ('Cloud', '<path d="M6 19a5 5 0 0 1-1-10 7 7 0 0 1 13-2 6 6 0 0 1 0 12Z"/>'),
    'globe': ('Globe', '<circle cx="12" cy="12" r="10"/><ellipse cx="12" cy="12" rx="4" ry="10"/><path d="M2 12h20"/>'),
    'home': ('Home', '<path d="m2 11 10-9 10 9M5 9v12h5v-7h4v7h5V9"/>'),
    'briefcase': ('Briefcase', '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M8 7V3h8v4M2 12c5 5 15 5 20 0m-10 1v4"/>'),
    'tools': ('Tools', '<path d="m14 4 3 3 4-4a6 6 0 0 1-7 8L5 21l-3-3 10-9a6 6 0 0 1 2-5Z"/>'),
    'gear': ('Gear', '<path d="m9 2 6 0 1 4 4 1 2 5-3 3v4l-5 3-3-3-4 1-4-4 1-4-3-3 3-5 4 1Z"/><circle cx="12" cy="12" r="3"/>'),
    'rocket': ('Rocket', '<path d="M9 15C8 8 15 2 22 2c0 7-6 14-13 13Zm0-7H4l-2 7h7m7 0v5l-7 2v-7m-4 3-3 4"/><circle cx="16" cy="8" r="2"/>'),
    'bolt': ('Bolt', '<path d="m14 2-11 12h8l-1 8 11-12h-8Z"/>'),
    'shield': ('Shield', '<path d="m12 2 9 4v7c0 5-9 9-9 9s-9-4-9-9V6Zm-4 10 3 3 5-6"/>'),
    'lock': ('Lock', '<rect x="4" y="10" width="16" height="12" rx="2"/><path d="M7 10V7a5 5 0 0 1 10 0v3m-5 5v3"/>'),
    'key': ('Key', '<circle cx="8" cy="8" r="5"/><path d="m12 12 9 9m-5-5 3-3m0 6 3-3"/>'),
    'bug': ('Bug', '<rect x="7" y="7" width="10" height="14" rx="5"/><path d="m9 7-2-4m8 4 2-4M3 9l4 3m10 0 4-3M2 16h5m10 0h5M5 22l3-3m8 0 3 3M12 8v12"/>'),
    'flask': ('Flask', '<path d="M8 2h8m-6 0v7L3 20q-1 2 2 2h14q3 0 2-2L14 9V2M7 15h10"/>'),
    'book': ('Book', '<path d="M12 5C8 2 4 2 2 3v17c4-2 7-1 10 1 3-2 6-3 10-1V3c-2-1-6-1-10 2Zm0 0v16"/>'),
    'document': ('Document', '<path d="M5 2h10l5 5v15H5Zm10 0v6h5M8 12h9m-9 4h9"/>'),
    'package': ('Package', '<path d="m12 2 10 5v10l-10 5-10-5V7Zm0 10 10-5M12 12 2 7m10 5v10M7 4l10 6v5"/>'),
    'monitor': ('Monitor', '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M12 17v5m-5 0h10"/>'),
    'coffee': ('Coffee', '<path d="M3 8h13v8a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5Zm13 1h2a4 4 0 0 1 0 8h-2M6 2v3m4-3v3m4-3v3"/>'),
}
CATALOG = {**GENERIC, **SYMBOLS}


def next_generic(used):
    """Use every generic shape before repeating the least-used one."""
    used = list(used)
    return min(GENERIC, key=lambda key: used.count(key))


def assign_missing(data):
    """Resolve legacy icons for UI use, keeping shared tab identities consistent."""
    groups = [data['tabs']] + [workspace['tabs'] for workspace in data.get('workspaces', [])]
    known = {tab['id']: tab['icon'] for group in reversed(groups) for tab in group if tab.get('icon')}
    for group in groups:
        used = [tab['icon'] for tab in group if tab.get('icon')]
        for tab in group:
            if not tab.get('icon'):
                tab['icon'] = known.get(tab['id']) or next_generic(used)
                known[tab['id']] = tab['icon']
                used.append(tab['icon'])


@lru_cache(maxsize=256)
def icon(key, color='#dde4ef'):
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
           f'stroke-linejoin="round">{CATALOG[key][1]}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    result = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result
