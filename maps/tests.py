from django.test import TestCase


class MapPageTests(TestCase):
    def test_index_renders_map_page(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GoogleMap-Mock')
        self.assertContains(response, 'id="map"')
        self.assertContains(response, 'maps/app.js')

    def test_places_api_returns_real_places(self):
        response = self.client.get('/api/places/')

        self.assertEqual(response.status_code, 200)
        place_names = {place['name'] for place in response.json()['places']}
        self.assertIn('경복궁', place_names)
        self.assertIn('롯데월드타워', place_names)

    def test_health_returns_ok(self):
        response = self.client.get('/health/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
