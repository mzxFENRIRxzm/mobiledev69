import json
import logging
from hashlib import sha256
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache


def fetch_address(latitude, longitude):
    query = urlencode({'lat': latitude, 'lon': longitude, 'limit': 1})
    request = Request(settings.GEOCODING_REVERSE_URL + '?' + query,
        headers={'User-Agent': 'THE_X/1.0 (https://github.com/mzxFENRIRxzm/mobiledev69)', 'Accept': 'application/json'})
    with urlopen(request, timeout=6) as response:
        data = json.loads(response.read(256_001))
    features = data.get('features', [])
    if not features:
        return ''
    properties = features[0].get('properties', {})
    parts = []
    for key in ('name', 'housenumber', 'street', 'district', 'city', 'county', 'state', 'postcode', 'country'):
        part = properties.get(key)
        if isinstance(part, str) and part.strip() and part.strip() not in parts:
            parts.append(part.strip())
    return ', '.join(parts)[:1000]


@never_cache
@require_POST
def reverse_address(request):
    if not settings.PUBLIC_SIGNUP_ENABLED:
        raise Http404
    try:
        lat, lng = (Decimal(request.POST.get(key, '')) for key in ('latitude', 'longitude'))
        if not lat.is_finite() or not lng.is_finite() or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise ValueError
        lat, lng = f'{lat:.6f}', f'{lng:.6f}'
    except (InvalidOperation, ValueError):
        return JsonResponse({'error': 'ตำแหน่งร้านไม่ถูกต้อง กรุณาปักหมุดใหม่'}, status=400)
    key = f'shop-address:v1:{lat}:{lng}'
    address = cache.get(key)
    if address is not None:
        return JsonResponse({'address': address})
    # Shared across threads in local development. Use shared cache for multiple workers.
    if not cache.add('shop-address:upstream-cooldown', True, timeout=2):
        response = JsonResponse({'error': 'กรุณารอสักครู่แล้วลองเติมที่อยู่อีกครั้ง'}, status=429)
        response['Retry-After'] = '2'
        return response
    try:
        address = fetch_address(lat, lng)
    except (URLError, OSError, ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        logging.getLogger(__name__).warning('Address lookup failed (%s)', type(error).__name__)
        return JsonResponse({'error': 'ค้นหาที่อยู่ไม่สำเร็จ กรุณากรอกที่อยู่เองหรือลองใหม่'}, status=502)
    cache.set(key, address, timeout=86400)
    return JsonResponse({'address': address})


def fetch_coordinates(address):
    query = urlencode({'q': address, 'limit': 1})
    request = Request(settings.GEOCODING_FORWARD_URL + '?' + query,
        headers={'User-Agent': 'THE_X/1.0 (https://github.com/mzxFENRIRxzm/mobiledev69)', 'Accept': 'application/json'})
    with urlopen(request, timeout=6) as response:
        data = json.loads(response.read(256_001))
    features = data.get('features', [])
    if not features:
        return None
    geometry = features[0].get('geometry', {})
    coordinates = geometry.get('coordinates', [])
    if len(coordinates) == 2:
        lng, lat = (Decimal(str(value)) for value in coordinates)
        if not lat.is_finite() or not lng.is_finite() or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise ValueError('Invalid upstream coordinates')
        return f'{lat:.6f}', f'{lng:.6f}'
    return None


@never_cache
@require_POST
def forward_address(request):
    if not settings.PUBLIC_SIGNUP_ENABLED:
        raise Http404
    address = request.POST.get('address', '').strip()
    if not 3 <= len(address) <= 1000:
        return JsonResponse({'error': 'กรุณากรอกที่อยู่ระหว่าง 3 ถึง 1000 ตัวอักษร'}, status=400)
    key = 'shop-geocode:v1:' + sha256(address.encode('utf-8')).hexdigest()
    coords = cache.get(key)
    if coords is not None:
        return JsonResponse({'latitude': coords[0], 'longitude': coords[1]})
    if not cache.add('shop-address:upstream-cooldown', True, timeout=2):
        response = JsonResponse({'error': 'กรุณารอสักครู่แล้วลองใหม่อีกครั้ง'}, status=429)
        response['Retry-After'] = '2'
        return response
    try:
        coords = fetch_coordinates(address)
    except (URLError, OSError, ValueError, InvalidOperation, TypeError, AttributeError, IndexError, KeyError) as error:
        logging.getLogger(__name__).warning('Geocoding lookup failed (%s)', type(error).__name__)
        return JsonResponse({'error': 'ค้นหาพิกัดไม่สำเร็จ'}, status=502)
    if coords:
        cache.set(key, coords, timeout=86400)
        return JsonResponse({'latitude': coords[0], 'longitude': coords[1]})
    return JsonResponse({'error': 'ไม่พบพิกัดสำหรับที่อยู่นี้'}, status=404)
