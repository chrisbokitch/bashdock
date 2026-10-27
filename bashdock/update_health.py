"""Write the startup receipt only inside this installation's update caches."""
import json
from pathlib import Path
import re
import secrets

from .input_diagnostics import recorder
from .local_updates import inbox_root
from .updates import cache_directory


def acknowledge_startup(arguments, *, installation, version):
    try:
        path = Path(arguments[arguments.index('--update-health') + 1]).resolve()
        token = arguments[arguments.index('--update-token') + 1]
    except (ValueError, IndexError):
        recorder.record('update_health', accepted=False, written=False)
        return False
    public = path.is_relative_to(cache_directory().resolve())
    local = (path.parent.parent == inbox_root(installation) and
             re.fullmatch(r'pending-[a-zA-Z0-9_-]+', path.parent.name) is not None)
    accepted = (path.name == 'health.json' and (public or local) and
                re.fullmatch('[0-9a-f]{64}', token) is not None)
    if not accepted:
        recorder.record('update_health', accepted=False, written=False, local=local, public=public)
        return False
    temporary = path.with_name('.health-' + secrets.token_hex(8) + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump({'token': token, 'version': version}, stream)
        temporary.replace(path)
        recorder.record('update_health', accepted=True, written=True, local=local, public=public)
        return True
    except OSError as error:
        recorder.record('update_health', accepted=True, written=False, local=local, public=public,
                        errno=getattr(error, 'errno', None), winerror=getattr(error, 'winerror', None))
        raise
    finally:
        temporary.unlink(missing_ok=True)
