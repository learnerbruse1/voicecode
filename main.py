import threading
import time
import webview
import app as server

_window = None

class Api:
    def set_on_top(self, on_top):
        if _window:
            _window.on_top = on_top

if __name__ == "__main__":
    threading.Thread(target=server.start_server, daemon=True).start()
    time.sleep(1.2)

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
