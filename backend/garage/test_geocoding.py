import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from .geocoding import fetch_address, fetch_coordinates


@override_settings(PUBLIC_SIGNUP_ENABLED=True)
class GeocodingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.data = {'latitude': '13.756300', 'longitude': '100.501800'}

    @patch('garage.geocoding.fetch_address', return_value='ถนนตัวอย่าง, กรุงเทพมหานคร')
    def test_valid_coordinates_cached_and_repeated_call_does_not_hit_upstream(self, fetch):
        first = self.client.post('/accounts/shop-address/', self.data)
        second = self.client.post('/accounts/shop-address/', self.data)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json(), first.json())
        fetch.assert_called_once_with('13.756300', '100.501800')

    @patch('garage.geocoding.fetch_address', return_value='')
    def test_rate_limit_for_different_locations_and_empty_result(self, fetch):
        self.assertEqual(self.client.post('/accounts/shop-address/', self.data).json(), {'address': ''})
        second = self.client.post('/accounts/shop-address/', {**self.data, 'latitude': '14'})
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second['Retry-After'], '2')
        self.assertEqual(fetch.call_count, 1)

    @patch('garage.geocoding.fetch_address')
    def test_invalid_coordinates_never_sent_to_upstream(self, fetch):
        for value in ('NaN', 'Infinity', '91', '', 'https://example.com'):
            self.assertEqual(self.client.post('/accounts/shop-address/', {**self.data, 'latitude': value}).status_code, 400)
        fetch.assert_not_called()

    @patch('garage.geocoding.fetch_address', side_effect=URLError('unavailable'))
    def test_upstream_failure_returns_editable_form_fallback_message(self, fetch):
        response = self.client.post('/accounts/shop-address/', self.data)
        self.assertEqual(response.status_code, 502)
        self.assertIn('กรอกที่อยู่เอง', response.json()['error'])

    def test_csrf_required_and_get_rejected(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post('/accounts/shop-address/', self.data).status_code, 403)
        self.assertEqual(self.client.get('/accounts/shop-address/').status_code, 405)

    @override_settings(PUBLIC_SIGNUP_ENABLED=False)
    def test_disabled_signup_disables_lookup(self):
        self.assertEqual(self.client.post('/accounts/shop-address/', self.data).status_code, 404)

    @patch('garage.geocoding.urlopen')
    def test_photon_properties_form_address_without_duplicate_parts(self, urlopen):
        urlopen.return_value = BytesIO(json.dumps({'features': [{'properties': {
            'name': 'ร้าน', 'street': 'ถนน', 'city': 'กรุงเทพ', 'state': 'กรุงเทพ', 'postcode': '10000'
        }}]}).encode())
        self.assertEqual(fetch_address('13', '100'), 'ร้าน, ถนน, กรุงเทพ, 10000')
        self.assertIn('lat=13&lon=100', urlopen.call_args.args[0].full_url)

    @patch('garage.geocoding.fetch_coordinates', return_value=('13.756300', '100.501800'))
    def test_forward_address_success(self, fetch):
        response = self.client.post('/accounts/shop-geocode/', {'address': 'กรุงเทพ'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'latitude': '13.756300', 'longitude': '100.501800'})
        fetch.assert_called_once_with('กรุงเทพ')

    @patch('garage.geocoding.fetch_coordinates', return_value=None)
    def test_forward_address_not_found(self, fetch):
        response = self.client.post('/accounts/shop-geocode/', {'address': 'กรุงเทพ'})
        self.assertEqual(response.status_code, 404)

    def test_forward_address_empty_address(self):
        self.assertEqual(self.client.post('/accounts/shop-geocode/', {'address': ''}).status_code, 400)

    @patch('garage.geocoding.fetch_coordinates', return_value=('13.756300', '100.501800'))
    def test_forward_cache_and_shared_cooldown(self, fetch):
        data = {'address': 'กรุงเทพ'}
        first = self.client.post('/accounts/shop-geocode/', data)
        self.assertEqual(self.client.post('/accounts/shop-geocode/', data).json(), first.json())
        self.assertEqual(self.client.post('/accounts/shop-address/', self.data).status_code, 429)
        fetch.assert_called_once()

    @patch('garage.geocoding.fetch_coordinates')
    def test_forward_validation_and_csrf(self, fetch):
        for address in ('', 'ab', 'x' * 1001):
            self.assertEqual(self.client.post('/accounts/shop-geocode/', {'address': address}).status_code, 400)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/accounts/shop-geocode/', {'address': 'Bangkok'}).status_code, 403)
        self.assertEqual(self.client.get('/accounts/shop-geocode/').status_code, 405)
        with override_settings(PUBLIC_SIGNUP_ENABLED=False):
            self.assertEqual(self.client.post('/accounts/shop-geocode/', {'address': 'Bangkok'}).status_code, 404)
        fetch.assert_not_called()

    @patch('garage.geocoding.urlopen')
    def test_forward_coordinate_order_and_invalid_upstream(self, urlopen):
        def response(coords):
            return BytesIO(json.dumps({'features': [{'geometry': {'coordinates': coords}}]}).encode())
        urlopen.return_value = response([100.5018, 13.7563])
        self.assertEqual(fetch_coordinates('Bangkok'), ('13.756300', '100.501800'))
        for coords in ([100, 91], ['NaN', 13], [181, 13]):
            urlopen.return_value = response(coords)
            with self.assertRaises(ValueError):
                fetch_coordinates('Bangkok')

    @patch('garage.geocoding.fetch_coordinates', side_effect=URLError('unavailable'))
    def test_forward_service_unavailable(self, fetch):
        self.assertEqual(self.client.post('/accounts/shop-geocode/', {'address': 'Bangkok'}).status_code, 502)
