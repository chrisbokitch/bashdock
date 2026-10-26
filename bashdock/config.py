"""Validated settings; atomic writes leave previous settings intact on failure."""
import json
import copy
import os
import shutil
import tempfile
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pathlib import Path
from . import terminal_preferences


def config_path():
    root = Path(os.environ.get("APPDATA", Path.home() / ".config"))
    return root / "bashdock" / "settings.json"


def default_tab(name="Git Bash"):
    return {"id": str(uuid4()), "name": name, "startup_folder": str(Path.home()),
            "current_folder": str(Path.home()), "buttons": [
        {"label": "Status", "command": "git status --short --branch"},
        {"label": "Diff", "command": "git diff"},
        {"label": "Log", "command": "git log --oneline -15"},
        {"label": "Clear", "command": "clear"},
    ]}


def defaults():
    return {"version": 2, "bash_path": "", "tabs": [default_tab()], "active_tab": 0,
            "confirm_on_exit": True, "terminal": terminal_preferences.defaults(), "workspaces": [],
            "updates": {"automatic": True, "download": True}}


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
    if "id" in tab:
        try:
            if not isinstance(tab["id"], str):
                raise ValueError()
            UUID(tab["id"])
        except (ValueError, AttributeError):
            raise ValueError("Tab IDs must be valid UUIDs.") from None
    for key in ("name", "startup_folder", "current_folder"):
        if not isinstance(tab.get(key), str) or not tab[key].strip():
            raise ValueError(f"Tab {key} must be a nonempty string.")
    validate_buttons(tab.get("buttons"))
    if tab.get("terminal") is not None:
        terminal_preferences.validated(tab["terminal"])


def validate_tab_group(tabs):
    ids = set()
    for tab in tabs:
        validate_tab(tab)
        if "id" in tab:
            identity = str(UUID(tab["id"]))
            if identity in ids:
                raise ValueError("The same tab cannot appear twice in one tab group.")
            ids.add(identity)


def assign_tab_ids(data):
    """Migrate old profiles, linking identical saved/open profiles when possible."""
    groups = [data["tabs"]] + [workspace["tabs"] for workspace in data["workspaces"]]
    identities = {}

    def signature(tab):
        return json.dumps({k: v for k, v in tab.items() if k != "id"}, sort_keys=True)

    # Prefer explicit identities, including those in saved workspaces.
    for tabs in groups:
        for tab in tabs:
            if "id" in tab:
                tab["id"] = str(UUID(tab["id"]))
                candidates = identities.setdefault(signature(tab), [])
                if tab["id"] not in candidates:
                    candidates.append(tab["id"])
    for tabs in groups:
        used = {tab["id"] for tab in tabs if "id" in tab}
        for tab in tabs:
            if "id" not in tab:
                candidates = identities.setdefault(signature(tab), [])
                # An old profile matching multiple identities is ambiguous; do
                # not guess which running shell it was meant to refer to.
                identity = candidates[0] if len(candidates) == 1 and candidates[0] not in used else None
                tab["id"] = identity or str(uuid4())
                if tab["id"] not in candidates:
                    candidates.append(tab["id"])
                used.add(tab["id"])
    return data


def validate_workspaces(workspaces):
    if not isinstance(workspaces, list):
        raise ValueError("Saved workspaces must be a list.")
    names = set()
    for workspace in workspaces:
        if not isinstance(workspace, dict):
            raise ValueError("Each saved workspace must be an object.")
        name = workspace.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Each workspace needs a name.")
        if name.strip().casefold() in names:
            raise ValueError("Workspace names must be unique.")
        names.add(name.strip().casefold())
        tabs = workspace.get("tabs")
        if not isinstance(tabs, list) or not tabs:
            raise ValueError("Each workspace needs at least one tab.")
        validate_tab_group(tabs)
        active = workspace.get("active_tab")
        if type(active) is not int or not 0 <= active < len(tabs):
            raise ValueError("The workspace's active tab must be one of its saved tabs.")


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("Settings must be a JSON object.")
    if data.get("version") != 2:
        raise ValueError("Unsupported settings version.")
    if not isinstance(data.get("bash_path"), str):
        raise ValueError("bash_path must be a string.")
    if type(data.get("confirm_on_exit", True)) is not bool:
        raise ValueError("confirm_on_exit must be a boolean.")
    terminal_preferences.validated(data.get("terminal", {}))
    updates = data.get("updates", {"automatic": True, "download": True})
    if not isinstance(updates, dict) or any(type(updates.get(k, True)) is not bool for k in ("automatic", "download")):
        raise ValueError("Update preferences must be booleans.")
    validate_workspaces(data.get("workspaces", []))
    if not isinstance(data.get("tabs"), list) or not data["tabs"]:
        raise ValueError("At least one tab is required.")
    validate_tab_group(data["tabs"])
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
                         "active_tab": 0, "confirm_on_exit": True,
                         "terminal": terminal_preferences.defaults(), "workspaces": [],
                         "updates": {"automatic": True, "download": True}})
    if isinstance(data, dict) and data.get("version") == 2:
        data = copy.deepcopy(data)
        data.setdefault("confirm_on_exit", True)
        data.setdefault("workspaces", [])
        if isinstance(data.get("updates", {}), dict):
            data["updates"] = {"automatic": True, "download": True, **data.get("updates", {})}
        data["terminal"] = terminal_preferences.validated(data.get("terminal", {}))
        validate(data)
        return validate(assign_tab_ids(data))
    return validate(data)


def load(path=None):
    if path is None:
        path = config_path()
        legacy = path.parent.parent / "gitbasher" / "settings.json"
        if not path.exists() and legacy.exists():
            # Copy validated settings once; preserve the original for older installs.
            data = read(legacy)
            save(data, path)
            return data
    if not path.exists():
        return defaults()
    return read(path)


def read(path):
    """Read an existing settings file; imports must never default a missing file."""
    return migrate(json.loads(Path(path).read_text(encoding="utf-8")))


def backup_path(path=None):
    path = Path(path or config_path())
    return path.with_name(path.name + ".bak")


def archive_path(label, path=None):
    path = Path(path or config_path())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return path.parent / "backups" / f"settings-{label}-{stamp}-{uuid4().hex[:8]}.json"


def archive_workspace(data, label="before-import"):
    """Keep a separate, non-rotating copy before replacing an open workspace."""
    path = archive_path(label)
    save(data, path, backup=False)
    return path


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix="settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save(data, path=None, *, backup=True):
    validate(data)
    path = Path(path or config_path())
    content = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    previous = path.read_bytes() if path.exists() else None
    if previous == content:
        if backup and not backup_path(path).exists():
            atomic_write(backup_path(path), content)
        return
    if backup:
        if previous is None:
            # Also protect the very first saved workspace.
            atomic_write(backup_path(path), content)
        else:
            try:
                migrate(json.loads(previous.decode("utf-8")))
            except (ValueError, UnicodeError):
                # A damaged file must never replace the last valid backup.
                atomic_write(archive_path("damaged", path), previous)
            else:
                atomic_write(backup_path(path), previous)
    atomic_write(path, content)


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
