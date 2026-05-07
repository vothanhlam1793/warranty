"""Custom server: serve static frontend + proxy API to backend."""

from __future__ import annotations

import os
import sys
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# Config
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "web")
BACKEND_URL = "http://localhost:8000"
PORT = 3000


class ProxyHandler(SimpleHTTPRequestHandler):
    """Serve static files, proxy /api/* and /uploads/* to backend."""

    def do_request(self, method: str):
        path = self.path.split("?", 1)[0]

        # Proxy API & uploads to backend
        if path.startswith(("/api/", "/uploads/")):
            self._proxy_request(method)
            return

        # Serve static files from web/
        if path == "/" or path == "/index.html":
            fpath = os.path.join(FRONTEND_DIR, "index.html")
        else:
            fpath = os.path.join(FRONTEND_DIR, path.lstrip("/"))

        if os.path.isfile(fpath):
            self.send_response(200)
            ext = os.path.splitext(fpath)[1]
            content_type = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".svg": "image/svg+xml",
            }.get(ext, "application/octet-stream")
            self.send_header("Content-Type", content_type)
            self.end_headers()
            with open(fpath, "rb") as f:
                self.wfile.write(f.read())
        else:
            # SPA fallback
            fpath = os.path.join(FRONTEND_DIR, "index.html")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            with open(fpath, "rb") as f:
                self.wfile.write(f.read())

    def _proxy_request(self, method: str):
        """Forward request to backend and return response."""
        url = BACKEND_URL + self.path
        body = None
        if method in ("POST", "PUT", "PATCH"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

        req = urllib.request.Request(url, data=body, method=method)
        # Forward relevant headers
        for hdr in ("Content-Type", "Cookie", "Authorization"):
            if hdr in self.headers:
                req.add_header(hdr, self.headers[hdr])

        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                # Forward response headers (especially Set-Cookie)
                for key, val in resp.getheaders():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for key, val in e.headers.items():
                if key.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(key, val)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, f"Proxy error: {e}")

    def do_GET(self):
        self.do_request("GET")

    def do_POST(self):
        self.do_request("POST")

    def do_PUT(self):
        self.do_request("PUT")

    def do_PATCH(self):
        self.do_request("PATCH")

    def do_DELETE(self):
        self.do_request("DELETE")

    def do_OPTIONS(self):
        self.do_request("OPTIONS")

    def log_message(self, format, *args):
        pass


def main():
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = PORT

    server = ThreadingHTTPServer(("0.0.0.0", port), ProxyHandler)
    print(f"Warranty Frontend + Proxy running at http://localhost:{port}")
    print(f"  Static files: {FRONTEND_DIR}")
    print(f"  API proxy: {BACKEND_URL}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
