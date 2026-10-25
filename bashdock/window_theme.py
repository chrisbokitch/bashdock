"""Apply native Windows caption colors without replacing the system title bar."""
import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget


class TitlebarTheme(QObject):
    """Theme each app window when its native handle is available, including modal dialogs."""
    def eventFilter(self, watched, event):
        if (sys.platform == "win32" and event.type() == QEvent.Type.Show
                and isinstance(watched, QWidget) and watched.isWindow()
                and watched.windowType() not in (Qt.WindowType.Popup, Qt.WindowType.ToolTip)):
            apply_titlebar(int(watched.winId()))
        return False


def install_titlebar_theme(app):
    if sys.platform != "win32":
        return
    if getattr(app, "_bashdock_titlebar_theme", None) is None:
        # Qt-owned file/folder and colour pickers can use the same caption theme
        # as our other dialogs; OS-owned common dialogs cannot use this filter.
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
        theme = TitlebarTheme(app)
        app.installEventFilter(theme)
        app._bashdock_titlebar_theme = theme


def colorref(hex_color):
    red, green, blue = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return red | (green << 8) | (blue << 16)


def apply_titlebar(hwnd):
    if sys.platform != "win32":
        return False
    try:
        dwm = ctypes.WinDLL("dwmapi", use_last_error=True)
        set_attribute = dwm.DwmSetWindowAttribute
        set_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        set_attribute.restype = ctypes.c_int32

        def apply(attribute, value):
            payload = ctypes.c_uint32(value)
            return set_attribute(hwnd, attribute, ctypes.byref(payload), ctypes.sizeof(payload)) == 0

        # Older Windows versions may only support the dark-mode hint. Unsupported
        # attributes return an HRESULT; leave the native title bar functional.
        dark = apply(20, 1)  # DWMWA_USE_IMMERSIVE_DARK_MODE
        caption = apply(35, colorref("181e29"))  # DWMWA_CAPTION_COLOR, Windows 11+
        apply(36, colorref("dde4ef"))  # DWMWA_TEXT_COLOR, Windows 11+
        return dark or caption
    except (OSError, AttributeError):
        return False
