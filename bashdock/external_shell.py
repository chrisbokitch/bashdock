"""Launch an independent terminal from the active tab's Git installation."""
import os
import ctypes
import subprocess
import sys
from pathlib import Path


def open_external(bash_path, folder):
    if sys.platform != "win32":
        raise RuntimeError("Opening an external shell requires Windows.")
    bash = Path(bash_path)
    if not bash.is_file() or bash.name.lower() != "bash.exe":
        raise ValueError("Git Bash was not found. Choose Git/bin/bash.exe in Configure tab.")
    directory = Path(folder)
    if not directory.is_dir():
        raise ValueError(f"The tab's current directory no longer exists: {folder}")
    # Git installs expose either bin/bash.exe or usr/bin/bash.exe.
    launcher = next((root / "git-bash.exe" for root in (bash.parent.parent, bash.parent.parent.parent)
                     if (root / "git-bash.exe").is_file()), None)
    if launcher:
        args = [str(launcher), f"--cd={directory.as_posix()}"]
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        streams = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        args = [str(bash), "--login", "-i"]
        flags = 0x00000010 | 0x00000200  # CREATE_NEW_CONSOLE | CREATE_NEW_PROCESS_GROUP
        streams = {}  # Let the new console provide interactive standard handles.
    # Do not inherit BashDock's console, pipes, or runtime files. The external
    # shell must remain usable after the app and its embedded sessions close.
    env = dict(os.environ, CHERE_INVOKING="1")
    runtime = getattr(sys, "_MEIPASS", None)
    set_dll_directory = None
    if runtime:
        # PyInstaller's DLL directory is inherited by child processes. Restore
        # normal system lookup for Git, then restore it for BashDock's helpers.
        root = Path(runtime).resolve()
        env["PATH"] = os.pathsep.join(part for part in env.get("PATH", "").split(os.pathsep)
                                     if part and not Path(part).resolve().is_relative_to(root))
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        set_dll_directory = kernel32.SetDllDirectoryW
        set_dll_directory.argtypes = [ctypes.c_wchar_p]
        set_dll_directory.restype = ctypes.c_int
        if not set_dll_directory(None):
            raise OSError("Could not reset the DLL search path for the external shell.")
    try:
        subprocess.Popen(args, cwd=str(directory), env=env,
                         creationflags=flags, close_fds=True, **streams)
    finally:
        if set_dll_directory is not None:
            set_dll_directory(runtime)
