import threading
import time
import webview
from pynput import keyboard as kb
import app as server

_window = None

class Api:
    def set_on_top(self, on_top):
        if _window:
            _window.on_top = on_top

def _start_hotkey_listener():
    alt_held = False

    def on_press(key):
        nonlocal alt_held
        if key in (kb.Key.alt_l, kb.Key.alt_r):
            alt_held = True
        try:
            if alt_held and key.char == 'z' and _window:
                _window.evaluate_js('window._recToggle && window._recToggle()')
        except AttributeError:
            pass

    def on_release(key):
        nonlocal alt_held
        if key in (kb.Key.alt_l, kb.Key.alt_r):
            alt_held = False

    with kb.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

if __name__ == "__main__":
    threading.Thread(target=server.start_server, daemon=True).start()
    time.sleep(1.2)

    threading.Thread(target=_start_hotkey_listener, daemon=True).start()

    _window = webview.create_window(
        "VoiceCode - Speech to Text",
        f"http://localhost:{server.PORT}",
        width=860,
        height=700,
        min_size=(620, 520),
        resizable=True,
        js_api=Api(),
    )
    webview.start()
