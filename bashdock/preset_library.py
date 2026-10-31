"""Portable personal preset groups; importing only defines buttons, never runs them."""
import copy
import json
from pathlib import Path

from . import config
from .command_presets import GROUPS, PresetButton, PresetGroup


FORMAT = 'bashdock-command-presets'


def group_from_tab(name, tab_name, buttons):
    """Copy staged tab buttons into an editable, app-wide personal group."""
    group = dict(name=name.strip(), description=f'Buttons copied from {tab_name.strip()}.',
                 requirements='', buttons=[dict(label=button['label'], command=button['command'],
                                                description=button.get('description', ''),
                                                confirm=button.get('confirm', False),
                                                confirmation_message=button.get('confirmation_message',
                                                    config.DEFAULT_CONFIRMATION_MESSAGE),
                                                timing=button.get('timing', False)) for button in buttons])
    config.validate_preset_groups([group])
    return group


def as_group(group):
    return PresetGroup(group['name'], group['description'], group['requirements'],
                       tuple(PresetButton(button['label'], button['command'],
                                          button.get('description', ''), button.get('confirm', False),
                                          button.get('confirmation_message', config.DEFAULT_CONFIRMATION_MESSAGE),
                                          button.get('timing', False)) for button in group['buttons']))


def copy_builtin(group):
    return dict(name=group.name + ' (copy)', description=group.description,
                requirements=group.requirements,
                buttons=[dict(button.definition(), description=button.description) for button in group.buttons])


def read_import(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('Preset import exceeds the 1 MB limit.')
    document = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or document.get('format') != FORMAT or document.get('version') != 1:
        raise ValueError('Not a supported BashDock preset group file.')
    groups = document.get('groups')
    if not isinstance(groups, list) or not groups:
        raise ValueError('Preset import must include at least one group.')
    config.validate_preset_groups(groups)
    return copy.deepcopy(groups)


def export_bytes(groups):
    if not groups:
        raise ValueError('Choose at least one personal preset group to export.')
    config.validate_preset_groups(groups)
    return (json.dumps(dict(format=FORMAT, version=1, groups=groups),
                       ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def merge(existing, imported, replace=False):
    """Keep all incoming groups; distinguish collisions without changing built-ins."""
    config.validate_preset_groups(existing)
    config.validate_preset_groups(imported)
    result = copy.deepcopy(existing)
    names = {group.name.casefold() for group in GROUPS}
    for incoming in imported:
        name = incoming['name'].strip()
        match = next((i for i, group in enumerate(result)
                      if group['name'].strip().casefold() == name.casefold()), None)
        if match is not None and replace:
            result[match] = copy.deepcopy(incoming)
            continue
        occupied = names | {group['name'].strip().casefold() for group in result}
        if name.casefold() in occupied:
            suffix = 2
            while True:
                postfix = f' (imported {suffix})'
                candidate = name[:100 - len(postfix)] + postfix
                if candidate.casefold() not in occupied:
                    break
                suffix += 1
            incoming = dict(copy.deepcopy(incoming), name=candidate)
        result.append(copy.deepcopy(incoming))
    config.validate_preset_groups(result)
    return result
