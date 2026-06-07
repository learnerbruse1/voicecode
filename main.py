import threading
import time
import ctypes
import webview
from pynput import keyboard as kb
import app as server

_window = None
_listener = None
_type_controller = kb.Controller()
_typing_from_global = False  # tracks whether current rec was triggered by global hotkey

# Map modifier name -> pynput Key
_MOD_MAP = {
    "alt":   (kb.Key.alt_l,  kb.Key.alt_r),
    "ctrl":  (kb.Key.ctrl_l, kb.Key.ctrl_r),
    "shift": (kb.Key.shift_l,kb.Key.shift_r),
}

def _type_text(text: str):
    """Type text at the current cursor position after a short delay
    to let the hotkey modifiers be released first."""
    def _do():
        time.sleep(0.15)  # wait for Alt key to be fully released
        _type_controller.type(text)
    threading.Thread(target=_do, daemon=True).start()

def _start_listener(hotkey_cfg):
    global _typing_from_global
    mods_needed = set(hotkey_cfg.get("modifiers", []))
    key_char    = hotkey_cfg.get("key", "").lower()
    held_mods   = set()
    _lock       = threading.Lock()

    def _mod_name(k):
        for name, variants in _MOD_MAP.items():
            if k in variants:
                return name
        return None

    def on_press(k):
        name = _mod_name(k)
        if name:
            with _lock: held_mods.add(name)
            return
        try:
            char = k.char.lower() if k.char else ""
        except AttributeError:
            char = ""
        with _lock:
            triggered = char == key_char and held_mods >= mods_needed
        if triggered and _window:
            _typing_from_global = True
            _window.evaluate_js("window._recToggle && window._recToggle()")

    def on_release(k):
        name = _mod_name(k)
        if name:
            with _lock: held_mods.discard(name)

    listener = kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener


class Api:
    def set_on_top(self, on_top):
        # Use Win32 SetWindowPos directly — avoids pywebview GUI thread deadlock
        HWND_TOPMOST   = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE     = 0x0002
        SWP_NOSIZE     = 0x0001
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "VoiceCode - Speech to Text")
        if hwnd:
            insert_after = HWND_TOPMOST if on_top else HWND_NOTOPMOST
            user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

    def update_hotkey(self, hotkey_cfg):
        global _listener
        if _listener:
            _listener.stop()
        _listener = _start_listener(hotkey_cfg)
        return True

    def rec_stopped_from_ui(self):
        """Called by JS when recording stops from inside the window (not global hotkey)."""
        global _typing_from_global
        _typing_from_global = False


def _on_transcription(text: str):
    """Called by app.py after each successful transcription."""
    if _typing_from_global:
        _type_text(text)
    # Always show in window too
    if _window:
        safe = text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        _window.evaluate_js(f"window._appendText && window._appendText(`{safe}`)")


if __name__ == "__main__":
    server.on_transcription = _on_transcription

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

