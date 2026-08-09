import ctypes
import importlib
import json
import logging
import os
import sys
import threading
import time
from contextlib import suppress
from ctypes import wintypes
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from . import app as server
from .settings import (
    DEFAULT_CONFIG,
    TYPING_DELAY_DEFAULT_MS,
    TYPING_DELAY_MAX_MS,
    TYPING_DELAY_MIN_MS,
    VALID_TYPING_MODES,
)

webview: Any = None
_webview_import_error: BaseException | None = None
try:
    import webview as _imported_webview

    webview = _imported_webview
except Exception as exc:
    _webview_import_error = exc

kb: Any = None
_keyboard_import_error: BaseException | None = None
try:
    from pynput import keyboard as _imported_keyboard  # type: ignore[import-untyped]

    kb = _imported_keyboard
except Exception as exc:
    _keyboard_import_error = exc


def _configure_console_encoding() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            with suppress(Exception):
                reconfigure(encoding="utf-8", errors="replace")


_configure_console_encoding()
logging.basicConfig(
    level=os.environ.get("VOICECODE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("voicecode.main")

_INSTANCE_MUTEX_NAME = "Local\\VoiceCode.Desktop.SingleInstance"
_APP_USER_MODEL_ID = "VoiceCode.Desktop.0.2"
_INSTANCE_ALREADY_EXISTS = 183
_instance_mutex_handle: int | None = None


class VoiceCodeAlreadyRunningError(RuntimeError):
    """Raised when a second launcher finds an existing VoiceCode instance."""


_window = None
_listener = None
_tray_icon = None
_tray_thread: threading.Thread | None = None
_server_thread: threading.Thread | None = None
_window_icon_handles: list[int] = []
_shutdown_lock = threading.Lock()
_shutdown_requested = False
_type_controller = kb.Controller() if kb is not None else None
_typing_from_global = False
_typing_lock = threading.Lock()
_delivery_lock = threading.Lock()

_MOD_MAP = (
    {
        "alt": (kb.Key.alt_l, kb.Key.alt_r),
        "ctrl": (kb.Key.ctrl_l, kb.Key.ctrl_r),
        "shift": (kb.Key.shift_l, kb.Key.shift_r),
    }
    if kb is not None
    else {}
)


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


_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002
_CLIPBOARD_RESTORE_DELAY = 0.12


def _setup_clipboard_api() -> None:
    """Declare the ctypes signatures used by the clipboard helpers."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.restype = ctypes.c_size_t


def _open_clipboard() -> bool:
    """Open the Windows clipboard with a short retry loop."""
    if os.name != "nt":
        return False
    _setup_clipboard_api()
    user32 = ctypes.windll.user32
    for _ in range(10):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.03)
    return False


def _clipboard_clear() -> bool:
    """Clear the Windows clipboard contents."""
    if os.name != "nt":
        return False
    _setup_clipboard_api()
    user32 = ctypes.windll.user32
    if not _open_clipboard():
        return False
    try:
        return bool(user32.EmptyClipboard())
    except Exception as exc:
        logger.debug("Failed to clear the Windows clipboard: %s", exc)
        return False
    finally:
        user32.CloseClipboard()


def _clipboard_set_text(text_value: str) -> bool:
    """Replace the Windows clipboard contents with UTF-16 text."""
    if os.name != "nt":
        return False
    _setup_clipboard_api()
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    memory = None
    try:
        encoded = text_value.encode("utf-16-le") + b"\x00\x00"
        memory = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(encoded))
        if not memory:
            return False
        pointer = kernel32.GlobalLock(memory)
        if not pointer:
            return False
        ctypes.memmove(pointer, encoded, len(encoded))
        kernel32.GlobalUnlock(memory)
        if not _open_clipboard():
            return False
        try:
            if not user32.EmptyClipboard():
                return False
            if not user32.SetClipboardData(_CF_UNICODETEXT, memory):
                return False
            memory = None
            return True
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        logger.warning("Failed to set the Windows clipboard: %s", exc)
        return False
    finally:
        if memory:
            kernel32.GlobalFree(memory)


def _clipboard_get_text() -> str | None:
    """Return clipboard text, or None when the clipboard holds no text.

    Raises OSError when the clipboard cannot be read.
    """
    if os.name != "nt":
        return None
    _setup_clipboard_api()
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    try:
        if not _open_clipboard():
            raise OSError("Clipboard is busy and could not be opened.")
        try:
            handle = user32.GetClipboardData(_CF_UNICODETEXT)
            if not handle:
                return None
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                raise OSError("Clipboard text could not be locked.")
            try:
                size = kernel32.GlobalSize(handle)
                if size <= 0:
                    return None
                raw = ctypes.string_at(pointer, size)
            finally:
                kernel32.GlobalUnlock(handle)
            text = raw.decode("utf-16-le", errors="replace")
            return text.rstrip("\x00") or None
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        logger.warning("Failed to read the Windows clipboard: %s", exc)
        raise


def _paste_clipboard(controller) -> None:
    """Send Ctrl+V to the active application."""
    if kb is None:
        raise RuntimeError("Keyboard input is unavailable.")
    controller.press(kb.Key.ctrl)
    controller.press("v")
    controller.release("v")
    controller.release(kb.Key.ctrl)


def _typing_mode_from_config() -> str:
    try:
        default_mode = str(DEFAULT_CONFIG.get("typing_mode", "clipboard"))
        mode = str(server.load_config().get("typing_mode", default_mode))
        return mode if mode in VALID_TYPING_MODES else default_mode
    except Exception:
        return "clipboard"


def _typing_delay_ms() -> int:
    try:
        value = server.load_config().get("typing_delay_ms", TYPING_DELAY_DEFAULT_MS)
        if isinstance(value, bool) or not isinstance(value, int):
            return TYPING_DELAY_DEFAULT_MS
        return max(TYPING_DELAY_MIN_MS, min(TYPING_DELAY_MAX_MS, value))
    except Exception:
        return TYPING_DELAY_DEFAULT_MS


def _deliver_via_clipboard(text: str) -> bool:
    """Paste ``text`` through the clipboard, restoring the previous text contents."""
    try:
        previous = _clipboard_get_text()
    except Exception:
        logger.info("Clipboard contents could not be read; using simulated keystrokes instead.")
        return False
    if not _clipboard_set_text(text):
        return False
    try:
        _paste_clipboard(_type_controller)
    except Exception as exc:
        logger.warning("Clipboard paste failed; falling back to keystrokes: %s", exc)
        return False
    finally:
        time.sleep(_CLIPBOARD_RESTORE_DELAY)
        if previous is not None:
            try:
                _clipboard_set_text(previous)
            except Exception:
                logger.debug("Failed to restore the clipboard after paste.", exc_info=True)
        else:
            _clipboard_clear()
    return True


def _deliver_text(text: str) -> None:
    """Deliver transcribed text to the active application in the configured mode."""
    with _delivery_lock:
        delay = _typing_delay_ms()
        if delay > 0:
            time.sleep(delay / 1000.0)
        if _type_controller is None:
            logger.warning("Global typing is unavailable because pynput could not be initialized.")
            return
        if os.name == "nt" and _typing_mode_from_config() == "clipboard":
            if _deliver_via_clipboard(text):
                return
            logger.info("Clipboard typing is unavailable; falling back to simulated keystrokes.")
        try:
            _type_controller.type(text)
        except Exception as exc:
            logger.warning("Failed to type transcribed text: %s", exc)


def _type_text(text: str) -> None:
    threading.Thread(target=_deliver_text, args=(text,), daemon=True).start()


def _start_listener(hotkey_cfg):
    if kb is None:
        raise RuntimeError(
            "Global hotkey support is unavailable because pynput could not be initialized: "
            f"{_keyboard_import_error}"
        )
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
    def minimize_window(self):
        if not _window:
            return False
        try:
            method = getattr(_window, "minimize", None)
            if method:
                method()
                return True
        except Exception as exc:
            logger.warning("Failed to minimize VoiceCode window: %s", exc)
        return False

    def toggle_maximize_window(self):
        if os.name == "nt":
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, "VoiceCode - Speech to Text")
                if hwnd:
                    sw_maximize = 3
                    sw_restore = 9
                    if user32.IsZoomed(hwnd):
                        user32.ShowWindow(hwnd, sw_restore)
                    else:
                        user32.ShowWindow(hwnd, sw_maximize)
                    return True
            except Exception as exc:
                logger.warning("Failed to toggle maximize state: %s", exc)
        if _window:
            for method_name in ("toggle_fullscreen", "maximize", "restore"):
                method = getattr(_window, method_name, None)
                if method:
                    try:
                        method()
                        return True
                    except Exception as exc:
                        logger.debug("window.%s failed: %s", method_name, exc)
        return False

    def close_window(self):
        return _request_shutdown(destroy_window=True)

    def copy_text(self, value):
        text_value = str(value or "")
        if os.name != "nt" or not text_value:
            return False
        return _clipboard_set_text(text_value)

    def open_log_folder(self):
        try:
            log_dir = Path(server._log_file()).resolve().parent
            log_dir.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(log_dir)
                return True
        except Exception as exc:
            logger.warning("Failed to open the VoiceCode log directory: %s", exc)
        return False

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


def _application_icon_path(extension: str = ".png") -> Path | None:
    filename = f"voicecode-icon{extension}"
    candidates = [
        Path(sys.executable).resolve().parent / "_internal" / "voicecode" / "static" / filename,
        Path(__file__).resolve().parent / "static" / filename,
        Path(sys.executable).resolve().parent / filename,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _set_windows_app_identity() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except Exception as exc:
        logger.debug("Failed to set Windows AppUserModelID: %s", exc)


def _find_voicecode_window() -> int | None:
    if os.name != "nt":
        return None
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    hwnd = user32.FindWindowW(None, "VoiceCode - Speech to Text")
    if hwnd:
        return int(hwnd)

    current_pid = os.getpid()
    found: list[int] = []
    callback_factory = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
    enum_proc_type = callback_factory(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _visit(candidate: int, _lparam: int) -> bool:
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(candidate, ctypes.byref(process_id))
        if process_id.value != current_pid:
            return True
        length = user32.GetWindowTextLengthW(candidate)
        if length <= 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(candidate, title, length + 1)
        if title.value.startswith("VoiceCode"):
            found.append(int(candidate))
            return False
        return True

    callback = enum_proc_type(_visit)
    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _release_windows_window_icons() -> None:
    global _window_icon_handles
    if os.name != "nt":
        return
    user32 = ctypes.windll.user32
    for handle in _window_icon_handles:
        with suppress(Exception):
            user32.DestroyIcon(handle)
    _window_icon_handles = []


def _apply_windows_window_icon() -> bool:
    global _window_icon_handles
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        user32.LoadImageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [
            ctypes.c_void_p,
            wintypes.UINT,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        shell32.ExtractIconExW.restype = wintypes.UINT
        hwnd = _find_voicecode_window()
        if not hwnd:
            return False

        _release_windows_window_icons()
        ico_path = _application_icon_path(".ico")
        handles: list[int] = []
        if ico_path is not None:
            image_icon = 1
            lr_loadfromfile = 0x0010
            for size in (16, 32, 48):
                handle = user32.LoadImageW(
                    None, str(ico_path), image_icon, size, size, lr_loadfromfile
                )
                if handle:
                    handles.append(int(handle))
        if not handles:
            large_icon = ctypes.c_void_p()
            small_icon = ctypes.c_void_p()
            extracted = shell32.ExtractIconExW(
                str(Path(sys.executable).resolve()),
                0,
                ctypes.byref(large_icon),
                ctypes.byref(small_icon),
                1,
            )
            if extracted:
                handles = [int(handle) for handle in (small_icon.value, large_icon.value) if handle]
        if not handles:
            logger.warning("VoiceCode window icon could not be loaded.")
            return False
        small = handles[0]
        large = handles[-1]
        wm_seticon = 0x0080
        user32.SendMessageW(hwnd, wm_seticon, None, small)
        user32.SendMessageW(hwnd, wm_seticon, ctypes.c_void_p(1), large)
        _window_icon_handles = handles
        logger.info("Applied VoiceCode icon to the Windows desktop window.")
        return True
    except Exception as exc:
        logger.debug("Failed to apply Windows window icon: %s", exc)
        return False


def _apply_windows_window_icon_with_retry() -> None:
    for _ in range(30):
        if _apply_windows_window_icon():
            return
        time.sleep(0.1)
    logger.warning("VoiceCode window handle was not ready for icon assignment.")


def _show_window() -> bool:
    shown = False
    if _window:
        for method_name in ("show", "restore"):
            method = getattr(_window, method_name, None)
            if method:
                try:
                    method()
                    shown = True
                except Exception as exc:
                    logger.debug("window.%s failed while restoring VoiceCode: %s", method_name, exc)
    return _focus_existing_window() or shown


def _start_tray_icon() -> bool:
    global _tray_icon, _tray_thread
    if _env_flag("VOICECODE_DISABLE_TRAY"):
        logger.info("Tray icon disabled by VOICECODE_DISABLE_TRAY.")
        return False
    if _tray_icon is not None:
        return True
    try:
        pystray = importlib.import_module("pystray")
        image_module = importlib.import_module("PIL.Image")
    except Exception as exc:
        logger.warning("Tray icon dependencies are unavailable: %s", exc)
        return False

    icon_path = _application_icon_path(".png")
    if icon_path is None:
        logger.warning("Tray icon asset was not found.")
        return False
    with image_module.open(icon_path) as source:
        image = source.convert("RGBA").resize((64, 64))

    def _show_from_tray(icon, item):  # noqa: ANN001, ARG001
        _show_window()

    def _quit_from_tray(icon, item):  # noqa: ANN001, ARG001
        threading.Thread(
            target=lambda: _request_shutdown(destroy_window=True),
            daemon=True,
            name="voicecode-tray-exit",
        ).start()

    _tray_icon = pystray.Icon(
        "VoiceCode",
        image,
        "VoiceCode",
        menu=pystray.Menu(
            pystray.MenuItem("Show VoiceCode", _show_from_tray, default=True),
            pystray.MenuItem("Exit VoiceCode", _quit_from_tray),
        ),
    )
    _tray_thread = threading.Thread(
        target=_tray_icon.run,
        daemon=True,
        name="voicecode-tray",
    )
    _tray_thread.start()
    logger.info("Tray icon started.")
    return True


def _request_shutdown(*, destroy_window: bool) -> bool:
    global _shutdown_requested, _tray_icon, _tray_thread, _listener, _window
    with _shutdown_lock:
        if _shutdown_requested:
            return True
        _shutdown_requested = True
    logger.info("VoiceCode shutdown requested.")

    if destroy_window and _window:
        window = _window
        _window = None
        try:
            window.destroy()
        except Exception as exc:
            logger.debug("Failed to destroy desktop window during shutdown: %s", exc)

    if _listener:
        try:
            _listener.stop()
            join = getattr(_listener, "join", None)
            if join:
                join(timeout=1)
        except Exception as exc:
            logger.debug("Failed to stop hotkey listener cleanly: %s", exc)
        _listener = None

    tray_icon = _tray_icon
    tray_thread = _tray_thread
    _tray_icon = None
    _tray_thread = None
    if tray_icon:
        try:
            tray_icon.stop()
        except Exception as exc:
            logger.debug("Failed to stop tray icon cleanly: %s", exc)
    if tray_thread and tray_thread is not threading.current_thread():
        tray_thread.join(timeout=1.5)

    server.shutdown_application()

    if _server_thread and _server_thread is not threading.current_thread():
        join_server = getattr(_server_thread, "join", None)
        if join_server:
            join_server(timeout=3)
    _release_windows_window_icons()
    logger.info("VoiceCode desktop shutdown completed.")
    return True


def _focus_existing_window() -> bool:
    """Restore and foreground the existing desktop window when possible."""
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = _find_voicecode_window()
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception as exc:
        logger.debug("Unable to focus the existing VoiceCode window: %s", exc)
        return False


def _voicecode_health_pid(timeout: float = 0.5) -> int | None:
    try:
        with urlopen(f"http://127.0.0.1:{server.PORT}/health", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        pid = payload.get("pid")
        return int(pid) if pid is not None else None
    except Exception:
        return None


def _recover_stale_instance() -> bool:
    """Terminate a windowless VoiceCode process that still owns the local port."""
    if os.name != "nt":
        return False
    pid = _voicecode_health_pid()
    if not pid or pid == os.getpid() or _focus_existing_window():
        return False
    try:
        psutil = importlib.import_module("psutil")
        process = psutil.Process(pid)
        if Path(process.exe()).resolve() != Path(sys.executable).resolve():
            return False
        logger.warning("Terminating stale windowless VoiceCode process: pid=%s", pid)
        process.terminate()
        try:
            process.wait(timeout=5)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and _voicecode_health_pid(timeout=0.2) == pid:
            time.sleep(0.1)
        return True
    except Exception as exc:
        logger.warning("Unable to recover stale VoiceCode process %s: %s", pid, exc)
        return False


def _acquire_instance_mutex() -> bool:
    """Acquire the Windows per-session single-instance mutex."""
    global _instance_mutex_handle
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        create_mutex.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_bool
        kernel32.SetLastError(0)
        handle = create_mutex(None, True, _INSTANCE_MUTEX_NAME)
        last_error = kernel32.GetLastError()
        if not handle:
            raise OSError("CreateMutexW failed.")
        if last_error == _INSTANCE_ALREADY_EXISTS:
            close_handle(handle)
            return False
        _instance_mutex_handle = int(handle)
        return True
    except OSError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Unable to create the VoiceCode single-instance lock: {exc}") from exc


def _release_instance_mutex() -> None:
    """Release the process-owned Windows single-instance mutex."""
    global _instance_mutex_handle
    if _instance_mutex_handle is None:
        return
    try:
        kernel32 = ctypes.windll.kernel32
        with suppress(Exception):
            kernel32.ReleaseMutex(_instance_mutex_handle)
        kernel32.CloseHandle(_instance_mutex_handle)
    except Exception as exc:
        logger.debug("Unable to close the VoiceCode single-instance lock: %s", exc)
    finally:
        _instance_mutex_handle = None


def _hide_console() -> None:
    if os.name != "nt":
        return
    try:
        windll = ctypes.windll
        hwnd = windll.kernel32.GetConsoleWindow()
        if hwnd:
            windll.user32.ShowWindow(hwnd, 0)
    except Exception as exc:
        logger.debug("Failed to hide console window: %s", exc)


def _show_existing_instance_message(message: str) -> None:
    logger.info("%s", message)
    if os.name != "nt":
        return
    with suppress(Exception):
        ctypes.windll.user32.MessageBoxW(None, message, "VoiceCode", 0x40)


def _show_startup_error(exc: BaseException) -> None:
    message = f"VoiceCode failed to start. {exc}"
    logger.exception(message)
    if os.name == "nt":
        try:
            windll = ctypes.windll
            windll.user32.MessageBoxW(None, message, "VoiceCode startup failed", 0x10)
        except Exception:
            pass


def _verify_ui_endpoint() -> None:
    url = f"http://127.0.0.1:{server.PORT}/"
    try:
        with urlopen(url, timeout=2) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"VoiceCode UI returned HTTP {response.status}. Reinstall the application."
                )
    except HTTPError as exc:
        raise RuntimeError(
            f"VoiceCode UI assets are unavailable (HTTP {exc.code}). Reinstall the application."
        ) from exc
    except (OSError, URLError) as exc:
        raise RuntimeError(f"VoiceCode UI could not be opened: {exc}") from exc


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
                        _focus_existing_window()
                        raise VoiceCodeAlreadyRunningError(
                            f"VoiceCode is already running (pid {server_pid}) on port {server.PORT}."
                        )
                    _verify_ui_endpoint()
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
    global _listener, _server_thread, _shutdown_requested, _window

    with _shutdown_lock:
        _shutdown_requested = False

    _set_windows_app_identity()
    if not _acquire_instance_mutex():
        for _ in range(20):
            if _focus_existing_window():
                raise VoiceCodeAlreadyRunningError("VoiceCode is already running.")
            time.sleep(0.15)
            if _acquire_instance_mutex():
                break
        else:
            if _recover_stale_instance():
                for _ in range(20):
                    if _acquire_instance_mutex():
                        break
                    time.sleep(0.1)
                else:
                    raise VoiceCodeAlreadyRunningError(
                        "VoiceCode could not recover the previous background process."
                    )
            else:
                raise VoiceCodeAlreadyRunningError(
                    "VoiceCode is still shutting down. Wait a moment and open it again."
                )
    try:
        if webview is None:
            raise RuntimeError(
                "Desktop UI support is unavailable because pywebview could not be initialized: "
                f"{_webview_import_error}"
            )

        server.on_transcription = _on_transcription

        _server_thread = threading.Thread(
            target=server.start_server,
            daemon=True,
        )
        _server_thread.start()
        _wait_for_server()

        cfg = server.load_config()
        _listener = _start_listener(cfg.get("hotkey", {"modifiers": ["alt"], "key": "z"}))

        _window = webview.create_window(
            "VoiceCode - Speech to Text",
            f"http://127.0.0.1:{server.PORT}",
            width=1120,
            height=760,
            min_size=(860, 560),
            resizable=True,
            js_api=Api(),
        )
        window_events = getattr(_window, "events", None)
        closing_event = getattr(window_events, "closing", None)
        closed_event = getattr(window_events, "closed", None)
        if closing_event is not None:
            closing_event += lambda: _request_shutdown(destroy_window=False)
        if closed_event is not None:
            closed_event += lambda: _request_shutdown(destroy_window=False)
        _start_tray_icon()

        def _desktop_ready() -> None:
            _hide_console()
            _apply_windows_window_icon_with_retry()

        webview.start(func=_desktop_ready)
    finally:
        _request_shutdown(destroy_window=False)
        _release_instance_mutex()


def run() -> bool:
    try:
        main()
    except VoiceCodeAlreadyRunningError as exc:
        if not _focus_existing_window():
            _show_existing_instance_message(str(exc))
        return True
    except Exception as exc:
        _show_startup_error(exc)
        return False
    return True


if __name__ == "__main__":
    run()
