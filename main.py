import threading
import time
import webview
from pynput import keyboard as kb
import app as server

_window = None
_listener = None

# Map modifier name -> pynput Key
_MOD_MAP = {
    "alt":   (kb.Key.alt_l,  kb.Key.alt_r),
    "ctrl":  (kb.Key.ctrl_l, kb.Key.ctrl_r),
    "shift": (kb.Key.shift_l,kb.Key.shift_r),
}

def _start_listener(hotkey_cfg):
    """Start a pynput listener for the given hotkey config. Returns the Listener."""
    mods_needed = set(hotkey_cfg.get("modifiers", []))
    key_char    = hotkey_cfg.get("key", "").lower()
    held_mods   = set()

    def _mod_name(k):
        for name, variants in _MOD_MAP.items():
            if k in variants:
                return name
        return None

    def on_press(k):
        name = _mod_name(k)
        if name:
            held_mods.add(name)
            return
        try:
            char = k.char.lower() if k.char else ""
        except AttributeError:
            char = ""
        if char == key_char and held_mods >= mods_needed and _window:
            _window.evaluate_js("window._recToggle && window._recToggle()")

    def on_release(k):
        name = _mod_name(k)
        if name:
            held_mods.discard(name)

    listener = kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener


class Api:
    def set_on_top(self, on_top):
        if _window:
            _window.on_top = on_top

    def update_hotkey(self, hotkey_cfg):
        """Called from JS when user saves a new hotkey. Restarts the listener."""
        global _listener
        if _listener:
            _listener.stop()
        _listener = _start_listener(hotkey_cfg)
        return True


if __name__ == "__main__":
    threading.Thread(target=server.start_server, daemon=True).start()
    time.sleep(1.2)

    cfg = server.load_config()
    _listener = _start_listener(cfg.get("hotkey", {"modifiers": ["alt"], "key": "z"}))

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
