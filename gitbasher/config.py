"""Validated settings; atomic writes leave previous settings intact on failure."""
import json
import os
import shutil
import tempfile
from pathlib import Path


def config_path():
    root = Path(os.environ.get("APPDATA", Path.home() / ".config"))
    return root / "gitbasher" / "settings.json"


def defaults():
    return {"bash_path": "", "startup_folder": str(Path.home()), "buttons": [
        {"label": "Status", "command": "git status --short --branch"},
        {"label": "Diff", "command": "git diff"},
        {"label": "Log", "command": "git log --oneline -15"},
        {"label": "Clear", "command": "clear"},
    ]}


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("Settings must be a JSON object.")
    for key in ("bash_path", "startup_folder"):
        if not isinstance(data.get(key), str):
            raise ValueError(f"{key} must be a string.")
    if not isinstance(data.get("buttons"), list):
        raise ValueError("buttons must be a list.")
    for button in data["buttons"]:
        if not isinstance(button, dict):
            raise ValueError("Each button must have a label and command.")
        if any(not isinstance(button.get(k), str) or not button[k].strip()
               for k in ("label", "command")):
            raise ValueError("Each button needs a nonempty label and command.")
        if any(ord(ch) < 32 and ch not in "\n\t" for ch in button["command"]):
            raise ValueError("Commands cannot contain terminal control characters.")
    return data


def load(path=None):
    path = path or config_path()
    if not path.exists():
        return defaults()
    return validate(json.loads(path.read_text(encoding="utf-8")))


def save(data, path=None):
    validate(data)
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix="settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def find_bash():
    # Never accept WSL's System32/bash.exe as Git Bash.
    roots = [Path(os.environ.get(key, fallback)) for key, fallback in (
        ("ProgramFiles", "C:/Program Files"),
        ("ProgramFiles(x86)", "C:/Program Files (x86)"),
        ("LOCALAPPDATA", str(Path.home() / "AppData/Local")),
    )]
    candidates = [root / sub for root in roots for sub in (
        "Git/bin/bash.exe", "Git/usr/bin/bash.exe", "Programs/Git/bin/bash.exe")]
    git = shutil.which("git.exe")
    if git:
        candidates.insert(0, Path(git).resolve().parent.parent / "bin/bash.exe")
    return next((str(path) for path in candidates if path.is_file()), "")
