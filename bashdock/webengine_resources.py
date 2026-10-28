"""Explicit release WebEngine resources shared by packaging and frozen checks."""
from pathlib import Path

RELEASE_RESOURCES = (
    'icudtl.dat', 'qtwebengine_resources.pak', 'qtwebengine_resources_100p.pak',
    'qtwebengine_resources_200p.pak', 'qtwebengine_devtools_resources.pak', 'v8_context_snapshot.bin',
)
DEBUG_RESOURCES = (
    'qtwebengine_resources.debug.pak', 'qtwebengine_resources_100p.debug.pak',
    'qtwebengine_resources_200p.debug.pak', 'qtwebengine_devtools_resources.debug.pak',
    'v8_context_snapshot.debug.bin',
)
RESOURCE_PREFIXES = ('pyside6/resources/', 'pyside6/qt/resources/')


def resource_name(destination):
    name = destination.replace('\\', '/').lower()
    for prefix in RESOURCE_PREFIXES:
        if name.startswith(prefix) and '/' not in name[len(prefix):]:
            return name[len(prefix):]
    return None


def select_release_resources(entries, *, debug_build):
    if debug_build is not False:
        raise ValueError('BashDock release packaging requires a release Qt build.')
    entries = list(entries)
    resources = {resource_name(e[0]): e for e in entries if resource_name(e[0])}
    missing = [name for name in RELEASE_RESOURCES if name not in resources or
               not Path(resources[name][1]).is_file() or Path(resources[name][1]).stat().st_size == 0]
    if missing:
        raise ValueError('Missing release WebEngine resources: ' + ', '.join(missing))
    unexpected = [name for name in resources if '.debug.' in name and name not in DEBUG_RESOURCES]
    if unexpected:
        raise ValueError('Review unexpected WebEngine debug resources: ' + ', '.join(unexpected))
    removed = [e for e in entries if resource_name(e[0]) in DEBUG_RESOURCES]
    return [e for e in entries if resource_name(e[0]) not in DEBUG_RESOURCES], removed


def validate_runtime_resources(directory, *, debug_build):
    if debug_build is not False:
        raise ValueError('Expected release Qt at runtime.')
    directory = Path(directory)
    missing = [name for name in RELEASE_RESOURCES if not (directory / name).is_file() or
               (directory / name).stat().st_size == 0]
    debug = [p.name for p in directory.glob('*.debug.*')]
    if missing or debug:
        raise ValueError(f'Invalid packaged WebEngine resources: missing={missing}, debug={debug}')
    return list(RELEASE_RESOURCES)
