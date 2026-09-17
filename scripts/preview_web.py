"""Local-only preview of the built Flutter app, with SPA route fallback."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

web = Path(__file__).resolve().parents[1] / "frontend" / "build" / "web"

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(web), **kwargs)

    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path == "/refresh":
            # Keep old bookmarks working without a separate recovery screen.
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if request_path in ("/flutter_service_worker.js", "/the_x_startup.js"):
            source = (Path(__file__).with_name("retire_flutter_worker.js")
                      if request_path == "/flutter_service_worker.js"
                      else Path(__file__).resolve().parents[1] / "frontend/web/the_x_startup.js")
            payload = source.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        # Development builds reuse filenames: always serve the latest file.
        for header in ("If-Modified-Since", "If-None-Match"):
            if header in self.headers:
                del self.headers[header]
        if request_path in ("/", "/index.html", "/login", "/callback", "/garage", "/loading", "/bookings", "/jobs", "/shops", "/admin"):
            # Also upgrade the last built index without editing build artifacts.
            # Other Dart changes still require flutter build web.
            payload = (web / "index.html").read_text(encoding="utf-8").replace(
                '<script src="flutter_bootstrap.js" async></script>',
                '<script src="the_x_startup.js" defer></script>',
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, *args):
        pass  # Callback query strings may contain authorization codes.

if __name__ == "__main__":
    if not (web / "index.html").exists():
        raise SystemExit("Missing frontend/build/web/index.html. Run flutter build web first.")
    print("THE_X preview: http://localhost:50000", flush=True)
    print("Open the normal app URL. Legacy Flutter cache is cleaned automatically; login storage is preserved.", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 50000), Handler).serve_forever()
