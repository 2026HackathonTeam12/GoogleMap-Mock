from django.test import TestCase


class MapPageTests(TestCase):
    def test_index_renders_map_page(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GoogleMap-Mock')
        self.assertContains(response, 'id="map"')
        self.assertContains(response, 'maps/app.js')

    def test_health_returns_ok(self):
        response = self.client.get('/health/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
