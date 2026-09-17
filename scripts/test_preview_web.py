import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer
import preview_web


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = preview_web.web
        preview_web.web = Path(self.temp.name)
        (preview_web.web / 'index.html').write_text('latest frontend', encoding='utf-8')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), preview_web.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        preview_web.web = self.original
        self.temp.cleanup()

    def test_routes_return_latest_content_even_with_conditional_cache_headers(self):
        for route in ['/garage', '/bookings?shop=1', '/shops', '/index.html']:
            request = Request(self.base + route, headers={'If-Modified-Since': 'Wed, 01 Jan 2031 00:00:00 GMT'})
            with urlopen(request) as response:
                self.assertEqual(response.status, 200)
                self.assertIn('no-store', response.headers['Cache-Control'])
                self.assertEqual(response.read(), b'latest frontend')

    def test_startup_only_cleans_flutter_assets(self):
        with urlopen(self.base + '/the_x_startup.js') as response:
            body = response.read().decode('utf-8')
            self.assertIn('flutter_service_worker.js', body)
            self.assertIn('flutter-app-cache', body)
            self.assertNotIn('localStorage.clear', body)
            self.assertNotIn('indexedDB.deleteDatabase', body)
            self.assertIn('no-store', response.headers['Cache-Control'])

    def test_retirement_worker_and_legacy_bookmark(self):
        with urlopen(self.base + '/flutter_service_worker.js?v=old') as response:
            self.assertIn(b'self.registration.unregister()', response.read())
            self.assertIn('application/javascript', response.headers['Content-Type'])
        with urlopen(self.base + '/refresh') as response:
            self.assertEqual(response.geturl(), self.base + '/')

    def test_old_build_gets_startup_on_normal_and_callback_routes(self):
        (preview_web.web / 'index.html').write_text('<script src="flutter_bootstrap.js" async></script>')
        for route in ['/', '/garage', '/callback?code=sample&state=unchanged']:
            with urlopen(self.base + route) as response:
                self.assertIn(b'the_x_startup.js', response.read())


if __name__ == '__main__':
    unittest.main()
