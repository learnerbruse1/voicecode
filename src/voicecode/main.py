import ctypes
import importlib
import json
import logging
import os
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import webview
from pynput import keyboard as kb  # type: ignore[import-untyped]

from . import app as server


def _configure_console_encoding() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_console_encoding()
logging.basicConfig(
    level=os.environ.get("VOICECODE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("voicecode.main")

_window = None
_listener = None
_type_controller = kb.Controller()
_typing_from_global = False
_typing_lock = threading.Lock()

_MOD_MAP = {
    "alt": (kb.Key.alt_l, kb.Key.alt_r),
    "ctrl": (kb.Key.ctrl_l, kb.Key.ctrl_r),
    "shift": (kb.Key.shift_l, kb.Key.shift_r),
}


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _set_typing_from_global(value: bool) -> None:
    global _typing_from_global
    with _typing_lock:
        _typing_from_global = value


def _consume_typing_from_global() -> bool:
    global _typing_from_global
    with _typing_lock:
        value = _typing_from_global
        _typing_from_global = False
        return value


def _eval_js_safe(script: str) -> None:
    if not _window:
        return
    try:
        _window.evaluate_js(script)
    except Exception as exc:
        logger.warning("Failed to evaluate JavaScript in the webview: %s", exc)


def _type_text(text: str) -> None:
    def _do() -> None:
        time.sleep(0.15)
        try:
            _type_controller.type(text)
        except Exception as exc:
            logger.warning("Failed to type transcribed text: %s", exc)

    threading.Thread(target=_do, daemon=True).start()


def _start_listener(hotkey_cfg):
    mods_needed = set(hotkey_cfg.get("modifiers", []))
    key_char = str(hotkey_cfg.get("key", "")).lower()
    held_mods = set()
    lock = threading.Lock()

    def _mod_name(k):
        for name, variants in _MOD_MAP.items():
            if k in variants:
                return name
        return None

    def _key_matches(k) -> bool:
        if key_char == "space":
            return k == kb.Key.space
        try:
            return bool(k.char) and k.char.lower() == key_char
        except AttributeError:
            return False

    hotkey_active = False

    def on_press(k):
        nonlocal hotkey_active
        name = _mod_name(k)
        if name:
            with lock:
                held_mods.add(name)
            return
        with lock:
            triggered = _key_matches(k) and held_mods >= mods_needed
        if triggered and not hotkey_active and _window:
            hotkey_active = True
            _set_typing_from_global(True)
            _eval_js_safe("window._recStart && window._recStart()")

    def on_release(k):
        nonlocal hotkey_active
        name = _mod_name(k)
        if name:
            with lock:
                held_mods.discard(name)
            return
        if _key_matches(k) and hotkey_active and _window:
            hotkey_active = False
            _eval_js_safe("window._recStop && window._recStop()")

    listener = kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    logger.info(
        "Global hotkey listener started: %s+%s",
        "+".join(sorted(mods_needed)) or "no-modifier",
        key_char,
    )
    return listener


class Api:
    def set_on_top(self, on_top):
        if os.name != "nt":
            logger.info("Always-on-top is only supported on Windows in this build.")
            return False
        try:
            hwnd_topmost = -1
            hwnd_notopmost = -2
            swp_nomove = 0x0002
            swp_nosize = 0x0001
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, "VoiceCode - Speech to Text")
            if hwnd:
                insert_after = hwnd_topmost if on_top else hwnd_notopmost
                user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, swp_nomove | swp_nosize)
                return True
            logger.warning("VoiceCode window handle was not found.")
        except Exception as exc:
            logger.warning("Failed to update always-on-top state: %s", exc)
        return False

    def update_hotkey(self, hotkey_cfg):
        global _listener
        try:
            if _listener:
                _listener.stop()
                _listener.join(timeout=0.5)
            _listener = _start_listener(hotkey_cfg)
            return True
        except Exception as exc:
            logger.warning("Failed to update global hotkey: %s", exc)
            return False

    def rec_stopped_from_ui(self):
        _set_typing_from_global(False)
        return True


def _on_transcription(text: str) -> None:
    if _consume_typing_from_global():
        _type_text(text)
    _eval_js_safe(f"window._appendText && window._appendText({json.dumps(text)})")


def _start_tray_icon() -> None:
    if not _env_flag("VOICECODE_ENABLE_TRAY"):
        return
    try:
        pystray = importlib.import_module("pystray")
        image_module = importlib.import_module("PIL.Image")
        image_draw_module = importlib.import_module("PIL.ImageDraw")
    except Exception as exc:
        logger.warning("Tray icon requested but optional dependencies are unavailable: %s", exc)
        return

    def _make_image():
        image = image_module.new("RGB", (64, 64), "#1a1d27")
        draw = image_draw_module.Draw(image)
        draw.ellipse((14, 8, 50, 44), fill="#6366f1")
        draw.rectangle((28, 40, 36, 54), fill="#e2e8f0")
        draw.rectangle((20, 52, 44, 58), fill="#e2e8f0")
        return image

    def _show_window(icon, item):  # noqa: ANN001, ARG001
        if not _window:
            return
        for method_name in ("show", "restore"):
            method = getattr(_window, method_name, None)
            if method:
                try:
                    method()
                except Exception as exc:
                    logger.debug("Failed to call window.%s from tray: %s", method_name, exc)

    def _quit(icon, item):  # noqa: ANN001, ARG001
        try:
            icon.stop()
        except Exception:
            pass
        if _listener:
            try:
                _listener.stop()
            except Exception:
                pass
        if _window:
            try:
                _window.destroy()
            except Exception as exc:
                logger.warning("Failed to destroy VoiceCode window from tray: %s", exc)

    icon = pystray.Icon(
        "VoiceCode",
        _make_image(),
        "VoiceCode",
        menu=pystray.Menu(
            pystray.MenuItem("Show VoiceCode", _show_window),
            pystray.MenuItem("Quit", _quit),
        ),
    )
    threading.Thread(target=icon.run, daemon=True).start()
    logger.info("Tray icon started.")


def _hide_console() -> None:
    if os.name != "nt":
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception as exc:
        logger.debug("Failed to hide console window: %s", exc)


def _show_startup_error(exc: BaseException) -> None:
    message = f"VoiceCode failed to start. {exc}"
    logger.exception(message)
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, "VoiceCode startup failed", 0x10)
        except Exception:
            pass


def _wait_for_server(timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{server.PORT}/health"
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8"))
                    server_pid = payload.get("pid")
                    if server_pid is None:
                        raise RuntimeError(
                            f"Port {server.PORT} is already in use by another service "
                            "that does not identify itself as VoiceCode."
                        )
                    if server_pid != os.getpid():
                        raise RuntimeError(
                            f"Port {server.PORT} is already used by another VoiceCode process "
                            f"(pid {server_pid}). Close the existing instance or set PORT."
                        )
                    return
        except RuntimeError:
            raise
        except (OSError, URLError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(
        f"HTTP server did not become ready within {timeout_seconds:.0f}s: {last_error}"
    )


def main() -> None:
    global _listener, _window

    server.on_transcription = _on_transcription

    threading.Thread(target=server.start_server, daemon=True).start()
    _wait_for_server()

    cfg = server.load_config()
    _listener = _start_listener(cfg.get("hotkey", {"modifiers": ["alt"], "key": "z"}))

    _window = webview.create_window(
        "VoiceCode - Speech to Text",
        f"http://127.0.0.1:{server.PORT}",
        width=860,
        height=700,
        min_size=(620, 520),
        resizable=True,
        js_api=Api(),
    )
    _start_tray_icon()
    webview.start(func=_hide_console)


def run() -> None:
    try:
        main()
    except Exception as exc:
        _show_startup_error(exc)
        raise


if __name__ == "__main__":
    run()
