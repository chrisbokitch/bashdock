import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bashdock import config


class ConfigTests(unittest.TestCase):
    def test_tab_ids_are_unique_uuids_and_legacy_saved_profiles_share_live_identity(self):
        from uuid import UUID
        import copy

        first, second = config.default_tab(), config.default_tab()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(4, UUID(first["id"]).version)
        old = config.defaults()
        old["tabs"] = [copy.deepcopy(first)]
        for tab in old["tabs"]:
            del tab["id"]
        old["workspaces"] = [{"name": "Legacy project", "tabs": [copy.deepcopy(old["tabs"][0])], "active_tab": 0}]
        migrated = config.migrate(old)
        ids = [tab["id"] for tab in migrated["tabs"]]
        self.assertEqual(ids[0], migrated["workspaces"][0]["tabs"][0]["id"])
        self.assertNotIn("id", old["tabs"][0])
        self.assertEqual(migrated, config.migrate(migrated))
        ambiguous = copy.deepcopy(old)
        ambiguous["tabs"].append(copy.deepcopy(ambiguous["tabs"][0]))
        migrated_ambiguous = config.migrate(ambiguous)
        open_ids = [tab["id"] for tab in migrated_ambiguous["tabs"]]
        self.assertEqual(2, len(set(open_ids)))
        self.assertNotIn(migrated_ambiguous["workspaces"][0]["tabs"][0]["id"], open_ids)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config.save(migrated, path)
            self.assertEqual(migrated, config.read(path))

    def test_invalid_ids_and_repeated_ids_in_a_group_are_rejected_but_shared_workspaces_are_valid(self):
        import copy
        data = config.defaults()
        for identity in (None, 1, "not-a-uuid"):
            data["tabs"][0]["id"] = identity
            with self.assertRaises(ValueError):
                config.validate(data)
        data = config.defaults()
        data["tabs"].append(copy.deepcopy(data["tabs"][0]))
        with self.assertRaises(ValueError):
            config.validate(data)
        data["tabs"].pop()
        for name in ("Project A", "Project B"):
            data["workspaces"].append({"name": name, "tabs": copy.deepcopy(data["tabs"]), "active_tab": 0})
        config.validate(data)

    def test_saved_workspaces_roundtrip_and_older_settings_gain_empty_library(self):
        data = config.defaults()
        data["workspaces"] = [{"name": "BashDock Development", "tabs": [config.default_tab("App"),
                                  config.default_tab("Droplet")], "active_tab": 1}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config.save(data, path)
            self.assertEqual(data, config.read(path))
        old = config.defaults()
        del old["workspaces"]
        self.assertEqual([], config.migrate(old)["workspaces"])
        self.assertNotIn("workspaces", old)

    def test_invalid_saved_workspaces_are_rejected(self):
        valid = {"name": "Project", "tabs": [config.default_tab()], "active_tab": 0}
        for entries in (None, {}, [None], [dict(valid, name=" ")], [dict(valid, tabs=[])],
                        [dict(valid, active_tab=True)], [dict(valid, active_tab=1)],
                        [valid, dict(valid, name=" project ")], [dict(valid, tabs=[{}])]):
            data = config.defaults()
            data["workspaces"] = entries
            with self.assertRaises(ValueError):
                config.validate(data)

    def test_imports_gitbasher_workspace_once_and_keeps_original(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict("os.environ", {"APPDATA": directory}):
            legacy = Path(directory) / "gitbasher/settings.json"
            data = config.defaults()
            data["tabs"].append(config.default_tab("Build"))
            data["active_tab"] = 1
            data["confirm_on_exit"] = False
            config.save(data, legacy)
            original = legacy.read_bytes()
            self.assertEqual(Path(directory) / "bashdock/settings.json", config.config_path())
            self.assertEqual(data, config.load())
            self.assertEqual(original, legacy.read_bytes())
            changed = config.defaults()
            config.save(changed)
            self.assertEqual(changed, config.load())

    def test_invalid_gitbasher_workspace_does_not_create_new_settings(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict("os.environ", {"APPDATA": directory}):
            legacy = Path(directory) / "gitbasher/settings.json"
            legacy.parent.mkdir()
            legacy.write_text('{"version": 999}', encoding="utf-8")
            with self.assertRaises(ValueError):
                config.load()
            self.assertFalse(config.config_path().exists())

    def test_roundtrip_preserves_unicode_order_and_multiline_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/settings.json"
            data = config.defaults()
            data["tabs"][0]["buttons"] = [{"label": "Dévelop", "command": "cd '/c/Development/my repo'\ngit status"},
                               {"label": "Next", "command": "printf '%s' '$HOME'"}]
            config.save(data, path)
            self.assertEqual(data, config.load(path))

    def test_replace_failure_preserves_existing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config.save(config.defaults(), path)
            original = path.read_bytes()
            changed = config.defaults()
            changed["tabs"][0]["buttons"] = []
            with patch("bashdock.config.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    config.save(changed, path)
            self.assertEqual(original, path.read_bytes())
            self.assertEqual({path, config.backup_path(path)}, set(path.parent.iterdir()))

    def test_automatic_backup_keeps_previous_valid_settings_and_ignores_noop_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            first = config.defaults()
            config.save(first, path)
            self.assertEqual(first, config.read(config.backup_path(path)))
            second = config.defaults()
            second["tabs"][0]["name"] = "Changed workspace"
            config.save(second, path)
            config.save(second, path)
            self.assertEqual(first, config.read(config.backup_path(path)))
            self.assertEqual(second, config.read(path))

    def test_saving_over_damaged_settings_preserves_bytes_and_good_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            good = config.defaults()
            config.save(good, path)
            damaged = b'\xff{"broken":'
            path.write_bytes(damaged)
            recovered = config.defaults()
            recovered["tabs"][0]["name"] = "Recovered"
            config.save(recovered, path)
            self.assertEqual(good, config.read(config.backup_path(path)))
            self.assertEqual(recovered, config.read(path))
            archives = list((path.parent / "backups").glob("settings-damaged-*.json"))
            self.assertEqual(1, len(archives))
            self.assertEqual(damaged, archives[0].read_bytes())

    def test_existing_unchanged_settings_gain_backup_and_primary_replace_failure_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            data = config.defaults()
            config.save(data, path, backup=False)
            original = path.read_bytes()
            config.save(data, path)
            self.assertEqual(original, config.backup_path(path).read_bytes())
            changed = config.defaults()
            changed["tabs"][0]["name"] = "New name"
            real_replace = config.os.replace

            def fail_primary(source, target):
                if target == path:
                    raise PermissionError("primary locked")
                real_replace(source, target)

            with patch("bashdock.config.os.replace", side_effect=fail_primary):
                with self.assertRaises(PermissionError):
                    config.save(changed, path)
            self.assertEqual(original, path.read_bytes())
            self.assertEqual(original, config.backup_path(path).read_bytes())
            self.assertFalse(list(path.parent.glob("settings-*.tmp")))

    def test_backup_failure_aborts_save_without_touching_primary_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config.save(config.defaults(), path)
            original = path.read_bytes()
            changed = config.defaults()
            changed["tabs"][0]["name"] = "Changed"
            real_write = config.atomic_write

            def fail_backup(target, content):
                if target == config.backup_path(path):
                    raise PermissionError("backup locked")
                real_write(target, content)

            with patch("bashdock.config.atomic_write", side_effect=fail_backup):
                with self.assertRaises(PermissionError):
                    config.save(changed, path)
            self.assertEqual(original, path.read_bytes())

    def test_import_requires_existing_valid_file_and_export_does_not_create_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.json"
            with self.assertRaises(FileNotFoundError):
                config.read(path)
            config.save(config.defaults(), path, backup=False)
            self.assertEqual([path], list(path.parent.iterdir()))
            path.write_text('{"version": 999}', encoding="utf-8")
            with self.assertRaises(ValueError):
                config.read(path)

    def test_invalid_settings_do_not_get_overwritten_on_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"buttons": 42}', encoding="utf-8")
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                config.load(path)
            self.assertEqual(original, path.read_bytes())

    def test_rejects_embedded_terminal_controls_but_allows_bash_syntax(self):
        for command in ("pwd\x03", "\x1b[31m", "echo\x00bad"):
            data = config.defaults()
            data["tabs"][0]["buttons"][0]["command"] = command
            with self.assertRaises(ValueError):
                config.validate(data)
        data["tabs"][0]["buttons"][0]["command"] = "export NAME='a b'\nprintf '%s\\n' \"$NAME\""
        config.validate(data)

    def test_migrates_original_single_shell_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            old = {"bash_path": "C:/Git/bin/bash.exe", "startup_folder": "C:/Development",
                   "buttons": [{"label": "Tests", "command": "python -m unittest"}]}
            path.write_text(json.dumps(old), encoding="utf-8")
            data = config.load(path)
            self.assertEqual(old["buttons"], data["tabs"][0]["buttons"])
            self.assertEqual(old["startup_folder"], data["tabs"][0]["current_folder"])
            self.assertEqual(old, json.loads(path.read_text()))
            config.save(data, path)
            self.assertEqual(data, config.load(path))

    def test_workspace_roundtrip_and_independent_default_button_lists(self):
        data = config.defaults()
        data["tabs"].append(config.default_tab("Build"))
        data["active_tab"] = 1
        data["tabs"][1]["current_folder"] = "C:/Development/build"
        data["tabs"][1]["buttons"][0]["command"] = "make"
        self.assertNotEqual(data["tabs"][0]["buttons"], data["tabs"][1]["buttons"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config.save(data, path)
            self.assertEqual(data, config.load(path))

    def test_invalid_tab_and_future_version_are_rejected(self):
        for key, value in (("version", 999), ("tabs", []), ("active_tab", -1), ("active_tab", True)):
            data = config.defaults()
            data[key] = value
            with self.assertRaises(ValueError):
                config.validate(data)

    def test_existing_workspace_defaults_to_confirmation_and_rejects_nonboolean(self):
        old = config.defaults()
        del old["confirm_on_exit"]
        self.assertTrue(config.migrate(old)["confirm_on_exit"])
        self.assertNotIn("confirm_on_exit", old)
        for value in ("false", 0, None):
            data = config.defaults()
            data["confirm_on_exit"] = value
            with self.assertRaises(ValueError):
                config.validate(data)

    def test_update_preferences_migrate_validate_and_survive_export(self):
        data = config.defaults()
        data.pop('updates')
        migrated = config.migrate(data)
        self.assertEqual({'automatic': True, 'download': True}, migrated['updates'])
        migrated['updates'] = {'automatic': False, 'download': False}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            config.save(migrated, path)
            self.assertEqual(migrated['updates'], config.read(path)['updates'])
        for invalid in (None, [], {'automatic': 1}, {'download': 'yes'}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                config.validate(dict(migrated, updates=invalid))


if __name__ == "__main__":
    unittest.main()
