import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 10000


class _Handler(BaseHTTPRequestHandler):
    def _ok(self):
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._ok()
        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        if self.path in ("/", "/health"):
            self._ok()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def start_keepalive() -> bool:
    raw = os.getenv("PORT") or str(DEFAULT_PORT)
    try:
        port = int(raw)
    except ValueError:
        port = DEFAULT_PORT

    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    except OSError as e:
        logging.error("Health-check port %s ochilmadi: %s", port, e)
        return False

    threading.Thread(target=server.serve_forever, daemon=True).start()
    logging.warning("Health-check: http://0.0.0.0:%s/health", port)
    return True
