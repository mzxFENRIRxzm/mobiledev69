"""Expose THE_X's Flutter build and Django/OIDC server through one local port."""

from __future__ import annotations

import argparse
import http.client
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PREFIXES = ("/api/", "/openid/", "/accounts/", "/admin/")
STATIC_ROOTS = {
    "/static/": PROJECT_ROOT / "backend" / "staticfiles",
    "/media/": PROJECT_ROOT / "backend" / "media",
}
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def route_for(path: str) -> str:
    """Return the local service name for a request path."""
    if any(path.startswith(prefix) for prefix in STATIC_ROOTS):
        return "file"
    if any(path.startswith(prefix) for prefix in BACKEND_PREFIXES):
        return "backend"
    return "frontend"


def local_file(path: str) -> Path | None:
    """Resolve a static/media URL without allowing traversal outside its root."""
    for prefix, root in STATIC_ROOTS.items():
        if not path.startswith(prefix):
            continue
        relative = unquote(path[len(prefix):]).replace("\\", "/")
        candidate = (root / relative).resolve()
        resolved_root = root.resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            return None
        return candidate
    return None


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PUT(self):
        self._dispatch()

    def do_PATCH(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def do_OPTIONS(self):
        self._dispatch()

    def _dispatch(self):
        path = urlsplit(self.path).path
        if path.startswith("/admin/") and not self.server.expose_django_admin:
            self.send_error(403, "Django admin is disabled on the public tunnel")
            return
        route = route_for(path)
        if route == "file":
            self._serve_file(path)
            return
        port = self.server.backend_port if route == "backend" else self.server.frontend_port
        self._proxy(port)

    def _serve_file(self, path: str):
        target = local_file(path)
        if target is None or not target.is_file():
            self.send_error(404)
            return
        try:
            stat = target.stat()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(stat.st_size))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                with target.open("rb") as source:
                    while chunk := source.read(64 * 1024):
                        self.wfile.write(chunk)
        except OSError:
            self.send_error(404)

    def _proxy(self, port: int):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {
            name: value for name, value in self.headers.items()
            if name.lower() not in HOP_BY_HOP and name.lower() != "host"
        }
        public_host = self.headers.get("Host", "")
        headers["Host"] = public_host
        headers["X-Forwarded-Proto"] = "https"
        headers["X-Forwarded-Host"] = public_host
        headers.setdefault("X-Forwarded-For", self.client_address[0])
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                lowered = name.lower()
                if lowered not in HOP_BY_HOP and lowered not in {"content-length", "server", "date"}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except (ConnectionError, OSError, http.client.HTTPException):
            self.send_error(502, "THE_X local service is unavailable")
        finally:
            connection.close()

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--frontend-port", type=int, default=50000)
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--expose-django-admin", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    server.frontend_port = args.frontend_port
    server.backend_port = args.backend_port
    server.expose_django_admin = args.expose_django_admin
    print(f"THE_X tunnel gateway: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
