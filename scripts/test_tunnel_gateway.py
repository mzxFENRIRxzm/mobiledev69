import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tunnel_gateway


class TunnelGatewayTests(unittest.TestCase):
    def test_routes_django_and_flutter_without_admin_collision(self):
        for path in ('/api/me/', '/openid/authorize/', '/accounts/login/', '/admin/auth/user/'):
            self.assertEqual(tunnel_gateway.route_for(path), 'backend')
        for path in ('/', '/login', '/callback?code=1', '/admin'):
            self.assertEqual(tunnel_gateway.route_for(path.split('?')[0]), 'frontend')

    def test_static_path_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(tunnel_gateway.STATIC_ROOTS, {'/media/': root}, clear=True):
                self.assertEqual(tunnel_gateway.local_file('/media/shop/photo.jpg'),
                                 (root / 'shop' / 'photo.jpg').resolve())
                self.assertIsNone(tunnel_gateway.local_file('/media/../secret.txt'))
                self.assertIsNone(tunnel_gateway.local_file('/media/%2e%2e/secret.txt'))


if __name__ == '__main__':
    unittest.main()
