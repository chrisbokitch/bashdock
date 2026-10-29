"""Open a specific Windows directory without URL/default-document dispatch."""
import ntpath
import os
import sys

from .shell_integration import valid_reported_directory


def open_folder(folder):
    if sys.platform != 'win32':
        raise RuntimeError('Opening a folder in Explorer requires Windows.')
    if not valid_reported_directory(folder):
        raise ValueError('The tab does not have an absolute Windows folder path.')
    path = ntpath.normpath(folder)
    if not os.path.isdir(path):
        raise ValueError(f"The tab's current directory no longer exists: {folder}")
    # Use the documented folder-specific verb with a native path on the GUI
    # thread, rather than Qt's worker-thread/default file-URL dispatch. No
    # command line, URL parsing, working-directory fallback, or shell expansion.
    # Keep the final separator: an extensionless name beside e.g. name.com
    # must be treated as a directory, not an executable name to resolve.
    os.startfile(ntpath.join(path, ''), 'explore')
