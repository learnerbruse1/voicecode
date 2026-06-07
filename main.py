import threading
import time
import ctypes
import ctypes.wintypes
import webview
import app as server

_window = None

# Win32 constants for RegisterHotKey
MOD_ALT = 0x0001
VK_Z = 0x5A
WM_HOTKEY = 0x0312
HOTKEY_ID = 1

class Api:
    def set_on_top(self, on_top):
        if _window:
            _window.on_top = on_top

def _hotkey_listener():
    """Run a Win32 message loop to receive WM_HOTKEY events (no admin needed)."""
    user32 = ctypes.windll.user32
    # Alt+Z as push-to-talk toggle: press = start, next press = stop
    # For hold-to-talk we need press/release — RegisterHotKey only fires on press.
    # So we use toggle mode here (press to start, press again to stop).
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_ALT, VK_Z):
        print("Warning: could not register Alt+Z hotkey")
        return

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            if _window:
                _window.evaluate_js('window._recToggle && window._recToggle()')
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    user32.UnregisterHotKey(None, HOTKEY_ID)

if __name__ == "__main__":
    threading.Thread(target=server.start_server, daemon=True).start()
    time.sleep(1.2)

    threading.Thread(target=_hotkey_listener, daemon=True).start()

    _window = webview.create_window(
        "VoiceCode - Speech to Text",
        f"http://localhost:{server.PORT}",
        width=820,
        height=680,
        min_size=(600, 500),
        resizable=True,
        js_api=Api(),
    )
    webview.start()
