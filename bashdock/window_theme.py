"""Apply native Windows caption colors without replacing the system title bar."""
import ctypes
import sys
from ctypes import wintypes


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
