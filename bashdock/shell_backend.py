"""Shared shell startup used by the desktop app and packaged build smoke test."""
import os
import sys
from pathlib import Path

from .shell_integration import create_init_file


def spawn_shell(bash_path, folder, dimensions, *, session_id=""):
    if sys.platform != "win32":
        raise RuntimeError("BashDock currently requires Windows 10/11.")
    import winpty
    if getattr(sys, "frozen", False):
        native_root = Path(winpty.__file__).parent
        missing = [name for name in ("conpty.dll", "OpenConsole.exe")
                   if not (native_root / name).is_file()]
        if missing:
            raise RuntimeError("Packaged terminal helper files are missing: " + ", ".join(missing)
                               + ". Rebuild and keep the entire dist/bashdock folder together.")
    env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor", CHERE_INVOKING="1",
               BASHDOCK_START_DIR=Path(folder).as_posix(), BASHDOCK_SESSION=session_id)
    init_file = create_init_file()
    try:
        process = winpty.PtyProcess.spawn(
            [bash_path, "--rcfile", init_file.as_posix(), "-i"], cwd=folder, env=env,
            dimensions=dimensions, backend=winpty.Backend.ConPTY,
        )
        return process, init_file
    except Exception:
        init_file.unlink(missing_ok=True)
        raise
