"""GUI-free icon definitions and assignment shared by settings and the tab UI."""

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
# Original line drawings; these are generic symbols, not third-party logos.
MORE_SYMBOLS = {
    # Development and automation.
    'brackets': ('Brackets', '<path d="m8 5-7 7 7 7m8-14 7 7-7 7"/>'),
    'binary': ('Binary', '<rect x="3" y="3" width="6" height="8" rx="2"/><path d="M16 3h2v8m-3 0h6M3 15h2v6m-3 0h6"/><rect x="14" y="14" width="6" height="8" rx="2"/>'),
    'braces': ('Braces', '<path d="M9 3H7v6l-4 3 4 3v6h2M15 3h2v6l4 3-4 3v6h-2"/>'),
    'script': ('Script', '<path d="M6 2h11v17a3 3 0 0 1-6 0H3a3 3 0 0 0 6 0V2m3 17h9a3 3 0 0 1-3 3H6M12 7h2m-2 4h2"/>'),
    'function': ('Function', '<path d="M16 3h-3c-2 0-3 2-3 4v10c0 3-1 4-3 4H5m1-12h10m0 6 5 6m0-6-5 6"/>'),
    'variable': ('Variable', '<path d="m5 7 8 10m0-10L5 17M3 3H1v18h2M21 3h2v18h-2"/>'),
    'merge': ('Merge', '<circle cx="6" cy="4" r="2"/><circle cx="18" cy="4" r="2"/><circle cx="12" cy="20" r="2"/><path d="M6 6v3c0 4 6 3 6 7v2m6-12v3c0 4-6 3-6 7"/>'),
    'commit': ('Commit', '<circle cx="12" cy="12" r="5"/><path d="M2 12h5m10 0h5"/>'),
    'pull-request': ('Pull request', '<circle cx="5" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M5 7v10M19 17V9c0-3-3-4-6-4h-1m3-3-3 3 3 3"/>'),
    'puzzle': ('Puzzle', '<path d="M4 4h5a3 3 0 1 1 6 0h5v5a3 3 0 1 0 0 6v5h-5a3 3 0 1 0-6 0H4v-5a3 3 0 1 1 0-6Z"/>'),
    'circuit': ('Circuit', '<circle cx="4" cy="5" r="2"/><circle cx="20" cy="5" r="2"/><circle cx="12" cy="20" r="2"/><path d="M4 7v5h16V7M12 12v6"/>'),
    'chip': ('Chip', '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/>'),
    'robot': ('Robot', '<rect x="4" y="7" width="16" height="14" rx="3"/><path d="M12 7V3m-2 0h4M1 12v5m22-5v5M8 12h1m6 0h1m-7 5h6"/>'),
    'wand': ('Wand', '<path d="m3 21 12-12 3 3L6 24m5-11 3 3M6 2v4M4 4h4m12-2v4m-2-2h4m-1 13v4m-2-2h4" transform="translate(0 -1)"/>'),
    'test-tube': ('Test tube', '<path d="m13 2 9 9m-7-7L3 16a4 4 0 0 0 5 5L20 9M8 11l5 5m-4-7 2 2"/>'),
    # Infrastructure, storage and connections.
    'network': ('Network', '<rect x="8" y="2" width="8" height="6" rx="1"/><rect x="1" y="16" width="7" height="6" rx="1"/><rect x="16" y="16" width="7" height="6" rx="1"/><path d="M12 8v4H4v4m8-4h8v4"/>'),
    'router': ('Router', '<rect x="2" y="12" width="20" height="9" rx="2"/><path d="M6 12V3m12 9V3M6 17h1m4 0h1m4 0h2"/>'),
    'wifi': ('Wi-Fi', '<path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0m-11 4a6 6 0 0 1 8 0"/><circle cx="12" cy="20" r="1"/>'),
    'antenna': ('Antenna', '<circle cx="12" cy="7" r="2"/><path d="M12 9v12m-5 0h10M6 2a8 8 0 0 0 0 10M18 2a8 8 0 0 1 0 10M8 4a4 4 0 0 0 0 6m8-6a4 4 0 0 1 0 6"/>'),
    'plug': ('Plug', '<path d="M8 2v6m8-6v6M5 8h14v4a7 7 0 0 1-14 0Zm7 11v3"/>'),
    'cable': ('Cable', '<rect x="2" y="2" width="6" height="7" rx="1"/><rect x="16" y="15" width="6" height="7" rx="1"/><path d="M5 9v6a4 4 0 0 0 8 0V9a3 3 0 0 1 6 0v6M4 5h2m12 14h2"/>'),
    'hard-drive': ('Hard drive', '<path d="M5 3h14l3 12v6H2v-6Zm-3 12h20m-5 3h2m-8 0h1"/>'),
    'storage': ('Storage', '<rect x="3" y="2" width="18" height="20" rx="2"/><path d="M3 9h18M3 15h18M7 6h1m-1 6h1m-1 6h1m5-12h4m-4 6h4m-4 6h4"/>'),
    'containers': ('Containers', '<rect x="3" y="12" width="8" height="9" rx="1"/><rect x="13" y="12" width="8" height="9" rx="1"/><rect x="8" y="2" width="8" height="8" rx="1"/><path d="M7 15v3m10-3v3M12 5v2"/>'),
    'ship': ('Ship', '<path d="m2 12 10-4 10 4-4 7H6Zm6-3V4h8v5m-4-5V1m0 7v11M2 22l5-1 5 1 5-1 5 1"/>'),
    'satellite': ('Satellite', '<path d="m9 6 9 9-3 3-9-9ZM7 8 2 3l3-2 5 5m6 8 5 5-2 3-5-5M3 13a8 8 0 0 0 8 8m-8-4a4 4 0 0 0 4 4m10-18 4-2-2 4m-3 3 3-3"/>'),
    'upload': ('Upload', '<path d="M12 16V2m-5 5 5-5 5 5M3 15v7h18v-7"/>'),
    'download': ('Download', '<path d="M12 2v14m-5-5 5 5 5-5M3 15v7h18v-7"/>'),
    'sync': ('Sync', '<path d="M3 10a9 9 0 0 1 16-4l2 3m0-6v6h-6M21 14a9 9 0 0 1-16 4l-2-3m0 6v-6h6"/>'),
    'gauge': ('Gauge', '<path d="M4 19a10 10 0 1 1 16 0ZM12 13l5-6M5 12h1m12 0h1M7 6l1 1m4-4v2"/><circle cx="12" cy="13" r="2"/>'),
    # Files, screens and organization.
    'laptop': ('Laptop', '<rect x="4" y="3" width="16" height="13" rx="1"/><path d="m4 16-3 5h22l-3-5M9 21h6"/>'),
    'keyboard': ('Keyboard', '<rect x="1" y="5" width="22" height="14" rx="2"/><path d="M5 9h1m3 0h1m3 0h1m3 0h1M5 13h1m3 0h1m3 0h1m3 0h1M8 16h8"/>'),
    'mouse': ('Mouse', '<rect x="6" y="2" width="12" height="20" rx="6"/><path d="M6 10h12M12 2v8m0-5v2"/>'),
    'window': ('Window', '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M2 8h20M6 5h1m3 0h1"/>'),
    'browser': ('Browser', '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M2 8h20M6 5h1m3 0h8m-5 6-4 4 4 4m-4-4h9"/>'),
    'layout': ('Layout', '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M2 9h20M9 9v12"/>'),
    'layers': ('Layers', '<path d="m12 2 10 5-10 5L2 7Zm-10 10 10 5 10-5M2 17l10 5 10-5"/>'),
    'archive': ('Archive', '<path d="M4 8v14h16V8M2 3h20v5H2Zm7 10h6"/>'),
    'clipboard': ('Clipboard', '<path d="M8 4H4v18h16V4h-4"/><rect x="8" y="2" width="8" height="5" rx="1"/><path d="M8 12h8m-8 5h8"/>'),
    'checklist': ('Checklist', '<path d="m2 5 2 2 4-4m3 2h11M2 12l2 2 4-4m3 2h11M2 19l2 2 4-4m3 2h11"/>'),
    'calendar': ('Calendar', '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M7 2v5m10-5v5M3 10h18M7 14h1m4 0h1m4 0h1M7 18h1m4 0h1"/>'),
    'clock': ('Clock', '<circle cx="12" cy="12" r="10"/><path d="M12 5v7l5 3"/>'),
    'search': ('Search', '<circle cx="10" cy="10" r="7"/><path d="m15 15 7 7"/>'),
    'chart': ('Chart', '<path d="M3 2v20h19M7 17v-5m5 5V6m5 11V9"/>'),
    'compass': ('Compass', '<circle cx="12" cy="12" r="10"/><path d="m16 7-3 7-6 3 3-7Z"/>'),
    # General-purpose, people and hobbies.
    'flag': ('Flag', '<path d="M4 22V2m0 1h8l2 3h7l-2 9h-7l-2-3H4"/>'),
    'pin': ('Pin', '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>'),
    'bookmark': ('Bookmark', '<path d="M6 2h12v20l-6-5-6 5Z"/>'),
    'tag': ('Tag', '<path d="M2 3h9l11 11-8 8L2 10Z"/><circle cx="7" cy="7" r="1"/>'),
    'bell': ('Bell', '<path d="M4 17h16l-3-4V8a5 5 0 0 0-10 0v5Zm6 4h4M12 1v2"/>'),
    'mail': ('Mail', '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 5 10 8L22 5M2 19l7-7m13 7-7-7"/>'),
    'chat': ('Chat', '<path d="M3 3h18v14H9l-6 5Zm4 5h10M7 12h7"/>'),
    'users': ('People', '<circle cx="9" cy="7" r="4"/><path d="M2 22v-4a7 7 0 0 1 14 0v4M17 3a4 4 0 0 1 0 8m2 3a6 6 0 0 1 3 5v3"/>'),
    'user': ('Person', '<circle cx="12" cy="7" r="5"/><path d="M3 22v-3a9 7 0 0 1 18 0v3"/>'),
    'gamepad': ('Gamepad', '<path d="M7 7h10c4 0 6 7 5 12-1 4-5-2-6-2H8c-1 0-5 6-6 2C1 14 3 7 7 7ZM12 7V3"/><path d="M5 12h6m-3-3v6m8-3h1m2 3h1"/>'),
    'music': ('Music', '<path d="M10 18V5l11-3v13M10 9l11-3"/><ellipse cx="6" cy="18" rx="4" ry="3"/><ellipse cx="17" cy="15" rx="4" ry="3"/>'),
    'camera': ('Camera', '<path d="M2 7h5l2-4h6l2 4h5v14H2Z"/><circle cx="12" cy="13" r="4"/>'),
    'image': ('Image', '<rect x="2" y="2" width="20" height="20" rx="2"/><circle cx="8" cy="8" r="2"/><path d="m2 18 6-6 5 5 4-6 5 7"/>'),
    'heart': ('Heart', '<path d="M12 21 3 12C-2 5 7-1 12 6c5-7 14-1 9 6Z"/>'),
    'leaf': ('Leaf', '<path d="M3 21C-1 5 10 3 22 2c-1 12-3 22-19 19ZM3 21 17 7M9 15V9m0 6h6"/>'),
}
CATALOG = {**GENERIC, **SYMBOLS, **MORE_SYMBOLS}

# Search aliases stay separate from the persisted IDs and display labels.
KEYWORDS = {
    'circle': 'round shape', 'diamond': 'shape gem', 'square': 'shape box',
    'triangle': 'shape', 'hexagon': 'shape', 'star': 'favorite favourite shape',
    'cross': 'plus shape', 'pentagon': 'shape', 'rings': 'circles shape linked',
    'grid': 'tiles dashboard shape', 'target': 'goal focus shape', 'cube': '3d shape box',
    'terminal': 'ssh remote console shell bash command powershell',
    'folder': 'directory project files', 'code': 'development programming source python javascript',
    'branch': 'git version control repository', 'server': 'ssh remote host backend infrastructure',
    'database': 'sql data backend', 'cloud': 'hosting remote infrastructure',
    'globe': 'web internet website world', 'home': 'house local personal',
    'briefcase': 'work business office', 'tools': 'wrench repair maintenance build',
    'gear': 'settings configure configuration', 'rocket': 'launch deploy release',
    'bolt': 'lightning fast power', 'shield': 'security protection', 'lock': 'security password private',
    'key': 'ssh security credentials authentication password', 'bug': 'debug issue error testing',
    'flask': 'python experiment science lab testing', 'book': 'documentation help reading learning',
    'document': 'file text notes', 'package': 'dependencies install distribution build',
    'monitor': 'desktop display computer screen', 'coffee': 'break drink personal',
    'brackets': 'development programming markup html', 'binary': 'bits data programming',
    'braces': 'json programming development', 'script': 'bash shell python automation file',
    'function': 'math programming development', 'variable': 'math programming development',
    'merge': 'git version control repository', 'commit': 'git version control repository',
    'pull-request': 'git review version control repository', 'puzzle': 'plugin extension module',
    'circuit': 'hardware electronics connection', 'chip': 'cpu hardware processor electronics',
    'robot': 'ai artificial intelligence assistant automation bot', 'wand': 'magic automation generate',
    'test-tube': 'testing experiment lab science', 'network': 'lan connection infrastructure remote',
    'router': 'lan internet connection infrastructure', 'wifi': 'wireless internet network',
    'antenna': 'wireless radio signal broadcast', 'plug': 'power connect electricity',
    'cable': 'usb connect wire hardware', 'hard-drive': 'disk backup storage hardware',
    'storage': 'disk data backup infrastructure', 'containers': 'docker development services deployment',
    'ship': 'shipping deployment transport docker', 'satellite': 'remote communications space',
    'upload': 'push transfer publish backup', 'download': 'pull transfer fetch install',
    'sync': 'refresh repeat update synchronize synchronise', 'gauge': 'performance speed metrics monitor',
    'laptop': 'computer portable screen hardware', 'keyboard': 'typing input hardware',
    'mouse': 'input pointer hardware', 'window': 'application desktop screen',
    'browser': 'web website internet frontend', 'layout': 'dashboard panels interface design',
    'layers': 'stack design collection', 'archive': 'backup zip compress files',
    'clipboard': 'copy paste notes', 'checklist': 'tasks todo done check testing',
    'calendar': 'date schedule events', 'clock': 'time schedule history', 'search': 'find filter lookup',
    'chart': 'graph metrics analytics statistics', 'compass': 'navigation directions explore',
    'flag': 'milestone goal marker', 'pin': 'location map marker', 'bookmark': 'favorite favourite saved',
    'tag': 'label release category', 'bell': 'notification alert reminder', 'mail': 'email inbox message',
    'chat': 'message conversation support', 'users': 'team group collaboration people',
    'user': 'person profile account personal', 'gamepad': 'gaming games controller entertainment',
    'music': 'audio sound entertainment', 'camera': 'photo photography capture',
    'image': 'picture photo graphics design', 'heart': 'favorite favourite health personal',
    'leaf': 'nature environment garden personal',
}


def search_text(key):
    return f'{key} {CATALOG[key][0]} {KEYWORDS.get(key, "")}'.casefold()


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


