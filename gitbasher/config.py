"""Validated settings; atomic writes leave previous settings intact on failure."""
import json
import copy
import os
import shutil
import tempfile
from pathlib import Path


def config_path():
    root = Path(os.environ.get("APPDATA", Path.home() / ".config"))
    return root / "gitbasher" / "settings.json"


def default_tab(name="Git Bash"):
    return {"name": name, "startup_folder": str(Path.home()),
            "current_folder": str(Path.home()), "buttons": [
        {"label": "Status", "command": "git status --short --branch"},
        {"label": "Diff", "command": "git diff"},
        {"label": "Log", "command": "git log --oneline -15"},
        {"label": "Clear", "command": "clear"},
    ]}


def defaults():
    return {"version": 2, "bash_path": "", "tabs": [default_tab()], "active_tab": 0,
            "confirm_on_exit": True}


def validate_buttons(buttons):
    if not isinstance(buttons, list):
        raise ValueError("buttons must be a list.")
    for button in buttons:
        if not isinstance(button, dict):
            raise ValueError("Each button must have a label and command.")
        if any(not isinstance(button.get(k), str) or not button[k].strip()
               for k in ("label", "command")):
            raise ValueError("Each button needs a nonempty label and command.")
        if any(ord(ch) < 32 and ch not in "\n\t" for ch in button["command"]):
            raise ValueError("Commands cannot contain terminal control characters.")


def validate_tab(tab):
    if not isinstance(tab, dict):
        raise ValueError("Each tab must be an object.")
    for key in ("name", "startup_folder", "current_folder"):
        if not isinstance(tab.get(key), str) or not tab[key].strip():
            raise ValueError(f"Tab {key} must be a nonempty string.")
    validate_buttons(tab.get("buttons"))


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("Settings must be a JSON object.")
    if data.get("version") != 2:
        raise ValueError("Unsupported settings version.")
    if not isinstance(data.get("bash_path"), str):
        raise ValueError("bash_path must be a string.")
    if type(data.get("confirm_on_exit", True)) is not bool:
        raise ValueError("confirm_on_exit must be a boolean.")
    if not isinstance(data.get("tabs"), list) or not data["tabs"]:
        raise ValueError("At least one tab is required.")
    for tab in data["tabs"]:
        validate_tab(tab)
    active = data.get("active_tab")
    if type(active) is not int or not 0 <= active < len(data["tabs"]):
        raise ValueError("active_tab must identify an existing tab.")
    return data


def migrate(data):
    if isinstance(data, dict) and "version" not in data and "tabs" not in data:
        if not isinstance(data.get("bash_path"), str) or not isinstance(data.get("startup_folder"), str):
            raise ValueError("Invalid legacy shell settings.")
        validate_buttons(data.get("buttons"))
        tab = default_tab()
        tab.update(startup_folder=data["startup_folder"], current_folder=data["startup_folder"],
                   buttons=copy.deepcopy(data["buttons"]))
        return validate({"version": 2, "bash_path": data["bash_path"], "tabs": [tab],
                         "active_tab": 0, "confirm_on_exit": True})
    if isinstance(data, dict) and data.get("version") == 2:
        data = dict(data)
        data.setdefault("confirm_on_exit", True)
    return validate(data)


def load(path=None):
    path = path or config_path()
    if not path.exists():
        return defaults()
    return migrate(json.loads(path.read_text(encoding="utf-8")))


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
