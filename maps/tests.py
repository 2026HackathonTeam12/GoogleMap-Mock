import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import OwnerProfile, Review


class MapPageTests(TestCase):
    @override_settings(GOOGLE_MAPS_API_KEY='')
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


class ReviewApiTests(TestCase):
    def test_create_and_list_reviews(self):
        create_response = self.client.post(
            '/api/reviews/',
            data=json.dumps({
                'place_id': 'place-1',
                'place_name': '테스트 카페',
                'author_name': '방문자',
                'rating': 5,
                'content': '커피가 좋았습니다.',
                'delete_password': '1234',
            }),
            content_type='application/json',
        )

        self.assertEqual(create_response.status_code, 201)

        list_response = self.client.get('/api/reviews/?place_id=place-1')

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()['data']), 1)
        self.assertEqual(list_response.json()['data'][0]['rating'], 5)

    def test_list_reviews_with_place_api_key_without_place_id(self):
        Review.objects.create(
            place_id='place-1',
            place_name='테스트 카페',
            author_name='방문자',
            rating=5,
            content='커피가 좋았습니다.',
        )
        Review.objects.create(
            place_id='place-2',
            place_name='다른 가게',
            author_name='방문자',
            rating=3,
            content='다른 리뷰입니다.',
        )
        owner = get_user_model().objects.create_user(username='owner', password='password')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            api_key='owner-place-key',
        )

        response = self.client.get('/api/reviews/', HTTP_X_API_KEY=profile.api_key)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['place_id'], 'place-1')
        self.assertEqual(len(response.json()['data']), 1)

    def test_delete_review_with_password(self):
        create_response = self.client.post(
            '/api/reviews/',
            data=json.dumps({
                'place_id': 'place-1',
                'place_name': '테스트 카페',
                'author_name': '방문자',
                'rating': 5,
                'content': '삭제할 리뷰입니다.',
                'delete_password': '1234',
            }),
            content_type='application/json',
        )
        review_id = create_response.json()['data']['id']

        delete_response = self.client.delete(
            f'/api/reviews/{review_id}/',
            data=json.dumps({'delete_password': '1234'}),
            content_type='application/json',
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(Review.objects.filter(pk=review_id).exists())

    def test_delete_review_rejects_wrong_password(self):
        create_response = self.client.post(
            '/api/reviews/',
            data=json.dumps({
                'place_id': 'place-1',
                'place_name': '테스트 카페',
                'author_name': '방문자',
                'rating': 5,
                'content': '삭제할 리뷰입니다.',
                'delete_password': '1234',
            }),
            content_type='application/json',
        )
        review_id = create_response.json()['data']['id']

        delete_response = self.client.delete(
            f'/api/reviews/{review_id}/',
            data=json.dumps({'delete_password': '0000'}),
            content_type='application/json',
        )

        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(Review.objects.filter(pk=review_id).exists())

    def test_owner_reply_requires_staff_or_api_key(self):
        review = Review.objects.create(
            place_id='place-1',
            place_name='테스트 카페',
            author_name='방문자',
            rating=4,
            content='다시 갈게요.',
        )

        response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '감사합니다.'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)

    def test_owner_can_reply_to_own_place(self):
        review = Review.objects.create(
            place_id='place-1',
            place_name='테스트 카페',
            author_name='방문자',
            rating=4,
            content='다시 갈게요.',
        )
        owner = get_user_model().objects.create_user(
            username='owner',
            password='password',
            is_staff=True,
        )
        OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
        )
        self.client.force_login(owner)

        response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '방문해 주셔서 감사합니다.'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['reply']['content'], '방문해 주셔서 감사합니다.')

    def test_owner_cannot_reply_to_other_place(self):
        review = Review.objects.create(
            place_id='place-1',
            place_name='테스트 카페',
            author_name='방문자',
            rating=4,
            content='다시 갈게요.',
        )
        owner = get_user_model().objects.create_user(
            username='owner',
            password='password',
            is_staff=True,
        )
        OwnerProfile.objects.create(
            user=owner,
            place_id='place-2',
            place_name='다른 가게',
        )
        self.client.force_login(owner)

        response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '답글입니다.'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)

    def test_place_api_key_can_reply_to_own_place(self):
        review = Review.objects.create(
            place_id='place-1',
            place_name='테스트 카페',
            author_name='방문자',
            rating=4,
            content='다시 갈게요.',
        )
        owner = get_user_model().objects.create_user(username='owner', password='password')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            api_key='owner-place-key',
        )

        response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '확인했습니다.'}),
            content_type='application/json',
            HTTP_X_API_KEY=profile.api_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['reply']['owner_name'], 'owner')

    def test_place_api_key_cannot_reply_to_other_place(self):
        review = Review.objects.create(
            place_id='place-1',
            place_name='테스트 카페',
            author_name='방문자',
            rating=4,
            content='다시 갈게요.',
        )
        owner = get_user_model().objects.create_user(username='owner', password='password')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-2',
            place_name='다른 가게',
            api_key='owner-place-key',
        )

        response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '확인했습니다.'}),
            content_type='application/json',
            HTTP_X_API_KEY=profile.api_key,
        )

        self.assertEqual(response.status_code, 401)

    def test_owner_signup_creates_profile_and_api_key(self):
        response = self.client.post(
            '/owner/signup/',
            data={
                'username': 'new-owner',
                'password': 'password123',
                'password_confirm': 'password123',
                'place_id': 'place-1',
                'place_name': '테스트 카페',
                'place_address': '서울',
            },
        )

        self.assertEqual(response.status_code, 302)
        profile = OwnerProfile.objects.get(place_id='place-1')
        self.assertTrue(profile.api_key.startswith('okr_'))

    def test_owner_signup_accepts_place_id_only(self):
        response = self.client.post(
            '/owner/signup/',
            data={
                'username': 'id-only-owner',
                'password': 'password123',
                'password_confirm': 'password123',
                'place_id': 'place-id-only',
                'place_name': '',
                'place_address': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        profile = OwnerProfile.objects.get(place_id='place-id-only')
        self.assertEqual(profile.place_name, 'place-id-only')

    def test_owner_signup_prefills_place_from_query(self):
        response = self.client.get(
            '/owner/signup/?place_id=place-1&place_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%20%EC%B9%B4%ED%8E%98&place_address=%EC%84%9C%EC%9A%B8',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="place-1" readonly')
        self.assertContains(response, 'value="테스트 카페" placeholder="비워두면 위치 ID로 저장됩니다" readonly')
        self.assertContains(response, 'value="서울"')

    def test_owner_login_redirects_to_account(self):
        owner = get_user_model().objects.create_user(username='owner-login', password='password123')
        OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
        )

        response = self.client.post(
            '/owner/login/',
            data={
                'username': 'owner-login',
                'password': 'password123',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/owner/account/')

    def test_owner_account_hides_api_key_until_revealed(self):
        owner = get_user_model().objects.create_user(username='owner-hidden-key', password='password123')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            api_key='owner-hidden-api-key',
        )
        self.client.force_login(owner)

        response = self.client.get('/owner/account/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-api-key="owner-hidden-api-key"')
        self.assertContains(response, '••••')
        self.assertContains(response, '보이기')
        self.assertContains(response, '복사')
        self.assertEqual(profile.api_key, 'owner-hidden-api-key')

    def test_owner_logout(self):
        owner = get_user_model().objects.create_user(username='owner-logout', password='password123')
        OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
        )
        self.client.force_login(owner)

        response = self.client.post('/owner/logout/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/')
        account_response = self.client.get('/owner/account/')
        self.assertEqual(account_response.status_code, 302)

    def test_owner_login_rejects_non_owner_account(self):
        get_user_model().objects.create_user(username='normal-user', password='password123')

        response = self.client.post(
            '/owner/login/',
            data={
                'username': 'normal-user',
                'password': 'password123',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '점주로 등록된 계정이 아닙니다.', status_code=403)

    def test_openapi_schema_includes_review_paths(self):
        response = self.client.get('/api/openapi.json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('/api/reviews/', response.json()['paths'])
