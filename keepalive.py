"""Render free web service uchun health-check server.

Render servisga tashqi trafik kelmasa uni uyquga yuboradi. UptimeRobot yoki
cron-job.org kabi xizmat /health manzilini muntazam chaqirib turishi kerak.
PORT muhit o'zgaruvchisi bo'lmasa (lokal ishga tushirish) server ko'tarilmaydi.
"""

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
    port = os.getenv("PORT")
    if not port:
        return False
    server = ThreadingHTTPServer(("0.0.0.0", int(port)), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logging.info("Health-check: http://0.0.0.0:%s/health", port)
    return True
