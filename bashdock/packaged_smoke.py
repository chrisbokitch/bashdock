"""Exercise the packaged shell backend without opening the desktop window."""
import json
import queue
import threading
import traceback
from pathlib import Path

from . import config
from .shell_backend import spawn_shell


def run(report_path, timeout=25):
    results = queue.Queue()

    def exercise():
        process = init_file = None
        try:
            settings = config.load()
            bash = settings["bash_path"] or config.find_bash()
            if not bash:
                raise RuntimeError("Git Bash was not found. Configure its executable in BashDock first.")
            process, init_file = spawn_shell(bash, str(Path.home()), (24, 80))
            # The complete marker never appears in terminal echo of the input command.
            process.write("HISTFILE=/dev/null; printf 'BASHDOCK_%s\\n' 'PACKAGED_SHELL_READY'\r")
            output = ""
            while "BASHDOCK_PACKAGED_SHELL_READY" not in output:
                chunk = process.read(4096)
                if not chunk:
                    raise RuntimeError("Shell closed before responding to the test command.")
                output = (output + chunk)[-65536:]
            process.write("exit\r")
            results.put({"ok": True, "message": "Packaged Git Bash accepts input and produces output."})
        except Exception:
            results.put({"ok": False, "error": traceback.format_exc()})
        finally:
            if process:
                try:
                    process.close(force=True)
                except Exception:
                    pass
            if init_file:
                init_file.unlink(missing_ok=True)

    worker = threading.Thread(target=exercise, daemon=True)
    worker.start()
    try:
        report = results.get(timeout=timeout)
    except queue.Empty:
        report = {"ok": False, "error": "Timed out waiting for packaged Git Bash to accept input and produce output."}
    destination = Path(report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    worker.join(timeout=1)
    return 0 if report["ok"] else 1
