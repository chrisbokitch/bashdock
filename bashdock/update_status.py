"""Small native status window; independent of Qt and the installation's DLLs."""
import ctypes
import threading
from ctypes import wintypes as w


class UpdateStatus:
    def __init__(self, title='BashDock update'):
        self.title = title
        self.text = 'Preparing the update…'
        self.ready = threading.Event()
        self.stopped = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, name='update-status', daemon=True)

    def __enter__(self):
        self.thread.start()
        if not self.ready.wait(10):
            self.close()
            raise OSError('The update status window could not open.')
        if self.error:
            raise OSError('The update status window could not open.') from self.error
        return self

    def set_text(self, text):
        self.text = text

    def close(self):
        self.stopped.set()
        self.thread.join(timeout=3)

    def __exit__(self, *args):
        self.close()

    def _run(self):
        window = class_name = None
        try:
            user = ctypes.WinDLL('user32', use_last_error=True)
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            gdi = ctypes.WinDLL('gdi32', use_last_error=True)
            user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                            w.HWND, w.HMENU, w.HINSTANCE, ctypes.c_void_p]
            user.CreateWindowExW.restype = w.HWND
            user.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            user.DefWindowProcW.restype = ctypes.c_ssize_t
            procedure_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
            @procedure_type
            def procedure(hwnd, message, wp, lp):
                if message == 0x0010:  # Do not dismiss a running transaction.
                    return 0
                return user.DefWindowProcW(hwnd, message, wp, lp)
            class WindowClass(ctypes.Structure):
                _fields_ = [('style', w.UINT), ('procedure', procedure_type),
                            ('class_extra', ctypes.c_int), ('window_extra', ctypes.c_int),
                            ('instance', w.HINSTANCE), ('icon', w.HICON), ('cursor', w.HANDLE),
                            ('background', w.HBRUSH), ('menu', w.LPCWSTR), ('name', w.LPCWSTR)]
            user.RegisterClassW.argtypes = [ctypes.POINTER(WindowClass)]
            user.RegisterClassW.restype = w.ATOM
            user.UnregisterClassW.argtypes = [w.LPCWSTR, w.HINSTANCE]
            user.LoadCursorW.argtypes = [w.HINSTANCE, ctypes.c_void_p]
            user.LoadCursorW.restype = w.HANDLE
            user.DestroyWindow.argtypes = [w.HWND]
            user.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
            user.SetForegroundWindow.argtypes = [w.HWND]
            user.SetWindowTextW.argtypes = [w.HWND, w.LPCWSTR]
            user.GetSystemMenu.argtypes = [w.HWND, w.BOOL]
            user.GetSystemMenu.restype = w.HMENU
            user.DeleteMenu.argtypes = [w.HMENU, w.UINT, w.UINT]
            user.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            user.SendMessageW.restype = ctypes.c_ssize_t
            user.PeekMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
            user.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
            user.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]
            user.DispatchMessageW.restype = ctypes.c_ssize_t
            user.GetSystemMetrics.argtypes = [ctypes.c_int]
            kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
            kernel.GetModuleHandleW.restype = w.HMODULE
            gdi.GetStockObject.argtypes = [ctypes.c_int]
            gdi.GetStockObject.restype = w.HANDLE
            instance = kernel.GetModuleHandleW(None)
            width, height = 540, 180
            x = max(0, (user.GetSystemMetrics(0) - width) // 2)
            y = max(0, (user.GetSystemMetrics(1) - height) // 2)
            class_name = f'BashDockUpdaterStatus-{id(self)}'
            definition = WindowClass()
            definition.procedure = procedure
            definition.instance = instance
            definition.cursor = user.LoadCursorW(None, 32512)
            definition.background = 6  # COLOR_WINDOW + 1.
            definition.name = class_name
            if not user.RegisterClassW(ctypes.byref(definition)):
                raise ctypes.WinError(ctypes.get_last_error())
            window = user.CreateWindowExW(0x00040000, class_name, self.title,
                                          0x00C00000 | 0x00080000 | 0x00020000,
                                          x, y, width, height, None, None, instance, None)
            if not window:
                raise ctypes.WinError(ctypes.get_last_error())
            # Closing mid-swap would be misleading. Minimizing remains available.
            user.DeleteMenu(user.GetSystemMenu(window, False), 0xF060, 0)
            label = user.CreateWindowExW(0, 'STATIC', self.text, 0x50000000,
                                         22, 24, width - 60, height - 65, window, None, instance, None)
            if not label:
                raise ctypes.WinError(ctypes.get_last_error())
            user.SendMessageW(label, 0x0030, gdi.GetStockObject(17), 1)
            user.ShowWindow(window, 5)
            user.SetForegroundWindow(window)
            self.ready.set()
            message = w.MSG()
            shown = None
            while not self.stopped.is_set():
                if shown != self.text:
                    shown = self.text
                    user.SetWindowTextW(label, shown)
                while user.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                    user.TranslateMessage(ctypes.byref(message))
                    user.DispatchMessageW(ctypes.byref(message))
                self.stopped.wait(0.05)
        except Exception as error:
            self.error = error
            self.ready.set()
        finally:
            if window:
                user.DestroyWindow(window)
            if class_name:
                user.UnregisterClassW(class_name, instance)
