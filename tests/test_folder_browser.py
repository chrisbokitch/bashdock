"""Explorer receives the exact native folder, never a default or file URL."""
import ntpath
import unittest
from unittest.mock import patch, call
from bashdock import folder_browser


class FolderBrowserTests(unittest.TestCase):
    def test_distinct_drive_and_unc_paths_use_native_folder_verb_without_url_conversion(self):
        folders = ['C:/Development/bashdock', 'D:/Website & café/#draft, 100%', '//server/share/Project A']
        expected = [r'C:\Development\bashdock', 'D:\\Website & café\\#draft, 100%', r'\\server\share\Project A']
        with patch.object(folder_browser.sys, 'platform', 'win32'), patch.object(folder_browser.os.path, 'isdir', return_value=True), patch.object(folder_browser.os, 'startfile', create=True) as launch:
            for folder in folders:
                folder_browser.open_folder(folder)
        self.assertEqual([call(ntpath.join(path, ''), 'explore') for path in expected], launch.call_args_list)

    def test_extensionless_folder_and_dot_com_sibling_are_explicit_directories(self):
        folders = ['C:/Development/bashdock', 'C:/Development/bashdock.com', 'C:/Users/chris',
                   'C:/Development/bashdock/', 'C:/', '//server/share/']
        expected = ['C:\\Development\\bashdock\\', 'C:\\Development\\bashdock.com\\',
                    'C:\\Users\\chris\\', 'C:\\Development\\bashdock\\', 'C:\\', '\\\\server\\share\\']
        with patch.object(folder_browser.sys, 'platform', 'win32'), patch.object(folder_browser.os.path, 'isdir', return_value=True), patch.object(folder_browser.os, 'startfile', create=True) as launch:
            for folder in folders:
                folder_browser.open_folder(folder)
        self.assertEqual([call(path, 'explore') for path in expected], launch.call_args_list)

    def test_invalid_and_missing_folders_do_not_open_a_default_folder(self):
        with patch.object(folder_browser.sys, 'platform', 'win32'), patch.object(folder_browser.os, 'startfile', create=True) as launch:
            for folder in ('', 'relative', 'C:relative', '/not-a-drive', 'C:/bad\npath'):
                with self.subTest(folder=folder), self.assertRaises(ValueError):
                    folder_browser.open_folder(folder)
            with patch.object(folder_browser.os.path, 'isdir', return_value=False):
                with self.assertRaisesRegex(ValueError, 'no longer exists'):
                    folder_browser.open_folder('C:/removed')
        launch.assert_not_called()

    def test_native_launch_errors_are_propagated_without_fallback(self):
        with patch.object(folder_browser.sys, 'platform', 'win32'), patch.object(folder_browser.os.path, 'isdir', return_value=True), patch.object(folder_browser.os, 'startfile', create=True, side_effect=OSError('Access denied')) as launch:
            with self.assertRaisesRegex(OSError, 'Access denied'):
                folder_browser.open_folder('C:/Project')
        launch.assert_called_once_with('C:\\Project\\', 'explore')
