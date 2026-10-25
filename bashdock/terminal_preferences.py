"""Defaults and validation shared by storage, the dialog, and terminal bridge."""
import re


def defaults():
    return {"font_family": "Cascadia Mono", "font_size": 15,
            "foreground": "#dde4ef", "background": "#10141c", "cursor_color": "#70dcc2",
            "selection_color": "#365e66", "cursor_style": "block", "cursor_blink": True,
            "scrollback": 10000, "copy_on_select": False, "right_click_paste": False}


def validated(settings):
    if not isinstance(settings, dict):
        raise ValueError("Terminal settings must be an object.")
    result = defaults()
    result.update({key: value for key, value in settings.items() if key in result})
    family = result["font_family"]
    if not isinstance(family, str) or not family.strip() or len(family) > 128 or any(ord(c) < 32 for c in family):
        raise ValueError("Terminal font must be a nonempty font family name.")
    for key, low, high in (("font_size", 8, 48), ("scrollback", 0, 100000)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError(f"Terminal {key} must be between {low} and {high}.")
    for key in ("foreground", "background", "cursor_color", "selection_color"):
        if not isinstance(result[key], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", result[key]):
            raise ValueError(f"Terminal {key} must be a six-digit hex colour.")
    if result["cursor_style"] not in ("block", "underline", "bar"):
        raise ValueError("Invalid terminal cursor style.")
    for key in ("cursor_blink", "copy_on_select", "right_click_paste"):
        if type(result[key]) is not bool:
            raise ValueError(f"Terminal {key} must be a boolean.")
    return result


def effective(tab, app_defaults):
    """A custom tab preset is independent of later changes to app defaults."""
    override = tab.get("terminal")
    return validated(app_defaults if override is None else override)
