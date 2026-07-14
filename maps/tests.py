import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import OwnerAccessToken, OwnerAuthorizationCode, OwnerProfile, PlatformOAuthClient, Review, ReviewReply


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

    def test_index_shows_owner_place_navigation_when_logged_in(self):
        owner = get_user_model().objects.create_user(username='owner', password='password')
        OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
        )
        self.client.force_login(owner)

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '테스트 카페')
        self.assertContains(response, '내 업장으로 이동')
        self.assertContains(response, 'window.OWNER_PLACE_ID = "place\\u002D1"')

    def test_health_returns_ok(self):
        response = self.client.get('/health/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})


class ReviewApiTests(TestCase):
    def issue_owner_token(self, profile):
        code = OwnerAuthorizationCode.objects.create(
            owner=profile,
            redirect_uri='http://testserver/oauth/callback/',
            state='state-123',
        )
        response = self.client.post(
            '/oauth/token/',
            data=json.dumps({
                'grant_type': 'authorization_code',
                'client_id': profile.client_id,
                'client_secret': profile.client_secret,
                'code': code.code,
                'redirect_uri': code.redirect_uri,
                'state': 'state-123',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        return response.json()['access_token']

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

    def test_list_reviews_with_bearer_token_without_place_id(self):
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
            client_id='owner-client',
            client_secret='owner-secret',
        )
        token = self.issue_owner_token(profile)

        response = self.client.get('/api/reviews/', HTTP_AUTHORIZATION=f'Bearer {token}')

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

    def test_owner_reply_requires_staff_or_bearer_token(self):
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
        self.assertEqual(response.json()['data']['replies'][0]['content'], '방문해 주셔서 감사합니다.')

        second_response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '또 방문해주세요.'}),
            content_type='application/json',
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(len(second_response.json()['data']['replies']), 2)

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

    def test_bearer_token_can_reply_to_own_place(self):
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
            client_id='owner-client',
            client_secret='owner-secret',
        )
        token = self.issue_owner_token(profile)

        response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '확인했습니다.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['replies'][0]['owner_name'], 'owner')

    def test_owner_can_delete_own_reply(self):
        review = Review.objects.create(
            place_id='place-1',
            place_name='테스트 카페',
            author_name='방문자',
            rating=4,
            content='다시 갈게요.',
        )
        owner = get_user_model().objects.create_user(username='owner', password='password')
        OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
        )
        self.client.force_login(owner)
        create_response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '삭제할 답글입니다.'}),
            content_type='application/json',
        )
        reply_id = create_response.json()['data']['replies'][0]['id']

        delete_response = self.client.delete(f'/api/reviews/{review.id}/reply/{reply_id}/')

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()['data']['replies'], [])

    def test_bearer_token_can_update_own_reply(self):
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
            client_id='owner-client',
            client_secret='owner-secret',
        )
        reply = ReviewReply.objects.create(
            review=review,
            owner=owner,
            content='수정 전 답글입니다.',
        )
        token = self.issue_owner_token(profile)

        response = self.client.patch(
            f'/api/reviews/{review.id}/reply/{reply.id}/',
            data=json.dumps({'content': '수정된 답글입니다.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['replies'][0]['content'], '수정된 답글입니다.')
        reply.refresh_from_db()
        self.assertEqual(reply.content, '수정된 답글입니다.')

    def test_bearer_token_cannot_reply_to_other_place(self):
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
            client_id='owner-client',
            client_secret='owner-secret',
        )
        token = self.issue_owner_token(profile)

        response = self.client.post(
            f'/api/reviews/{review.id}/reply/',
            data=json.dumps({'content': '확인했습니다.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 401)

    def test_owner_signup_creates_profile_and_oauth_credentials(self):
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
        self.assertTrue(profile.client_id.startswith('oci_'))
        self.assertTrue(profile.client_secret.startswith('ocs_'))

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

    def test_owner_account_hides_client_secret_until_revealed(self):
        owner = get_user_model().objects.create_user(username='owner-hidden-key', password='password123')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-hidden-client-secret',
        )
        self.client.force_login(owner)

        response = self.client.get('/owner/account/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'owner-client')
        self.assertContains(response, 'data-copy-value="owner-hidden-client-secret"')
        self.assertContains(response, '••••')
        self.assertContains(response, '보이기')
        self.assertContains(response, '복사')
        self.assertEqual(profile.client_secret, 'owner-hidden-client-secret')

    def test_oauth_authorize_redirects_with_code_after_login(self):
        owner = get_user_model().objects.create_user(username='oauth-owner', password='password123')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-secret',
        )

        response = self.client.post(
            '/oauth/authorize/',
            data={
                'response_type': 'code',
                'client_id': profile.client_id,
                'redirect_uri': 'http://testserver/oauth/callback/',
                'state': 'state-123',
                'username': 'oauth-owner',
                'password': 'password123',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('http://testserver/oauth/callback/?code=', response.headers['Location'])
        self.assertIn('&client_id=owner-client', response.headers['Location'])
        self.assertIn('&state=state-123', response.headers['Location'])
        self.assertEqual(OwnerAuthorizationCode.objects.filter(owner=profile).count(), 1)

    def test_oauth_authorize_requires_client_id(self):
        owner = get_user_model().objects.create_user(username='oauth-owner', password='password123')
        OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-secret',
        )

        response = self.client.post(
            '/oauth/authorize/',
            data={
                'response_type': 'code',
                'redirect_uri': 'http://localhost:8000/oauth/callback/',
                'state': 'state-123',
                'username': 'oauth-owner',
                'password': 'password123',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'client_id is required', status_code=400)

    def test_oauth_authorize_get_requires_client_id(self):
        owner = get_user_model().objects.create_user(username='oauth-owner', password='password123')
        OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-secret',
        )
        self.client.force_login(owner)

        response = self.client.get(
            '/oauth/authorize/?response_type=code&redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Foauth%2Fcallback%2F&state=state-123&scope=owner%3Areviews',
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'client_id is required', status_code=400)

    def test_oauth_authorize_get_with_client_id_uses_current_owner(self):
        owner = get_user_model().objects.create_user(username='oauth-owner', password='password123')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-secret',
        )
        self.client.force_login(owner)

        response = self.client.get(
            '/oauth/authorize/?response_type=code&client_id=owner-client&redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Foauth%2Fcallback%2F&state=state-123&scope=owner%3Areviews',
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('http://127.0.0.1:8000/oauth/callback/?code=', response.headers['Location'])
        self.assertIn('&client_id=owner-client', response.headers['Location'])
        self.assertEqual(OwnerAuthorizationCode.objects.filter(owner=profile).count(), 1)

    def test_oauth_test_page_is_public(self):
        response = self.client.get('/oauth/test/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '로그인 팝업 열기')
        self.assertContains(response, 'Access Token 남은 시간')
        self.assertContains(response, 'Refresh Token 남은 시간')

    def test_oauth_redirect_viewer_page_is_public(self):
        response = self.client.get('/oauth/redirect-viewer/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OAuth 리뷰 조회 플로우')
        self.assertContains(response, 'Authorize URL')
        self.assertContains(response, 'Redirect URI')
        self.assertContains(response, 'Code')
        self.assertContains(response, 'Client ID')
        self.assertContains(response, 'Access Token')
        self.assertContains(response, '내 가게 리뷰')
        self.assertContains(response, '요청 / 응답')

    def test_oauth_token_issues_bearer_and_refresh_token_for_authorization_code(self):
        owner = get_user_model().objects.create_user(username='oauth-owner', password='password123')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-secret',
        )
        code = OwnerAuthorizationCode.objects.create(
            owner=profile,
            redirect_uri='http://testserver/oauth/callback/',
            state='state-123',
        )

        response = self.client.post(
            '/oauth/token/',
            data=json.dumps({
                'grant_type': 'authorization_code',
                'client_id': profile.client_id,
                'client_secret': profile.client_secret,
                'code': code.code,
                'redirect_uri': code.redirect_uri,
                'state': 'state-123',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['token_type'], 'Bearer')
        self.assertEqual(payload['scope'], 'owner:reviews')
        self.assertEqual(payload['client_id'], 'owner-client')
        self.assertEqual(payload['place_id'], 'place-1')
        self.assertIn('refresh_token', payload)
        self.assertTrue(OwnerAccessToken.objects.filter(token=payload['access_token']).exists())
        code.refresh_from_db()
        self.assertTrue(code.used_at)

    def test_oauth_token_refresh_rotates_token(self):
        owner = get_user_model().objects.create_user(username='oauth-owner', password='password123')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-secret',
        )
        token = OwnerAccessToken.objects.create(owner=profile)

        response = self.client.post(
            '/oauth/token/',
            data=json.dumps({
                'grant_type': 'refresh_token',
                'client_id': profile.client_id,
                'client_secret': profile.client_secret,
                'refresh_token': token.refresh_token,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotEqual(payload['access_token'], token.token)
        token.refresh_from_db()
        self.assertTrue(token.revoked_at)

    def test_oauth_revoke_blocks_access_token(self):
        owner = get_user_model().objects.create_user(username='oauth-owner', password='password123')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-secret',
        )
        token = OwnerAccessToken.objects.create(owner=profile)

        revoke_response = self.client.post(
            '/oauth/revoke/',
            data=json.dumps({
                'token': token.token,
                'client_id': profile.client_id,
                'client_secret': profile.client_secret,
            }),
            content_type='application/json',
        )
        reviews_response = self.client.get('/api/reviews/', HTTP_AUTHORIZATION=f'Bearer {token.token}')

        self.assertEqual(revoke_response.status_code, 200)
        self.assertEqual(reviews_response.status_code, 400)

    def test_oauth_token_rejects_invalid_client_secret(self):
        owner = get_user_model().objects.create_user(username='oauth-owner', password='password123')
        profile = OwnerProfile.objects.create(
            user=owner,
            place_id='place-1',
            place_name='테스트 카페',
            client_id='owner-client',
            client_secret='owner-secret',
        )
        token = OwnerAccessToken.objects.create(owner=profile)

        response = self.client.post(
            '/oauth/token/',
            data=json.dumps({
                'grant_type': 'refresh_token',
                'client_id': profile.client_id,
                'client_secret': 'wrong-secret',
                'refresh_token': token.refresh_token,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_client')

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


class PlatformOAuthTests(TestCase):
    redirect_uri = 'http://localhost:8080/api/integrations/MOCK_MAP/oauth/callback'

    def setUp(self):
        self.platform = PlatformOAuthClient.objects.create(
            name='ShopHub Test',
            client_id='oci_shophub_test',
            client_secret='ocs_shophub_test_secret',
            redirect_uris=self.redirect_uri,
            scopes='owner:reviews',
            is_active=True,
        )
        self.owner = get_user_model().objects.create_user(username='platform-owner', password='password123')
        self.profile = OwnerProfile.objects.create(
            user=self.owner,
            place_id='place-platform-1',
            place_name='플랫폼 테스트 카페',
        )

    def test_platform_authorize_get_shows_login_page(self):
        response = self.client.get(
            '/oauth/authorize/',
            {
                'response_type': 'code',
                'client_id': self.platform.client_id,
                'redirect_uri': self.redirect_uri,
                'state': 'state-platform',
                'scope': 'owner:reviews',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ShopHub')
        self.assertContains(response, 'MockMap 점주 계정으로 로그인')

    def test_platform_authorize_post_redirects_with_code(self):
        response = self.client.post(
            '/oauth/authorize/',
            data={
                'response_type': 'code',
                'client_id': self.platform.client_id,
                'redirect_uri': self.redirect_uri,
                'state': 'state-platform',
                'username': 'platform-owner',
                'password': 'password123',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f'{self.redirect_uri}?code=', response.headers['Location'])
        self.assertIn('state=state-platform', response.headers['Location'])
        code = OwnerAuthorizationCode.objects.get(owner=self.profile, platform_client=self.platform)
        self.assertFalse(code.is_used)

    def test_platform_token_exchange_returns_place_id(self):
        code = OwnerAuthorizationCode.objects.create(
            owner=self.profile,
            platform_client=self.platform,
            redirect_uri=self.redirect_uri,
            state='state-platform',
        )
        response = self.client.post(
            '/oauth/token/',
            data=json.dumps({
                'grant_type': 'authorization_code',
                'client_id': self.platform.client_id,
                'client_secret': self.platform.client_secret,
                'code': code.code,
                'redirect_uri': self.redirect_uri,
                'state': 'state-platform',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['place_id'], 'place-platform-1')
        self.assertEqual(payload['place_name'], '플랫폼 테스트 카페')
        self.assertEqual(payload['client_id'], self.platform.client_id)
        self.assertIn('access_token', payload)
        self.assertIn('refresh_token', payload)

    def test_platform_authorize_rejects_invalid_redirect_uri(self):
        response = self.client.get(
            '/oauth/authorize/',
            {
                'response_type': 'code',
                'client_id': self.platform.client_id,
                'redirect_uri': 'http://evil.example/callback',
                'state': 'state-platform',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'redirect_uri is not allowed', status_code=400)
