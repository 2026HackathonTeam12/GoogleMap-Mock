from django.test import TestCase, override_settings


class MapPageTests(TestCase):
    def test_index_renders_map_page(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '서울 장소 지도')
        self.assertContains(response, 'id="map"')
        self.assertContains(response, 'maps/app.js')
        self.assertContains(response, 'unpkg.com/leaflet')

    @override_settings(GOOGLE_MAPS_API_KEY='test-key')
    def test_index_loads_google_maps_with_places_when_key_exists(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'maps.googleapis.com/maps/api/js')
        self.assertContains(response, 'libraries=places')
        self.assertNotContains(response, 'unpkg.com/leaflet')

    def test_health_returns_ok(self):
        response = self.client.get('/health/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
